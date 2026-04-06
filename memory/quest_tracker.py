"""Quest and event tracking subsystem."""

from __future__ import annotations

from engine.entities import CampaignState


class QuestTracker:
    """Provides quest lookup, update, and event logging methods."""

    def list_active_quests(self, state: CampaignState) -> list[str]:
        items = []
        for quest in state.quests.values():
            if quest.status == "active":
                items.append(f"{quest.id}: {quest.title} - {quest.description}")
        return items

    def update_quest_status(self, state: CampaignState, quest_id: str, status: str) -> None:
        quest = state.quests.get(quest_id)
        if not quest:
            raise ValueError(f"Quest '{quest_id}' not found")
        quest.status = status
        state.event_log.append(f"Quest '{quest.title}' set to {status}.")

    def set_outcome(self, state: CampaignState, quest_id: str, outcome: str) -> None:
        quest = state.quests.get(quest_id)
        if not quest:
            raise ValueError(f"Quest '{quest_id}' not found")
        quest.status = "completed"
        state.quest_outcomes[quest_id] = outcome
        state.event_log.append(f"Quest '{quest.title}' completed via {outcome}.")

    def refresh_availability(self, state: CampaignState) -> None:
        for quest in state.quests.values():
            if quest.status == "completed":
                continue
            availability = quest.availability or {}
            if not availability:
                continue

            reputation_reqs = availability.get("faction_reputation", {})
            relation_reqs = availability.get("npc_relationship_tiers", {})

            rep_ok = all(state.faction_reputation.get(faction, 0) >= int(minimum) for faction, minimum in reputation_reqs.items())
            relation_ok = all(
                state.npcs.get(npc_id) and state.npcs[npc_id].relationship_tier in allowed_tiers
                for npc_id, allowed_tiers in relation_reqs.items()
            )
            available_now = rep_ok and relation_ok

            if available_now and quest.status == "locked":
                quest.status = "inactive"
            elif not available_now and quest.status in {"inactive", "active"}:
                quest.status = "locked"

    def add_event(self, state: CampaignState, message: str) -> None:
        state.event_log.append(message)
