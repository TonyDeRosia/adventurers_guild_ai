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

    def add_event(self, state: CampaignState, message: str) -> None:
        state.event_log.append(message)
