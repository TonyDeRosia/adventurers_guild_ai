"""NPC memory and relationship tracking subsystem."""

from __future__ import annotations

from engine.entities import CampaignState


class NPCMemoryTracker:
    """Tracks NPC notes and disposition changes over time."""

    def record_interaction(self, state: CampaignState, npc_id: str, note: str, delta: int = 0) -> None:
        npc = state.npcs.get(npc_id)
        if not npc:
            raise ValueError(f"NPC '{npc_id}' not found")

        npc.notes.append(note)
        npc.disposition = max(-100, min(100, npc.disposition + delta))
        npc.relationship_tier = self.relationship_tier_for_score(npc.disposition)

    def describe_npc(self, state: CampaignState, npc_id: str) -> str:
        npc = state.npcs.get(npc_id)
        if not npc:
            raise ValueError(f"NPC '{npc_id}' not found")

        mood = self.relationship_tier_for_score(npc.disposition)

        latest_note = npc.notes[-1] if npc.notes else "No recent interactions"
        return f"{npc.name} appears {mood}. Latest memory: {latest_note}."

    @staticmethod
    def relationship_tier_for_score(score: int) -> str:
        if score >= 60:
            return "loyal"
        if score >= 20:
            return "friendly"
        if score <= -20:
            return "hostile"
        return "neutral"
