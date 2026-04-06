"""Abstractions for local-first model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from models.provider import LocalTemplateProvider, NarrationRequest


@dataclass
class ChatMessage:
    role: str
    content: str


class NarrationModelAdapter(ABC):
    """Provider interface for text generation."""

    provider_name: str

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", history: list[ChatMessage] | None = None) -> str:
        """Generate a narration string from prompt context."""


class NullNarrationAdapter(NarrationModelAdapter):
    """Fallback adapter that avoids external dependencies."""

    provider_name = "null"

    def __init__(self) -> None:
        self.provider = LocalTemplateProvider()

    def generate(self, prompt: str, system_prompt: str = "", history: list[ChatMessage] | None = None) -> str:
        request = NarrationRequest(
            system_tone=system_prompt,
            campaign_tone=system_prompt,
            scene_context=prompt,
            player_state_summary=prompt,
        )
        return self.provider.narrate(request)
