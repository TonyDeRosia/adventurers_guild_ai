"""Lightweight narration provider scaffold for future local backend adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NarrationRequest:
    system_tone: str
    profile_tone: str
    scene_context: str
    player_state_summary: str
    action: str


class NarrationProvider(Protocol):
    provider_name: str

    def narrate(self, request: NarrationRequest) -> str:
        """Generate narration from organized local prompt context."""


class MockNarrationProvider:
    """Deterministic local fallback provider used by terminal mode."""

    provider_name = "mock"

    def narrate(self, request: NarrationRequest) -> str:
        return (
            "[Mock narrator] "
            f"{request.scene_context} {request.player_state_summary} "
            f"You chose to '{request.action}'."
        )
