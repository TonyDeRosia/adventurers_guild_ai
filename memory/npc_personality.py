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
        if npc.personality_profile is None:
            npc.personality_profile = self.generate_profile(
                npc_name=npc.name,
                role_hint=(npc.personality_nodes.role if npc.personality_nodes else "") or npc.personality_archetype or "",
                temperament_hint=npc.personality_nodes.temperament if npc.personality_nodes else "",
                social_hint=npc.personality_nodes.social_style if npc.personality_nodes else "",
                speech_hint=npc.personality_nodes.speech_style if npc.personality_nodes else "",
            )

    def ensure_scene_profiles(self, state: CampaignState, scene_state: dict[str, Any]) -> None:
        for npc_id, npc in state.npcs.items():
            if npc.location_id == state.current_location_id:
                self.initialize_npc(state, npc_id)
        for lite in scene_state.get("lightweight_npcs", []):
            if not isinstance(lite, dict):
                continue
            if str(lite.get("location_id", state.current_location_id)) != state.current_location_id:
                continue
            self.ensure_lightweight_profile(lite)

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
        self._apply_profile_event_shift(state, npc_id, event_type)
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
            profile = npc.personality_profile or self.generate_profile(npc_name=npc.name)
            player_stance = self._describe_player_stance(npc)
            behavior_note = self._build_behavior_note(profile, player_stance)
            guidance.append(
                f"{npc.name}: {profile.archetype}; {profile.baseline_temperament}, {profile.social_style}, "
                f"{profile.confidence_fear_tendency}, {profile.moral_leaning}. Speaks in a {profile.conversational_tone} register. "
                f"Driven by {profile.motivations}. Emotional baseline: {profile.emotional_baseline}. "
                f"Under stress: {profile.stress_response}. In conflict: {profile.conflict_response}. "
                f"Power/threat/kindness/disrespect: {profile.reaction_to_power}; {profile.reaction_to_threat}; "
                f"{profile.reaction_to_kindness}; {profile.reaction_to_disrespect}. "
                f"Toward player: {player_stance}. Current mood: {mood}. Behavioral note: {behavior_note}. Memory cues: {memory_tags}."
            )
        return guidance

    def build_lightweight_prompt_guidance(self, scene_state: dict[str, Any], current_location_id: str) -> list[str]:
        guidance: list[str] = []
        for npc in scene_state.get("lightweight_npcs", []):
            if not isinstance(npc, dict):
                continue
            if str(npc.get("location_id", current_location_id)) != current_location_id:
                continue
            profile = self.ensure_lightweight_profile(npc)
            attitude = str(npc.get("attitude_to_player", "unknown")).strip() or "unknown"
            behavior_note = self._build_behavior_note_dict(profile, attitude)
            guidance.append(
                f"{npc.get('display_name', 'Unknown')}: {profile['archetype']}; {profile['baseline_temperament']}, {profile['social_style']}, "
                f"{profile['confidence_fear_tendency']}, {profile['moral_leaning']}. Voice: {profile['conversational_tone']}. "
                f"Motivation: {profile['motivations']}. Emotional baseline: {profile['emotional_baseline']}. "
                f"Stress/conflict: {profile['stress_response']}; {profile['conflict_response']}. "
                f"Power/threat/kindness/disrespect: {profile['reaction_to_power']}; {profile['reaction_to_threat']}; "
                f"{profile['reaction_to_kindness']}; {profile['reaction_to_disrespect']}. "
                f"Stance toward player: {attitude}. Behavioral note: {behavior_note}."
            )
        return guidance

    def ensure_lightweight_profile(self, npc_record: dict[str, Any]) -> dict[str, str]:
        existing = npc_record.get("personality_profile")
        if isinstance(existing, dict) and str(existing.get("baseline_temperament", "")).strip():
            return {k: str(v) for k, v in existing.items()}
        generated = self.generate_profile(
            npc_name=str(npc_record.get("display_name", "Unknown")),
            role_hint=str(npc_record.get("role_hint", "")),
            temperament_hint=str(npc_record.get("tone_default", "")),
            social_hint=str(npc_record.get("personality_seed", "")),
        )
        profile = {
            "identity_label": generated.identity_label,
            "archetype": generated.archetype,
            "baseline_temperament": generated.baseline_temperament,
            "emotional_baseline": generated.emotional_baseline,
            "social_style": generated.social_style,
            "confidence_fear_tendency": generated.confidence_fear_tendency,
            "moral_leaning": generated.moral_leaning,
            "motivations": generated.motivations,
            "conversational_tone": generated.conversational_tone,
            "stress_response": generated.stress_response,
            "conflict_response": generated.conflict_response,
            "reaction_to_power": generated.reaction_to_power,
            "reaction_to_threat": generated.reaction_to_threat,
            "reaction_to_kindness": generated.reaction_to_kindness,
            "reaction_to_disrespect": generated.reaction_to_disrespect,
        }
        npc_record["personality_profile"] = profile
        return profile

    def generate_profile(
        self,
        *,
        npc_name: str,
        role_hint: str = "",
        temperament_hint: str = "",
        social_hint: str = "",
        speech_hint: str = "",
    ) -> NPC.PersonalityProfile:
        role = role_hint.lower()
        archetype = role_hint.strip() or "unknown local actor"
        baseline_temperament = temperament_hint.strip() or "guarded"
        if "guard" in role:
            baseline_temperament = "disciplined and alert"
        elif "merchant" in role:
            baseline_temperament = "pragmatic and socially adaptive"
        elif "elder" in role:
            baseline_temperament = "measured and tradition-minded"
        elif "stranger" in role or "figure" in role:
            baseline_temperament = "watchful and hard to read"
        social_style = social_hint.strip() or ("formal" if "guard" in role or "elder" in role else "measured")
        emotional_baseline = "contained but attentive"
        confidence_fear_tendency = "steady confidence"
        if "cautious" in baseline_temperament or "watchful" in baseline_temperament:
            confidence_fear_tendency = "leans cautious under uncertainty"
            emotional_baseline = "guarded and vigilant"
        moral_leaning = "duty-first" if "guard" in role else "situational but not needlessly cruel"
        motivations = "maintain local stability and protect personal interests"
        if "merchant" in role:
            motivations = "secure profitable outcomes while avoiding unnecessary risk"
            emotional_baseline = "pleasant on the surface, calculating underneath"
        elif "stranger" in role or "figure" in role:
            motivations = "protect their secrets and assess who can be trusted"
            emotional_baseline = "cool restraint masking active suspicion"
        conversational_tone = speech_hint.strip() or ("formal and concise" if "guard" in role else "brief, deliberate")
        stress_response = "tightens language and watches for leverage"
        conflict_response = "tests motives, then chooses de-escalation or force based on perceived threat"
        reaction_to_power = "respects clear authority but resists humiliation or arbitrary control"
        reaction_to_threat = "narrows choices quickly and either hardens or withdraws based on advantage"
        reaction_to_kindness = "acknowledges goodwill cautiously, then opens up in increments"
        reaction_to_disrespect = "stiffens posture and becomes sharper or colder before deciding next move"
        return NPC.PersonalityProfile(
            identity_label=npc_name.strip() or "Unknown",
            archetype=archetype,
            baseline_temperament=baseline_temperament,
            emotional_baseline=emotional_baseline,
            social_style=social_style,
            confidence_fear_tendency=confidence_fear_tendency,
            moral_leaning=moral_leaning,
            motivations=motivations,
            conversational_tone=conversational_tone,
            stress_response=stress_response,
            conflict_response=conflict_response,
            reaction_to_power=reaction_to_power,
            reaction_to_threat=reaction_to_threat,
            reaction_to_kindness=reaction_to_kindness,
            reaction_to_disrespect=reaction_to_disrespect,
        )

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

    def _describe_player_stance(self, npc: NPC) -> str:
        trust = int(npc.dynamic_state.trust_toward_player)
        fear = int(npc.dynamic_state.fear_toward_player)
        anger = int(npc.dynamic_state.anger)
        if trust - anger >= 10:
            return "cautiously supportive"
        if anger - trust >= 12:
            return "resentful and defensive"
        if fear >= 15:
            return "wary and risk-averse"
        return "evaluating and undecided"

    def _apply_profile_event_shift(self, state: CampaignState, npc_id: str, event_type: str) -> None:
        npc = state.npcs[npc_id]
        if npc.personality_profile is None:
            return
        profile = npc.personality_profile
        recent = npc.memory_log[-8:]
        kindness_count = sum(1 for entry in recent if entry.event_type == "player_kindness")
        betrayal_count = sum(1 for entry in recent if entry.event_type == "player_betrayal")
        fear_count = sum(1 for entry in recent if entry.event_type in {"player_threat", "player_betrayal"})
        victory_count = sum(1 for entry in recent if entry.event_type in {"player_defeat", "npc_victory"})

        if kindness_count >= 3:
            profile.social_style = self._bounded_shift(
                profile.social_style,
                target="more cooperative and less defensive",
                marker="cooperative",
            )
            profile.reaction_to_kindness = self._bounded_shift(
                profile.reaction_to_kindness,
                target="responds with cautious warmth while still checking intent",
                marker="cautious warmth",
            )
        elif betrayal_count >= 2:
            profile.social_style = self._bounded_shift(
                profile.social_style,
                target="more guarded and suspicious",
                marker="guarded",
            )
            profile.conflict_response = self._bounded_shift(
                profile.conflict_response,
                target="leans on contingencies and deception checks before commitment",
                marker="contingencies",
            )
        if fear_count >= 2:
            profile.confidence_fear_tendency = self._bounded_shift(
                profile.confidence_fear_tendency,
                target="more risk-averse when pressure spikes",
                marker="risk-averse",
            )
            profile.stress_response = self._bounded_shift(
                profile.stress_response,
                target="withdraws for leverage, scans exits, and uses clipped language",
                marker="scans exits",
            )
        elif victory_count >= 2:
            profile.confidence_fear_tendency = self._bounded_shift(
                profile.confidence_fear_tendency,
                target="confidence rising, occasionally bordering on pride",
                marker="rising",
            )
        if event_type == "player_kindness":
            profile.conversational_tone = self._bounded_shift(
                profile.conversational_tone,
                target="careful but warmer",
                marker="warmer",
            )

    def _bounded_shift(self, current: str, *, target: str, marker: str) -> str:
        base = (current or "").strip()
        if marker in base.lower():
            return base
        if not base:
            return target
        return f"{base}; now slightly {target}"

    def _build_behavior_note(self, profile: NPC.PersonalityProfile, player_stance: str) -> str:
        return (
            "Actions and body language should reflect this temperament, with hesitation/escalation paced by stress and threat. "
            f"Trust behavior should track the current player stance ({player_stance}) rather than flipping abruptly."
        )

    def _build_behavior_note_dict(self, profile: dict[str, str], player_stance: str) -> str:
        return (
            "Use the profile to guide reactions, posture, and escalation pace. "
            f"Let trust or suspicion shift gradually from the current stance ({player_stance})."
        )

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
