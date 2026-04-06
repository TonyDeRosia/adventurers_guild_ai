"""Dialogue tree runner with stateful choice effects."""

from __future__ import annotations

from dataclasses import dataclass

from engine.content_registry import ContentRegistry, DialogueNode, DialogueOption
from engine.entities import CampaignState
from memory.npc_memory import NPCMemoryTracker
from memory.quest_tracker import QuestTracker


@dataclass
class DialogueOutput:
    text: str
    options: list[str]
    completed: bool


class DialogueService:
    def __init__(self, content: ContentRegistry, quests: QuestTracker, npcs: NPCMemoryTracker) -> None:
        self.content = content
        self.quests = quests
        self.npcs = npcs

    def start_dialogue(self, state: CampaignState, npc_id: str) -> DialogueOutput | None:
        tree = self.content.get_dialogue(npc_id)
        if tree is None:
            return None
        state.active_dialogue_npc_id = npc_id
        state.active_dialogue_node_id = tree.start_node
        node = tree.nodes[tree.start_node]
        return self._render_node(node)

    def choose_option(self, state: CampaignState, option_number: int) -> DialogueOutput:
        npc_id = state.active_dialogue_npc_id
        node_id = state.active_dialogue_node_id
        if not npc_id or not node_id:
            return DialogueOutput("No active dialogue.", [], True)

        tree = self.content.get_dialogue(npc_id)
        if tree is None:
            state.active_dialogue_npc_id = None
            state.active_dialogue_node_id = None
            return DialogueOutput("Dialogue data missing.", [], True)

        node = tree.nodes[node_id]
        if option_number < 1 or option_number > len(node.options):
            return DialogueOutput("Invalid choice number.", self._option_lines(node), False)

        chosen = node.options[option_number - 1]
        self._apply_effects(state, npc_id, chosen)

        if not chosen.next_node:
            state.active_dialogue_npc_id = None
            state.active_dialogue_node_id = None
            return DialogueOutput("The conversation ends.", [], True)

        next_node = tree.nodes[chosen.next_node]
        state.active_dialogue_node_id = chosen.next_node
        if not next_node.options:
            state.active_dialogue_npc_id = None
            state.active_dialogue_node_id = None
            return DialogueOutput(next_node.text, [], True)
        return self._render_node(next_node)

    def _apply_effects(self, state: CampaignState, npc_id: str, option: DialogueOption) -> None:
        effects = option.effects
        for quest_update in effects.get("quest_updates", []):
            self.quests.update_quest_status(state, quest_update["quest_id"], quest_update["status"])

        delta = effects.get("relationship_delta", 0)
        if delta:
            self.npcs.record_interaction(state, npc_id, f"Dialogue choice: {option.id}", delta=delta)
            npc = state.npcs[npc_id]
            npc.relationships[state.player.id] = npc.disposition

        for key, value in effects.get("set_flags", {}).items():
            state.world_flags[key] = bool(value)

    def _render_node(self, node: DialogueNode) -> DialogueOutput:
        return DialogueOutput(node.text, self._option_lines(node), False)

    def _option_lines(self, node: DialogueNode) -> list[str]:
        return [f"{idx}) {option.text}" for idx, option in enumerate(node.options, start=1)]
