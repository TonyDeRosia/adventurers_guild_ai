"""Model adapter registry and factory."""

from __future__ import annotations

from models.base import NarrationModelAdapter, NullNarrationAdapter
from models.gpt4all_adapter import GPT4AllAdapter
from models.ollama_adapter import OllamaAdapter


def create_model_adapter(provider: str, **kwargs: str) -> NarrationModelAdapter:
    provider = provider.lower().strip()
    if provider == "ollama":
        return OllamaAdapter(**kwargs)
    if provider == "gpt4all":
        return GPT4AllAdapter(**kwargs)
    if provider in {"local_template", "null"}:
        return NullNarrationAdapter()
    return NullNarrationAdapter()
