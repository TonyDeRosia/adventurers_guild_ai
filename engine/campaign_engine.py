"""Core campaign loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from engine.character_sheet import CharacterSheetService
from engine.entities import CampaignState
from engine.inventory import InventoryService
from memory.npc_memory import NPCMemoryTracker
from memory.quest_tracker import QuestTracker
from memory.world_state import WorldStateTracker
from models.base import NarrationModelAdapter
from prompts.renderer import PromptRenderer
from rules.combat import CombatEngine, Enemy


@dataclass
class TurnResult:
    narrative: str
    system_messages: list[str]
    should_exit: bool = False


class CampaignEngine:
    """Coordinates subsystems while keeping concerns separated."""

    def __init__(self, model: NarrationModelAdapter) -> None:
        self.model = model
        self.prompts = PromptRenderer()
        self.world = WorldStateTracker()
        self.quests = QuestTracker()
        self.npc_memory = NPCMemoryTracker()
        self.combat = CombatEngine()
        self.inventory = InventoryService()
        self.character_sheet = CharacterSheetService()

    def run_turn(self, state: CampaignState, action: str) -> TurnResult:
        state.turn_count += 1
        normalized = action.strip().lower()
        system_messages: list[str] = []

        if normalized in {"exit", "quit"}:
            return TurnResult(narrative="Your adventure pauses here.", system_messages=[], should_exit=True)

        if normalized == "look":
            system_messages.append(self.world.get_current_location_summary(state))
            if state.current_location_id == "moonfall_catacombs" and not state.world_flags.get("catacombs_cleared", False):
                if state.active_enemy_id is None:
                    state.active_enemy_id = "bone_warden"
                    state.active_enemy_hp = 14
                    system_messages.append("A Bone Warden rises from the dust. Combat has begun!")
                else:
                    system_messages.append(f"The Bone Warden blocks your path (HP {state.active_enemy_hp}).")

        elif normalized.startswith("move "):
            destination = normalized.split(" ", 1)[1]
            move_message = self.world.move_to_location(state, destination)
            system_messages.append(move_message)
            if state.current_location_id == "moonfall_catacombs" and not state.world_flags.get("catacombs_cleared", False):
                state.active_enemy_id = "bone_warden"
                state.active_enemy_hp = 14
                system_messages.append("You descend into the catacombs and disturb a Bone Warden!")

        elif normalized == "sheet":
            system_messages.append(self.character_sheet.summary(state.player))

        elif normalized.startswith("take "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.add_item(state.player, item))

        elif normalized.startswith("drop "):
            item = action.split(" ", 1)[1]
            system_messages.append(self.inventory.remove_item(state.player, item))

        elif normalized == "inventory":
            bag = ", ".join(state.player.inventory) if state.player.inventory else "Inventory is empty"
            system_messages.append(f"Inventory: {bag}")

        elif normalized == "quests":
            active = self.quests.list_active_quests(state)
            system_messages.append("Active quests: " + ("; ".join(active) if active else "none"))

        elif normalized.startswith("talk "):
            npc_id = normalized.split(" ", 1)[1]
            if npc_id in state.npcs:
                self.npc_memory.record_interaction(state, npc_id, f"Turn {state.turn_count}: {action}", delta=5)
                system_messages.append(self.npc_memory.describe_npc(state, npc_id))
                state.npcs[npc_id].relationships[state.player.id] = state.npcs[npc_id].disposition
                if npc_id == "elder_thorne":
                    quest = state.quests["q_catacomb_blight"]
                    if quest.status == "inactive":
                        quest.status = "active"
                        system_messages.append("Elder Thorne offers the quest 'Silence Beneath Moonfall'.")
                    elif quest.status == "completed":
                        system_messages.append("Elder Thorne thanks you again for saving Moonfall.")
                    else:
                        system_messages.append("Elder Thorne urges you to cleanse the catacombs.")
            else:
                system_messages.append(f"No NPC with id '{npc_id}' is present.")

        elif normalized.startswith("attack"):
            if state.active_enemy_id != "bone_warden" or state.active_enemy_hp is None or state.active_enemy_hp <= 0:
                system_messages.append("There is no active enemy to attack.")
                return self._finish_turn(state, action, system_messages)
            enemy = Enemy(name="Bone Warden", hp=state.active_enemy_hp, armor_class=12, attack_bonus=3, damage_die=6)
            result = self.combat.resolve_attack(
                attacker_name=state.player.name,
                attack_bonus=state.player.attack_bonus,
                defender_name=enemy.name,
                defender_armor_class=enemy.armor_class,
                defender_hp=state.active_enemy_hp,
            )
            state.active_enemy_hp = result.remaining_hp
            outcome = (
                f"Attack roll {result.raw_roll} (+bonus => {result.total_roll}) vs AC {enemy.armor_class}. "
                f"{'Hit' if result.hit else 'Miss'} for {result.damage} damage."
            )
            system_messages.append(outcome)
            if result.remaining_hp == 0:
                msg = self.character_sheet.grant_xp(state.player, 40)
                system_messages.append(f"Bone Warden defeated. {msg}")
                state.active_enemy_id = None
                state.world_flags["catacombs_cleared"] = True
                state.quests["q_catacomb_blight"].status = "completed"
                self.inventory.add_item(state.player, "Moonsigil Relic")
                system_messages.append("You recover the Moonsigil Relic from the chamber.")
            else:
                retaliation = self.combat.resolve_attack(
                    attacker_name=enemy.name,
                    attack_bonus=enemy.attack_bonus,
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
                        narrative="You fall in the catacombs. Your campaign ends here.",
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
            system_messages.append(
                f"Quest: {quest_status}. Elder Thorne relation: {relation}. "
                f"Active enemy HP: {enemy_hp}. Player HP: {state.player.hp}/{state.player.max_hp}."
            )

        elif normalized == "help":
            system_messages.append(
                "Commands: look, move <location_id>, talk <npc_id>, attack, rest, status, inventory, "
                "take <item>, drop <item>, quests, sheet, save, load, help, exit"
            )

        else:
            system_messages.append("Action noted.")

        return self._finish_turn(state, action, system_messages)

    def _finish_turn(self, state: CampaignState, action: str, system_messages: list[str]) -> TurnResult:
        for msg in system_messages:
            self.quests.add_event(state, msg)
        location_summary = self.world.get_current_location_summary(state)
        turn_prompt = self.prompts.build_turn_prompt(state, action, location_summary)
        system_prompt = self.prompts.build_system_prompt(state)
        narrative = self.model.generate(turn_prompt, system_prompt)
        return TurnResult(narrative=narrative, system_messages=system_messages)
