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

        elif normalized.startswith("move "):
            destination = normalized.split(" ", 1)[1]
            system_messages.append(self.world.move_to_location(state, destination))

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
            else:
                system_messages.append(f"No NPC with id '{npc_id}' is present.")

        elif normalized.startswith("attack"):
            enemy = Enemy(name="Goblin Raider", hp=10, armor_class=11, attack_bonus=2)
            result = self.combat.resolve_attack(
                attacker_name=state.player.name,
                attack_bonus=state.player.attack_bonus,
                defender_name=enemy.name,
                defender_armor_class=enemy.armor_class,
                defender_hp=enemy.hp,
            )
            outcome = (
                f"Attack roll {result.raw_roll} (+bonus => {result.total_roll}) vs AC {enemy.armor_class}. "
                f"{'Hit' if result.hit else 'Miss'} for {result.damage} damage."
            )
            system_messages.append(outcome)
            if result.remaining_hp == 0 and result.hit:
                msg = self.character_sheet.grant_xp(state.player, 25)
                system_messages.append(f"Enemy defeated. {msg}")

        elif normalized == "help":
            system_messages.append(
                "Commands: look, move <location_id>, talk <npc_id>, attack, inventory, "
                "take <item>, drop <item>, quests, sheet, save, load, help, exit"
            )

        else:
            system_messages.append("Action noted.")

        for msg in system_messages:
            self.quests.add_event(state, msg)

        location_summary = self.world.get_current_location_summary(state)
        turn_prompt = self.prompts.build_turn_prompt(state, action, location_summary)
        system_prompt = self.prompts.build_system_prompt(state)
        narrative = self.model.generate(turn_prompt, system_prompt)

        return TurnResult(narrative=narrative, system_messages=system_messages)
