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
        scene = request.scene_context.replace("\n", " ")
        return (
            "[Local template narrator] "
            f"{scene[:150]} ... "
            "You steady your breath and prepare your next move."
        )
