"""Runtime configuration for local-first deployment."""

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


@dataclass
class ImageRuntimeConfig:
    provider: str = "local"
    base_url: str = "http://localhost:8188"
    enabled: bool = True
    comfyui_path: str = ""


@dataclass
class AppRuntimeConfig:
    model: ModelRuntimeConfig
    image: ImageRuntimeConfig


class RuntimeConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppRuntimeConfig:
        if not self.path.exists():
            return AppRuntimeConfig(model=ModelRuntimeConfig(), image=ImageRuntimeConfig())

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return AppRuntimeConfig(model=ModelRuntimeConfig(), image=ImageRuntimeConfig())

        if "model" in payload or "image" in payload:
            model_payload = payload.get("model", {})
            image_payload = payload.get("image", {})
        else:
            # Backward compatibility with pre-structured model-only config.
            model_payload = payload
            image_payload = {}

        return AppRuntimeConfig(
            model=ModelRuntimeConfig(
                provider=str(model_payload.get("provider", "null")),
                model_name=str(model_payload.get("model_name", "llama3")),
                base_url=str(model_payload.get("base_url", "http://localhost:11434")),
                timeout_seconds=int(model_payload.get("timeout_seconds", 45)),
            ),
            image=ImageRuntimeConfig(
                provider=str(image_payload.get("provider", "local")),
                base_url=str(image_payload.get("base_url", "http://localhost:8188")),
                enabled=bool(image_payload.get("enabled", True)),
                comfyui_path=str(image_payload.get("comfyui_path", "")),
            ),
        )

    def save(self, config: AppRuntimeConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
