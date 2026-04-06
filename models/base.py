"""Abstractions for local-first model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.provider import NarrationProvider, NarrationRequest


class NarrationModelAdapter(ABC):
    """Provider interface for text generation."""

    provider_name: str

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a narration string from prompt context."""


class ProviderBackedNarrationAdapter(NarrationModelAdapter):
    """Adapter that routes organized prompt parts to provider scaffolds."""

    provider_name = "provider_backed"

    def __init__(self, provider: NarrationProvider) -> None:
        self.provider = provider

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        request = NarrationRequest(
            system_tone=system_prompt,
            profile_tone="",
            scene_context=prompt,
            player_state_summary="",
            action="continue",
        )
        return self.provider.narrate(request)

    def generate_from_parts(self, request: NarrationRequest) -> str:
        return self.provider.narrate(request)


class NullNarrationAdapter(ProviderBackedNarrationAdapter):
    """Fallback adapter that avoids external dependencies."""

    provider_name = "null"

    def __init__(self) -> None:
        from models.provider import MockNarrationProvider

        super().__init__(MockNarrationProvider())

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        request = NarrationRequest(
            system_tone=system_prompt,
            profile_tone="",
            scene_context=prompt[:180],
            player_state_summary="",
            action="continue",
        )
        return self.provider.narrate(request)
