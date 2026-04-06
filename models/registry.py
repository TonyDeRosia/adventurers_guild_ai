"""Model adapter registry and factory."""

from __future__ import annotations

from typing import Any

from models.base import NarrationModelAdapter, NullNarrationAdapter
from models.gpt4all_adapter import GPT4AllAdapter
from models.ollama_adapter import OllamaAdapter


def create_model_adapter(provider: str, **kwargs: Any) -> NarrationModelAdapter:
    provider = provider.lower().strip()
    if provider == "ollama":
        adapter = OllamaAdapter(**kwargs)
        configured_model = str(kwargs.get("model", "")).strip()
        detected_models = adapter.list_local_models()
        if configured_model and detected_models and configured_model not in detected_models:
            return NullNarrationAdapter()
        if configured_model and not detected_models:
            return NullNarrationAdapter()
        return adapter
    if provider == "gpt4all":
        return GPT4AllAdapter(**kwargs)
    if provider in {"local_template", "null"}:
        return NullNarrationAdapter()
    return NullNarrationAdapter()
