"""Data-driven NPC dialogue with branching choices and effects."""

from __future__ import annotations

from dataclasses import dataclass

from engine.content_repository import ContentRepository, DialogueChoice, DialogueNode
from engine.entities import CampaignState, DialogueState
from memory.npc_memory import NPCMemoryTracker
from memory.quest_tracker import QuestTracker


@dataclass
class DialogueView:
    npc_text: str
    choices: list[str]


class DialogueService:
    """Handles dialogue state transitions and side-effects."""

    def __init__(
        self,
        content: ContentRepository,
        quests: QuestTracker,
        npc_memory: NPCMemoryTracker,
    ) -> None:
        self.content = content
        self.quests = quests
        self.npc_memory = npc_memory

    def start_dialogue(self, state: CampaignState, npc_id: str) -> DialogueView | None:
        tree = self.content.dialogues.get(npc_id)
        if not tree:
            return None

        start_node = tree.start_node
        if npc_id == "elder_thorne" and state.quests.get("q_catacomb_blight"):
            if state.quests["q_catacomb_blight"].status == "completed":
                start_node = "after_completion"
        if npc_id == "captain_mirel" and state.quests.get("q_supply_line"):
            if state.quests["q_supply_line"].status == "completed":
                start_node = "after_return"

        state.active_dialogue = DialogueState(npc_id=npc_id, node_id=start_node)
        return self._build_view(npc_id, start_node)

    def choose(self, state: CampaignState, index: int):
        if not state.active_dialogue:
            return "No active dialogue. Start one with 'talk <npc_id>'.", None

        npc_id = state.active_dialogue.npc_id
        node_id = state.active_dialogue.node_id
        tree = self.content.dialogues.get(npc_id)
        if not tree:
            state.active_dialogue = None
            return "Dialogue data missing.", None
        node = tree.nodes.get(node_id)
        if not node:
            state.active_dialogue = None
            return "Dialogue node missing.", None

        if index < 1 or index > len(node.choices):
            return f"Choose a number between 1 and {len(node.choices)}.", self._build_view(npc_id, node_id)

        choice = node.choices[index - 1]
        effects_messages = self._apply_effects(state, npc_id, choice)

        next_node = choice.next_node
        if not next_node:
            state.active_dialogue = None
            return "Dialogue closed." + (" " + " ".join(effects_messages) if effects_messages else ""), None

        state.active_dialogue = DialogueState(npc_id=npc_id, node_id=next_node)
        next_view = self._build_view(npc_id, next_node)
        return " ".join(effects_messages), next_view

    def _apply_effects(self, state: CampaignState, npc_id: str, choice: DialogueChoice) -> list[str]:
        effects = choice.effects
        messages: list[str] = []
        if not effects:
            return messages

        relationship_delta = int(effects.get("relationship_delta", 0))
        if relationship_delta:
            self.npc_memory.record_interaction(
                state,
                npc_id,
                f"Dialogue choice: {choice.id}",
                delta=relationship_delta,
            )
            state.npcs[npc_id].relationships[state.player.id] = state.npcs[npc_id].disposition
            messages.append(f"Relationship with {state.npcs[npc_id].name} changed by {relationship_delta}.")

        quest_updates = effects.get("quest_updates", {})
        for quest_id, status in quest_updates.items():
            self.quests.update_quest_status(state, quest_id, status)
            messages.append(f"Quest '{quest_id}' set to {status}.")

        set_flags = effects.get("set_flags", {})
        for key, value in set_flags.items():
            state.world_flags[key] = value
            messages.append(f"Flag '{key}' set to {value}.")

        give_items = effects.get("give_items", [])
        if give_items:
            state.world_flags.setdefault("_pending_dialogue_rewards", [])
            pending = state.world_flags["_pending_dialogue_rewards"]
            for item_id in give_items:
                pending.append(item_id)
                messages.append(f"Received item reward: {item_id}.")

        return messages

    def _build_view(self, npc_id: str, node_id: str) -> DialogueView:
        tree = self.content.dialogues[npc_id]
        node: DialogueNode = tree.nodes[node_id]
        choices = [f"{idx}) {choice.text}" for idx, choice in enumerate(node.choices, start=1)]
        return DialogueView(npc_text=node.npc_text, choices=choices)
