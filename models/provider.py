"""Scaffold provider interface for future local inference backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class NarrationRequest:
    system_tone: str
    campaign_tone: str
    scene_context: str
    player_state_summary: str


class NarrationProvider(Protocol):
    provider_name: str

    def narrate(self, request: NarrationRequest) -> str:
        """Generate narration from structured prompt layers."""


class LocalTemplateProvider:
    """Offline-safe placeholder provider used by terminal MVP."""

    provider_name = "local_template"

    def narrate(self, request: NarrationRequest) -> str:
        action = "act"
        location = "the current scene"
        for line in request.scene_context.splitlines():
            stripped = line.strip()
            if stripped.startswith("Action:"):
                action = stripped.split(":", 1)[1].strip() or action
            if stripped.startswith("Location:"):
                location = stripped.split(":", 1)[1].strip() or location
        return (
            f"You commit to {action}, and the air shifts around you in {location}. "
            "The moment opens into your next decision."
        )
