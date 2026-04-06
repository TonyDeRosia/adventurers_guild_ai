"""Dialogue tree runner with stateful choice effects."""

from __future__ import annotations

from dataclasses import dataclass

from engine.content_registry import ContentRegistry, DialogueNode, DialogueOption
from engine.entities import CampaignState
from memory.npc_memory import NPCMemoryTracker
from memory.npc_personality import NPCPersonalitySystem
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
        self.personality = NPCPersonalitySystem(content)

    def start_dialogue(self, state: CampaignState, npc_id: str) -> DialogueOutput | None:
        tree = self.content.get_dialogue(npc_id)
        if tree is None:
            return None
        state.active_dialogue_npc_id = npc_id
        state.active_dialogue_node_id = tree.start_node
        self.personality.apply_event(
            state,
            npc_id,
            event_type="dialogue_started",
            payload={"summary": f"Started dialogue with {npc_id}", "player_action": "talk"},
        )
        node = tree.nodes[tree.start_node]
        return self._render_node(state, npc_id, node)

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
        available_options = self._available_options(state, npc_id, node)
        if option_number < 1 or option_number > len(available_options):
            return DialogueOutput("Invalid choice number.", self._option_lines(available_options), False)

        chosen = available_options[option_number - 1]
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
        return self._render_node(state, npc_id, next_node)

    def _apply_effects(self, state: CampaignState, npc_id: str, option: DialogueOption) -> None:
        effects = option.effects
        for quest_update in effects.get("quest_updates", []):
            self.quests.update_quest_status(state, quest_update["quest_id"], quest_update["status"])

        delta = effects.get("relationship_delta", 0)
        if delta:
            self.npcs.record_interaction(state, npc_id, f"Dialogue choice: {option.id}", delta=delta)
            npc = state.npcs[npc_id]
            npc.relationships[state.player.id] = npc.disposition
            self.personality.apply_state_delta(
                state,
                npc_id,
                {
                    "trust_toward_player": delta,
                    "loyalty": int(delta / 2),
                    "anger": -1 if delta > 0 else 2,
                },
            )

        for faction, rep_delta in effects.get("reputation_delta", {}).items():
            state.faction_reputation[faction] = state.faction_reputation.get(faction, 0) + int(rep_delta)

        for key, value in effects.get("set_flags", {}).items():
            state.world_flags[key] = bool(value)

        if effects.get("npc_state_delta"):
            self.personality.apply_state_delta(state, npc_id, effects["npc_state_delta"])
        if effects.get("personality_event"):
            self.personality.apply_event(
                state,
                npc_id,
                event_type=str(effects["personality_event"]),
                payload={
                    "summary": f"Dialogue effect {option.id}",
                    "player_action": option.text,
                    "tags": effects.get("personality_tags", []),
                },
            )

    def _render_node(self, state: CampaignState, npc_id: str, node: DialogueNode) -> DialogueOutput:
        options = self._available_options(state, npc_id, node)
        evaluation = self.personality.evaluate(state, npc_id, scene="quest_offer" if "quest" in node.text.lower() else "dialogue")
        styled_text = f"[{evaluation.tone}/{evaluation.speech_style}] {node.text}"
        if not options:
            return DialogueOutput(styled_text, [], True)
        return DialogueOutput(styled_text, self._option_lines(options), False)

    def _option_lines(self, options: list[DialogueOption]) -> list[str]:
        return [f"{idx}) {option.text}" for idx, option in enumerate(options, start=1)]

    def _available_options(self, state: CampaignState, npc_id: str, node: DialogueNode) -> list[DialogueOption]:
        return [option for option in node.options if self._conditions_met(state, npc_id, option.conditions)]

    def _conditions_met(self, state: CampaignState, npc_id: str, conditions: dict[str, object]) -> bool:
        if not conditions:
            return True

        rep_min = conditions.get("faction_reputation_min", {})
        if isinstance(rep_min, dict):
            for faction, minimum in rep_min.items():
                if state.faction_reputation.get(str(faction), 0) < int(minimum):
                    return False

        required_tiers = conditions.get("npc_relationship_tiers")
        if isinstance(required_tiers, list) and required_tiers:
            npc = state.npcs.get(npc_id)
            if not npc or npc.relationship_tier not in required_tiers:
                return False

        required_flags = conditions.get("required_flags", {})
        if isinstance(required_flags, dict):
            for key, value in required_flags.items():
                if state.world_flags.get(str(key)) is not bool(value):
                    return False

        state_min = conditions.get("npc_state_min", {})
        if isinstance(state_min, dict):
            npc = state.npcs.get(npc_id)
            if not npc:
                return False
            for field, minimum in state_min.items():
                if not hasattr(npc.dynamic_state, field):
                    return False
                if int(getattr(npc.dynamic_state, field)) < int(minimum):
                    return False

        state_max = conditions.get("npc_state_max", {})
        if isinstance(state_max, dict):
            npc = state.npcs.get(npc_id)
            if not npc:
                return False
            for field, maximum in state_max.items():
                if not hasattr(npc.dynamic_state, field):
                    return False
                if int(getattr(npc.dynamic_state, field)) > int(maximum):
                    return False

        required_behaviors = conditions.get("required_behaviors", [])
        if isinstance(required_behaviors, list) and required_behaviors:
            npc = state.npcs.get(npc_id)
            if not npc:
                return False
            if not all(behavior in npc.unlocked_behaviors for behavior in required_behaviors):
                return False
        return True
