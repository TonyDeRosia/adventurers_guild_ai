"""Core campaign loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

from engine.character_sheet import CharacterSheetService
from engine.content_registry import ContentRegistry
from engine.dialogue_service import DialogueService
from engine.entities import CampaignState
from engine.inventory import InventoryService
from memory.campaign_memory import CampaignMemory
from memory.campaign_state_orchestrator import CampaignStateOrchestrator
from memory.npc_memory import NPCMemoryTracker
from memory.npc_personality import NPCPersonalitySystem
from memory.quest_tracker import QuestTracker
from memory.retrieval import MemoryRetrievalPipeline, RetrievalRequest
from memory.summary import SummaryGenerator
from memory.world_state import WorldStateTracker
from models.base import ChatMessage, NarrationModelAdapter
from models.base import NullNarrationAdapter, ProviderUnavailableError
from prompts.renderer import PromptRenderer
from rules.combat import CombatEngine


@dataclass
class TurnResult:
    narrative: str
    system_messages: list[str]
    messages: list[dict[str, str]]
    should_exit: bool = False
    metadata: dict[str, object] | None = None


class CampaignEngine:
    """Coordinates subsystems while keeping concerns separated."""

    def __init__(self, model: NarrationModelAdapter, data_dir: Path | None = None) -> None:
        self.model = model
        self.prompts = PromptRenderer()
        self.world = WorldStateTracker()
        self.quests = QuestTracker()
        self.npc_memory = NPCMemoryTracker()
        self.content = ContentRegistry(data_dir or Path("data"))
        self.personality = NPCPersonalitySystem(self.content)
        self.combat = CombatEngine()
        self.inventory = InventoryService(self.content)
        self.character_sheet = CharacterSheetService()
        self.dialogue = DialogueService(self.content, self.quests, self.npc_memory)
        self.memory = CampaignMemory()
        self.state_orchestrator = CampaignStateOrchestrator()
        self.retrieval = MemoryRetrievalPipeline()
        self.summary = SummaryGenerator()
        self._last_prompt_debug_by_campaign: dict[str, dict[str, object]] = {}

    def run_turn(self, state: CampaignState, action: str) -> TurnResult:
        state.turn_count += 1
        for faction, baseline in self.content.faction_defaults().items():
            state.faction_reputation.setdefault(faction, baseline)
        self.quests.refresh_availability(state)
        normalized = action.strip().lower()

        if normalized in {"exit", "quit"}:
            return TurnResult(
                narrative="Your adventure pauses here.",
                system_messages=[],
                messages=[{"type": "narrator", "text": "Your adventure pauses here."}],
                should_exit=True,
            )

        intent = self._classify_turn_intent(action)
        print(f"[turn-routing] intent={intent}")
        if intent == "system":
            return self._finish_turn(
                state,
                action,
                self._build_system_intent_messages(state, normalized),
                requested_mode="system",
                skip_narrator=True,
            )
        if intent == "structured":
            return self._finish_turn(
                state,
                action,
                self._build_structured_intent_messages(state, normalized),
                requested_mode="structured_lookup",
                skip_narrator=True,
            )

        system_messages: list[str] = []
        requested_mode = "play"

        if normalized == "look":
            system_messages.append(self.world.get_current_location_summary(state))
            self._maybe_start_location_encounter(state, system_messages)

        elif normalized.startswith("move "):
            destination = normalized.split(" ", 1)[1]
            move_message = self.world.move_to_location(state, destination)
            system_messages.append(move_message)
            self._maybe_start_location_encounter(state, system_messages)

        elif normalized == "sheet":
            system_messages.append(self.character_sheet.summary(state.player))

        elif normalized.startswith("take "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.add_item(state.player, item))

        elif normalized.startswith("drop "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.remove_item(state.player, item))

        elif normalized == "inventory":
            system_messages.append(self.inventory.describe_inventory(state.player))

        elif normalized.startswith("use "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.use_item(state.player, item))

        elif normalized.startswith("equip "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.equip_item(state.player, item))

        elif normalized == "quests":
            active = self.quests.list_active_quests(state)
            system_messages.append("Active quests: " + ("; ".join(active) if active else "none"))

        elif normalized.startswith("talk "):
            npc_id = normalized.split(" ", 1)[1]
            if npc_id in state.npcs:
                if state.npcs[npc_id].location_id != state.current_location_id:
                    system_messages.append(f"{state.npcs[npc_id].name} is not here.")
                else:
                    self.npc_memory.record_interaction(state, npc_id, f"Turn {state.turn_count}: {action}", delta=1)
                    self.personality.apply_event(
                        state,
                        npc_id,
                        event_type="player_kindness",
                        payload={"summary": "Player initiated respectful dialogue", "player_action": action, "impact": {"trust_toward_player": 1}},
                    )
                    dialogue_output = self.dialogue.start_dialogue(state, npc_id)
                    if dialogue_output:
                        system_messages.append(dialogue_output.text)
                        if dialogue_output.options:
                            system_messages.extend(dialogue_output.options)
                            system_messages.append("Type 'choose <number>' to select a response.")
                    else:
                        system_messages.append(self.npc_memory.describe_npc(state, npc_id))
                    npc = state.npcs[npc_id]
                    system_messages.append(f"Relationship tier with {npc.name}: {npc.relationship_tier}.")
                    eval_snapshot = self.personality.evaluate(state, npc_id, scene="dialogue")
                    system_messages.append(
                        f"Disposition lens: tone={eval_snapshot.tone}, friendliness={eval_snapshot.friendliness}, "
                        f"hostility={eval_snapshot.hostility}, willingness={eval_snapshot.willingness_to_share}."
                    )
                    self._post_talk_consequences(state, npc_id, system_messages)
            else:
                system_messages.append(f"No NPC with id '{npc_id}' is present.")

        elif normalized.startswith("choose "):
            try:
                choice = int(normalized.split(" ", 1)[1])
            except ValueError:
                system_messages.append("Choice must be a number.")
                return self._finish_turn(state, action, system_messages)
            result = self.dialogue.choose_option(state, choice)
            system_messages.append(result.text)
            system_messages.extend(result.options)
            if not result.options and not result.completed:
                system_messages.append("Type 'choose <number>' to continue.")

        elif normalized.startswith("attack"):
            if state.active_enemy_id is None or state.active_enemy_hp is None or state.active_enemy_hp <= 0:
                system_messages.append("There is no active enemy to attack.")
                return self._finish_turn(state, action, system_messages)

            enemy = self.content.get_enemy(state.active_enemy_id)
            if enemy is None:
                system_messages.append("Enemy data is missing.")
                return self._finish_turn(state, action, system_messages)

            guarding = bool(state.combat_effects.get("enemy_guarded", False))
            enemy_armor = enemy.armor + (2 if guarding else 0)
            if guarding:
                state.combat_effects["enemy_guarded"] = False
            result = self.combat.resolve_player_attack(
                attacker_name=state.player.name,
                defender_name=enemy.name,
                defender_armor_class=enemy_armor,
                defender_hp=state.active_enemy_hp,
                base_attack_bonus=state.player.attack_bonus,
                strength=state.player.strength,
                damage_die=8,
            )
            state.active_enemy_hp = result.remaining_hp
            outcome = (
                f"Attack roll {result.raw_roll} (+bonus => {result.total_roll}) vs AC {enemy_armor}. "
                f"{'Hit' if result.hit else 'Miss'} for {result.damage} damage."
            )
            system_messages.append(outcome)
            if result.remaining_hp == 0:
                self._resolve_catacombs_victory(state, enemy, system_messages, outcome="combat")
            else:
                if self._resolve_enemy_turn(state, enemy, system_messages):
                    return TurnResult(
                        narrative="You fall in the catacombs. Your campaign ends here.",
                        system_messages=system_messages,
                        messages=self._build_structured_messages(system_messages, "You fall in the catacombs. Your campaign ends here."),
                        should_exit=True,
                    )

        elif normalized == "defend":
            if not self._ensure_enemy_active(state, system_messages):
                return self._finish_turn(state, action, system_messages)
            state.combat_effects["player_defending"] = True
            system_messages.append("You brace for impact, reducing incoming damage this round.")
            enemy = self.content.get_enemy(state.active_enemy_id or "")
            if enemy and self._resolve_enemy_turn(state, enemy, system_messages):
                return TurnResult(
                    narrative="You fall in the catacombs. Your campaign ends here.",
                    system_messages=system_messages,
                    messages=self._build_structured_messages(system_messages, "You fall in the catacombs. Your campaign ends here."),
                    should_exit=True,
                )

        elif normalized == "ability":
            if not self._ensure_enemy_active(state, system_messages):
                return self._finish_turn(state, action, system_messages)
            enemy = self.content.get_enemy(state.active_enemy_id or "")
            if enemy is None:
                system_messages.append("Enemy data is missing.")
                return self._finish_turn(state, action, system_messages)
            guarding = bool(state.combat_effects.get("enemy_guarded", False))
            enemy_armor = enemy.armor + (2 if guarding else 0)
            if guarding:
                state.combat_effects["enemy_guarded"] = False
            result = self.combat.resolve_special_ability(
                attacker_name=state.player.name,
                defender_name=enemy.name,
                defender_armor_class=enemy_armor,
                defender_hp=state.active_enemy_hp or enemy.max_hp,
                base_attack_bonus=state.player.attack_bonus,
                intellect=state.player.intellect,
            )
            state.active_enemy_hp = result.remaining_hp
            system_messages.append(
                f"You unleash a focused ability: roll {result.raw_roll} ({result.total_roll} total), "
                f"{'hit' if result.hit else 'miss'} for {result.damage} damage."
            )
            if result.remaining_hp == 0:
                self._resolve_catacombs_victory(state, enemy, system_messages, outcome="combat")
            elif self._resolve_enemy_turn(state, enemy, system_messages):
                return TurnResult(
                    narrative="You fall in the catacombs. Your campaign ends here.",
                    system_messages=system_messages,
                    messages=self._build_structured_messages(system_messages, "You fall in the catacombs. Your campaign ends here."),
                    should_exit=True,
                )

        elif normalized == "flee":
            if not self._ensure_enemy_active(state, system_messages):
                return self._finish_turn(state, action, system_messages)
            escaped, raw = self.combat.resolve_flee_attempt(state.player.agility)
            if escaped:
                state.active_enemy_id = None
                state.active_enemy_hp = None
                state.world_flags["catacombs_cleared"] = False
                state.world_events.append("retreated_from_bone_warden")
                system_messages.append(f"You disengage successfully (roll {raw}) and retreat.")
                state.faction_reputation["guild"] = state.faction_reputation.get("guild", 0) - 1
            else:
                system_messages.append(f"Escape attempt failed (roll {raw}).")
                enemy = self.content.get_enemy(state.active_enemy_id or "")
                if enemy and self._resolve_enemy_turn(state, enemy, system_messages):
                    return TurnResult(
                        narrative="You fall while trying to flee. Your campaign ends here.",
                        system_messages=system_messages,
                        messages=self._build_structured_messages(system_messages, "You fall while trying to flee. Your campaign ends here."),
                        should_exit=True,
                    )

        elif normalized.startswith("rest"):
            if state.active_enemy_id is not None and (state.active_enemy_hp or 0) > 0:
                system_messages.append("You cannot rest while an active threat is engaged.")
            else:
                state.player.hp = state.player.max_hp
                system_messages.append("You take a safe rest and recover to full health.")

        elif normalized == "status":
            active_quest_count = sum(1 for quest in state.quests.values() if quest.status == "active")
            nearby_npcs = sum(1 for npc in state.npcs.values() if npc.location_id == state.current_location_id)
            enemy_hp = state.active_enemy_hp if state.active_enemy_hp is not None else 0
            system_messages.append(
                f"Active quests: {active_quest_count}. Nearby NPCs: {nearby_npcs}. "
                f"Active enemy HP: {enemy_hp}. Player HP: {state.player.hp}/{state.player.max_hp}. "
                f"Rep town/guild/unknown: {state.faction_reputation.get('town', 0)}/"
                f"{state.faction_reputation.get('guild', 0)}/{state.faction_reputation.get('unknown', 0)}."
            )

        elif normalized == "help":
            system_messages.append(
                "Commands: look, move <location_id>, talk <npc_id>, choose <number>, attack, rest, status, "
                "inventory, use <item>, equip <item>, take <item>, drop <item>, quests, sheet, "
                "defend, ability, flee, analyze <question>, summarize, save, load, help, exit"
            )

        elif normalized == "summarize":
            requested_mode = "summarize"
            system_messages.append(self._campaign_summary(state))

        elif normalized.startswith("analyze"):
            requested_mode = "analyze"
            question = action.split(" ", 1)[1] if " " in action else "summarize my campaign so far"
            system_messages.append(self._analysis_response(state, question))

        else:
            system_messages.append("Action noted.")

        return self._finish_turn(state, action, system_messages, requested_mode=requested_mode)

    def _maybe_start_location_encounter(self, state: CampaignState, system_messages: list[str]) -> None:
        if state.current_location_id == "moonfall_catacombs" and not state.world_flags.get("catacombs_cleared", False):
            enemy = self.content.get_enemy("bone_warden")
            if enemy and state.active_enemy_id is None:
                state.active_enemy_id = enemy.id
                state.active_enemy_hp = enemy.max_hp
                system_messages.append(enemy.encounter_text)
            elif enemy:
                system_messages.append(f"The {enemy.name} blocks your path (HP {state.active_enemy_hp}).")

    def _post_talk_consequences(self, state: CampaignState, npc_id: str, system_messages: list[str]) -> None:
        if npc_id == "elder_thorne" and state.quests.get("q_catacomb_blight") and state.quests["q_catacomb_blight"].status == "completed":
            if state.world_flags.get("catacombs_cleared_violently"):
                system_messages.append("Thorne marks your report: 'Hard steel, but effective. Moonfall is safer.'")
            if state.quest_outcomes.get("q_catacomb_blight") == "dialogue":
                system_messages.append("Thorne nods at your restraint. 'You ended it without bloodshed. Noted.'")
            if state.quest_outcomes.get("q_catacomb_blight") == "item":
                system_messages.append("Thorne inspects the relic and smiles. 'A clever resolution, not a brutal one.'")
            if state.world_flags.get("moonlantern_returned"):
                system_messages.append("'Elira sent word. Returning the moonlantern earned goodwill in the woods.'")
            if state.npcs[npc_id].relationship_tier == "loyal":
                system_messages.append("'Moonfall stands with you as one of our own,' Thorne says.")

        if npc_id == "warden_elira" and "moonlantern" in state.player.inventory:
            if state.quests.get("q_moonlantern_oath") and state.quests["q_moonlantern_oath"].status in {"active", "completed"}:
                state.player.inventory.remove("moonlantern")
                state.world_flags["moonlantern_returned"] = True
                self.quests.set_outcome(state, "q_moonlantern_oath", "item")
                state.npcs[npc_id].disposition += 6
                state.npcs[npc_id].relationships[state.player.id] = state.npcs[npc_id].disposition
                state.npcs[npc_id].relationship_tier = self.npc_memory.relationship_tier_for_score(state.npcs[npc_id].disposition)
                state.faction_reputation["town"] = state.faction_reputation.get("town", 0) + 2
                state.world_events.append("elira_moonlantern_returned")
                self.personality.apply_event(
                    state,
                    npc_id,
                    event_type="player_kindness",
                    payload={
                        "summary": "Player returned Moonlantern to Elira",
                        "world_event_id": "elira_moonlantern_returned",
                        "impact": {"trust_toward_player": 8, "hope": 6, "stress": -3, "loyalty": 6},
                        "tags": ["gift", "kindness"],
                    },
                )
                self.inventory.add_item(state.player, "rangers_charm")
                system_messages.append("You return the Moonlantern. Elira rewards you with a Ranger's Charm.")

        if npc_id == "elder_thorne" and "moonsigil_relic" in state.player.inventory:
            if state.quests.get("q_catacomb_blight") and state.quests["q_catacomb_blight"].status == "active":
                state.player.inventory.remove("moonsigil_relic")
                self.quests.set_outcome(state, "q_catacomb_blight", "item")
                state.world_flags["catacombs_cleared"] = True
                state.world_flags["catacombs_cleared_violently"] = False
                state.faction_reputation["guild"] = state.faction_reputation.get("guild", 0) + 2
                state.world_events.append("catacombs_stabilized_with_relic")
                self.personality.apply_event(
                    state,
                    npc_id,
                    event_type="quest_completed",
                    payload={
                        "summary": "Player resolved catacomb blight peacefully with relic",
                        "world_event_id": "catacombs_stabilized_with_relic",
                        "impact": {"trust_toward_player": 8, "hope": 4, "anger": -4, "loyalty": 5},
                        "tags": ["quest", "peaceful_resolution"],
                    },
                )
                system_messages.append("Thorne accepts the Moonsigil Relic as proof and seals the crypt entrance.")

    def _finish_turn(
        self,
        state: CampaignState,
        action: str,
        system_messages: list[str],
        requested_mode: str = "play",
        skip_narrator: bool = False,
    ) -> TurnResult:
        turn_started = time.perf_counter()
        self.memory.record_recent(state, f"Player action: {action}")
        for msg in system_messages:
            self.quests.add_event(state, msg)
            self.memory.record_recent(state, msg)
            self._capture_important_memory(state, msg)

        if self.summary.should_summarize(action, system_messages):
            summary = self.summary.build_summary(state, action, system_messages)
            self.memory.add_session_summary(
                state,
                trigger=action,
                summary=summary,
                quest_ids=[quest.id for quest in state.quests.values() if quest.status == "active"],
                npc_ids=[npc_id for npc_id, npc in state.npcs.items() if npc.location_id == state.current_location_id],
                world_flags=[k for k, v in state.world_flags.items() if v],
            )
            self.memory.record_long_term(
                state,
                category="summary",
                text=summary,
                location_id=state.current_location_id,
                weight=2,
            )

        if skip_narrator:
            self.state_orchestrator.update_runtime_state(state, action=action, system_messages=system_messages, narrative="")
            self.memory.record_conversation_turn(
                state,
                player_input=action,
                system_messages=system_messages,
                narrator_response="",
                requested_mode=requested_mode,
            )
            total_ms = (time.perf_counter() - turn_started) * 1000
            timing = {
                "turn_finalize_ms": round(total_ms, 2),
            }
            return TurnResult(
                narrative="",
                system_messages=system_messages,
                messages=self._build_structured_messages(system_messages, ""),
                metadata={
                    "requested_mode": requested_mode,
                    "provider_attempted": False,
                    "fallback_used": False,
                    "fallback_reason": "",
                    "sanitized_output": False,
                    "guidance_requested": False,
                    "recommendation_cleanup_applied": False,
                    "custom_rule_cleanup_applied": False,
                    "grounding_cleanup_applied": False,
                    "turn_count": state.turn_count,
                    "timing": timing,
                },
            )

        location_started = time.perf_counter()
        location_summary = self.world.get_current_location_summary(state)
        location_ms = (time.perf_counter() - location_started) * 1000
        retrieval_started = time.perf_counter()
        retrieval_request = RetrievalRequest(
            location_id=state.current_location_id,
            active_quest_ids=[quest.id for quest in state.quests.values() if quest.status == "active"],
            current_npc_id=state.active_dialogue_npc_id,
            recent_actions=[event.lower() for event in state.event_log[-4:]],
            important_world_state=[flag.lower() for flag, enabled in state.world_flags.items() if enabled],
        )
        memory_context = self.retrieval.retrieve(state, retrieval_request)
        guidance_requested = self._player_requested_guidance(action)
        print(f"[narration] guidance_requested={str(guidance_requested).lower()}")
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        prompt_started = time.perf_counter()
        gm_context_text = self.state_orchestrator.build_gm_context(state)
        prompt_packet = self.prompts.build_prompt_packet(
            state,
            action=action,
            location_summary=location_summary,
            memory=memory_context,
            requested_mode=requested_mode,
            guidance_requested=guidance_requested,
            npc_guidance=self.personality.build_prompt_guidance(state),
            gm_context=gm_context_text,
        )
        self._last_prompt_debug_by_campaign[state.campaign_id] = {
            "campaign_id": state.campaign_id,
            "turn_count": state.turn_count,
            "requested_mode": requested_mode,
            "action": action,
            "current_location_id": state.current_location_id,
            "location_summary": location_summary,
            "gm_context": gm_context_text,
            "system_prompt": prompt_packet.system_prompt,
            "turn_prompt": prompt_packet.turn_prompt,
            "structured_runtime_snapshot": {
                "inventory_count": len(state.structured_state.runtime.inventory),
                "spellbook_count": len(state.structured_state.runtime.spellbook),
                "npc_count": len(
                    [
                        npc
                        for npc in state.structured_state.runtime.npc_relationships.values()
                        if str(npc.get("location_id", "")) == state.current_location_id
                    ]
                ),
                "minion_count": len(state.structured_state.runtime.party_state.get("minions", [])),
                "active_quest_count": len(
                    [quest for quest, status in state.structured_state.runtime.quest_state.items() if status == "active"]
                ),
            },
        }
        prompt_build_ms = (time.perf_counter() - prompt_started) * 1000
        history_started = time.perf_counter()
        history = self._build_model_history(state)
        history_ms = (time.perf_counter() - history_started) * 1000
        selected_provider = self.model.provider_name
        selected_model = getattr(self.model, "model", getattr(self.model, "model_path", "n/a"))
        provider_attempted = True
        fallback_used = False
        fallback_reason = ""
        raw_narrative = ""
        model_started = time.perf_counter()
        try:
            raw_narrative = self.model.generate(prompt_packet.turn_prompt, prompt_packet.system_prompt, history=history)
            if not raw_narrative.strip():
                raise ProviderUnavailableError("Provider returned empty text")
        except ProviderUnavailableError as exc:
            fallback_reason = str(exc)
            if selected_provider in {"null", "local_template"}:
                raise
            fallback_used = True
            raw_narrative = NullNarrationAdapter().generate(prompt_packet.turn_prompt, prompt_packet.system_prompt, history=history)
        model_ms = (time.perf_counter() - model_started) * 1000
        sanitized_narrative, was_sanitized = self._sanitize_narrative(raw_narrative)
        if not fallback_used:
            print(
                f"[turn-routing] provider={selected_provider} model={selected_model} attempted={provider_attempted} "
                f"fallback={fallback_used} reason=none sanitized={was_sanitized}"
            )
        else:
            print(
                f"[turn-routing] provider={selected_provider} model={selected_model} attempted={provider_attempted} "
                f"fallback={fallback_used} reason={fallback_reason} sanitized={was_sanitized}"
            )
        suggested_moves_enabled = state.settings.suggested_moves_active()
        narrative, cleanup_applied = self._apply_recommendation_policy(
            sanitized_narrative,
            guidance_requested=guidance_requested,
            suggested_moves_enabled=suggested_moves_enabled,
        )
        narrative, custom_rule_cleanup_applied = self._apply_custom_narrator_rule_validation(state, narrative)
        narrative, grounding_cleanup_applied = self._apply_grounding_enforcement(state, action, narrative)
        print(f"[narration] recommendation_cleanup_applied={str(cleanup_applied).lower()}")
        print(f"[narrator-rules] validation_cleanup_applied={str(custom_rule_cleanup_applied).lower()}")
        print(f"[narration] grounding_cleanup_applied={str(grounding_cleanup_applied).lower()}")
        self.memory.record_recent(state, f"Narrator: {narrative}")
        self.state_orchestrator.update_runtime_state(state, action=action, system_messages=system_messages, narrative=narrative)
        self.memory.record_conversation_turn(
            state,
            player_input=action,
            system_messages=system_messages,
            narrator_response=narrative,
            requested_mode=requested_mode,
        )
        total_ms = (time.perf_counter() - turn_started) * 1000
        timing = {
            "location_summary_ms": round(location_ms, 2),
            "memory_retrieval_ms": round(retrieval_ms, 2),
            "prompt_build_ms": round(prompt_build_ms, 2),
            "history_build_ms": round(history_ms, 2),
            "llm_generate_ms": round(model_ms, 2),
            "turn_finalize_ms": round(total_ms, 2),
        }
        return TurnResult(
            narrative=narrative,
            system_messages=system_messages,
            messages=self._build_structured_messages(system_messages, narrative),
            metadata={
                "requested_mode": requested_mode,
                "model_provider": selected_provider,
                "model_name": selected_model,
                "provider_attempted": provider_attempted,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "sanitized_output": was_sanitized,
                "guidance_requested": guidance_requested,
                "recommendation_cleanup_applied": cleanup_applied,
                "custom_rule_cleanup_applied": custom_rule_cleanup_applied,
                "grounding_cleanup_applied": grounding_cleanup_applied,
                "turn_count": state.turn_count,
                "timing": timing,
            },
        )

    def _classify_turn_intent(self, action: str) -> str:
        normalized = re.sub(r"\s+", " ", action.strip().lower())
        system_keywords = (
            "rules",
            "narrator rules",
            "your rules",
            "tell me your rules",
            "brief the narrator rules",
            "what are your narrator rules",
            "system behavior",
            "explain",
            "how do you work",
        )
        structured_keywords = (
            "stats",
            "my stats",
            "character sheet",
            "sheet",
            "inventory",
            "spellbook",
            "what do i have",
            "equipped",
        )
        if any(keyword in normalized for keyword in system_keywords):
            return "system"
        if any(keyword in normalized for keyword in structured_keywords):
            return "structured"
        return "gameplay"

    def _build_system_intent_messages(self, state: CampaignState, normalized: str) -> list[str]:
        if "rule" in normalized:
            return self._build_narrator_rules_response(state)
        return [
            "System info: I can provide rules, mechanics explanations, and structured status without advancing narration.",
            "Use a concrete in-world action to continue gameplay narration.",
        ]

    def _build_narrator_rules_response(self, state: CampaignState) -> list[str]:
        rules = state.structured_state.canon.custom_narrator_rules
        if not rules:
            return ["Narrator rules: none configured for this campaign."]
        rendered: list[str] = ["Narrator rules:"]
        for idx, rule in enumerate(rules, start=1):
            text = str(rule.get("text", "")).strip() if isinstance(rule, dict) else ""
            if text:
                rendered.append(f"{idx}. {text}")
        if len(rendered) == 1:
            return ["Narrator rules: none configured for this campaign."]
        return rendered

    def _build_structured_intent_messages(self, state: CampaignState, normalized: str) -> list[str]:
        structured_runtime = state.structured_state.runtime
        inventory_intent = (
            normalized == "inventory"
            or "what is in my inventory" in normalized
            or "show inventory" in normalized
            or "open inventory" in normalized
            or "what do i have" in normalized
        )
        spellbook_intent = normalized in {"spellbook", "open my spellbook"} or "open my spellbook" in normalized or "show spellbook" in normalized
        stats_intent = (
            normalized in {"sheet", "stats", "what are my stats"}
            or "what are my stats" in normalized
            or "show my stats" in normalized
            or "character sheet" in normalized
            or "equipped" in normalized
        )
        system_messages: list[str] = []
        if stats_intent:
            system_messages.append(self.character_sheet.summary(state.player))
        if inventory_intent:
            if not structured_runtime.inventory_state:
                self.state_orchestrator.update_runtime_state(
                    state,
                    action="inventory_sync",
                    system_messages=[],
                    narrative="",
                )
            system_messages.append(self.inventory.describe_inventory(state.player))
        if spellbook_intent:
            spells = structured_runtime.spellbook
            if spells:
                formatted = ", ".join(f"{entry.get('name', 'Unknown')} ({entry.get('type', 'ability')})" for entry in spells[:12])
                suffix = "..." if len(spells) > 12 else ""
                system_messages.append(f"Spellbook: {formatted}{suffix}")
            else:
                system_messages.append("Spellbook: empty.")
        return system_messages

    def _sanitize_narrative(self, narrative: str) -> tuple[str, bool]:
        text = narrative.strip()
        original = text
        banned_markers = (
            "local template narrator",
            "requested mode",
            "conversation context",
            "memory context",
            "scene context",
            "player state summary",
        )
        banned_line_prefixes = (
            "recent chat turns:",
            "recent memory:",
            "long-term memory:",
            "session summaries:",
            "unresolved plot threads:",
            "important world facts:",
            "respond with 2-4 sentences",
        )
        filtered_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            lowered = re.sub(r"^[\[\]\-\*\s]+", "", stripped.lower())
            if any(lowered.startswith(marker) for marker in banned_markers):
                continue
            if any(lowered.startswith(prefix) for prefix in banned_line_prefixes):
                continue
            filtered_lines.append(stripped)
        text = " ".join(filtered_lines) if filtered_lines else text
        text = re.sub(r"\[(?:Local template narrator|Requested Mode|Conversation Context|Memory Context|Scene Context|Player State Summary)\]", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"(Respond with 2-4 sentences(?: and one suggested next move)?\.?)+", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"(Recent chat turns:|Recent memory:|Long-term memory:|Session summaries:|Unresolved plot threads:|Important world facts:).*?(?=(?:\[[^\]]+\])|$)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s{2,}", " ", text).strip()
        if not text:
            text = "The world holds its breath for a heartbeat, waiting for your next move."
        return text, text != original

    def _player_requested_guidance(self, action: str) -> bool:
        normalized = re.sub(r"\s+", " ", action.strip().lower())
        if not normalized:
            return False
        guidance_patterns = (
            r"\bwhat should i do next\b",
            r"\bnext move\b",
            r"\bsuggestion(?:s)?\b",
            r"\brecommend(?:ed|ation|ations)?\b",
            r"\badvice\b",
            r"\bhint(?:s)?\b",
            r"\bwhat are my options\b",
            r"\boptions\b",
            r"\bgive me (?:some )?ideas\b",
            r"\bideas\b",
            r"\bwhat can i do\b",
            r"\bhelp me choose\b",
        )
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in guidance_patterns)

    def _apply_recommendation_policy(
        self, narrative: str, guidance_requested: bool, suggested_moves_enabled: bool
    ) -> tuple[str, bool]:
        if guidance_requested and suggested_moves_enabled:
            return narrative, False
        cleaned = self._strip_recommendation_segments(narrative)
        if cleaned:
            return cleaned, cleaned != narrative.strip()
        return "The world holds its breath for a heartbeat, waiting for your next move.", True

    def _strip_recommendation_segments(self, narrative: str) -> str:
        text = narrative.strip()
        line_patterns = (
            r"^\s*(?:[-*]\s*)?(?:suggested|recommended)\s*(?:next)?\s*move[s]?\s*:\s*.*$",
            r"^\s*(?:[-*]\s*)?next\s*move\s*:\s*.*$",
            r"^\s*(?:[-*]\s*)?your\s*first\s*course\s*of\s*action\s*:?\s*.*$",
            r"^\s*(?:[-*]\s*)?you\s*should(?:\s*now)?\b.*$",
            r"^\s*(?:[-*]\s*)?consider\b.*$",
            r"^\s*(?:[-*]\s*)?a\s*good\s*next\s*step\s*would\s*be\b.*$",
        )
        for pattern in line_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

        sentence_patterns = (
            r"(?:^|\s)(?:suggested|recommended)\s*(?:next)?\s*move\s*:\s*[^.!?\n]+[.!?]?",
            r"(?:^|\s)next\s*move\s*:\s*[^.!?\n]+[.!?]?",
            r"(?:^|\s)your\s*first\s*course\s*of\s*action\s*:?\s*[^.!?\n]+[.!?]?",
            r"(?:^|\s)you\s*should(?:\s*now)?\s+[^.!?\n]+[.!?]",
            r"(?:^|\s)consider\s+[^.!?\n]+[.!?]",
            r"(?:^|\s)a\s*good\s*next\s*step\s*would\s*be\s+[^.!?\n]+[.!?]",
            r"(?:^|\s)(?:i\s+)?recommend(?:\s+that)?\s+[^.!?\n]+[.!?]",
            r"(?:^|\s)(?:you\s+)?could\s+[^.!?\n]+[.!?]",
            r"(?:^|\s)(?:you\s+may\s+want\s+to|try\s+to)\s+[^.!?\n]+[.!?]",
            r"(?:^|\s)one\s+option\s+is\s+to\s+[^.!?\n]+[.!?]",
        )
        for pattern in sentence_patterns:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

        text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text

    def _apply_custom_narrator_rule_validation(self, state: CampaignState, narrative: str) -> tuple[str, bool]:
        rules = state.structured_state.canon.custom_narrator_rules
        if not rules:
            return narrative, False
        texts = [
            str(entry.get("text", "")).strip().lower()
            for entry in rules
            if isinstance(entry, dict) and str(entry.get("text", "")).strip()
        ]
        if not texts:
            return narrative, False
        cleaned = narrative.strip()
        applied = False
        if any("never make decisions for me" in rule or "don't make decisions for me" in rule for rule in texts):
            before = cleaned
            cleaned = re.sub(
                r"\b(?:you|your character)\s+(?:decide|decides|chose|choose|chooses|start|starts|begin|begins)\s+to\b[^.!?\n]*[.!?]?",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
            if cleaned != before:
                applied = True
        if not cleaned:
            cleaned = "The air stills, awaiting your command."
            applied = True
        return cleaned, applied

    def _apply_grounding_enforcement(self, state: CampaignState, action: str, narrative: str) -> tuple[str, bool]:
        original = narrative.strip()
        text = original
        location = state.locations.get(state.current_location_id)
        location_text = f"{state.current_location_id} {location.name if location else ''} {location.description if location else ''} {state.world_meta.world_theme} {state.world_meta.premise}".lower()
        action_word_count = len([piece for piece in action.split() if piece.strip()])
        sentence_chunks = re.split(r"(?<=[.!?])\s+", text)
        filtered: list[str] = []
        unsupported_environment_terms = {
            "forest": ["forest", "woods", "grove"],
            "temple": ["temple", "sanctum", "shrine"],
            "desert": ["desert", "dune", "oasis"],
            "ocean": ["ocean", "sea", "coast", "shore"],
        }
        removed_count = 0
        for sentence in sentence_chunks:
            trimmed = sentence.strip()
            if not trimmed:
                continue
            lowered = trimmed.lower()
            if re.search(r"\b(?:you feel|you think|you realize|you decide|you know)\b", lowered):
                removed_count += 1
                continue
            if re.search(r"\b(?:your power is growing|your power grows|you are becoming stronger|you grow stronger)\b", lowered):
                removed_count += 1
                continue
            if re.search(r"\b(?:fate|destiny|in time you will|you are destined|your future)\b", lowered):
                removed_count += 1
                continue
            if re.search(r"\b(?:hours later|days later|weeks later|months later|after a long journey|time passes)\b", lowered):
                if action_word_count <= 8:
                    removed_count += 1
                    continue
            if re.search(r"\b(?:you arrive at|you enter|you step into)\b", lowered) and not action.lower().strip().startswith("move "):
                removed_count += 1
                continue
            environment_unsupported = False
            for terms in unsupported_environment_terms.values():
                if any(term in lowered for term in terms) and not any(term in location_text for term in terms):
                    environment_unsupported = True
                    break
            if environment_unsupported:
                removed_count += 1
                continue
            filtered.append(trimmed)
        cleaned = " ".join(filtered).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if not cleaned:
            cleaned = "The scene holds steady at your current location, awaiting your next command."
        applied = cleaned != original
        if applied:
            print(f"[narration-enforcement] removed_unsupported_segments={removed_count}")
        return cleaned, applied

    def get_last_prompt_debug_packet(self, campaign_id: str) -> dict[str, object]:
        return dict(self._last_prompt_debug_by_campaign.get(campaign_id, {}))

    def _build_model_history(self, state: CampaignState) -> list[ChatMessage]:
        history: list[ChatMessage] = []
        for turn in state.conversation_turns[-6:]:
            if turn.player_input:
                history.append(ChatMessage(role="user", content=turn.player_input))
            if turn.narrator_response:
                history.append(ChatMessage(role="assistant", content=turn.narrator_response))
        return history

    def _build_structured_messages(self, system_messages: list[str], narrative: str) -> list[dict[str, str]]:
        payload = [{"type": self._classify_message_type(message), "text": message} for message in system_messages]
        if narrative.strip():
            payload.append({"type": "narrator", "text": narrative})
        return payload

    def _classify_message_type(self, message: str) -> str:
        lowered = message.lower()
        if "quest" in lowered:
            return "quest"
        if "relationship tier" in lowered or "choose <number>" in lowered or lowered.startswith('"'):
            return "npc"
        return "system"

    def _campaign_summary(self, state: CampaignState) -> str:
        active_quests = [quest.title for quest in state.quests.values() if quest.status == "active"]
        recent = state.recent_memory[-3:] if state.recent_memory else state.event_log[-3:]
        return (
            f"Campaign '{state.campaign_name}' at turn {state.turn_count}. "
            f"Location: {state.current_location_id}. "
            f"Active quests: {', '.join(active_quests) if active_quests else 'none'}. "
            f"Recent: {' | '.join(recent) if recent else 'no recent events'}."
        )

    def _analysis_response(self, state: CampaignState, question: str) -> str:
        lowered = question.lower()
        if "active quest" in lowered:
            active = self.quests.list_active_quests(state)
            return "Active quests: " + ("; ".join(active) if active else "none")
        if "npc" in lowered and ("think" in lowered or "relationship" in lowered):
            npc_id = state.active_dialogue_npc_id
            if not npc_id:
                npc_id = next((n.id for n in state.npcs.values() if n.location_id == state.current_location_id), None)
            if npc_id and npc_id in state.npcs:
                npc = state.npcs[npc_id]
                return f"{npc.name} disposition={npc.disposition}, tier={npc.relationship_tier}."
            return "No relevant NPC is currently in focus."
        if "recent" in lowered or "happened" in lowered:
            return "Recent actions: " + (" | ".join(state.recent_memory[-5:]) if state.recent_memory else "none")
        if "choice" in lowered or "affecting the world" in lowered:
            flags = [f"{k}=true" for k, v in state.world_flags.items() if v]
            return "World-impacting choices: " + (", ".join(flags) if flags else "none tracked yet")
        return self._campaign_summary(state)

    def _capture_important_memory(self, state: CampaignState, message: str) -> None:
        lowered = message.lower()
        if "quest" in lowered and ("active" in lowered or "completed" in lowered):
            self.memory.record_long_term(
                state,
                category="quest",
                text=message,
                location_id=state.current_location_id,
                quest_id=next((quest.id for quest in state.quests.values() if quest.status == "active"), None),
                weight=3,
            )
        if "relationship tier" in lowered:
            npc_id = state.active_dialogue_npc_id
            self.memory.record_long_term(
                state,
                category="npc",
                text=message,
                location_id=state.current_location_id,
                npc_id=npc_id,
                weight=3,
            )
        if "travel to" in lowered or "defeated" in lowered:
            self.memory.record_long_term(
                state,
                category="world",
                text=message,
                location_id=state.current_location_id,
                weight=2,
            )
        if "you recover" in lowered or "find" in lowered:
            self.memory.add_plot_thread(state, f"Follow up on discovery: {message}")
        if "catacombs_cleared" in str(state.world_events[-2:]):
            self.memory.add_world_fact(state, "The catacombs have been cleared, shifting town safety.")

    def _ensure_enemy_active(self, state: CampaignState, system_messages: list[str]) -> bool:
        if state.active_enemy_id is None or state.active_enemy_hp is None or state.active_enemy_hp <= 0:
            system_messages.append("There is no active enemy.")
            return False
        return True

    def _resolve_enemy_turn(self, state: CampaignState, enemy, system_messages: list[str]) -> bool:
        defending = bool(state.combat_effects.get("player_defending", False))
        retaliation, metadata = self.combat.resolve_enemy_turn(
            enemy_name=enemy.name,
            enemy_behavior=enemy.behavior,
            enemy_attack_bonus=enemy.attack,
            enemy_damage_die=enemy.damage_die,
            enemy_hp=state.active_enemy_hp or enemy.max_hp,
            enemy_max_hp=enemy.max_hp,
            defender_name=state.player.name,
            defender_armor_class=state.player.armor_class,
            defender_hp=state.player.hp,
            defender_vitality=state.player.vitality,
            defender_is_defending=defending,
        )
        state.combat_effects["player_defending"] = False
        state.player.hp = retaliation.remaining_hp
        if metadata.get("guarded"):
            state.combat_effects["enemy_guarded"] = True
            system_messages.append(f"{enemy.name} fights cautiously and raises a guard.")
        recoil_damage = int(metadata.get("recoil_damage", 0))
        if recoil_damage and state.active_enemy_hp is not None:
            state.active_enemy_hp = max(0, state.active_enemy_hp - recoil_damage)
            system_messages.append(f"{enemy.name}'s reckless momentum causes {recoil_damage} self-damage.")
            if state.active_enemy_hp == 0:
                self._resolve_catacombs_victory(state, enemy, system_messages, outcome="combat")
                return False
        system_messages.append(
            f"{enemy.name} counters with roll {retaliation.raw_roll} ({retaliation.total_roll} total): "
            f"{'hit' if retaliation.hit else 'miss'}, {retaliation.damage} damage to you."
        )
        return state.player.hp == 0

    def _resolve_catacombs_victory(self, state: CampaignState, enemy, system_messages: list[str], outcome: str) -> None:
        msg = self.character_sheet.grant_xp(state.player, enemy.reward.xp)
        system_messages.append(f"{enemy.name} defeated. {msg}")
        state.active_enemy_id = None
        state.active_enemy_hp = None
        state.world_flags["catacombs_cleared"] = True
        state.world_flags["catacombs_cleared_violently"] = outcome == "combat"
        if "q_catacomb_blight" in state.quests:
            self.quests.set_outcome(state, "q_catacomb_blight", outcome)
        state.faction_reputation["guild"] = state.faction_reputation.get("guild", 0) + 3
        state.faction_reputation["town"] = state.faction_reputation.get("town", 0) + 2
        state.world_events.append(f"catacombs_cleared_{outcome}")
        if "elder_thorne" in state.npcs:
            self.personality.apply_event(
                state,
                "elder_thorne",
                event_type="quest_completed",
                payload={
                    "summary": f"Catacombs resolved via {outcome}",
                    "world_event_id": f"catacombs_cleared_{outcome}",
                    "impact": {
                        "trust_toward_player": 5 if outcome != "combat" else 2,
                        "fear_toward_player": 2 if outcome == "combat" else -2,
                        "hope": 4,
                        "anger": 2 if outcome == "combat" else -2,
                    },
                    "tags": ["quest", outcome],
                },
            )
        state.world_flags["catacombs_echo_silenced"] = True
        for reward_item in enemy.reward.items:
            self.inventory.add_item(state.player, reward_item)
            system_messages.append(f"You recover {reward_item.replace('_', ' ').title()} from the chamber.")
        if (
            state.quests.get("q_moonlantern_oath")
            and state.quests["q_moonlantern_oath"].status == "active"
            and "moonlantern" not in state.player.inventory
        ):
            self.inventory.add_item(state.player, "moonlantern")
            system_messages.append("Among the bones, you also find Elira's missing Moonlantern.")
