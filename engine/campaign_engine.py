"""Core campaign loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time
from difflib import SequenceMatcher
from typing import Any

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
from prompts.renderer import TurnPromptContext
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
        self._scene_state_list_caps: dict[str, int] = {
            "visible_entities": 8,
            "damaged_objects": 8,
            "altered_environment": 8,
            "active_effects": 6,
            "recent_consequences": 5,
        }
        self._filler_loop_phrases: tuple[str, ...] = (
            "eyes widening in alarm",
            "posture crumbling",
            "torches flickering",
            "patrons leaning in",
            "air thick with tension",
        )

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
        scene_state = self._ensure_scene_state(state)
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
            self._update_scene_state_from_turn(state, action=action, narrative="", system_messages=system_messages, is_gameplay=False)
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

        action_subtype = self._classify_gameplay_action_subtype(action)
        # Boundary: engine provides social structure (participants + continuity); narrator prompt/rules
        # own prose shape for both pure dialogue and mixed social turns.
        if action_subtype == "dialogue":
            target_actor = self._resolve_scene_actor_target(action, scene_state)
            if target_actor is not None:
                self._materialize_lightweight_npc(state, scene_state, target_actor)
                target_actor["last_interaction_turn"] = state.turn_count
                scene_state["last_target_actor_id"] = str(target_actor.get("actor_id", ""))
                print(f"[npc-dialogue] target_context={target_actor.get('actor_id', '')}")

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
        scene_state_summary = self._summarize_scene_state_for_prompt(scene_state)
        turn_context = self._build_structured_turn_context(state, action, scene_state)
        recent_consequence_summary = self._build_recent_consequence_summary(scene_state)
        print(f"[narration-debug] current_action_received={action.strip()}")
        print("[narration-debug] structured_state_summary_built=true")
        print(f"[narration-debug] recent_memory_summary_length={len(recent_consequence_summary)}")
        print("[narration-debug] raw_narration_history_included=false")
        prompt_packet = self.prompts.build_prompt_packet(
            state,
            action=action,
            location_summary=location_summary,
            memory=memory_context,
            requested_mode=requested_mode,
            guidance_requested=guidance_requested,
            npc_guidance=self.personality.build_prompt_guidance(state),
            gm_context=gm_context_text,
            scene_state_summary=scene_state_summary,
            turn_context=turn_context,
        )
        self._last_prompt_debug_by_campaign[state.campaign_id] = {
            "campaign_id": state.campaign_id,
            "turn_count": state.turn_count,
            "requested_mode": requested_mode,
            "action": action,
            "current_location_id": state.current_location_id,
            "location_summary": location_summary,
            "scene_state_summary": scene_state_summary,
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
                )
                + len(
                    [
                        actor
                        for actor in scene_state.get("scene_actors", [])
                        if isinstance(actor, dict)
                        and bool(actor.get("visible", True))
                        and str(actor.get("location_id", state.current_location_id)) == state.current_location_id
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
        retry_used = False
        retry_reason = ""
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
        validation = self._validate_narration_output(action, sanitized_narrative, state, scene_state)
        print(f"[narration-debug] validator_result={'valid' if validation['valid'] else 'invalid'}")
        if not validation["valid"]:
            retry_used = True
            retry_reason = str(validation["reason"])
            print(f"[narration-debug] invalid_reason={retry_reason}")
            retry_prompt_packet = self.prompts.build_prompt_packet(
                state,
                action=action,
                location_summary=location_summary,
                memory=memory_context,
                requested_mode=requested_mode,
                guidance_requested=guidance_requested,
                npc_guidance=self.personality.build_prompt_guidance(state),
                gm_context=gm_context_text,
                scene_state_summary=scene_state_summary,
                turn_context=turn_context,
                retry_action_priority=True,
            )
            retry_raw = self.model.generate(retry_prompt_packet.turn_prompt, retry_prompt_packet.system_prompt, history=history)
            retry_sanitized, retry_was_sanitized = self._sanitize_narrative(retry_raw)
            sanitized_narrative = retry_sanitized
            was_sanitized = was_sanitized or retry_was_sanitized
            validation = self._validate_narration_output(action, sanitized_narrative, state, scene_state)
            print(f"[narration-debug] retry_used=true")
            print(f"[narration-debug] retry_validator_result={'valid' if validation['valid'] else 'invalid'}")
        else:
            print("[narration-debug] retry_used=false")
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
        action_subtype = self._classify_gameplay_action_subtype(action)
        last_narration = state.structured_state.runtime.last_narration
        consecutive_repetition_count = int(scene_state.get("consecutive_repetition_count", 0) or 0)
        narration_invalid = self._is_invalid_narration_output(sanitized_narrative) or (not bool(validation["valid"]))
        repetition_candidate = self._is_repetitive_narration(sanitized_narrative, last_narration)
        narration_repetitive = repetition_candidate and consecutive_repetition_count >= 2
        strict_validation_reasons = {"no_output", "refusal", "action_override", "stale_state_loop", "scene_reset"}
        strict_invalid = (not bool(validation["valid"])) and str(validation.get("reason", "")) in strict_validation_reasons
        # Minimal narration control mode:
        # engine owns structural truth/recovery; narrator rules own narrative behavior.
        if narration_invalid or narration_repetitive or strict_invalid:
            narrative = self._build_scene_aware_fallback(action, scene_state)
            cleanup_applied = False
            custom_rule_cleanup_applied = False
            grounding_cleanup_applied = False
            quality_fallback_used = True
        else:
            if action_subtype == "dialogue" and sanitized_narrative.strip():
                print("[control-audit] fallback_skipped_reason=valid_dialogue")
            narrative = sanitized_narrative.strip()
            cleanup_applied = False
            custom_rule_cleanup_applied = False
            grounding_cleanup_applied = False
            quality_fallback_used = False
            print("[control-audit] preserved_generated_output=true")
            print("[narrative-quality] preserved_valid_output=true")
        if quality_fallback_used:
            scene_state["consecutive_repetition_count"] = 0
        elif repetition_candidate:
            scene_state["consecutive_repetition_count"] = consecutive_repetition_count + 1
            print("[control-audit] repetition_threshold_not_met")
        else:
            scene_state["consecutive_repetition_count"] = 0
        print(f"[turn-quality] invalid={str(narration_invalid).lower()}")
        print(f"[turn-quality] repetitive={str(narration_repetitive).lower()}")
        print(f"[turn-quality] fallback_used={str(quality_fallback_used).lower()}")
        print(f"[narration] recommendation_cleanup_applied={str(cleanup_applied).lower()}")
        print(f"[narrator-rules] validation_cleanup_applied={str(custom_rule_cleanup_applied).lower()}")
        print(f"[narration] grounding_cleanup_applied={str(grounding_cleanup_applied).lower()}")
        state.structured_state.runtime.last_narration = narrative
        self._update_scene_state_from_turn(state, action=action, narrative=narrative, system_messages=system_messages, is_gameplay=True)
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
                "quality_invalid_output": narration_invalid,
                "quality_repetitive_output": narration_repetitive,
                "quality_fallback_used": quality_fallback_used,
                "retry_used": retry_used,
                "retry_reason": retry_reason,
                "turn_count": state.turn_count,
                "timing": timing,
            },
        )

    def _classify_turn_intent(self, action: str) -> str:
        normalized = re.sub(r"\s+", " ", action.strip().lower())
        internal_thought_phrases = (
            "i think",
            "i wonder",
            "i consider",
            "i reflect",
        )
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
        if any(phrase in normalized for phrase in internal_thought_phrases):
            return "gameplay"
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
        return narrative.strip(), False

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

    def _is_invalid_narration_output(self, narrative: str) -> bool:
        text = re.sub(r"\s+", " ", narrative.strip().lower())
        if not text:
            return True
        refusal_markers = ("i cannot", "i can't", "cannot create", "i won't", "i will not")
        if any(marker in text for marker in refusal_markers):
            return True
        if len(text) < 3:
            return True
        return False

    def _is_repetitive_narration(self, narrative: str, last_narration: str) -> bool:
        current = re.sub(r"\s+", " ", narrative.strip().lower())
        prior = re.sub(r"\s+", " ", str(last_narration or "").strip().lower())
        if not current or not prior:
            return False
        if current == prior and len(current) > 20:
            return True
        similarity = SequenceMatcher(None, current, prior).ratio()
        if similarity >= 0.98 and len(current) > 40 and len(prior) > 40:
            return True
        repeated_fillers = [phrase for phrase in self._filler_loop_phrases if phrase in current and phrase in prior]
        return bool(repeated_fillers)

    def _validate_narration_output(self, action: str, narrative: str, state: CampaignState, scene_state: dict[str, Any]) -> dict[str, str | bool]:
        normalized_action = self._normalize_action(action)
        normalized_narrative = re.sub(r"\s+", " ", narrative.strip().lower())
        if not normalized_narrative:
            return {"valid": False, "reason": "no_output"}
        if self._is_refusal_output(normalized_narrative):
            return {"valid": False, "reason": "refusal"}
        if self._detect_action_override(normalized_action, normalized_narrative, scene_state):
            return {"valid": False, "reason": "action_override"}
        if self._is_clear_stale_state_loop(normalized_narrative, state):
            return {"valid": False, "reason": "stale_state_loop"}
        if self._is_scene_reset_output(normalized_narrative, state):
            return {"valid": False, "reason": "scene_reset"}
        return {"valid": True, "reason": "ok"}

    def _normalize_action(self, action: str) -> str:
        return re.sub(r"\s+", " ", action.strip().lower())

    def _detect_action_override(self, action: str, narrative: str, scene_state: dict[str, Any]) -> bool:
        def _has_term(text: str, term: str) -> bool:
            return bool(re.search(rf"\b{re.escape(term)}\b", text))

        conflict_pairs = [
            (("freeze", "ice", "frost", "immobilize"), ("flame", "fire", "burn", "blaze")),
            (("fire", "flame", "burn"), ("freeze", "ice", "frost")),
        ]
        for action_terms, conflict_terms in conflict_pairs:
            if any(term in action for term in action_terms):
                if any(_has_term(narrative, term) for term in conflict_terms) and not any(
                    _has_term(narrative, term) for term in action_terms
                ):
                    return True
        previous_action = str(scene_state.get("last_player_action", "")).lower()
        if previous_action and previous_action != action:
            if any(token in previous_action for token in ("fire", "flame", "ice", "freeze")) and any(
                token in narrative for token in re.findall(r"[a-z]{4,}", previous_action)
            ):
                if not any(token in narrative for token in re.findall(r"[a-z]{4,}", action)[:3]):
                    return True
        return False

    def _is_clear_stale_state_loop(self, narrative: str, state: CampaignState) -> bool:
        if not state.conversation_turns:
            return False
        prior = state.conversation_turns[-1].narrator_response.lower()
        if not prior:
            return False
        similarity = SequenceMatcher(None, narrative, prior).ratio()
        if similarity >= 0.995 and len(narrative) > 40 and len(prior) > 40:
            return True
        return any(phrase in narrative and phrase in prior for phrase in self._filler_loop_phrases)

    def _is_refusal_output(self, normalized_narrative: str) -> bool:
        refusal_markers = ("i cannot", "i can't", "cannot create", "i won't", "i will not")
        return any(marker in normalized_narrative for marker in refusal_markers)

    def _is_scene_reset_output(self, narrative: str, state: CampaignState) -> bool:
        if state.turn_count <= 2:
            return False
        reset_markers = ("you arrive at", "as you enter", "the scene opens", "once again you stand", "at the start of")
        return any(marker in narrative for marker in reset_markers)

    def _build_structured_turn_context(self, state: CampaignState, action: str, scene_state: dict[str, Any]) -> TurnPromptContext:
        location = str(scene_state.get("location_name") or state.current_location_id or "unknown")
        participants = [npc.name for npc in state.npcs.values() if npc.location_id == state.current_location_id]
        npc_states: list[str] = []
        for npc_id, npc in state.npcs.items():
            if npc.location_id != state.current_location_id:
                continue
            eval_snapshot = self.personality.evaluate(state, npc_id, scene="dialogue")
            visible_condition = self._describe_npc_visible_condition(npc)
            relationship = f"{npc.relationship_tier} toward {state.player.name}"
            personality_summary = self._describe_npc_personality(npc)
            intent = self._describe_npc_intent(eval_snapshot)
            npc_states.append(
                f"{npc.name} ({npc.personality_nodes.role if npc.personality_nodes and npc.personality_nodes.role else 'npc'}): "
                f"visible condition {visible_condition}; stance {relationship}; personality {personality_summary}; likely behavior {intent}."
            )
        environment_state = [str(v) for v in scene_state.get("altered_environment", []) if str(v).strip()]
        if not environment_state:
            environment_state = [str(scene_state.get("scene_summary", "")).strip()] if str(scene_state.get("scene_summary", "")).strip() else []
        unresolved_threats: list[str] = []
        if state.active_enemy_id and (state.active_enemy_hp or 0) > 0:
            enemy = self.content.get_enemy(state.active_enemy_id)
            if enemy:
                hp = int(state.active_enemy_hp or enemy.max_hp)
                condition = "fresh" if hp >= enemy.max_hp * 0.75 else "wounded" if hp >= enemy.max_hp * 0.35 else "near collapse"
                pressure = "high pressure" if enemy.behavior == "aggressive" else "moderate pressure"
                unresolved_threats.append(
                    f"{enemy.name}: visible condition {condition} ({hp}/{enemy.max_hp} HP); aggression/pressure {pressure}; "
                    f"combat behavior {enemy.behavior}; likely state {'advancing' if enemy.behavior == 'aggressive' else 'guarding'}."
                )
            else:
                unresolved_threats.append(f"Hostile threat active: {state.active_enemy_id} (HP {state.active_enemy_hp}).")
        recent_consequences = [str(v) for v in scene_state.get("recent_consequences", []) if str(v).strip()][-3:]
        narrator_rules = [
            str(entry.get("text", "")).strip()
            for entry in state.structured_state.canon.custom_narrator_rules
            if isinstance(entry, dict) and str(entry.get("text", "")).strip()
        ]
        return TurnPromptContext(
            current_player_action=action.strip(),
            scene_location=location,
            active_participants=participants[-6:],
            npc_states=npc_states[-6:],
            environment_state=environment_state[-5:],
            unresolved_threats=unresolved_threats,
            recent_consequences=recent_consequences,
            narrator_rules=narrator_rules[-5:],
        )

    def _describe_npc_visible_condition(self, npc: Any) -> str:
        stress = int(getattr(npc.dynamic_state, "stress", 0) or 0)
        anger = int(getattr(npc.dynamic_state, "anger", 0) or 0)
        fear = int(getattr(npc.dynamic_state, "fear_toward_player", 0) or 0)
        if stress >= 20 or anger >= 20:
            return "tense and visibly strained"
        if fear >= 15:
            return "guarded and watchful"
        return "steady and composed"

    def _describe_npc_personality(self, npc: Any) -> str:
        if npc.personality_nodes:
            bits = [npc.personality_nodes.temperament, npc.personality_nodes.social_style, npc.personality_nodes.speech_style]
            cleaned = [bit for bit in bits if bit]
            if cleaned:
                return ", ".join(cleaned[:2])
        archetype = str(getattr(npc, "personality_archetype", "") or "").strip()
        return archetype if archetype else "distinct but currently unread"

    def _describe_npc_intent(self, evaluation: Any) -> str:
        tone = str(getattr(evaluation, "tone", "neutral"))
        hostility = int(getattr(evaluation, "hostility", 0) or 0)
        willingness = int(getattr(evaluation, "willingness_to_share", 0) or 0)
        if hostility >= 18:
            return f"{tone}, confrontational, testing boundaries"
        if willingness >= 10:
            return f"{tone}, open to sharing useful detail"
        return f"{tone}, polite but guarded"

    def _build_recent_consequence_summary(self, scene_state: dict[str, Any]) -> str:
        recent = [str(v).strip() for v in scene_state.get("recent_consequences", []) if str(v).strip()]
        return " | ".join(recent[-3:]) if recent else "none"

    def _contains_blocked_filler(self, action: str, narrative: str) -> bool:
        action_text = action.lower()
        narrative_text = narrative.lower()
        blocked_pairs = (
            "the air is thick",
            "darkness surrounding you",
            "your minions",
            "the air grows thick with anticipation",
            "tension hangs in the air",
            "the world seems to hold its breath",
            "the world holds its breath",
        )
        return any(phrase in narrative_text and phrase not in action_text for phrase in blocked_pairs)

    def _is_action_grounded(self, action: str, narrative: str) -> bool:
        action_tokens = {
            token
            for token in re.findall(r"[a-z]+", action.lower())
            if len(token) >= 4 and token not in {"with", "into", "from", "that", "this", "then", "cast"}
        }
        narrative_text = narrative.lower()
        references_action = any(token in narrative_text for token in action_tokens) if action_tokens else bool(narrative_text)
        has_immediate_effect = bool(
            re.search(
                r"\b(strikes|hits|lands|burns|cracks|shatters|reveals|opens|closes|moves|falls|breaks|radiates|echoes|splits|stops|ignites)\b",
                narrative_text,
            )
        )
        return references_action and has_immediate_effect

    def _ensure_scene_state(self, state: CampaignState) -> dict[str, Any]:
        runtime = state.structured_state.runtime
        scene_state = runtime.scene_state if isinstance(runtime.scene_state, dict) else {}
        if not scene_state:
            print("[scene-state] initialized=true")
        location = state.locations.get(state.current_location_id)
        scene_state.setdefault("location_id", state.current_location_id or None)
        scene_state.setdefault("location_name", location.name if location else None)
        scene_state.setdefault("scene_summary", "")
        scene_state.setdefault("visible_entities", [])
        scene_state.setdefault("damaged_objects", [])
        scene_state.setdefault("altered_environment", [])
        scene_state.setdefault("active_effects", [])
        scene_state.setdefault("recent_consequences", [])
        scene_state.setdefault("last_player_action", "")
        scene_state.setdefault("last_immediate_result", "")
        scene_state.setdefault("scene_actors", [])
        scene_state.setdefault("lightweight_npcs", [])
        scene_state.setdefault("last_target_actor_id", "")
        scene_state.setdefault("consecutive_repetition_count", 0)
        runtime.scene_state = scene_state
        return scene_state

    def _summarize_scene_state_for_prompt(self, scene_state: dict[str, Any]) -> str:
        lines: list[str] = []
        location_parts = [str(scene_state.get("location_name", "")).strip(), str(scene_state.get("location_id", "")).strip()]
        location_text = " / ".join(part for part in location_parts if part)
        if location_text:
            lines.append(f"- Location: {location_text}")
        mapping = (
            ("visible_entities", "Visible entities"),
            ("damaged_objects", "Damaged objects"),
            ("altered_environment", "Environment changes"),
            ("active_effects", "Active visible effects"),
            ("recent_consequences", "Recent consequences"),
        )
        for key, label in mapping:
            values = [str(v).strip() for v in scene_state.get(key, []) if str(v).strip()]
            if values:
                lines.append(f"- {label}: {', '.join(values)}")
        summary = str(scene_state.get("scene_summary", "")).strip()
        if summary:
            lines.append(f"- Scene summary: {summary}")
        return "none" if not lines else "\n".join(["Current Scene State:"] + lines)

    def _normalize_scene_entry(self, value: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", value.lower()).strip()

    def _merge_scene_consequence(self, scene_state: dict[str, Any], key: str, value: str) -> None:
        clean_value = re.sub(r"\s+", " ", value.strip())
        if not clean_value:
            return
        normalized = self._normalize_scene_entry(clean_value)
        entries = [str(v) for v in scene_state.get(key, []) if str(v).strip()]
        normalized_existing = {self._normalize_scene_entry(entry) for entry in entries}
        if normalized in normalized_existing:
            return
        entries.append(clean_value)
        cap = self._scene_state_list_caps.get(key, 5)
        scene_state[key] = entries[-cap:]

    def _extract_consequences_from_narration(self, text: str) -> dict[str, list[str]]:
        lowered = text.lower()
        extracted: dict[str, list[str]] = {
            "damaged_objects": [],
            "altered_environment": [],
            "active_effects": [],
            "recent_consequences": [],
        }
        if "wall" in lowered and re.search(r"\b(crack|char|burn|scorch|damage|blacken|fracture)\w*", lowered):
            extracted["damaged_objects"].append("cracked wall")
            extracted["altered_environment"].append("scorched stone")
            extracted["recent_consequences"].append("the wall is visibly damaged")
        if "door" in lowered and re.search(r"\b(break|splinter|shatter|open)\w*", lowered):
            extracted["damaged_objects"].append("broken door")
            extracted["recent_consequences"].append("doorway opened")
        if "floor" in lowered and re.search(r"\b(frost|ice|frozen|slick)\w*", lowered):
            extracted["altered_environment"].append("frost-covered floor")
            extracted["recent_consequences"].append("the floor is slick with frost")
        if re.search(r"\b(radiant|holy|flare|nova|glow)\w*", lowered):
            extracted["active_effects"].append("radiant flare")
        return extracted

    def _extract_consequences_from_action(self, action: str) -> dict[str, list[str]]:
        lowered = action.lower()
        extracted: dict[str, list[str]] = {
            "damaged_objects": [],
            "altered_environment": [],
            "active_effects": [],
            "recent_consequences": [],
        }
        if "wall" in lowered and any(token in lowered for token in ("fireball", "attack", "strike", "blast", "hit")):
            extracted["damaged_objects"].append("cracked wall")
            extracted["altered_environment"].append("scorched stone")
            extracted["recent_consequences"].append("the wall is visibly damaged")
        if "door" in lowered and any(token in lowered for token in ("break", "smash", "attack", "open", "kick")):
            extracted["damaged_objects"].append("broken door")
            extracted["recent_consequences"].append("doorway opened")
        if "floor" in lowered and any(token in lowered for token in ("ice", "frost", "freeze", "blast")):
            extracted["altered_environment"].append("frost-covered floor")
            extracted["recent_consequences"].append("the floor is slick with frost")
        if any(token in lowered for token in ("holy nova", "radiant", "radiance")):
            extracted["active_effects"].append("radiant flare")
        return extracted

    def _extract_scene_actor_labels(self, text: str) -> list[str]:
        lowered = text.lower()
        labels: list[str] = []
        patterns = (
            "mysterious figure",
            "hooded figure",
            "stranger",
            "guard",
            "merchant",
            "woman in a cloak",
            "figure",
        )
        for pattern in patterns:
            if pattern in lowered:
                labels.append(pattern)
        return labels

    def _register_scene_actor(self, state: CampaignState, scene_state: dict[str, Any], label: str) -> dict[str, Any]:
        clean_label = re.sub(r"\s+", " ", label.strip().lower())
        existing = next(
            (
                actor
                for actor in scene_state.get("scene_actors", [])
                if isinstance(actor, dict) and (
                    str(actor.get("short_label", "")).lower() == clean_label
                    or str(actor.get("display_name", "")).lower() == clean_label
                )
            ),
            None,
        )
        if existing is not None:
            existing["visible"] = True
            return existing
        actor_id = f"scene_actor_{state.current_location_id}_{len(scene_state.get('scene_actors', [])) + 1}"
        actor = {
            "actor_id": actor_id,
            "display_name": clean_label.title(),
            "short_label": clean_label,
            "entity_type": "npc" if any(word in clean_label for word in ("guard", "merchant", "stranger", "figure", "woman")) else "unknown",
            "visible": True,
            "introduced_turn": state.turn_count,
            "last_interaction_turn": 0,
            "tags": [token for token in clean_label.split() if token not in {"the", "a", "an", "in"}],
            "provisional": True,
            "location_id": state.current_location_id,
        }
        scene_state.setdefault("scene_actors", []).append(actor)
        print(f"[scene-actors] registered id={actor_id}")
        self._materialize_lightweight_npc(state, scene_state, actor)
        return actor

    def _update_scene_state_from_turn(
        self,
        state: CampaignState,
        *,
        action: str,
        narrative: str,
        system_messages: list[str],
        is_gameplay: bool,
    ) -> None:
        scene_state = self._ensure_scene_state(state)
        location = state.locations.get(state.current_location_id)
        prior_location_id = str(scene_state.get("location_id") or "")
        if prior_location_id and prior_location_id != state.current_location_id:
            scene_state["scene_actors"] = []
            scene_state["lightweight_npcs"] = []
            scene_state["last_target_actor_id"] = ""
        scene_state["location_id"] = state.current_location_id or None
        scene_state["location_name"] = location.name if location else scene_state.get("location_name")
        scene_actors = [actor for actor in scene_state.get("scene_actors", []) if isinstance(actor, dict)]
        for actor in scene_actors:
            if str(actor.get("location_id", state.current_location_id)) != state.current_location_id:
                actor["visible"] = False
        visible_actor_names = [str(actor.get("display_name", "")).strip() for actor in scene_actors if bool(actor.get("visible", True))]
        npc_names = [npc.name for npc in state.npcs.values() if npc.location_id == state.current_location_id]
        scene_state["visible_entities"] = sorted({*npc_names, *visible_actor_names})[-self._scene_state_list_caps["visible_entities"] :]
        print(f"[scene-actors] visible_count={len([name for name in scene_state['visible_entities'] if name])}")
        if not is_gameplay:
            return
        scene_state["last_player_action"] = action.strip()
        for source in [narrative, *system_messages[-2:]]:
            for label in self._extract_scene_actor_labels(source):
                self._register_scene_actor(state, scene_state, label)
        visible_actor_names = [
            str(actor.get("display_name", "")).strip()
            for actor in scene_state.get("scene_actors", [])
            if isinstance(actor, dict) and bool(actor.get("visible", True))
        ]
        scene_state["visible_entities"] = sorted({*npc_names, *visible_actor_names})[-self._scene_state_list_caps["visible_entities"] :]
        print(f"[scene-actors] visible_count={len([name for name in scene_state['visible_entities'] if name])}")
        immediate_sources = [narrative] + system_messages[-2:]
        merged = " ".join(source for source in immediate_sources if source.strip())
        extracted = self._extract_consequences_from_narration(merged)
        action_extracted = self._extract_consequences_from_action(action)
        for key in extracted.keys():
            extracted[key].extend(action_extracted[key])
        for key, values in extracted.items():
            for value in values:
                self._merge_scene_consequence(scene_state, key, value)
        if extracted["recent_consequences"]:
            scene_state["last_immediate_result"] = extracted["recent_consequences"][-1]
        elif narrative.strip():
            scene_state["last_immediate_result"] = re.sub(r"\s+", " ", narrative.strip())[:120]
        damaged = scene_state.get("damaged_objects", [])
        altered = scene_state.get("altered_environment", [])
        effects = scene_state.get("active_effects", [])
        summary_parts: list[str] = []
        if damaged:
            summary_parts.append(f"damage: {', '.join(damaged[-2:])}")
        if altered:
            summary_parts.append(f"environment: {', '.join(altered[-2:])}")
        if effects:
            summary_parts.append(f"effects: {', '.join(effects[-2:])}")
        scene_state["scene_summary"] = "; ".join(summary_parts)
        print("[scene-state] updated=true")
        print(f"[scene-state] damaged_objects={scene_state.get('damaged_objects', [])}")
        print(f"[scene-state] altered_environment={scene_state.get('altered_environment', [])}")
        print(f"[scene-state] recent_consequences_count={len(scene_state.get('recent_consequences', []))}")

    def _build_scene_aware_fallback(self, action: str, scene_state: dict[str, Any]) -> str:
        subtype = self._classify_gameplay_action_subtype(action)
        print(f"[turn-quality] fallback_subtype={subtype}")
        if subtype == "internal":
            return self._build_internal_fallback(scene_state)
        if subtype == "perception":
            return self._build_perception_fallback(scene_state)
        if subtype == "movement":
            return self._build_movement_fallback(scene_state)
        if subtype == "interaction":
            return self._build_interaction_fallback(action, scene_state)
        if subtype == "attack_or_spell":
            return self._build_attack_or_spell_fallback(action, scene_state)
        if subtype == "dialogue":
            return self._build_dialogue_fallback(action, scene_state)
        return self._build_generic_fallback(scene_state)

    def _classify_gameplay_action_subtype(self, action: str) -> str:
        normalized = re.sub(r"\s+", " ", action.strip().lower())
        if not normalized:
            return "generic"
        if any(phrase in normalized for phrase in ("i think", "i wonder", "i consider", "i reflect")):
            return "internal"
        if re.search(r"['\"][^'\"]+['\"]", normalized):
            return "dialogue"
        if "wait for" in normalized and "reply" in normalized:
            return "dialogue"
        if any(keyword in normalized for keyword in (" say ", " ask ", " tell ", " shout ", " speak ")):
            return "dialogue"
        if normalized.startswith(("say ", "ask ", "tell ", "shout ", "speak ")):
            return "dialogue"
        if any(
            phrase in normalized
            for phrase in (
                "look",
                "look around",
                "inspect",
                "examine",
                "what is around me",
                "what is all around me",
                "what do i see",
                "around me",
                "survey",
            )
        ):
            return "perception"
        if any(phrase in normalized for phrase in ("walk", "move", "step", "approach", "go to", "circle", "pace", "around")):
            return "movement"
        if any(phrase in normalized for phrase in ("touch", "open", "grab", "take", "pick up", "push", "pull")):
            return "interaction"
        if any(phrase in normalized for phrase in ("cast", "attack", "hit", "strike", "kick", "slash", "shoot", "spell")):
            return "attack_or_spell"
        return "generic"

    def _build_internal_fallback(self, scene_state: dict[str, Any]) -> str:
        location = str(scene_state.get("location_name") or "the current area")
        altered = [str(v) for v in scene_state.get("altered_environment", []) if str(v).strip()]
        recent = [str(v) for v in scene_state.get("recent_consequences", []) if str(v).strip()]
        details = [f"A brief pause settles over you in {location} as the scene continues around you."]
        if altered:
            details.append(f"{altered[-1].capitalize()} remains visible at the edge of your attention.")
        if recent:
            details.append(f"The latest visible change still holds: {recent[-1]}.")
        if not altered and not recent:
            details.append("Your stance stays steady while nearby sounds and movement carry on without interruption.")
        return " ".join(details)

    def _build_perception_fallback(self, scene_state: dict[str, Any]) -> str:
        location = str(scene_state.get("location_name") or "the current area")
        damaged = [str(v) for v in scene_state.get("damaged_objects", []) if str(v).strip()]
        altered = [str(v) for v in scene_state.get("altered_environment", []) if str(v).strip()]
        visible_entities = [str(v) for v in scene_state.get("visible_entities", []) if str(v).strip()]
        recent = [str(v) for v in scene_state.get("recent_consequences", []) if str(v).strip()]
        details: list[str] = [f"The scene in {location} stays clearly in view around you."]
        if damaged:
            details.append(f"Visible damage includes {', '.join(damaged[-2:])}.")
        if altered:
            details.append(f"The environment still shows {', '.join(altered[-2:])}.")
        if visible_entities:
            details.append(f"You can see {', '.join(visible_entities[-3:])} in the space with you.")
        if recent:
            details.append(f"The latest visible consequence remains: {recent[-1]}.")
        if len(details) == 1:
            details.append("No abrupt new change breaks the room, but the surroundings remain readable from your position.")
        return " ".join(details)

    def _build_movement_fallback(self, scene_state: dict[str, Any]) -> str:
        location = str(scene_state.get("location_name") or "the area")
        damaged = [str(v) for v in scene_state.get("damaged_objects", []) if str(v).strip()]
        altered = [str(v) for v in scene_state.get("altered_environment", []) if str(v).strip()]
        sentence = [f"You shift position within {location}, changing your angle on the scene."]
        if damaged:
            sentence.append(f"From the new viewpoint, {damaged[-1]} stands out more clearly.")
        if altered:
            sentence.append(f"{altered[-1].capitalize()} remains evident from this spot.")
        if not damaged and not altered:
            sentence.append("Nearby features slide into a slightly different alignment as you move.")
        return " ".join(sentence)

    def _build_interaction_fallback(self, action: str, scene_state: dict[str, Any]) -> str:
        target = self._extract_action_target(action)
        location = str(scene_state.get("location_name") or "the current space")
        if target:
            return f"You act directly on {target} in {location}. The interaction produces an immediate, visible response in front of you."
        return f"You carry out the interaction in {location}. The immediate effect is local and visible where you are."

    def _build_attack_or_spell_fallback(self, action: str, scene_state: dict[str, Any]) -> str:
        target = self._extract_action_target(action)
        action_text = action.lower()
        damaged = [str(v) for v in scene_state.get("damaged_objects", []) if str(v).strip()]
        recent = [str(v) for v in scene_state.get("recent_consequences", []) if str(v).strip()]
        attack_label = "fireball" if "fireball" in action_text else "attack"
        if target and any(target.lower() in entry.lower() for entry in damaged):
            if "wall" in target.lower():
                return f"The {attack_label} slams into the already-cracked wall again. Fresh force widens the damage already carved into the stone."
            return f"The {attack_label} hits {target} again, where prior damage is already visible. Fresh force worsens the marked surface."
        if target:
            return f"Your {attack_label} lands on {target} with immediate visible impact in the scene."
        if damaged:
            return f"Your {attack_label} lands near {damaged[-1]}, adding fresh visible disruption to the damaged area."
        if recent:
            return f"The impact adds to the ongoing scene consequences. {recent[-1].capitalize()}."
        return f"The {attack_label} lands with immediate visible force, leaving a concrete change in the space around you."

    def _build_dialogue_fallback(self, action: str, scene_state: dict[str, Any]) -> str:
        spoken = self._extract_dialogue_content(action)
        visible_entities = [str(v) for v in scene_state.get("visible_entities", []) if str(v).strip()]
        if spoken:
            base = f'Your words — "{spoken}" — carry through the current space.'
        else:
            base = "Your voice carries through the current space."
        if visible_entities:
            return f"{base} {', '.join(visible_entities[-2:])} remain in view as the sound settles."
        return f"{base} No immediate spoken reply breaks the scene."

    def _build_generic_fallback(self, scene_state: dict[str, Any]) -> str:
        location = str(scene_state.get("location_name") or "the current space")
        return (
            f"You carry out the action in {location}. No major new shift breaks the scene immediately, "
            "but the surroundings remain visible and grounded around you."
        )

    def _extract_action_target(self, action: str) -> str:
        normalized = re.sub(r"\s+", " ", action.strip())
        lowered = normalized.lower()
        for token in (" at ", " the ", " to "):
            if token in lowered:
                parts = re.split(token, normalized, maxsplit=1, flags=re.IGNORECASE)
                candidate = parts[-1].strip(" .!?")
                if candidate and len(candidate) >= 3:
                    candidate = re.sub(r"\b(?:again|now|please)\b$", "", candidate, flags=re.IGNORECASE).strip(" ,.!?")
                    candidate = re.sub(r"^(?:the|a|an)\s+", "", candidate, flags=re.IGNORECASE)
                    return candidate
        words = [piece for piece in normalized.split() if piece]
        return " ".join(words[-3:]).strip(" .!?") if words else ""

    def _extract_dialogue_content(self, action: str) -> str:
        match = re.search(r"['\"]([^'\"]+)['\"]", action)
        if match:
            return match.group(1).strip()
        normalized = re.sub(r"\s+", " ", action.strip())
        lowered = normalized.lower()
        for prefix in ("say ", "ask ", "tell ", "shout ", "speak "):
            if lowered.startswith(prefix):
                return normalized[len(prefix) :].strip(" .!?")
        return ""

    def _resolve_scene_actor_target(self, action: str, scene_state: dict[str, Any]) -> dict[str, Any] | None:
        actors = [actor for actor in scene_state.get("scene_actors", []) if isinstance(actor, dict) and bool(actor.get("visible", True))]
        if not actors:
            return None
        if len(actors) == 1:
            actor = actors[0]
            print(f"[scene-actors] target_resolved={actor.get('actor_id', '')}")
            return actor
        lowered = action.lower()
        generic_refs = ("them", "the figure", "the stranger", "him", "her", "that person", "that figure")
        for actor in actors:
            labels = [
                str(actor.get("display_name", "")).lower(),
                str(actor.get("short_label", "")).lower(),
                *[str(tag).lower() for tag in actor.get("tags", []) if str(tag).strip()],
            ]
            if any(label and label in lowered for label in labels):
                print(f"[scene-actors] target_resolved={actor.get('actor_id', '')}")
                return actor
        if any(ref in lowered for ref in generic_refs):
            sorted_actors = sorted(
                actors,
                key=lambda actor: (int(actor.get("last_interaction_turn", -1)), int(actor.get("introduced_turn", -1)), str(actor.get("actor_id", ""))),
            )
            actor = sorted_actors[-1]
            print(f"[scene-actors] target_resolved={actor.get('actor_id', '')}")
            return actor
        sorted_actors = sorted(
            actors,
            key=lambda actor: (int(actor.get("last_interaction_turn", -1)), int(actor.get("introduced_turn", -1)), str(actor.get("actor_id", ""))),
        )
        actor = sorted_actors[-1]
        print(f"[scene-actors] target_resolved={actor.get('actor_id', '')}")
        return actor

    def _materialize_lightweight_npc(self, state: CampaignState, scene_state: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        linked_actor_id = str(actor.get("actor_id", ""))
        existing = next(
            (npc for npc in scene_state.get("lightweight_npcs", []) if isinstance(npc, dict) and str(npc.get("linked_actor_id", "")) == linked_actor_id),
            None,
        )
        if existing:
            return existing
        role_hint = str(actor.get("short_label") or actor.get("display_name") or "stranger").lower()
        personality_seed = self._infer_personality_seed(role_hint)
        tone_default = {
            "hostile": "sharp",
            "evasive": "guarded",
            "cautious": "reserved",
            "curious": "inquiring",
            "deferential": "respectful",
        }.get(personality_seed, "neutral")
        npc_id = f"npc_lite_{state.turn_count}_{linked_actor_id or 'scene'}"
        npc_record = {
            "npc_id": npc_id,
            "linked_actor_id": linked_actor_id,
            "display_name": actor.get("display_name", "figure"),
            "role_hint": role_hint,
            "tone_default": tone_default,
            "personality_seed": personality_seed,
            "attitude_to_player": "unknown",
            "willingness_to_talk": 1,
            "last_dialogue_turn": 0,
            "last_dialogue_summary": "",
        }
        scene_state.setdefault("lightweight_npcs", []).append(npc_record)
        print(f"[npc-lite] materialized id={npc_id} tone={tone_default}")
        return npc_record

    def _infer_personality_seed(self, role_hint: str) -> str:
        lowered = role_hint.lower()
        if "hostile" in lowered or "enemy" in lowered or "bandit" in lowered:
            return "hostile"
        if "guard" in lowered:
            return "deferential"
        if "merchant" in lowered:
            return "neutral"
        if "hooded" in lowered or "stranger" in lowered or "figure" in lowered:
            return "cautious"
        if "villager" in lowered or "fright" in lowered:
            return "evasive"
        return "neutral"

    def _is_concrete_scene_grounded_output(self, action: str, narrative: str, scene_state: dict[str, Any]) -> bool:
        text = re.sub(r"\s+", " ", narrative.strip().lower())
        if len(text) < 24:
            return False
        blocked_phrases = (
            "the action resolves immediately",
            "the immediate outcome is visible at the point of impact",
            "your movement changes position right away",
            "specific surface features and changes become immediately visible",
        )
        if any(phrase in text for phrase in blocked_phrases):
            return False
        if self._is_action_grounded(action, narrative):
            return True
        subtype = self._classify_gameplay_action_subtype(action)
        concrete_markers = (
            "wall",
            "stone",
            "floor",
            "room",
            "chamber",
            "torch",
            "dust",
            "arch",
            "view",
            "visible",
            "scene",
        )
        if subtype == "perception" and any(marker in text for marker in concrete_markers):
            return True
        scene_terms: list[str] = []
        for key in ("location_name", "scene_summary", "last_immediate_result"):
            value = str(scene_state.get(key, "")).strip().lower()
            if value:
                scene_terms.extend(re.findall(r"[a-z]{4,}", value))
        for key in ("damaged_objects", "altered_environment", "visible_entities", "recent_consequences"):
            for value in scene_state.get(key, []):
                scene_terms.extend(re.findall(r"[a-z]{4,}", str(value).lower()))
        return any(term in text for term in scene_terms[:20]) if scene_terms else False

    def get_last_prompt_debug_packet(self, campaign_id: str) -> dict[str, object]:
        return dict(self._last_prompt_debug_by_campaign.get(campaign_id, {}))

    def _build_model_history(self, state: CampaignState) -> list[ChatMessage]:
        history: list[ChatMessage] = []
        for turn in state.conversation_turns[-4:]:
            if turn.player_input:
                history.append(ChatMessage(role="user", content=turn.player_input))
            if turn.narrator_response:
                compact = re.sub(r"\s+", " ", turn.narrator_response.strip()).split(".")[0][:160].strip()
                history.append(ChatMessage(role="assistant", content=f"Outcome summary: {compact}"))
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
