"""Data-driven NPC personality profile and evolution system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.content_registry import ContentRegistry
from engine.entities import CampaignState, NPC


@dataclass
class PersonalityEvaluation:
    tone: str
    willingness_to_share: int
    hostility: int
    friendliness: int
    quest_openness: int
    speech_style: str


class NPCPersonalitySystem:
    """Evaluates NPC behavior using profile + dynamic state + memories + context."""

    def __init__(self, content: ContentRegistry) -> None:
        self.content = content

    def initialize_npc(self, state: CampaignState, npc_id: str) -> None:
        npc = state.npcs[npc_id]
        profile = self.content.get_npc_profile(npc.profile_id or npc_id)
        if profile is None:
            return
        if not npc.profile_id:
            npc.profile_id = str(profile.get("id", npc_id))
        defaults = profile.get("state_defaults", {})
        for field, value in defaults.items():
            if hasattr(npc.dynamic_state, field):
                setattr(npc.dynamic_state, field, int(getattr(npc.dynamic_state, field) or value))
        if not npc.personality_archetype:
            npc.personality_archetype = str(profile.get("base_archetype", "") or "") or None
        if npc.personality_nodes is None:
            nodes = profile.get("personality_nodes", {})
            if isinstance(nodes, dict):
                npc.personality_nodes = NPC.PersonalityNodes(
                    role=str(nodes.get("role", "")),
                    temperament=str(nodes.get("temperament", "")),
                    morals=str(nodes.get("morals", "")),
                    social_style=str(nodes.get("social_style", "")),
                    fears=[str(v) for v in nodes.get("fears", [])],
                    desires=[str(v) for v in nodes.get("desires", [])],
                    loyalties=[str(v) for v in nodes.get("loyalties", [])],
                    secrets=[str(v) for v in nodes.get("secrets", [])],
                    aggression=str(nodes.get("aggression", "")),
                    speech_style=str(nodes.get("speech_style", profile.get("speech_style", "plain"))),
                    decision_bias=str(nodes.get("decision_bias", "")),
                    faction_alignment=str(nodes.get("faction_alignment", "")),
                )

    def record_memory(
        self,
        state: CampaignState,
        npc_id: str,
        event_type: str,
        summary: str,
        world_event_id: str | None = None,
        player_action: str | None = None,
        impact: dict[str, int] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        npc = state.npcs[npc_id]
        npc.memory_log.append(
            NPC.MemoryEntry(
                event_type=event_type,
                summary=summary,
                turn=state.turn_count,
                world_event_id=world_event_id,
                player_action=player_action,
                impact=impact or {},
                tags=tags or [],
            )
        )
        npc.memory_log = npc.memory_log[-30:]
        npc.dynamic_state.memory_tags = list(dict.fromkeys((npc.dynamic_state.memory_tags + (tags or []))[-12:]))

    def apply_state_delta(self, state: CampaignState, npc_id: str, delta: dict[str, int]) -> None:
        npc = state.npcs[npc_id]
        for field, change in delta.items():
            if not hasattr(npc.dynamic_state, field):
                continue
            current = int(getattr(npc.dynamic_state, field))
            setattr(npc.dynamic_state, field, max(-100, min(100, current + int(change))))

    def apply_event(self, state: CampaignState, npc_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        self.initialize_npc(state, npc_id)
        summary = payload.get("summary", event_type.replace("_", " "))
        self.record_memory(
            state,
            npc_id,
            event_type=event_type,
            summary=str(summary),
            world_event_id=payload.get("world_event_id"),
            player_action=payload.get("player_action"),
            impact=payload.get("impact"),
            tags=payload.get("tags") or [],
        )
        if payload.get("impact"):
            self.apply_state_delta(state, npc_id, payload["impact"])
        self._apply_evolution_rules(state, npc_id, event_type, payload)

    def evaluate(self, state: CampaignState, npc_id: str, scene: str) -> PersonalityEvaluation:
        self.initialize_npc(state, npc_id)
        npc = state.npcs[npc_id]
        profile = self.content.get_npc_profile(npc.profile_id or npc_id) or {}
        dynamic = npc.dynamic_state

        base_friendliness = int(profile.get("moral_tendencies", {}).get("compassion", 0))
        base_hostility = int(profile.get("moral_tendencies", {}).get("severity", 0))
        friendliness = base_friendliness + dynamic.trust_toward_player + dynamic.hope + dynamic.loyalty - dynamic.anger
        hostility = base_hostility + dynamic.fear_toward_player + dynamic.anger + dynamic.stress - dynamic.hope
        willingness = dynamic.trust_toward_player + dynamic.hope - dynamic.fear_toward_player - dynamic.stress
        quest_openness = dynamic.loyalty + dynamic.hope - dynamic.anger

        recent_betrayal = any(m.event_type == "player_betrayal" for m in npc.memory_log[-5:])
        if recent_betrayal:
            hostility += 8
            willingness -= 8

        tone = "guarded"
        if friendliness - hostility >= 8:
            tone = "warm"
        elif hostility - friendliness >= 8:
            tone = "cold"
        elif dynamic.stress >= 20:
            tone = "strained"

        if scene == "quest_offer" and quest_openness < -5:
            tone = "skeptical"

        speech_style = (
            npc.personality_nodes.speech_style
            if npc.personality_nodes and npc.personality_nodes.speech_style
            else str(profile.get("speech_style", "plain"))
        )
        npc.dynamic_state.current_mood = tone
        return PersonalityEvaluation(
            tone=tone,
            willingness_to_share=max(-100, min(100, willingness)),
            hostility=max(-100, min(100, hostility)),
            friendliness=max(-100, min(100, friendliness)),
            quest_openness=max(-100, min(100, quest_openness)),
            speech_style=speech_style,
        )

    def build_prompt_guidance(self, state: CampaignState) -> list[str]:
        guidance: list[str] = []
        for npc_id, npc in state.npcs.items():
            if npc.location_id != state.current_location_id:
                continue
            self.initialize_npc(state, npc_id)
            mood = npc.dynamic_state.current_mood or "neutral"
            memory_tags = ", ".join(npc.dynamic_state.memory_tags[-4:]) if npc.dynamic_state.memory_tags else "none"
            node_summary = self._node_summary(npc)
            guidance.append(
                f"{npc.name}: archetype={npc.personality_archetype or 'none'}; nodes={node_summary}; "
                f"state(trust={npc.dynamic_state.trust_toward_player}, fear={npc.dynamic_state.fear_toward_player}, "
                f"suspicion={npc.dynamic_state.suspicion}, anger={npc.dynamic_state.anger}, attraction={npc.dynamic_state.attraction}, mood={mood}); "
                f"recent_memory_tags={memory_tags}."
            )
        return guidance

    def _node_summary(self, npc: NPC) -> str:
        if npc.personality_nodes is None:
            return "fallback-freeform"
        nodes = npc.personality_nodes
        segments = [
            f"role={nodes.role or 'unspecified'}",
            f"temperament={nodes.temperament or 'unspecified'}",
            f"morals={nodes.morals or 'unspecified'}",
            f"social_style={nodes.social_style or 'unspecified'}",
            f"aggression={nodes.aggression or 'unspecified'}",
            f"speech_style={nodes.speech_style or 'plain'}",
            f"decision_bias={nodes.decision_bias or 'balanced'}",
            f"faction_alignment={nodes.faction_alignment or 'none'}",
            f"fears={','.join(nodes.fears) if nodes.fears else 'none'}",
            f"desires={','.join(nodes.desires) if nodes.desires else 'none'}",
            f"loyalties={','.join(nodes.loyalties) if nodes.loyalties else 'none'}",
            f"secrets={','.join(nodes.secrets[:2]) if nodes.secrets else 'none'}",
        ]
        return "; ".join(segments)

    def _apply_evolution_rules(
        self, state: CampaignState, npc_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        npc = state.npcs[npc_id]
        profile = self.content.get_npc_profile(npc.profile_id or npc_id)
        if profile is None:
            return
        for rule in profile.get("evolution_rules", []):
            rule_id = str(rule.get("id", ""))
            if not rule_id:
                continue
            if rule_id in npc.applied_evolution_rules and not rule.get("repeatable", False):
                continue
            if rule.get("event_type") != event_type:
                continue
            if not self._rule_conditions_met(state, npc, rule, payload):
                continue
            self.apply_state_delta(state, npc_id, rule.get("state_delta", {}))
            unlock = rule.get("unlock_behavior")
            if unlock and unlock not in npc.unlocked_behaviors:
                npc.unlocked_behaviors.append(unlock)
            note = rule.get("memory_note")
            if note:
                self.record_memory(state, npc_id, "evolution_rule", str(note), tags=["evolution"])
            npc.applied_evolution_rules.append(rule_id)

    def _rule_conditions_met(self, state: CampaignState, npc: NPC, rule: dict[str, Any], payload: dict[str, Any]) -> bool:
        conditions = rule.get("conditions", {})
        world_flags = conditions.get("required_world_flags", {})
        for key, value in world_flags.items():
            if state.world_flags.get(str(key)) is not bool(value):
                return False

        quest_status = conditions.get("quest_status", {})
        for quest_id, expected in quest_status.items():
            quest = state.quests.get(str(quest_id))
            if not quest or quest.status != expected:
                return False

        counts = conditions.get("memory_event_count", {})
        for event_type, minimum in counts.items():
            seen = sum(1 for entry in npc.memory_log if entry.event_type == event_type)
            if seen < int(minimum):
                return False

        payload_tags = set(payload.get("tags") or [])
        required_tags = set(conditions.get("required_tags", []))
        if required_tags and not required_tags.intersection(payload_tags):
            return False

        return True
