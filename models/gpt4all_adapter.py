"""GPT4All-compatible adapter stub.

Kept dependency-free in phase 1; wire to the official SDK in a later phase.
"""

from __future__ import annotations

from models.base import ChatMessage, NarrationModelAdapter


class GPT4AllAdapter(NarrationModelAdapter):
    provider_name = "gpt4all"

    def __init__(self, model_path: str = "") -> None:
        self.model_path = model_path

    def generate(self, prompt: str, system_prompt: str = "", history: list[ChatMessage] | None = None) -> str:
        if not self.model_path:
            return (
                "[GPT4All adapter not configured] Set model_path and connect the "
                "runtime in a later phase."
            )
        return (
            "[GPT4All placeholder narrator] "
            "Model path configured, but runtime integration is not active in phase 1."
        )
