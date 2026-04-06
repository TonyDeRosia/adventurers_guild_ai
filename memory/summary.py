"""Session summary generation and update flow."""

from __future__ import annotations

from engine.entities import CampaignState


class SummaryGenerator:
    """Generates compact structured campaign summaries for reuse."""

    IMPORTANT_ACTION_KEYWORDS = ("move", "talk", "attack", "quest", "defeat", "return", "completed", "save")

    def should_summarize(self, action: str, system_messages: list[str]) -> bool:
        lowered_action = action.lower()
        if lowered_action in {"save", "load"}:
            return True
        if any(token in lowered_action for token in self.IMPORTANT_ACTION_KEYWORDS):
            return True
        combined = " ".join(system_messages).lower()
        return any(token in combined for token in self.IMPORTANT_ACTION_KEYWORDS)

    def build_summary(self, state: CampaignState, action: str, system_messages: list[str]) -> str:
        active_quests = [quest.title for quest in state.quests.values() if quest.status == "active"]
        quest_part = ", ".join(active_quests[:2]) if active_quests else "none"
        recent = "; ".join(system_messages[:2]) if system_messages else "No major system update"
        return (
            f"Turn {state.turn_count} at {state.current_location_id}: action '{action}'. "
            f"Updates: {recent}. Active quests: {quest_part}."
        )
