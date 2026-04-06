"""Core campaign loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.character_sheet import CharacterSheetService
from engine.content_registry import ContentRegistry
from engine.dialogue_service import DialogueService
from engine.entities import CampaignState
from engine.inventory import InventoryService
from memory.npc_memory import NPCMemoryTracker
from memory.quest_tracker import QuestTracker
from memory.world_state import WorldStateTracker
from models.base import NarrationModelAdapter
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
        self.content = ContentRegistry(data_dir or Path("data"))
        self.inventory = InventoryService(self.content)
        self.character_sheet = CharacterSheetService()
        self.dialogue = DialogueService(self.content, self.quests, self.npc_memory)

    def run_turn(self, state: CampaignState, action: str) -> TurnResult:
        state.turn_count += 1
        for faction, baseline in self.content.faction_defaults().items():
            state.faction_reputation.setdefault(faction, baseline)
        self.quests.refresh_availability(state)
        normalized = action.strip().lower()
        system_messages: list[str] = []

        if normalized in {"exit", "quit"}:
            return TurnResult(narrative="Your adventure pauses here.", system_messages=[], should_exit=True)

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
                        should_exit=True,
                    )

        elif normalized.startswith("rest"):
            if state.current_location_id != "moonfall_town":
                system_messages.append("You can only safely rest in Moonfall Town.")
            else:
                state.player.hp = state.player.max_hp
                system_messages.append("You rest at the inn and recover to full health.")

        elif normalized == "status":
            quest_status = state.quests["q_catacomb_blight"].status
            relation = state.npcs["elder_thorne"].relationships.get(state.player.id, 0)
            enemy_hp = state.active_enemy_hp if state.active_enemy_hp is not None else 0
            trust = "yes" if state.world_flags.get("thorne_trusts_player", False) else "no"
            system_messages.append(
                f"Quest: {quest_status}. Elder Thorne relation: {relation}. "
                f"Trust flag: {trust}. Active enemy HP: {enemy_hp}. Player HP: {state.player.hp}/{state.player.max_hp}. "
                f"Rep town/guild/unknown: {state.faction_reputation.get('town', 0)}/"
                f"{state.faction_reputation.get('guild', 0)}/{state.faction_reputation.get('unknown', 0)}."
            )

        elif normalized == "help":
            system_messages.append(
                "Commands: look, move <location_id>, talk <npc_id>, choose <number>, attack, rest, status, "
                "inventory, use <item>, equip <item>, take <item>, drop <item>, quests, sheet, "
                "defend, ability, flee, save, load, help, exit"
            )

        else:
            system_messages.append("Action noted.")

        return self._finish_turn(state, action, system_messages)

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
        if npc_id == "elder_thorne" and state.quests["q_catacomb_blight"].status == "completed":
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
            if state.quests["q_moonlantern_oath"].status in {"active", "completed"}:
                state.player.inventory.remove("moonlantern")
                state.world_flags["moonlantern_returned"] = True
                self.quests.set_outcome(state, "q_moonlantern_oath", "item")
                state.npcs[npc_id].disposition += 6
                state.npcs[npc_id].relationships[state.player.id] = state.npcs[npc_id].disposition
                state.npcs[npc_id].relationship_tier = self.npc_memory.relationship_tier_for_score(state.npcs[npc_id].disposition)
                state.faction_reputation["town"] = state.faction_reputation.get("town", 0) + 2
                state.world_events.append("elira_moonlantern_returned")
                self.inventory.add_item(state.player, "rangers_charm")
                system_messages.append("You return the Moonlantern. Elira rewards you with a Ranger's Charm.")

        if npc_id == "elder_thorne" and "moonsigil_relic" in state.player.inventory:
            if state.quests["q_catacomb_blight"].status == "active":
                state.player.inventory.remove("moonsigil_relic")
                self.quests.set_outcome(state, "q_catacomb_blight", "item")
                state.world_flags["catacombs_cleared"] = True
                state.world_flags["catacombs_cleared_violently"] = False
                state.faction_reputation["guild"] = state.faction_reputation.get("guild", 0) + 2
                state.world_events.append("catacombs_stabilized_with_relic")
                system_messages.append("Thorne accepts the Moonsigil Relic as proof and seals the crypt entrance.")

    def _finish_turn(self, state: CampaignState, action: str, system_messages: list[str]) -> TurnResult:
        for msg in system_messages:
            self.quests.add_event(state, msg)
        location_summary = self.world.get_current_location_summary(state)
        turn_prompt = self.prompts.build_turn_prompt(state, action, location_summary)
        system_prompt = self.prompts.build_system_prompt(state)
        narrative = self.model.generate(turn_prompt, system_prompt)
        return TurnResult(narrative=narrative, system_messages=system_messages)

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
        self.quests.set_outcome(state, "q_catacomb_blight", outcome)
        state.faction_reputation["guild"] = state.faction_reputation.get("guild", 0) + 3
        state.faction_reputation["town"] = state.faction_reputation.get("town", 0) + 2
        state.world_events.append(f"catacombs_cleared_{outcome}")
        state.world_flags["catacombs_echo_silenced"] = True
        for reward_item in enemy.reward.items:
            self.inventory.add_item(state.player, reward_item)
            system_messages.append(f"You recover {reward_item.replace('_', ' ').title()} from the chamber.")
        if state.quests["q_moonlantern_oath"].status == "active" and "moonlantern" not in state.player.inventory:
            self.inventory.add_item(state.player, "moonlantern")
            system_messages.append("Among the bones, you also find Elira's missing Moonlantern.")
