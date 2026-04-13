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
    ollama_path: str = ""


@dataclass
class ImageRuntimeConfig:
    provider: str = "local"
    base_url: str = "http://localhost:8188"
    enabled: bool = True
    comfyui_path: str = ""
    comfyui_workflow_path: str = ""
    comfyui_output_dir: str = ""
    manual_image_generation_enabled: bool = True
    campaign_auto_visual_timing: str = "after_narration"
    checkpoint_source: str = "local"
    checkpoint_model_page: str = "https://civitai.com/models/4384/dreamshaper"
    checkpoint_folder: str = ""
    preferred_checkpoint: str = ""
    preferred_launcher: str = "auto"
    auto_negative_prompt_additions: list[str] = None
    managed_service_enabled: bool = True
    managed_install_path: str = ""
    managed_logs_path: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.auto_negative_prompt_additions, list):
            self.auto_negative_prompt_additions = []
        else:
            self.auto_negative_prompt_additions = [str(v).strip() for v in self.auto_negative_prompt_additions if str(v).strip()]


@dataclass
class AppRuntimeConfig:
    model: ModelRuntimeConfig
    image: ImageRuntimeConfig


class RuntimeConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def _normalize_campaign_auto_visual_timing(value: str | None) -> str:
        clean = str(value or "").strip().lower()
        aliases = {
            "auto_before": "before_narration",
            "auto_before_narration": "before_narration",
            "auto_after": "after_narration",
            "auto_after_narration": "after_narration",
            "manual": "off",
        }
        normalized = aliases.get(clean, clean)
        if normalized in {"off", "before_narration", "after_narration"}:
            return normalized
        return "off"

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
                ollama_path=str(model_payload.get("ollama_path", "")),
            ),
            image=ImageRuntimeConfig(
                provider=str(image_payload.get("provider", "local")),
                base_url=str(image_payload.get("base_url", "http://localhost:8188")),
                enabled=bool(image_payload.get("enabled", True)),
                comfyui_path=str(image_payload.get("comfyui_path", "")),
                comfyui_workflow_path=str(image_payload.get("comfyui_workflow_path", "")),
                comfyui_output_dir=str(image_payload.get("comfyui_output_dir", "")),
                manual_image_generation_enabled=bool(image_payload.get("manual_image_generation_enabled", True)),
                campaign_auto_visual_timing=self._normalize_campaign_auto_visual_timing(
                    image_payload.get("campaign_auto_visual_timing", image_payload.get("turn_visuals_mode", "after_narration"))
                ),
                checkpoint_source=str(image_payload.get("checkpoint_source", "local")),
                checkpoint_model_page=str(image_payload.get("checkpoint_model_page", "https://civitai.com/models/4384/dreamshaper")),
                checkpoint_folder=str(image_payload.get("checkpoint_folder", "")),
                preferred_checkpoint=str(image_payload.get("preferred_checkpoint", "")),
                preferred_launcher=str(image_payload.get("preferred_launcher", "auto")),
                auto_negative_prompt_additions=[
                    str(v).strip()
                    for v in image_payload.get("auto_negative_prompt_additions", [])
                    if str(v).strip()
                ]
                if isinstance(image_payload.get("auto_negative_prompt_additions", []), list)
                else [],
                managed_service_enabled=bool(image_payload.get("managed_service_enabled", True)),
                managed_install_path=str(image_payload.get("managed_install_path", "")),
                managed_logs_path=str(image_payload.get("managed_logs_path", "")),
            ),
        )

    def save(self, config: AppRuntimeConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
