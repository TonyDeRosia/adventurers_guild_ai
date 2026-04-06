"""Runtime model configuration for local-first deployment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ModelRuntimeConfig:
    provider: str = "null"
    model_name: str = "llama3"
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 45


class RuntimeConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ModelRuntimeConfig:
        if not self.path.exists():
            return ModelRuntimeConfig()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return ModelRuntimeConfig(
            provider=str(payload.get("provider", "null")),
            model_name=str(payload.get("model_name", "llama3")),
            base_url=str(payload.get("base_url", "http://localhost:11434")),
            timeout_seconds=int(payload.get("timeout_seconds", 45)),
        )

    def save(self, config: ModelRuntimeConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
