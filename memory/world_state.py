"""World and location tracking subsystem."""

from __future__ import annotations

from engine.entities import CampaignState


class WorldStateTracker:
    """Handles location movement and world flag changes."""

    def get_current_location_summary(self, state: CampaignState) -> str:
        location = state.locations[state.current_location_id]
        exits = ", ".join(location.connections) if location.connections else "none"
        return f"{location.name}: {location.description} Exits: {exits}."

    def move_to_location(self, state: CampaignState, destination_id: str) -> str:
        current = state.locations[state.current_location_id]
        if destination_id not in current.connections:
            return f"You cannot travel directly to '{destination_id}' from {current.name}."

        state.current_location_id = destination_id
        destination = state.locations[destination_id]
        return f"You travel to {destination.name}."

    def set_world_flag(self, state: CampaignState, key: str, value: bool) -> None:
        state.world_flags[key] = value
