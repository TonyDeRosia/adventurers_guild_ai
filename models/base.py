"""Abstractions for local-first model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NarrationModelAdapter(ABC):
    """Provider interface for text generation."""

    provider_name: str

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a narration string from prompt context."""


class NullNarrationAdapter(NarrationModelAdapter):
    """Fallback adapter that avoids external dependencies."""

    provider_name = "null"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            "[Local fallback narrator] "
            "No model backend configured. Proceeding with deterministic narration. "
            f"Context: {prompt[:180]}"
        )
