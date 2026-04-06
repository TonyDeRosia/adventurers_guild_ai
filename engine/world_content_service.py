"""World content hooks sourced from structured data."""

from __future__ import annotations

from engine.content_repository import ContentRepository
from engine.entities import CampaignState


class WorldContentService:
    """Handles non-combat location pickups and quest turn-ins."""

    def __init__(self, content: ContentRepository) -> None:
        self.content = content

    def collect_location_items(self, state: CampaignState) -> list[str]:
        item_ids = self.content.location_items.get(state.current_location_id, [])
        messages: list[str] = []
        for item_id in item_ids:
            flag_key = f"items.collected.{state.current_location_id}.{item_id}"
            if state.world_flags.get(flag_key):
                continue
            state.world_flags[flag_key] = True
            pending = state.world_flags.setdefault("_pending_world_items", [])
            pending.append(item_id)
            messages.append(f"You find: {item_id}.")
        return messages

    def process_turnin(self, state: CampaignState, npc_id: str, has_item: callable) -> list[str]:
        rule = self.content.npc_turnins.get(npc_id)
        if not rule:
            return []
        quest = state.quests.get(rule.quest_id)
        if not quest or quest.status != "active":
            return []
        if not has_item(rule.required_item_id):
            return []
        state.world_flags[rule.completion_flag] = True
        quest.status = "completed"
        return [
            f"{state.npcs[npc_id].name} accepts {rule.required_item_id}.",
            f"Quest '{quest.title}' completed.",
        ]
