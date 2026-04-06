"""Core campaign loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.character_sheet import CharacterSheetService
from engine.content_repository import ContentRepository
from engine.dialogue_service import DialogueService
from engine.entities import CampaignState
from engine.inventory import InventoryService
from engine.world_content_service import WorldContentService
from memory.npc_memory import NPCMemoryTracker
from memory.quest_tracker import QuestTracker
from memory.world_state import WorldStateTracker
from models.base import NarrationModelAdapter, ProviderBackedNarrationAdapter
from models.provider import NarrationRequest
from prompts.renderer import PromptRenderer
from rules.combat import CombatEngine


@dataclass
class TurnResult:
    narrative: str
    system_messages: list[str]
    should_exit: bool = False


class CampaignEngine:
    """Coordinates subsystems while keeping concerns separated."""

    def __init__(self, model: NarrationModelAdapter, data_dir: Path | None = None) -> None:
        self.model = model
        self.prompts = PromptRenderer()
        self.world = WorldStateTracker()
        self.quests = QuestTracker()
        self.npc_memory = NPCMemoryTracker()
        self.combat = CombatEngine()
        resolved_data_dir = data_dir or Path(__file__).resolve().parent.parent / "data"
        self.content = ContentRepository(resolved_data_dir)
        self.inventory = InventoryService(self.content)
        self.character_sheet = CharacterSheetService()
        self.dialogue = DialogueService(self.content, self.quests, self.npc_memory)
        self.world_content = WorldContentService(self.content)

    def run_turn(self, state: CampaignState, action: str) -> TurnResult:
        state.turn_count += 1
        normalized = action.strip().lower()
        system_messages: list[str] = []
        self.inventory.ensure_compatibility(state.player)

        if normalized in {"exit", "quit"}:
            return TurnResult(narrative="Your adventure pauses here.", system_messages=[], should_exit=True)

        if normalized == "look":
            system_messages.append(self.world.get_current_location_summary(state))
            system_messages.extend(self._maybe_start_location_encounter(state))
            system_messages.extend(self._collect_world_items(state))

        elif normalized.startswith("move "):
            destination = normalized.split(" ", 1)[1]
            move_message = self.world.move_to_location(state, destination)
            system_messages.append(move_message)
            if move_message.startswith("You travel"):
                system_messages.extend(self._maybe_start_location_encounter(state))
                system_messages.extend(self._collect_world_items(state))

        elif normalized == "sheet":
            system_messages.append(self.character_sheet.summary(state.player))

        elif normalized.startswith("take "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.add_item(state.player, item))

        elif normalized.startswith("drop "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.remove_item(state.player, item))

        elif normalized == "inventory":
            system_messages.append(self.inventory.list_inventory(state.player))

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
                self.npc_memory.record_interaction(state, npc_id, f"Turn {state.turn_count}: {action}", delta=1)
                state.npcs[npc_id].relationships[state.player.id] = state.npcs[npc_id].disposition
                turn_in_messages = self._attempt_turnin(state, npc_id)
                if turn_in_messages:
                    system_messages.extend(turn_in_messages)
                dialogue_view = self.dialogue.start_dialogue(state, npc_id)
                if dialogue_view:
                    system_messages.append(f"{state.npcs[npc_id].name}: {dialogue_view.npc_text}")
                    system_messages.extend(dialogue_view.choices)
                    system_messages.append("Choose with: choose <number>")
                else:
                    system_messages.append(self.npc_memory.describe_npc(state, npc_id))
            else:
                system_messages.append(f"No NPC with id '{npc_id}' is present.")

        elif normalized.startswith("choose "):
            if state.active_dialogue is None:
                system_messages.append("No active dialogue. Start with 'talk <npc_id>'.")
            else:
                token = normalized.split(" ", 1)[1].strip()
                if not token.isdigit():
                    system_messages.append("Choose a numeric option, e.g. 'choose 1'.")
                else:
                    effect_message, next_view = self.dialogue.choose(state, int(token))
                    if effect_message:
                        system_messages.append(effect_message)
                    self._claim_pending_rewards(state, system_messages)
                    if next_view:
                        system_messages.append(f"{state.npcs[state.active_dialogue.npc_id].name}: {next_view.npc_text}")
                        system_messages.extend(next_view.choices)
                        system_messages.append("Choose with: choose <number>")

        elif normalized.startswith("attack"):
            if not state.active_enemy_id or state.active_enemy_hp is None or state.active_enemy_hp <= 0:
                system_messages.append("There is no active enemy to attack.")
                return self._finish_turn(state, action, system_messages)

            enemy = self.content.enemies.get(state.active_enemy_id)
            if not enemy:
                system_messages.append(f"Unknown active enemy '{state.active_enemy_id}'.")
                return self._finish_turn(state, action, system_messages)

            attack_bonus = state.player.attack_bonus + self.inventory.get_attack_bonus_from_equipment(state.player)
            result = self.combat.resolve_attack(
                attacker_name=state.player.name,
                attack_bonus=attack_bonus,
                defender_name=enemy.name,
                defender_armor_class=enemy.armor,
                defender_hp=state.active_enemy_hp,
            )
            state.active_enemy_hp = result.remaining_hp
            system_messages.append(
                f"Attack roll {result.raw_roll} (+bonus => {result.total_roll}) vs AC {enemy.armor}. "
                f"{'Hit' if result.hit else 'Miss'} for {result.damage} damage."
            )
            if result.remaining_hp == 0:
                self._resolve_enemy_defeat(state, enemy.id, system_messages)
            else:
                retaliation = self.combat.resolve_attack(
                    attacker_name=enemy.name,
                    attack_bonus=enemy.attack,
                    defender_name=state.player.name,
                    defender_armor_class=state.player.armor_class,
                    defender_hp=state.player.hp,
                    damage_die=enemy.damage_die,
                )
                state.player.hp = retaliation.remaining_hp
                system_messages.append(
                    f"{enemy.name} counters with roll {retaliation.raw_roll} ({retaliation.total_roll} total): "
                    f"{'hit' if retaliation.hit else 'miss'}, {retaliation.damage} damage to you."
                )
                if state.player.hp == 0:
                    return TurnResult(
                        narrative="You fall in battle. Your campaign ends here.",
                        system_messages=system_messages,
                        should_exit=True,
                    )

        elif normalized.startswith("rest"):
            if state.current_location_id != "moonfall_town":
                system_messages.append("You can only safely rest in Moonfall Town.")
            else:
                state.player.hp = state.player.max_hp
                system_messages.append("You rest at the inn and recover to full health.")

        elif normalized == "status":
            first_npc_id = next(iter(state.npcs.keys()), "")
            relation = state.npcs[first_npc_id].relationships.get(state.player.id, 0) if first_npc_id else 0
            enemy_hp = state.active_enemy_hp if state.active_enemy_hp is not None else 0
            active_quests = ", ".join(q.id for q in state.quests.values() if q.status == "active") or "none"
            key_flags = ", ".join(f"{k}={v}" for k, v in sorted(state.world_flags.items()) if not k.startswith("_"))
            system_messages.append(
                f"Active quests: {active_quests}. First NPC relation: {relation}. "
                f"Active enemy HP: {enemy_hp}. Player HP: {state.player.hp}/{state.player.max_hp}. Flags: {key_flags}"
            )

        elif normalized == "help":
            system_messages.append(
                "Commands: look, move <location_id>, talk <npc_id>, choose <number>, attack, rest, status, "
                "inventory, use <item>, equip <item>, take <item>, drop <item>, quests, sheet, save, load, help, exit"
            )

        else:
            system_messages.append("Action noted.")

        return self._finish_turn(state, action, system_messages)

    def _maybe_start_location_encounter(self, state: CampaignState) -> list[str]:
        if state.active_enemy_id:
            enemy = self.content.enemies.get(state.active_enemy_id)
            hp = state.active_enemy_hp if state.active_enemy_hp is not None else 0
            return [f"{enemy.name if enemy else state.active_enemy_id} blocks your path (HP {hp})."]

        enemy_id = self.content.location_encounters.get(state.current_location_id)
        if not enemy_id:
            return []
        cleared_flag = f"encounter.cleared.{enemy_id}"
        if state.world_flags.get(cleared_flag):
            return []
        enemy = self.content.enemies.get(enemy_id)
        if not enemy:
            return []
        state.active_enemy_id = enemy_id
        state.active_enemy_hp = enemy.max_hp
        return [enemy.encounter_text]

    def _resolve_enemy_defeat(self, state: CampaignState, enemy_id: str, system_messages: list[str]) -> None:
        enemy = self.content.enemies[enemy_id]
        if enemy.reward.xp:
            msg = self.character_sheet.grant_xp(state.player, enemy.reward.xp)
            system_messages.append(f"{enemy.name} defeated. {msg}")
        for item_id in enemy.reward.item_ids:
            system_messages.append(self.inventory.add_item_by_id(state.player, item_id))
        for key, value in enemy.reward.set_flags.items():
            state.world_flags[key] = value
        state.active_enemy_id = None
        state.active_enemy_hp = None
        state.world_flags[f"encounter.cleared.{enemy_id}"] = True
        if state.world_flags.get("moonfall.charm_path_unlocked"):
            state.world_flags["moonfall.catacombs_resolved_style"] = "peaceful_attempt_then_battle"

    def _collect_world_items(self, state: CampaignState) -> list[str]:
        messages = self.world_content.collect_location_items(state)
        out: list[str] = []
        for msg in messages:
            out.append(msg)
        self._claim_pending_world_items(state, out)
        return out

    def _claim_pending_world_items(self, state: CampaignState, system_messages: list[str]) -> None:
        pending = state.world_flags.pop("_pending_world_items", [])
        for item_id in pending:
            system_messages.append(self.inventory.add_item_by_id(state.player, item_id))
        if state.current_location_id == "brindlewatch_outpost" and self.inventory.has_item(state.player, "sealed_supply_crate"):
            state.world_flags["brindlewatch.crate_found"] = True

    def _claim_pending_rewards(self, state: CampaignState, system_messages: list[str]) -> None:
        pending = state.world_flags.pop("_pending_dialogue_rewards", [])
        for item_id in pending:
            system_messages.append(self.inventory.add_item_by_id(state.player, item_id))

    def _attempt_turnin(self, state: CampaignState, npc_id: str) -> list[str]:
        turn_in_messages = self.world_content.process_turnin(
            state,
            npc_id,
            has_item=lambda item_id: self.inventory.has_item(state.player, item_id),
        )
        if turn_in_messages:
            rule = self.content.npc_turnins[npc_id]
            self.inventory.remove_item(state.player, rule.required_item_id)
        return turn_in_messages

    def _finish_turn(self, state: CampaignState, action: str, system_messages: list[str]) -> TurnResult:
        for msg in system_messages:
            self.quests.add_event(state, msg)
        location_summary = self.world.get_current_location_summary(state)
        prompt_bundle = self.prompts.build_prompt_bundle(state, location_summary)
        if isinstance(self.model, ProviderBackedNarrationAdapter):
            narrative = self.model.generate_from_parts(
                NarrationRequest(
                    system_tone=prompt_bundle.system_tone,
                    profile_tone=prompt_bundle.profile_tone,
                    scene_context=prompt_bundle.scene_context,
                    player_state_summary=prompt_bundle.player_state_summary,
                    action=action,
                )
            )
        else:
            narrative = self.model.generate(
                f"{prompt_bundle.profile_tone}\n{prompt_bundle.scene_context}\n{prompt_bundle.player_state_summary}",
                prompt_bundle.system_tone,
            )
        return TurnResult(narrative=narrative, system_messages=system_messages)
