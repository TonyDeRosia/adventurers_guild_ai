"""Local web chat runtime and HTTP API for Adventurer Guild AI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import sys
import urllib.request
import zipfile
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import Request
    import uvicorn
except ModuleNotFoundError:  # pragma: no cover - optional dependency in some test environments
    FastAPI = None
    HTTPException = Exception
    CORSMiddleware = None
    FileResponse = None
    JSONResponse = None
    StaticFiles = None
    Request = Any
    uvicorn = None

from app.pathing import initialize_user_data_paths, project_root, static_dir
from app.runtime_config import AppRuntimeConfig, ImageRuntimeConfig, ModelRuntimeConfig, RuntimeConfigStore
from engine.campaign_engine import CampaignEngine, TurnResult
from engine.character_sheets import CharacterSheet
from engine.entities import CampaignSettings, CampaignState
from engine.game_state_manager import GameStateManager
from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter, NullImageAdapter
from images.comfyui_adapter import ComfyUIAdapter
from images.local_adapter import LocalPlaceholderImageAdapter
from images.prompt_builder import TurnImagePromptBuilder
from images.workflow_manager import WorkflowManager
from models.ollama_adapter import OllamaAdapter
from models.registry import create_model_adapter
from models.supported_models import get_supported_model, get_supported_models


@dataclass
class WebSession:
    state: CampaignState
    active_slot: str = "autosave"
    message_history: list[dict[str, Any]] = field(default_factory=list)


class WebRuntime:
    """Owns campaign state, settings, and message continuity for the web UI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.paths = initialize_user_data_paths()
        self.state_manager = GameStateManager(self.paths.content_data, self.paths.saves, self.paths.user_data)
        self.config_store = RuntimeConfigStore(self.paths.config / "app_config.json")
        self.app_config: AppRuntimeConfig = self.config_store.load()
        self.workflow_manager = WorkflowManager(self.paths.workflows)
        self.generated_image_dir = self.paths.generated_images
        self.turn_image_prompts = TurnImagePromptBuilder()
        self.history_store_path = self.paths.campaign_memory / "web_message_history.json"
        self.history_store = self._load_history_store()
        self.scene_visual_store_path = self.paths.campaign_memory / "scene_visual_store.json"
        self.scene_visual_store = self._load_scene_visual_store()

        self.engine = CampaignEngine(self._create_model_adapter(), data_dir=self.paths.content_data)
        self.image_adapter = self._create_image_adapter()
        default_slot = "autosave" if self.state_manager.can_load("autosave") else "campaign_1"
        self.session = WebSession(state=self._load_or_create(default_slot), active_slot=default_slot)
        self.session.message_history = self._history_for_slot(self.session.active_slot)
        self.image_startup_status: dict[str, Any] = {}
        self._history_lock = threading.Lock()
        self._turn_visual_lock = threading.Lock()
        self._active_turn_visual_jobs: set[tuple[str, int, str]] = set()
        self._model_install_lock = threading.Lock()
        self._model_install_jobs: dict[str, dict[str, Any]] = {}
        print("[web-runtime] session initialized")

    def _campaign_namespace(self, slot: str, state: CampaignState | None = None) -> str:
        scoped_state = state or self.session.state
        campaign_id = str(scoped_state.campaign_id or "").strip() or "unknown_campaign"
        return f"{slot}::{campaign_id}"

    def _load_history_store(self) -> dict[str, list[dict[str, Any]]]:
        if not self.history_store_path.exists():
            return {}
        try:
            payload = json.loads(self.history_store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _persist_history_store(self) -> None:
        self.history_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_store_path.write_text(json.dumps(self.history_store, indent=2), encoding="utf-8")

    def _load_scene_visual_store(self) -> dict[str, dict[str, Any]]:
        if not self.scene_visual_store_path.exists():
            return {}
        try:
            payload = json.loads(self.scene_visual_store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _persist_scene_visual_store(self) -> None:
        self.scene_visual_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_visual_store_path.write_text(json.dumps(self.scene_visual_store, indent=2), encoding="utf-8")

    def _normalize_campaign_auto_visual_timing(self, value: str | None) -> str:
        clean = str(value or "").strip().lower()
        aliases = {
            "auto_after": "after_narration",
            "auto_after_narration": "after_narration",
            "auto_before": "before_narration",
            "auto_before_narration": "before_narration",
            "manual": "off",
        }
        normalized = aliases.get(clean, clean)
        if normalized in {"off", "before_narration", "after_narration"}:
            return normalized
        return "off"

    def _normalize_narration_format_mode(self, value: str | None) -> str:
        clean = str(value or "").strip().lower()
        return clean if clean in {"book", "compact", "dialogue_focused"} else "book"

    def _normalize_scene_visual_mode(self, value: str | None) -> str:
        clean = str(value or "").strip().lower()
        return clean if clean in {"off", "manual", "before_narration", "after_narration"} else "after_narration"

    def _set_scene_visual(
        self,
        *,
        slot: str,
        image_url: str,
        prompt: str,
        source: str,
        stage: str,
        turn: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        namespace = self._campaign_namespace(slot)
        caption = self._build_scene_visual_caption(source=source, turn=turn)
        self.scene_visual_store[namespace] = {
            "image_url": image_url,
            "prompt": prompt,
            "caption": caption,
            "source": source,
            "stage": stage,
            "turn": turn,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._persist_scene_visual_store()
        self.engine.state_orchestrator.set_scene_visual_state(self.session.state, self.scene_visual_store[namespace])

    def _scene_visual_for_slot(self, slot: str | None = None) -> dict[str, Any] | None:
        target_slot = str(slot or self.session.active_slot)
        namespace = self._campaign_namespace(target_slot)
        payload = self.scene_visual_store.get(namespace)
        if payload is None:
            payload = self.scene_visual_store.get(target_slot)
        if not isinstance(payload, dict):
            return None
        response = dict(payload)
        turn = int(response.get("turn", 0) or 0)
        source = str(response.get("source", "")).strip()
        response["caption"] = str(response.get("caption", "")).strip() or self._build_scene_visual_caption(source=source, turn=turn)
        return response

    def _build_scene_visual_caption(self, *, source: str, turn: int) -> str:
        if turn > 0:
            return f"Scene visual updated for Turn {turn}."
        if source == "manual":
            return "Latest generated image loaded in Scene Visual."
        return "Scene visual reflects the current area."

    def _history_for_slot(self, slot: str) -> list[dict[str, Any]]:
        namespace = self._campaign_namespace(slot)
        existing = self.history_store.get(namespace)
        if not isinstance(existing, list):
            existing = self.history_store.get(slot)
        if isinstance(existing, list) and existing:
            return existing
        replayed: list[dict[str, Any]] = []
        for turn in self.session.state.conversation_turns:
            replayed.append(self._message("player", turn.player_input))
            replayed.extend(self._message(self._normalize_message_type("system", msg), msg) for msg in turn.system_messages)
            if turn.narrator_response:
                replayed.append(self._message("narrator", turn.narrator_response))
        self.history_store[namespace] = replayed
        return replayed

    def _load_or_create(self, slot: str) -> CampaignState:
        if self.state_manager.can_load(slot):
            loaded = self.state_manager.load(slot)
            if loaded is not None:
                print(f"[campaign-load] display_mode={loaded.settings.display_mode}")
                return loaded
        return self.state_manager.create_new_campaign(
            player_name="Aria",
            char_class="Ranger",
            profile="classic_fantasy",
            mature_content_enabled=False,
            content_settings_enabled=True,
            campaign_tone="heroic",
            maturity_level="standard",
            thematic_flags=["adventure", "mystery"],
        )

    def _create_model_adapter(self):
        return create_model_adapter(
            self.app_config.model.provider,
            model=self.app_config.model.model_name,
            base_url=self.app_config.model.base_url,
            timeout_seconds=self.app_config.model.timeout_seconds,
        )

    def get_model_status(self) -> dict[str, Any]:
        provider = self.app_config.model.provider
        model_name = self.app_config.model.model_name
        base_url = self.app_config.model.base_url
        if provider != "ollama":
            print(
                f"[model-status] provider={provider} model={model_name} base_url={base_url} "
                "readiness_result=not_required model_check_result=not_required"
            )
            return {
                "provider": provider,
                "model": model_name,
                "base_url": base_url,
                "reachable": True,
                "model_exists": True,
                "ready": True,
                "user_message": f"{provider} provider is ready.",
                "fallback_reason": "",
            }

        adapter = OllamaAdapter(
            model=model_name,
            base_url=base_url,
            timeout_seconds=self.app_config.model.timeout_seconds,
        )
        status = adapter.check_readiness()
        print(
            f"[model-status] provider={provider} model={model_name} base_url={base_url} "
            f"readiness_result={status['reachable']} model_check_result={status['model_exists']}"
        )
        return status

    def get_image_status(self) -> dict[str, Any]:
        provider = self.app_config.image.provider
        base_url = self.app_config.image.base_url
        if provider == "comfyui":
            path_config = self.get_path_configuration_status()
            image_paths = path_config["image"]
            if not bool(image_paths["comfyui_root"]["valid"]):
                reason = "missing_path" if not image_paths["comfyui_root"]["configured"] else "invalid_path"
                print(f"[path-config] image_features_disabled reason={reason}")
                return {
                    "provider": "comfyui",
                    "base_url": base_url,
                    "reachable": False,
                    "ready": False,
                    "status_code": "setup_required",
                    "status_level": "error",
                    "user_message": str(image_paths["comfyui_root"]["message"]),
                    "next_action": "Set your ComfyUI folder in AI Setup, then click Recheck.",
                    "error": reason,
                }
            if not bool(image_paths["workflow_path"]["valid"]):
                reason = "missing_workflow_path" if not image_paths["workflow_path"]["configured"] else "invalid_workflow_path"
                print(f"[path-config] image_features_disabled reason={reason}")
                return {
                    "provider": "comfyui",
                    "base_url": base_url,
                    "reachable": False,
                    "ready": False,
                    "status_code": "workflow_required",
                    "status_level": "error",
                    "user_message": str(image_paths["workflow_path"]["message"]),
                    "next_action": "Set your workflow JSON file in AI Setup, then click Recheck.",
                    "error": reason,
                }
            if not bool(image_paths["checkpoint_dir"]["valid"]):
                reason = "missing_checkpoint_folder" if not image_paths["checkpoint_dir"]["configured"] else "invalid_checkpoint_folder"
                print(f"[path-config] image_features_disabled reason={reason}")
                return {
                    "provider": "comfyui",
                    "base_url": base_url,
                    "reachable": False,
                    "ready": False,
                    "status_code": "checkpoint_required",
                    "status_level": "error",
                    "user_message": str(image_paths["checkpoint_dir"]["message"]),
                    "next_action": "Set your checkpoint folder in AI Setup, then click Recheck.",
                    "error": reason,
                }
            base_status = ComfyUIAdapter(base_url=base_url).check_readiness()
            comfyui_root = self._find_comfyui_root()
            installed = comfyui_root is not None
            if base_status.get("reachable", False):
                return {
                    **base_status,
                    "installed": True,
                    "running": True,
                    "status_code": "reachable",
                    "comfyui_path": str(comfyui_root or ""),
                    "launcher_mode": self._determine_launcher_mode(comfyui_root),
                }
            if installed:
                return {
                    **base_status,
                    "installed": True,
                    "running": False,
                    "status_code": "not_running",
                    "status_level": "error",
                    "user_message": "ComfyUI is installed but not running.",
                    "next_action": "Start Image Engine, then click Recheck.",
                    "comfyui_path": str(comfyui_root),
                    "launcher_mode": self._determine_launcher_mode(comfyui_root),
                }
            return {
                **base_status,
                "installed": False,
                "running": False,
                "status_code": "not_installed",
                "status_level": "error",
                "user_message": "ComfyUI is not installed in the configured local setup path.",
                "next_action": "Install Image Engine, then click Recheck.",
                "comfyui_path": "",
                "launcher_mode": "none",
            }
        if provider == "null":
            return {
                "provider": provider,
                "base_url": base_url,
                "reachable": False,
                "ready": False,
                "status_level": "info",
                "user_message": "Image provider is disabled.",
                "next_action": "Set image provider to local or comfyui, then click Recheck.",
                "error": "",
            }
        return {
            "provider": provider,
            "base_url": base_url,
            "reachable": True,
            "ready": True,
            "status_level": "ready",
            "user_message": f"{provider} image provider is ready.",
            "next_action": "No action needed.",
            "error": "",
        }

    def get_dependency_readiness(self) -> dict[str, Any]:
        model_status = self.get_model_status()
        image_status = self.get_image_status()
        provider = str(model_status.get("provider", self.app_config.model.provider))
        model_name = str(model_status.get("model", self.app_config.model.model_name))
        model_error = str(model_status.get("error", "")).lower()
        ollama_cli = self._find_ollama_cli()
        ollama_installed = bool(ollama_cli)
        ollama_not_running = provider == "ollama" and not bool(model_status.get("reachable", True))
        ollama_unavailable = ollama_not_running and (
            not ollama_installed
            or ("connection refused" not in model_error and "failed to establish a new connection" not in model_error)
        )
        model_provider_item = {
            "provider_type": "model_provider",
            "provider": provider,
            "reachable": bool(model_status.get("reachable", True)),
            "selected_model": model_name,
            "model_exists": bool(model_status.get("model_exists", True)),
            "status_level": "ready" if model_status.get("reachable", True) else "error",
            "user_message": (
                f"{provider} is reachable."
                if model_status.get("reachable", True)
                else "Ollama is not installed (CLI not found on PATH)."
                if provider == "ollama" and not ollama_installed
                else "Ollama appears installed but is not running."
                if ollama_not_running and not ollama_unavailable
                else "Ollama is unavailable. Install Ollama or verify the configured base URL."
            ),
            "next_action": (
                "No action needed."
                if model_status.get("reachable", True)
                else "Install Ollama, then click Recheck."
                if provider == "ollama" and not ollama_installed
                else "Run: ollama serve"
                if provider == "ollama"
                else "Verify provider settings, then click Recheck."
            ),
            "actions": (
                []
                if model_status.get("reachable", True)
                else [{"id": "install_ollama", "label": "Install Ollama"}, {"id": "recheck", "label": "Recheck"}]
                if provider == "ollama" and not ollama_installed
                else [{"id": "start_ollama", "label": "Start Ollama"}, {"id": "recheck", "label": "Recheck"}]
            ),
        }
        model_item = {
            "provider_type": "selected_model",
            "provider": provider,
            "reachable": bool(model_status.get("reachable", True)),
            "selected_model": model_name,
            "model_exists": bool(model_status.get("model_exists", True)),
            "status_level": "ready" if model_status.get("model_exists", True) else "error",
            "user_message": (
                f"Model {model_name} is installed."
                if model_status.get("model_exists", True)
                else f"Model {model_name} is not installed."
            ),
            "next_action": (
                "No action needed."
                if model_status.get("model_exists", True)
                else f"Run: ollama pull {model_name}"
            ),
            "actions": (
                [{"id": "recheck", "label": "Recheck"}]
                if model_status.get("model_exists", True)
                else [{"id": "install_model", "label": "Install Story Model"}, {"id": "recheck", "label": "Recheck"}]
                if provider == "ollama" and ollama_installed
                else [{"id": "recheck", "label": "Recheck"}]
            ),
        }
        image_item = {
            "provider_type": "image_provider",
            "provider": image_status.get("provider", self.app_config.image.provider),
            "reachable": bool(image_status.get("reachable", True)),
            "selected_model": "",
            "model_exists": True,
            "status_level": image_status.get("status_level", "ready"),
            "user_message": str(image_status.get("user_message", "")),
            "next_action": str(image_status.get("next_action", "No action needed.")),
            "status_code": str(image_status.get("status_code", "")),
            "fallback_available": True,
            "actions": self._image_readiness_actions(image_status),
        }
        if self.image_startup_status:
            image_item["startup_status"] = dict(self.image_startup_status)
        return {
            "items": [model_provider_item, model_item, image_item],
            "primary_actions": [
                {"id": "setup_text_ai", "label": "Set Up Text AI"},
                {"id": "setup_image_ai", "label": "Set Up Image AI"},
                {"id": "setup_everything", "label": "Set Up Everything"},
            ],
            "setup_checklist": [
                "Primary onboarding actions:",
                "1) Click Set Up Text AI to install/start Ollama and install the selected model.",
                "2) Click Set Up Image AI to bootstrap and start ComfyUI.",
                "3) Click Set Up Everything to run both in sequence.",
                "Fallback actions:",
                "Use Recheck and Copy command if a step fails and manual intervention is needed.",
                "Fallback story mode stays available even when providers are missing.",
            ],
            "setup_guidance": [
                "Ollama is used for story narration when model provider is set to ollama.",
                "Start Ollama before playing: ollama serve",
                f"Install a missing model with: ollama pull {self.app_config.model.model_name}",
                "ComfyUI is used when image provider is set to comfyui for image generation requests.",
                "If providers are unavailable, the app still runs with local narrator fallback mode.",
            ],
        }

    def _image_readiness_actions(self, image_status: dict[str, Any]) -> list[dict[str, str]]:
        if self.app_config.image.provider != "comfyui":
            return [{"id": "recheck", "label": "Recheck"}]
        status_code = str(image_status.get("status_code", ""))
        if status_code in {"setup_required", "workflow_required", "checkpoint_required"}:
            return [{"id": "recheck", "label": "Recheck"}]
        if status_code == "not_installed":
            return [{"id": "install_image_engine", "label": "Install Image Engine"}, {"id": "recheck", "label": "Recheck"}]
        if status_code == "not_running":
            return [{"id": "start_image_engine", "label": "Start Image Engine"}, {"id": "recheck", "label": "Recheck"}]
        return [{"id": "recheck", "label": "Recheck"}]

    def _find_ollama_cli(self) -> str | None:
        configured = str(self.app_config.model.ollama_path or "").strip()
        if configured:
            configured_path = Path(configured)
            candidates: list[Path] = []
            if configured_path.is_file():
                candidates.append(configured_path)
            else:
                candidates.extend(
                    [
                        configured_path / "ollama.exe",
                        configured_path / "ollama",
                        configured_path / "bin" / "ollama.exe",
                        configured_path / "bin" / "ollama",
                    ]
                )
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)
        if os.name == "nt":
            return shutil.which("ollama.exe") or shutil.which("ollama")
        return shutil.which("ollama")

    def pick_folder(self, title: str, initial_path: str = "") -> dict[str, Any]:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            return {"ok": False, "message": "Folder picker is unavailable in this environment.", "error": str(exc)}
        try:
            root = tk.Tk()
            root.withdraw()
            selected = filedialog.askdirectory(title=title, initialdir=initial_path or str(self.paths.user_data))
            root.destroy()
        except Exception as exc:
            return {"ok": False, "message": "Folder picker could not be opened.", "error": str(exc)}
        if not selected:
            return {"ok": False, "message": "No folder selected."}
        return {"ok": True, "path": selected}

    def pick_file(self, title: str, initial_path: str = "", filters: list[str] | None = None) -> dict[str, Any]:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            return {"ok": False, "message": "File picker is unavailable in this environment.", "error": str(exc)}
        filter_list = filters or [".json"]
        file_types = [("Allowed files", " ".join(f"*{suffix}" for suffix in filter_list)), ("All files", "*.*")]
        try:
            root = tk.Tk()
            root.withdraw()
            selected = filedialog.askopenfilename(
                title=title,
                initialdir=(str(Path(initial_path).parent) if initial_path else str(self.paths.user_data)),
                filetypes=file_types,
            )
            root.destroy()
        except Exception as exc:
            return {"ok": False, "message": "File picker could not be opened.", "error": str(exc)}
        if not selected:
            return {"ok": False, "message": "No file selected."}
        return {"ok": True, "path": selected}

    def connect_ollama_path(self, selected_path: str) -> dict[str, Any]:
        candidate = Path(str(selected_path or "").strip())
        if not candidate.exists():
            return {"ok": False, "message": "Selected Ollama folder does not exist."}
        self.app_config.model.ollama_path = str(candidate)
        cli = self._find_ollama_cli()
        if not cli:
            return {
                "ok": False,
                "message": "Could not find ollama executable in the selected folder.",
                "next_step": "Pick the folder that contains ollama.exe (or bin/ollama).",
            }
        self.config_store.save(self.app_config)
        model_status = self.get_model_status()
        return {
            "ok": True,
            "message": "Ollama path saved and connected.",
            "cli_path": cli,
            "status": model_status,
        }

    def connect_comfyui_path(self, selected_path: str) -> dict[str, Any]:
        candidate = Path(str(selected_path or "").strip())
        if not candidate.exists():
            return {"ok": False, "message": "Selected ComfyUI folder does not exist."}
        validation = self.validate_comfyui_install(candidate)
        if not validation.get("ok", False):
            missing = ", ".join(validation.get("missing_files", []))
            return {
                "ok": False,
                "message": f"ComfyUI folder is missing required files: {missing}.",
                "validation": validation,
            }
        self.app_config.image.comfyui_path = str(candidate)
        self.config_store.save(self.app_config)
        return {
            "ok": True,
            "message": "ComfyUI folder saved and connected.",
            "validation": validation,
        }

    def get_comfyui_model_status(self) -> dict[str, Any]:
        comfyui_root = self._find_comfyui_root()
        checkpoint_root = self._resolve_checkpoint_folder(comfyui_root)
        curated = [
            {
                "id": "sd15_checkpoint",
                "label": "Stable Diffusion v1.5 Checkpoint",
                "target_subdir": "checkpoints",
                "expected_files": ["v1-5-pruned-emaonly.safetensors", "sd15.safetensors"],
                "download_url": "https://huggingface.co/runwayml/stable-diffusion-v1-5",
            },
            {
                "id": "vae",
                "label": "SD VAE (optional quality boost)",
                "target_subdir": "vae",
                "expected_files": ["vae-ft-mse-840000-ema-pruned.safetensors"],
                "download_url": "https://huggingface.co/stabilityai/sd-vae-ft-mse-original",
            },
            {
                "id": "dreamshaper_checkpoint",
                "label": "DreamShaper Checkpoint (preferred)",
                "target_subdir": "checkpoints",
                "expected_files": ["dreamshaper.safetensors", "dreamshaper_8.safetensors", "dreamshaperxl.safetensors"],
                "download_url": "https://civitai.com/models/4384/dreamshaper",
            },
        ]
        for item in curated:
            target_dir = checkpoint_root if item["target_subdir"] == "checkpoints" else (comfyui_root / "models" / item["target_subdir"] if comfyui_root else None)
            present = False
            if target_dir and target_dir.exists():
                files = {p.name.lower() for p in target_dir.iterdir() if p.is_file()}
                expected = {name.lower() for name in item["expected_files"]}
                present = bool(files.intersection(expected))
            item["present"] = present
            item["target_path"] = str(target_dir or "")
        return {
            "comfyui_path": str(comfyui_root or ""),
            "checkpoint_folder": str(checkpoint_root or ""),
            "preferred_checkpoint": self.app_config.image.preferred_checkpoint,
            "launcher_mode": self._determine_launcher_mode(comfyui_root),
            "items": curated,
        }

    def _resolve_checkpoint_folder(self, comfyui_root: Path | None = None) -> Path | None:
        if self.app_config.image.checkpoint_folder:
            return Path(self.app_config.image.checkpoint_folder)
        if comfyui_root:
            return comfyui_root / "models" / "checkpoints"
        return None

    def _determine_launcher_mode(self, comfyui_root: Path | None = None) -> str:
        root = comfyui_root or self._find_comfyui_root()
        if not root:
            return "none"
        launchers = [
            ("nvidia_gpu", "run_nvidia_gpu.bat"),
            ("gpu", "run_gpu.bat"),
            ("amd_gpu", "run_amd_gpu.bat"),
            ("cpu", "run_cpu.bat"),
        ]
        for mode, script in launchers:
            if (root / script).exists():
                return mode
        return "python_main"

    def _is_windows(self) -> bool:
        return os.name == "nt"

    def _resolve_ollama_windows_installer_url(self) -> str:
        download_page = "https://ollama.com/download"
        with urllib.request.urlopen(download_page, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")
        matches = re.findall(r'href="([^"]+OllamaSetup\.exe[^"]*)"', html, flags=re.IGNORECASE)
        if matches:
            candidate = matches[0]
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return candidate
            return f"https://ollama.com{candidate}"
        return "https://ollama.com/download/OllamaSetup.exe"

    def _run_command_capture(self, command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )

    def _run_ollama_pull_with_logs(self, ollama_cli: str, model: str, timeout_seconds: int = 60 * 60) -> dict[str, Any]:
        command = [ollama_cli, "pull", model]
        print(f"[ollama-install] run command={' '.join(command)} timeout_seconds={timeout_seconds}")
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            print(f"[ollama-install] popen-fallback reason={exc}")
            completed = self._run_command_capture(command, timeout_seconds=timeout_seconds)
            output = (completed.stdout or completed.stderr or "").strip()
            snippet = output[-500:] if output else ""
            return {"returncode": completed.returncode, "timed_out": False, "details": snippet, "log_lines": output.splitlines()}
        log_lines: list[str] = []
        start_ts = time.time()
        timed_out = False
        while True:
            if process.stdout is None:
                break
            line = process.stdout.readline()
            if line:
                clean = line.rstrip()
                log_lines.append(clean)
                print(f"[ollama-install] stdout model={model} line={clean}")
            if process.poll() is not None:
                break
            if (time.time() - start_ts) > timeout_seconds:
                timed_out = True
                process.kill()
                print(f"[ollama-install] timeout model={model} timeout_seconds={timeout_seconds}")
                break
        if process.stdout is not None:
            remainder = process.stdout.read() or ""
            for line in remainder.splitlines():
                clean = line.rstrip()
                if clean:
                    log_lines.append(clean)
                    print(f"[ollama-install] stdout model={model} line={clean}")
        return_code = process.wait(timeout=5)
        combined_text = "\n".join(log_lines).strip()
        snippet = combined_text[-500:] if combined_text else ""
        return {"returncode": return_code, "timed_out": timed_out, "details": snippet, "log_lines": log_lines}

    def _record_model_install_status(self, model: str, status: dict[str, Any]) -> None:
        clean_model = model.strip().lower()
        with self._model_install_lock:
            self._model_install_jobs[clean_model] = {
                **status,
                "model": model,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_model_install_status(self, model_name: str | None = None) -> dict[str, Any]:
        model = (model_name or self.app_config.model.model_name or "").strip().lower()
        with self._model_install_lock:
            current = dict(self._model_install_jobs.get(model, {})) if model else {}
        if not current:
            return {"ok": False, "status": "idle", "message": "No install task found.", "model": model}
        return current

    def _start_model_install(self, model_name: str) -> dict[str, Any]:
        model = model_name.strip()
        model_key = model.lower()
        existing = self.get_model_install_status(model)
        if existing.get("status") in {"started", "installing"}:
            print(f"[model-install] duplicate request ignored model={model} existing_status={existing.get('status')}")
            return {"ok": True, "status": "started", "message": f"Install already in progress for {model}.", "model": model}

        def _runner() -> None:
            result = self.install_story_model(model)
            final_status = {
                "ok": bool(result.get("ok", False)),
                "status": "installed" if result.get("ok", False) else "failed",
                "message": str(result.get("message", "Install finished.")),
                "details": result.get("details", ""),
                "readiness_refreshed": bool(result.get("readiness_refreshed", False)),
                "next_step": result.get("next_step"),
            }
            print(f"[model-install] completed model={model} status={final_status['status']}")
            self._record_model_install_status(model, final_status)

        self._record_model_install_status(model, {"ok": True, "status": "started", "message": f"Install queued for {model}."})
        thread = threading.Thread(target=_runner, daemon=True, name=f"model-install-{model_key}")
        thread.start()
        print(f"[model-install] thread-started model={model} thread={thread.name}")
        return {"ok": True, "status": "started", "message": f"Install started for {model}.", "model": model}

    def _refresh_readiness_snapshot(self) -> dict[str, Any]:
        print("[setup-orchestrator] readiness refresh triggered")
        return self.get_dependency_readiness()

    def install_ollama(self) -> dict[str, Any]:
        print("[setup-action] install-ollama requested")
        if not self._is_windows():
            reason = "windows-only flow"
            print(f"[setup-action] install-ollama failure reason={reason}")
            return {
                "ok": False,
                "message": "Automatic Ollama install is currently supported on Windows only.",
                "next_step": "Install Ollama manually from https://ollama.com/download.",
            }

        existing_cli = self._find_ollama_cli()
        if existing_cli:
            print(f"[setup-action] install-ollama success reason=already-installed cli={existing_cli}")
            started = self.start_ollama_service()
            return {
                "ok": True,
                "message": "Ollama is already installed.",
                "next_step": started.get("message", "Run `ollama serve` if it is not running."),
                "readiness_refreshed": True,
            }

        try:
            installer_url = self._resolve_ollama_windows_installer_url()
        except OSError as exc:
            print(f"[setup-action] install-ollama failure reason=resolve-url error={exc}")
            return {
                "ok": False,
                "message": "Could not resolve the official Ollama installer URL.",
                "next_step": "Open https://ollama.com/download and install manually.",
            }

        print(f"[setup-action] downloading installer url={installer_url}")
        installer_path = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
        try:
            with urllib.request.urlopen(installer_url, timeout=60) as response:
                installer_path.write_bytes(response.read())
        except OSError as exc:
            print(f"[setup-action] install-ollama failure reason=download error={exc}")
            return {
                "ok": False,
                "message": "Failed to download the Ollama installer.",
                "next_step": "Check your network connection and retry.",
            }
        print(f"[setup-action] installer saved path={installer_path}")

        try:
            process = subprocess.Popen([str(installer_path)])
            print("[setup-action] installer launched")
            process.wait(timeout=20 * 60)
        except PermissionError:
            reason = "permission denied"
            print(f"[setup-action] install-ollama failure reason={reason}")
            return {
                "ok": False,
                "message": "Installation requires admin privileges. Please run installer manually.",
                "next_step": f"Run {installer_path} as Administrator.",
            }
        except subprocess.TimeoutExpired:
            print("[setup-action] install-ollama failure reason=installer-timeout")
            return {
                "ok": False,
                "message": "Installer did not complete within the expected time.",
                "next_step": f"Finish installation manually from {installer_path}.",
            }
        except OSError as exc:
            print(f"[setup-action] install-ollama failure reason={exc}")
            return {
                "ok": False,
                "message": "Could not launch the Ollama installer.",
                "next_step": f"Run {installer_path} manually.",
            }

        ollama_cli = self._find_ollama_cli()
        if not ollama_cli:
            print("[setup-action] install-ollama failure reason=cli-not-found-after-install")
            return {
                "ok": False,
                "message": "Installer finished but Ollama CLI is still not detected.",
                "next_step": "Restart the app or terminal and click Recheck.",
            }

        start_result = self.start_ollama_service()
        if start_result.get("ok"):
            print("[setup-action] install-ollama success")
            return {
                "ok": True,
                "message": "Ollama installed and service started.",
                "readiness_refreshed": True,
            }
        print(f"[setup-action] install-ollama failure reason={start_result.get('message', 'service-start-failed')}")
        return {
            "ok": False,
            "message": "Ollama installed, but service did not start automatically.",
            "next_step": start_result.get("next_step", "Run `ollama serve`, then click Recheck."),
            "readiness_refreshed": True,
        }

    def start_ollama_service(self) -> dict[str, Any]:
        print("[setup-action] start-ollama requested")
        if self.app_config.model.provider != "ollama":
            print("[setup-action] start-ollama failure reason=model provider is not ollama")
            return {
                "ok": False,
                "message": "Model provider is not set to ollama.",
                "next_step": "Set model provider to ollama, then retry.",
            }
        if self.get_model_status().get("reachable", False):
            print("[setup-action] start-ollama success reason=already running")
            return {"ok": True, "message": "Ollama is already running."}
        ollama_cli = self._find_ollama_cli()
        if not ollama_cli:
            print("[setup-action] start-ollama failure reason=ollama cli not found")
            return {
                "ok": False,
                "message": "Ollama is not installed (CLI not found on PATH).",
                "next_step": "Install Ollama from https://ollama.com/download, then click Recheck.",
            }
        try:
            if os.name == "nt":
                subprocess.Popen(
                    [ollama_cli, "serve"],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    [ollama_cli, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except OSError as exc:
            print(f"[setup-action] start-ollama failure reason={exc}")
            return {
                "ok": False,
                "message": f"Could not start Ollama service: {exc}",
                "next_step": "Run `ollama serve` in your terminal, then click Recheck.",
            }
        for _ in range(6):
            time.sleep(0.5)
            if self.get_model_status().get("reachable", False):
                print("[setup-action] start-ollama success reason=service reachable")
                return {"ok": True, "message": "Ollama service started.", "readiness_refreshed": True}
        print("[setup-action] start-ollama failure reason=service not reachable after launch")
        return {
            "ok": False,
            "message": "Ollama start command was sent, but the service is still not reachable.",
            "next_step": "Open a terminal and run `ollama serve`, then click Recheck.",
        }

    def install_story_model(self, model_name: str | None = None) -> dict[str, Any]:
        model = (model_name or self.app_config.model.model_name or "llama3").strip()
        print(f"[setup-action] install-model requested model={model or '(empty)'}")
        print(f"[model-install] requested model={model or '(empty)'}")
        if not model:
            print("[setup-action] install-model failure reason=model name missing")
            result = {"ok": False, "status": "failed", "message": "Model name is required.", "model": model}
            self._record_model_install_status(model or "unknown", result)
            return result
        ollama_cli = self._find_ollama_cli()
        if not ollama_cli:
            print("[setup-action] install-model failure reason=ollama cli not found")
            result = {
                "ok": False,
                "status": "failed",
                "message": "Ollama is not installed (CLI not found on PATH).",
                "next_step": "Install Ollama from https://ollama.com/download first.",
                "model": model,
            }
            self._record_model_install_status(model, result)
            return result
        if not self.get_model_status().get("reachable", False):
            print("[setup-action] install-model failure reason=ollama service not reachable")
            result = {
                "ok": False,
                "status": "failed",
                "message": "Ollama is installed but not running.",
                "next_step": "Start Ollama first, then install the model.",
                "model": model,
            }
            self._record_model_install_status(model, result)
            return result
        self._record_model_install_status(model, {"ok": True, "status": "installing", "message": f"Installing {model}...", "model": model})
        print(f"[model-install] dispatch method=ollama_pull model={model} cli={ollama_cli}")
        pull_result = self._run_ollama_pull_with_logs(ollama_cli, model)
        if pull_result.get("timed_out"):
            print(f"[setup-action] install-model failure reason=timeout model={model}")
            result = {
                "ok": False,
                "status": "failed",
                "message": f"Model install timed out for {model}.",
                "next_step": f"Run `ollama pull {model}` manually, then click Recheck.",
                "details": pull_result.get("details", ""),
                "model": model,
            }
            self._record_model_install_status(model, result)
            return result
        if int(pull_result.get("returncode", 1)) != 0:
            print(f"[setup-action] install-model failure reason=exit_{pull_result.get('returncode')} model={model}")
            result = {
                "ok": False,
                "status": "failed",
                "message": f"Failed to install model {model}.",
                "details": pull_result.get("details", ""),
                "next_step": f"Run `ollama pull {model}` manually and retry.",
                "model": model,
            }
            self._record_model_install_status(model, result)
            return result
        print(f"[setup-action] install-model success model={model}")
        result = {
            "ok": True,
            "status": "installed",
            "message": "Story model installed. Text generation is ready.",
            "details": pull_result.get("details", ""),
            "readiness_refreshed": True,
            "model": model,
        }
        self._record_model_install_status(model, result)
        return result

    def orchestrate_setup_text_ai(self, model_name: str | None = None) -> dict[str, Any]:
        model = (model_name or self.app_config.model.model_name or "llama3").strip() or "llama3"
        print("[setup-orchestrator] setup-text requested")
        if self.app_config.model.provider != "ollama":
            print("[setup-orchestrator] setup-text step=provider-check failure")
            return {
                "ok": False,
                "message": "Text AI setup requires model provider set to ollama.",
                "next_step": "Set model provider to ollama, then click Set Up Text AI.",
                "summary": "Text AI failed: provider is not ollama.",
            }

        steps: list[dict[str, str]] = []
        if not self._find_ollama_cli():
            print("[setup-orchestrator] setup-text step=install-ollama start")
            result = self.install_ollama()
            if result.get("ok"):
                print("[setup-orchestrator] setup-text step=install-ollama success")
                steps.append({"step": "install-ollama", "state": "ready", "message": str(result.get("message", "Ollama installed."))})
                self._refresh_readiness_snapshot()
            else:
                print("[setup-orchestrator] setup-text step=install-ollama failure")
                steps.append({"step": "install-ollama", "state": "failed", "message": str(result.get("message", "Failed to install Ollama."))})
                return {"ok": False, "message": str(result.get("message", "Failed to install Ollama.")), "next_step": result.get("next_step"), "steps": steps, "summary": "Text AI failed during install-ollama."}

        if not self.get_model_status().get("reachable", False):
            print("[setup-orchestrator] setup-text step=start-ollama start")
            result = self.start_ollama_service()
            if result.get("ok"):
                print("[setup-orchestrator] setup-text step=start-ollama success")
                steps.append({"step": "start-ollama", "state": "ready", "message": str(result.get("message", "Ollama started."))})
                self._refresh_readiness_snapshot()
            else:
                print("[setup-orchestrator] setup-text step=start-ollama failure")
                steps.append({"step": "start-ollama", "state": "failed", "message": str(result.get("message", "Failed to start Ollama."))})
                return {"ok": False, "message": str(result.get("message", "Failed to start Ollama.")), "next_step": result.get("next_step"), "steps": steps, "summary": "Text AI failed during start-ollama."}

        model_status = self.get_model_status()
        if not model_status.get("model_exists", False):
            print("[setup-orchestrator] setup-text step=install-model start")
            result = self.install_story_model(model)
            if result.get("ok"):
                print("[setup-orchestrator] setup-text step=install-model success")
                steps.append({"step": "install-model", "state": "ready", "message": str(result.get("message", "Story model installed."))})
                self._refresh_readiness_snapshot()
            else:
                print("[setup-orchestrator] setup-text step=install-model failure")
                steps.append({"step": "install-model", "state": "failed", "message": str(result.get("message", "Failed to install story model."))})
                return {"ok": False, "message": str(result.get("message", "Failed to install story model.")), "next_step": result.get("next_step"), "steps": steps, "summary": "Text AI failed during install-model."}

        final_status = self.get_model_status()
        ready = bool(final_status.get("reachable", False) and final_status.get("model_exists", False))
        summary = "Text AI ready." if ready else "Text AI failed: readiness check did not pass."
        return {
            "ok": ready,
            "message": "Text AI setup complete." if ready else "Text AI setup did not complete.",
            "steps": steps,
            "summary": summary,
            "readiness": self._refresh_readiness_snapshot(),
            "next_step": None if ready else f"Run: ollama pull {model}",
        }

    def orchestrate_setup_image_ai(self) -> dict[str, Any]:
        print("[setup-orchestrator] setup-image requested")
        if self.app_config.image.provider != "comfyui":
            print("[setup-orchestrator] setup-image step=provider-check failure")
            return {
                "ok": False,
                "message": "Image AI setup requires image provider set to comfyui.",
                "next_step": "Set image provider to comfyui, then click Set Up Image AI.",
                "summary": "Image AI failed: provider is not comfyui.",
            }
        steps: list[dict[str, str]] = []
        if self._find_comfyui_root() is None:
            print("[setup-orchestrator] setup-image step=install-image-engine start")
            result = self.install_image_engine()
            if result.get("ok"):
                print("[setup-orchestrator] setup-image step=install-image-engine success")
                steps.append({"step": "install-image-engine", "state": "ready", "message": str(result.get("message", "ComfyUI installed."))})
                self._refresh_readiness_snapshot()
            else:
                print("[setup-orchestrator] setup-image step=install-image-engine failure")
                steps.append({"step": "install-image-engine", "state": "failed", "message": str(result.get("message", "Failed to install image engine."))})
                return {"ok": False, "message": str(result.get("message", "Failed to install image engine.")), "next_step": result.get("next_step"), "steps": steps, "summary": "Image AI failed during install-image-engine."}

        if not self.get_image_status().get("reachable", False):
            print("[setup-orchestrator] setup-image step=start-image-engine start")
            result = self.start_image_engine()
            if result.get("ok"):
                print("[setup-orchestrator] setup-image step=start-image-engine success")
                steps.append({"step": "start-image-engine", "state": "ready", "message": str(result.get("message", "ComfyUI started."))})
                self._refresh_readiness_snapshot()
            else:
                print("[setup-orchestrator] setup-image step=start-image-engine failure")
                steps.append({"step": "start-image-engine", "state": "failed", "message": str(result.get("message", "Failed to start image engine."))})
                return {"ok": False, "message": str(result.get("message", "Failed to start image engine.")), "next_step": result.get("next_step"), "steps": steps, "summary": "Image AI failed during start-image-engine."}

        ready = bool(self.get_image_status().get("reachable", False))
        return {
            "ok": ready,
            "message": "Image AI setup complete." if ready else "Image AI setup did not complete.",
            "steps": steps,
            "summary": "Image AI ready." if ready else "Image AI failed: readiness check did not pass.",
            "readiness": self._refresh_readiness_snapshot(),
        }

    def orchestrate_setup_everything(self, model_name: str | None = None) -> dict[str, Any]:
        print("[setup-orchestrator] setup-everything requested")
        text_result = self.orchestrate_setup_text_ai(model_name)
        if not text_result.get("ok"):
            return {
                "ok": False,
                "message": "Setup Everything stopped during Text AI setup.",
                "text": text_result,
                "image": None,
                "summary": f"Text AI failed: {text_result.get('message', 'unknown error')}",
            }
        image_result = self.orchestrate_setup_image_ai()
        if not image_result.get("ok"):
            return {
                "ok": False,
                "message": "Setup Everything stopped during Image AI setup.",
                "text": text_result,
                "image": image_result,
                "summary": f"Text AI ready. Image AI failed: {image_result.get('message', 'unknown error')}",
            }
        return {
            "ok": True,
            "message": "Setup Everything complete.",
            "text": text_result,
            "image": image_result,
            "summary": "Text AI ready. Image AI ready.",
            "readiness": self._refresh_readiness_snapshot(),
        }

    def _default_comfyui_path(self) -> Path:
        return self.paths.user_data / "tools" / "ComfyUI"

    def validate_comfyui_install(self, path: Path) -> dict[str, Any]:
        missing_files: list[str] = []
        if not (path / "main.py").exists():
            missing_files.append("main.py")
        if not (path / "custom_nodes").exists():
            missing_files.append("custom_nodes/")
        if not (path / "models").exists():
            missing_files.append("models/")
        if not ((path / "run_cpu.bat").exists() or (path / "run_nvidia_gpu.bat").exists()):
            missing_files.append("run_cpu.bat|run_nvidia_gpu.bat")
        if os.name == "nt":
            embedded_python = path.parent / "python_embeded" / "python.exe"
            if not embedded_python.exists() and not shutil.which("python") and not shutil.which("py"):
                missing_files.append("python-runtime")
        valid = len(missing_files) == 0
        return {"ok": valid, "valid": valid, "missing_files": missing_files}

    def _write_comfyui_cpu_launcher(self, comfyui_root: Path) -> bool:
        launcher = comfyui_root / "run_cpu.bat"
        embedded_python = comfyui_root.parent / "python_embeded" / "python.exe"
        if embedded_python.exists():
            command = "..\\python_embeded\\python.exe main.py"
        else:
            command = "python main.py"
        content = f"@echo off\r\ncd /d %~dp0\r\n{command}\r\npause\r\n"
        try:
            launcher.write_text(content, encoding="utf-8")
            print("[setup-orchestrator] comfyui install repair reason=created-missing-launcher")
            return True
        except OSError as exc:
            print(f"[setup-orchestrator] comfyui install repair failure reason={exc}")
            return False

    def _append_image_startup_log(self, lines: list[str], message: str) -> None:
        if message:
            lines.append(f"{datetime.now(timezone.utc).isoformat()} | {message}")

    def _sanitize_image_startup_log(self, lines: list[str], max_lines: int = 120, max_chars: int = 6000) -> str:
        safe_lines = [line.replace("\r", "").strip() for line in lines if line and line.strip()]
        if len(safe_lines) > max_lines:
            safe_lines = safe_lines[-max_lines:]
        text = "\n".join(safe_lines)
        if len(text) > max_chars:
            text = f"...(trimmed)\n{text[-max_chars:]}"
        return text

    def _read_startup_log_tail(self, startup_log_path: Path, max_lines: int = 80) -> list[str]:
        if not startup_log_path.exists():
            return []
        try:
            lines = startup_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
        except OSError:
            return []

    def _detect_runtime_error(self, startup_log_text: str) -> str:
        lowered = startup_log_text.lower()
        markers = [
            "modulenotfounderror",
            "traceback (most recent call last)",
            "runtimeerror",
            "error:",
            "failed to import",
            "no module named",
        ]
        for marker in markers:
            if marker in lowered:
                return marker
        return ""

    def _extract_comfyui_bind_urls(self, startup_log_text: str) -> list[str]:
        candidates = re.findall(r"(https?://[0-9a-zA-Z\.\-_:]+)", startup_log_text)
        return sorted(set(candidates))

    def _download_and_extract_comfyui(self, target_dir: Path) -> tuple[bool, str]:
        archive_path = Path(tempfile.gettempdir()) / "ComfyUI-master.zip"
        repo_url = "https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip"
        print(f"[setup-action] install-image-engine bootstrap-download url={repo_url}")
        try:
            with urllib.request.urlopen(repo_url, timeout=60) as response:
                archive_path.write_bytes(response.read())
            with zipfile.ZipFile(archive_path, "r") as archive:
                extract_root = target_dir.parent / "ComfyUI-master"
                if extract_root.exists():
                    shutil.rmtree(extract_root, ignore_errors=True)
                archive.extractall(target_dir.parent)
            extracted = target_dir.parent / "ComfyUI-master"
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            extracted.rename(target_dir)
            return True, "ok"
        except OSError as exc:
            print(f"[setup-action] install-image-engine failure reason={exc}")
            return False, "Failed to download or unpack ComfyUI bootstrap files."
        except zipfile.BadZipFile:
            print("[setup-action] install-image-engine failure reason=invalid-archive")
            return False, "ComfyUI archive download was invalid."

    def _find_comfyui_root(self) -> Path | None:
        candidates: list[Path] = []
        configured = str(self.app_config.image.comfyui_path or "").strip()
        if configured:
            candidates.append(Path(configured))
        default_managed = self._default_comfyui_path()
        if default_managed.exists():
            candidates.append(default_managed)
        for candidate in candidates:
            if (candidate / "main.py").exists():
                return candidate
        return None

    def _validate_comfyui_root_config(self, configured_path: str) -> dict[str, Any]:
        raw = str(configured_path or "").strip()
        if not raw:
            print("[path-config] comfyui_root configured=false")
            return {"configured": False, "valid": False, "path": "", "message": "Set your ComfyUI folder."}
        candidate = Path(raw)
        if not candidate.exists() or not candidate.is_dir():
            print("[path-config] comfyui_root valid=false")
            return {"configured": True, "valid": False, "path": raw, "message": "This path does not exist."}
        validation = self.validate_comfyui_install(candidate)
        if not validation.get("ok", False):
            missing = ", ".join(validation.get("missing_files", []))
            print("[path-config] comfyui_root valid=false")
            return {
                "configured": True,
                "valid": False,
                "path": raw,
                "message": f"This folder is missing {missing}.",
                "missing_files": validation.get("missing_files", []),
            }
        print("[path-config] comfyui_root valid=true")
        return {"configured": True, "valid": True, "path": str(candidate), "message": "ComfyUI folder is valid."}

    def _validate_workflow_path_config(self, configured_path: str) -> dict[str, Any]:
        raw = str(configured_path or "").strip()
        if not raw:
            print("[path-config] workflow_path configured=false")
            return {"configured": False, "valid": False, "path": "", "message": "Set your workflow file (.json)."}
        candidate = Path(raw)
        if not candidate.exists() or not candidate.is_file():
            print("[path-config] workflow_path valid=false")
            return {"configured": True, "valid": False, "path": raw, "message": "Workflow path does not exist."}
        if candidate.suffix.lower() != ".json":
            print("[path-config] workflow_path valid=false")
            return {"configured": True, "valid": False, "path": raw, "message": "Workflow file must be a .json file."}
        print("[path-config] workflow_path valid=true")
        return {"configured": True, "valid": True, "path": str(candidate), "message": "Workflow path is valid."}

    def _validate_output_dir_config(self, configured_path: str) -> dict[str, Any]:
        raw = str(configured_path or "").strip()
        if not raw:
            return {
                "configured": False,
                "valid": True,
                "path": "",
                "resolved_path": str(self.generated_image_dir),
                "message": "Using app-managed generated images folder.",
            }
        candidate = Path(raw)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            return {"configured": True, "valid": False, "path": raw, "message": "Output folder does not exist and cannot be created."}
        return {"configured": True, "valid": True, "path": str(candidate), "resolved_path": str(candidate), "message": "Output folder is valid."}

    def _validate_checkpoint_dir_config(self, configured_path: str, comfyui_path: str = "") -> dict[str, Any]:
        raw = str(configured_path or "").strip()
        if not raw:
            comfy_root = Path(str(comfyui_path or "").strip()) if str(comfyui_path or "").strip() else None
            inferred = (comfy_root / "models" / "checkpoints") if comfy_root else None
            if inferred and inferred.exists() and inferred.is_dir():
                return {
                    "configured": False,
                    "valid": True,
                    "path": "",
                    "resolved_path": str(inferred),
                    "message": "Using ComfyUI default checkpoints folder.",
                }
            return {"configured": False, "valid": False, "path": "", "message": "Checkpoint folder is required."}
        candidate = Path(raw)
        if not candidate.exists() or not candidate.is_dir():
            return {"configured": True, "valid": False, "path": raw, "message": "Folder not found."}
        return {"configured": True, "valid": True, "path": str(candidate), "resolved_path": str(candidate), "message": "Checkpoint folder is valid."}

    def get_path_configuration_status(self) -> dict[str, Any]:
        comfyui_root = self._validate_comfyui_root_config(self.app_config.image.comfyui_path)
        workflow_path = self._validate_workflow_path_config(self.app_config.image.comfyui_workflow_path)
        output_dir = self._validate_output_dir_config(self.app_config.image.comfyui_output_dir)
        checkpoint_dir = self._validate_checkpoint_dir_config(
            self.app_config.image.checkpoint_folder,
            self.app_config.image.comfyui_path,
        )
        pipeline_ready = bool(comfyui_root["valid"] and workflow_path["valid"] and checkpoint_dir["valid"] and output_dir["valid"])
        return {
            "image": {
                "comfyui_root": comfyui_root,
                "workflow_path": workflow_path,
                "checkpoint_dir": checkpoint_dir,
                "output_dir": output_dir,
                "pipeline_ready": pipeline_ready,
            }
        }

    def validate_visual_pipeline_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        comfyui_path = str(payload.get("comfyui_path", "")).strip()
        workflow_path = str(payload.get("comfyui_workflow_path", "")).strip()
        output_dir = str(payload.get("comfyui_output_dir", "")).strip()
        checkpoint_folder = str(payload.get("checkpoint_folder", "")).strip()
        print("[path-config] apply_requested")
        status = {
            "image": {
                "comfyui_root": self._validate_comfyui_root_config(comfyui_path),
                "workflow_path": self._validate_workflow_path_config(workflow_path),
                "output_dir": self._validate_output_dir_config(output_dir),
                "checkpoint_dir": self._validate_checkpoint_dir_config(checkpoint_folder, comfyui_path),
            }
        }
        image_status = status["image"]
        image_status["pipeline_ready"] = bool(
            image_status["comfyui_root"]["valid"]
            and image_status["workflow_path"]["valid"]
            and image_status["output_dir"]["valid"]
            and image_status["checkpoint_dir"]["valid"]
        )
        return status

    def apply_visual_pipeline_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        path_config = self.validate_visual_pipeline_config(payload)
        image_status = path_config["image"]
        field_map = {
            "comfyui_root": "comfyui_path",
            "workflow_path": "comfyui_workflow_path",
            "checkpoint_dir": "checkpoint_folder",
            "output_dir": "comfyui_output_dir",
        }
        invalid_key = next((key for key, item in image_status.items() if isinstance(item, dict) and not item.get("valid", False)), None)
        if invalid_key:
            reason = image_status[invalid_key].get("message", "invalid")
            print(f"[path-config] apply_failed field={field_map.get(invalid_key, invalid_key)} reason={reason}")
            return {
                "ok": False,
                "message": f"Visual pipeline settings are invalid: {reason}",
                "error_field": field_map.get(invalid_key, invalid_key),
                "path_config": path_config,
            }
        self.app_config.image.comfyui_path = str(payload.get("comfyui_path", self.app_config.image.comfyui_path)).strip()
        self.app_config.image.comfyui_workflow_path = str(
            payload.get("comfyui_workflow_path", self.app_config.image.comfyui_workflow_path)
        ).strip()
        self.app_config.image.comfyui_output_dir = str(payload.get("comfyui_output_dir", self.app_config.image.comfyui_output_dir)).strip()
        self.app_config.image.checkpoint_folder = str(payload.get("checkpoint_folder", self.app_config.image.checkpoint_folder)).strip()
        self.config_store.save(self.app_config)
        self.image_adapter = self._create_image_adapter()
        print("[path-config] apply_succeeded")
        print("[path-config] runtime_config_reloaded")
        return {"ok": True, "message": "Visual pipeline settings applied.", "path_config": self.get_path_configuration_status()}

    def install_image_engine(self) -> dict[str, Any]:
        print("[setup-action] install-image-engine requested")
        if not self._is_windows():
            reason = "windows-only flow"
            print(f"[setup-action] install-image-engine failure reason={reason}")
            return {
                "ok": False,
                "message": "Automatic ComfyUI setup is currently supported on Windows only.",
                "next_step": "Install ComfyUI manually and set image provider to comfyui.",
            }
        existing = self._find_comfyui_root()
        if existing is not None:
            validation = self.validate_comfyui_install(existing)
            if validation.get("ok"):
                print(f"[setup-action] install-image-engine success reason=already-installed path={existing}")
                self.app_config.image.comfyui_path = str(existing)
                self.config_store.save(self.app_config)
                return {"ok": True, "message": "ComfyUI is already installed.", "readiness_refreshed": True}
            print(f"[setup-orchestrator] comfyui install repair reason=existing-install-invalid missing={validation.get('missing_files')}")
        target_dir = self._default_comfyui_path()
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        print("[setup-orchestrator] comfyui install start")
        ok, install_message = self._download_and_extract_comfyui(target_dir)
        if not ok:
            return {
                "ok": False,
                "message": install_message,
                "next_step": "Open https://github.com/comfyanonymous/ComfyUI and install manually.",
            }
        validation = self.validate_comfyui_install(target_dir)
        if not validation.get("ok"):
            print("[setup-orchestrator] comfyui install repair")
            if "run_cpu.bat|run_nvidia_gpu.bat" in validation.get("missing_files", []):
                self._write_comfyui_cpu_launcher(target_dir)
            validation = self.validate_comfyui_install(target_dir)
            if not validation.get("ok"):
                return {
                    "ok": False,
                    "message": f"ComfyUI install is incomplete: missing {', '.join(validation.get('missing_files', []))}.",
                    "next_step": "Retry installation, or install manually from the official repository.",
                }
        self.app_config.image.comfyui_path = str(target_dir)
        self.config_store.save(self.app_config)
        webbrowser.open("https://github.com/comfyanonymous/ComfyUI")
        print("[setup-orchestrator] comfyui install success")
        print("[setup-action] install-image-engine success")
        return {
            "ok": True,
            "message": "ComfyUI install verified and ready to launch.",
            "next_step": "Install Python dependencies in ComfyUI, then click Start Image Engine.",
            "readiness_refreshed": True,
        }

    def start_image_engine(self) -> dict[str, Any]:
        print("[setup-action] start-image-engine requested")
        startup_log_lines: list[str] = []
        startup_log_file = self.paths.logs / "image_engine_startup.log"
        startup_log_file.parent.mkdir(parents=True, exist_ok=True)
        self.image_startup_status = {}
        if self.app_config.image.provider != "comfyui":
            print("[setup-action] start-image-engine failure reason=image provider is not comfyui")
            return {
                "ok": False,
                "message": "Image provider is not set to comfyui.",
                "next_step": "Set image provider to comfyui, then retry.",
                "failure_stage": "provider-check",
                "failure_stage_message": "image provider is not comfyui",
                "steps": [{"step": "provider-check", "state": "failed", "message": "Image provider is not set to comfyui."}],
            }
        path_config = self.get_path_configuration_status().get("image", {})
        if not bool(path_config.get("workflow_path", {}).get("configured")):
            return {
                "ok": False,
                "message": "Workflow JSON is not configured.",
                "next_step": "Set workflow JSON in Visual Pipeline settings and click Apply Visual Pipeline Settings.",
                "failure_stage": "path-check",
                "failure_stage_message": "workflow json missing",
                "steps": [{"step": "path-check", "state": "failed", "message": "Workflow JSON is not configured."}],
            }
        if not bool(path_config.get("workflow_path", {}).get("valid")):
            return {
                "ok": False,
                "message": "Workflow JSON path is invalid.",
                "next_step": "Choose a valid workflow .json file and apply settings.",
                "failure_stage": "path-check",
                "failure_stage_message": "workflow json invalid",
                "steps": [{"step": "path-check", "state": "failed", "message": "Configured workflow file does not exist."}],
            }
        if self.get_image_status().get("reachable", False):
            print("[setup-action] start-image-engine success reason=already running")
            self.image_startup_status = {
                "stage": "wait-for-readiness",
                "reason": "already-reachable",
                "summary": "ComfyUI is already running.",
                "log_text": "",
                "log_available": False,
                "log_file": str(startup_log_file),
            }
            return {
                "ok": True,
                "message": "ComfyUI is already running.",
                "steps": [{"step": "wait-for-readiness", "state": "ready", "message": "Engine is already reachable."}],
            }
        print("[setup-orchestrator] setup-image step=detect-install-path")
        comfyui_root = self._find_comfyui_root()
        if comfyui_root is None:
            print("[setup-action] start-image-engine failure reason=install-path-missing")
            print("[setup-orchestrator] setup-image failure stage=detect-install-path")
            return {
                "ok": False,
                "message": "ComfyUI install path was not found.",
                "next_step": "Install Image Engine first.",
                "failure_stage": "detect-install-path",
                "failure_stage_message": "install path missing",
                "steps": [{"step": "detect-install-path", "state": "failed", "message": "ComfyUI install path was not found."}],
            }
        self.app_config.image.comfyui_path = str(comfyui_root)
        self.config_store.save(self.app_config)
        self._append_image_startup_log(startup_log_lines, f"Using install path: {comfyui_root}")
        print("[setup-orchestrator] setup-image step=verify-install")
        validation = self.validate_comfyui_install(comfyui_root)
        if not validation.get("ok"):
            print("[setup-orchestrator] setup-image step=repair-install")
            self.install_image_engine()
            comfyui_root = self._find_comfyui_root()
            if comfyui_root is None:
                return {
                    "ok": False,
                    "message": "ComfyUI install could not be repaired.",
                    "next_step": "Re-run install or install ComfyUI manually.",
                    "failure_stage": "launch-engine",
                    "failure_stage_message": "launcher script missing and could not be repaired",
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": "Install path was found."},
                        {"step": "verify-install", "state": "failed", "message": f"Missing files: {', '.join(validation.get('missing_files', []))}"},
                    ],
                }
            self.app_config.image.comfyui_path = str(comfyui_root)
            self.config_store.save(self.app_config)
            validation = self.validate_comfyui_install(comfyui_root)
        if not validation.get("ok"):
            missing_files = list(validation.get("missing_files", []))
            unresolved = [item for item in missing_files if item != "run_cpu.bat|run_nvidia_gpu.bat"]
            if unresolved:
                missing = ", ".join(unresolved)
                return {
                    "ok": False,
                    "message": f"ComfyUI install is incomplete: missing {missing}.",
                    "next_step": "Repair the install/runtime, then retry Start Image Engine.",
                    "failure_stage": "verify-install",
                    "failure_stage_message": "required files/runtime missing",
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                        {"step": "verify-install", "state": "failed", "message": f"Missing: {missing}"},
                    ],
                }
        nvidia_script = comfyui_root / "run_nvidia_gpu.bat"
        generic_gpu_script = comfyui_root / "run_gpu.bat"
        amd_gpu_script = comfyui_root / "run_amd_gpu.bat"
        cpu_script = comfyui_root / "run_cpu.bat"
        if not cpu_script.exists():
            print("[setup-orchestrator] setup-image step=repair-launcher")
            self._write_comfyui_cpu_launcher(comfyui_root)
            cpu_script = comfyui_root / "run_cpu.bat"
            validation = self.validate_comfyui_install(comfyui_root)
        launcher_order = [nvidia_script, generic_gpu_script, amd_gpu_script, cpu_script]
        launcher_script = next((script for script in launcher_order if script.exists()), comfyui_root / "main.py")
        launcher = launcher_script
        if os.name == "nt" and launcher_script == comfyui_root / "main.py":
            print("[setup-action] start-image-engine failure reason=launcher-script-missing")
            print("[setup-orchestrator] setup-image failure stage=launch-engine")
            return {
                "ok": False,
                "message": "ComfyUI launcher script was not found (run_nvidia_gpu.bat / run_cpu.bat).",
                "next_step": "Restore ComfyUI launcher scripts or reinstall ComfyUI, then click Recheck.",
                "failure_stage": "launch-engine",
                "failure_stage_message": "launcher script missing and could not be repaired",
                "steps": [
                    {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                    {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                    {"step": "repair-launcher", "state": "failed", "message": "Launcher script missing and could not be repaired."},
                    {"step": "launch-engine", "state": "failed", "message": "Launcher script missing."},
                ],
            }
        print("[setup-orchestrator] setup-image step=launch-engine")
        process: subprocess.Popen[str] | None = None
        try:
            if os.name == "nt" and launcher_script.exists() and launcher_script.suffix == ".bat":
                self._append_image_startup_log(startup_log_lines, f"Launching script: {launcher_script.name}")
                with startup_log_file.open("w", encoding="utf-8") as handle:
                    handle.write("")
                process = subprocess.Popen(
                    [
                        "cmd.exe",
                        "/c",
                        f"\"{launcher_script}\" 1>>\"{startup_log_file}\" 2>&1",
                    ],
                    cwd=str(comfyui_root),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
                )
            else:
                python_exe = shutil.which("python") or shutil.which("py")
                if not python_exe:
                    print("[setup-action] start-image-engine failure reason=python-not-found")
                    print("[setup-orchestrator] setup-image failure stage=launch-engine")
                    return {
                        "ok": False,
                        "message": "Python was not found on PATH.",
                        "next_step": "Install Python and retry, or start ComfyUI manually.",
                        "failure_stage": "launch-engine",
                        "failure_stage_message": "process launch failed",
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                        {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                        {"step": "launch-engine", "state": "failed", "message": "Python executable not found on PATH."},
                    ],
                }
                command = [python_exe, "main.py"]
                self._append_image_startup_log(startup_log_lines, f"Launching command: {' '.join(command)}")
                process = subprocess.Popen(
                    command,
                    cwd=str(comfyui_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
        except OSError as exc:
            print(f"[setup-action] start-image-engine failure reason={exc}")
            print("[setup-orchestrator] setup-image failure stage=launch-engine")
            return {
                "ok": False,
                "message": f"Could not start ComfyUI: {exc}",
                "next_step": "Start ComfyUI manually, then click Recheck.",
                "failure_stage": "launch-engine",
                "failure_stage_message": "process launch failed",
                "steps": [
                    {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                    {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                    {"step": "launch-engine", "state": "failed", "message": f"Process launch failed: {exc}"},
                ],
            }
        if process is None:
            return {"ok": False, "message": "ComfyUI process launch did not initialize.", "failure_stage": "launch-engine", "failure_stage_message": "process launch failed"}
        print(f"[setup-action] start-image-engine launch command={launcher}")
        print("[setup-orchestrator] setup-image step=wait-for-readiness")
        expected_base = self.app_config.image.base_url
        expected = urlparse(expected_base)
        for _ in range(20):
            time.sleep(0.75)
            if process.poll() is not None:
                if getattr(process, "stdout", None) is not None:
                    try:
                        captured, _ = process.communicate(timeout=0.2)
                        if captured:
                            startup_log_lines.extend(str(captured).splitlines()[-80:])
                    except (OSError, subprocess.SubprocessError):
                        pass
                tail_lines = self._read_startup_log_tail(startup_log_file)
                startup_log_lines.extend(tail_lines)
                startup_log_text = self._sanitize_image_startup_log(startup_log_lines)
                runtime_error = self._detect_runtime_error(startup_log_text)
                self.image_startup_status = {
                    "stage": "wait-for-readiness",
                    "reason": "process-exited-immediately",
                    "summary": "Image AI failed: ComfyUI exited during startup.",
                    "runtime_error_hint": runtime_error,
                    "log_text": startup_log_text,
                    "log_available": bool(startup_log_text),
                    "log_file": str(startup_log_file),
                }
                return {
                    "ok": False,
                    "message": "Image AI failed: ComfyUI exited during startup.",
                    "next_step": "Open setup details to review startup log and fix the runtime/dependency issue.",
                    "failure_stage": "wait-for-readiness",
                    "failure_stage_message": "ComfyUI exited during startup",
                    "startup_status": self.image_startup_status,
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                        {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                        {"step": "repair-launcher", "state": "ready", "message": "Launcher verified or repaired."},
                        {"step": "launch-engine", "state": "ready", "message": "ComfyUI launch command sent."},
                        {"step": "wait-for-readiness", "state": "failed", "message": "ComfyUI process exited before readiness endpoint was reachable."},
                    ],
                }
            if self.get_image_status().get("reachable", False):
                print("[setup-action] start-image-engine success")
                self.image_startup_status = {
                    "stage": "wait-for-readiness",
                    "reason": "ready",
                    "summary": "ComfyUI started and is reachable.",
                    "log_text": self._sanitize_image_startup_log(startup_log_lines + self._read_startup_log_tail(startup_log_file)),
                    "log_available": True,
                    "log_file": str(startup_log_file),
                }
                return {
                    "ok": True,
                    "message": "ComfyUI started and is reachable.",
                    "readiness_refreshed": True,
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                        {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                        {"step": "repair-launcher", "state": "ready", "message": "Launcher verified or repaired."},
                        {"step": "launch-engine", "state": "ready", "message": "ComfyUI launch command sent."},
                        {"step": "wait-for-readiness", "state": "ready", "message": "ComfyUI responded to readiness probe."},
                    ],
                }
        tail_lines = self._read_startup_log_tail(startup_log_file)
        if getattr(process, "stdout", None) is not None:
            try:
                captured, _ = process.communicate(timeout=0.2)
                if captured:
                    startup_log_lines.extend(str(captured).splitlines()[-80:])
            except (OSError, subprocess.SubprocessError):
                pass
        startup_log_lines.extend(tail_lines)
        startup_log_text = self._sanitize_image_startup_log(startup_log_lines)
        bound_urls = self._extract_comfyui_bind_urls(startup_log_text)
        runtime_error = self._detect_runtime_error(startup_log_text)
        reason = "timeout-waiting-for-comfyui"
        message = "ComfyUI launch command was sent, but readiness timed out."
        stage_message = "timeout waiting for ComfyUI"
        if runtime_error:
            reason = "runtime-error-in-launcher-output"
            message = "Image AI failed: launcher output reported a runtime/dependency error."
            stage_message = "runtime/dependency error in launcher output"
        elif bound_urls and not any(expected.netloc in url for url in bound_urls):
            reason = "bound-to-unexpected-address"
            message = "Image AI failed: ComfyUI appears to be running on a different address/port."
            stage_message = "ComfyUI bound to unexpected address/port"
        else:
            message = "Image AI failed: ComfyUI is still running but not reachable yet."
            stage_message = "ComfyUI still running but not reachable"
        self.image_startup_status = {
            "stage": "wait-for-readiness",
            "reason": reason,
            "summary": message,
            "runtime_error_hint": runtime_error,
            "detected_bind_urls": bound_urls,
            "expected_base_url": expected_base,
            "log_text": startup_log_text,
            "log_available": bool(startup_log_text),
            "log_file": str(startup_log_file),
        }
        print("[setup-action] start-image-engine failure reason=timeout-waiting-for-comfyui")
        print("[setup-orchestrator] setup-image failure stage=wait-for-readiness")
        return {
            "ok": False,
            "message": message,
            "next_step": "Wait for startup to finish, then click Recheck.",
            "failure_stage": "wait-for-readiness",
            "failure_stage_message": stage_message,
            "startup_status": self.image_startup_status,
            "steps": [
                {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                {"step": "repair-launcher", "state": "ready", "message": "Launcher verified or repaired."},
                {"step": "launch-engine", "state": "ready", "message": "ComfyUI launch command sent."},
                {"step": "wait-for-readiness", "state": "failed", "message": "Process launched but readiness check failed before timeout window closed."},
            ],
        }

    def _create_image_adapter(self) -> ImageGeneratorAdapter:
        cfg = self.app_config.image
        if not cfg.enabled:
            return NullImageAdapter()
        if cfg.provider == "comfyui":
            return ComfyUIAdapter(base_url=cfg.base_url, output_dir=self.generated_image_dir)
        if cfg.provider == "local" and self.workflow_manager.list_templates():
            return LocalPlaceholderImageAdapter(self.generated_image_dir)
        return NullImageAdapter()

    def _message(self, message_type: str, text: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "id": f"m_{len(self.session.message_history) + 1}",
            "type": self._normalize_message_type(message_type, text),
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload.update(extra)
        return payload

    def _append_message(self, message_type: str, text: str, persist: bool = True, **extra: Any) -> None:
        entry = self._message(message_type, text, **extra)
        with self._history_lock:
            self.session.message_history.append(entry)
            self.history_store[self._campaign_namespace(self.session.active_slot)] = self.session.message_history
            if persist:
                self._persist_history_store()

    def _flush_history_store(self) -> None:
        with self._history_lock:
            self.history_store[self._campaign_namespace(self.session.active_slot)] = self.session.message_history
            self._persist_history_store()

    def _normalize_message_type(self, message_type: str, text: str) -> str:
        if message_type in {"player", "narrator", "npc", "quest", "image", "system", "error"}:
            return message_type
        lowered = text.lower()
        if "quest" in lowered:
            return "quest"
        if lowered.startswith('"') or "relationship tier" in lowered:
            return "npc"
        return "system"

    def serialize_state(self) -> dict[str, Any]:
        state = self.session.state
        return {
            "campaign_id": state.campaign_id,
            "campaign_name": state.campaign_name,
            "turn_count": state.turn_count,
            "current_location_id": state.current_location_id,
            "player": {
                "name": state.player.name,
                "class": state.player.char_class,
                "role": state.player.role,
                "archetype": state.player.archetype,
                "hp": state.player.hp,
                "max_hp": state.player.max_hp,
                "energy_or_mana": state.player.energy_or_mana,
                "attack": state.player.attack_bonus,
                "defense": state.player.defense,
                "speed": state.player.speed,
                "magic": state.player.magic,
                "willpower": state.player.willpower,
                "presence": state.player.presence,
                "classic_attributes": state.player.classic_attributes,
            },
            "active_enemy_id": state.active_enemy_id,
            "active_enemy_hp": state.active_enemy_hp,
            "faction_reputation": state.faction_reputation,
            "quest_status": {qid: quest.status for qid, quest in state.quests.items()},
            "conversation_turn_count": len(state.conversation_turns),
            "settings": {
                "profile": state.settings.profile,
                "narration_tone": state.settings.narration_tone,
                "mature_content_enabled": state.settings.mature_content_enabled,
                "image_generation_enabled": state.settings.image_generation_enabled,
                "suggested_moves_enabled": state.settings.suggested_moves_enabled,
                "display_mode": state.settings.display_mode,
                "player_suggested_moves_override": state.settings.player_suggested_moves_override,
                "effective_suggested_moves_enabled": state.settings.suggested_moves_active(),
                "content_settings": {
                    "tone": state.settings.content_settings.tone,
                    "maturity_level": state.settings.content_settings.maturity_level,
                    "thematic_flags": state.settings.content_settings.thematic_flags,
                },
                "play_style": {
                    "allow_freeform_powers": state.settings.play_style.allow_freeform_powers,
                    "auto_update_character_sheet_from_actions": state.settings.play_style.auto_update_character_sheet_from_actions,
                    "strict_sheet_enforcement": state.settings.play_style.strict_sheet_enforcement,
                    "auto_sync_player_declared_identity": state.settings.play_style.auto_sync_player_declared_identity,
                    "auto_generate_npc_personalities": state.settings.play_style.auto_generate_npc_personalities,
                    "auto_evolve_npc_personalities": state.settings.play_style.auto_evolve_npc_personalities,
                    "reactive_world_persistence": state.settings.play_style.reactive_world_persistence,
                    "narration_format_mode": state.settings.play_style.narration_format_mode,
                    "scene_visual_mode": state.settings.play_style.scene_visual_mode,
                },
            },
            "world_meta": {
                "world_name": state.world_meta.world_name,
                "world_theme": state.world_meta.world_theme,
                "starting_location_name": state.world_meta.starting_location_name,
                "tone": state.world_meta.tone,
                "premise": state.world_meta.premise,
                "player_concept": state.world_meta.player_concept,
            },
            "character_sheet_guidance_strength": state.character_sheet_guidance_strength,
            "character_sheets": [
                {
                    "id": sheet.id,
                    "name": sheet.name,
                    "sheet_type": sheet.sheet_type,
                    "role": sheet.role,
                    "archetype": sheet.archetype,
                    "level_or_rank": sheet.level_or_rank,
                    "faction": sheet.faction,
                    "description": sheet.description,
                    "stats": sheet.stats.__dict__,
                    "classic_attributes": sheet.classic_attributes.__dict__,
                    "traits": sheet.traits,
                    "abilities": sheet.abilities,
                    "guaranteed_abilities": [
                        {
                            "name": entry.name,
                            "type": entry.type,
                            "description": entry.description,
                            "cost_or_resource": entry.cost_or_resource,
                            "cooldown": entry.cooldown,
                            "tags": list(entry.tags),
                            "notes": entry.notes,
                        }
                        for entry in sheet.guaranteed_abilities
                    ],
                    "equipment": sheet.equipment,
                    "weaknesses": sheet.weaknesses,
                    "temperament": sheet.temperament,
                    "loyalty": sheet.loyalty,
                    "fear": sheet.fear,
                    "desire": sheet.desire,
                    "social_style": sheet.social_style,
                    "speech_style": sheet.speech_style,
                    "notes": sheet.notes,
                    "state": sheet.state.__dict__,
                    "guidance_strength": sheet.guidance_strength,
                }
                for sheet in state.character_sheets
            ],
            "inventory_state": state.structured_state.runtime.inventory_state,
            "spellbook": state.structured_state.runtime.spellbook,
            "custom_narrator_rules": state.structured_state.canon.custom_narrator_rules,
            "active_slot": self.session.active_slot,
        }

    def list_saves(self) -> list[str]:
        return sorted(path.stem for path in self.paths.saves.glob("*.json")) if self.paths.saves.exists() else []

    def list_campaigns(self) -> list[dict[str, Any]]:
        campaigns = []
        save_paths = sorted(self.paths.saves.glob("*.json")) if self.paths.saves.exists() else []
        for save_path in save_paths:
            slot = save_path.stem
            updated = save_path.stat().st_mtime if save_path.exists() else time.time()
            try:
                payload = json.loads(save_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise TypeError("save payload root must be a JSON object")
                world_meta = payload.get("world_meta", {})
                if not isinstance(world_meta, dict):
                    world_meta = {}
                settings_payload = payload.get("settings", {})
                if not isinstance(settings_payload, dict):
                    settings_payload = {}
                raw_display_mode = str(settings_payload.get("display_mode", "story")).strip().lower()
                try:
                    turn_count = int(payload.get("turn_count", 0))
                except (TypeError, ValueError):
                    turn_count = 0
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                campaigns.append(
                    {
                        "slot": slot,
                        "campaign_id": "",
                        "campaign_name": "(Unreadable save file)",
                        "world_name": "Unknown world",
                        "turn_count": 0,
                        "updated": updated,
                        "loadable": False,
                    }
                )
                continue
            campaigns.append(
                {
                    "slot": slot,
                    "campaign_id": str(payload.get("campaign_id", "")),
                    "campaign_name": str(payload.get("campaign_name", slot)),
                    "world_name": str(world_meta.get("world_name", "Unknown world")),
                    "turn_count": turn_count,
                    "display_mode": raw_display_mode if raw_display_mode in {"story", "mud", "rpg"} else "story",
                    "updated": updated,
                    "loadable": True,
                }
            )
        return sorted(campaigns, key=lambda item: item["updated"], reverse=True)

    def save_active_campaign(self, slot: str | None = None) -> dict[str, Any]:
        target_slot = (slot or self.session.active_slot or "autosave").strip()
        if not target_slot:
            raise ValueError("save slot cannot be empty")
        self.state_manager.save(self.session.state, target_slot)
        if target_slot != self.session.active_slot:
            with self._history_lock:
                self.history_store[self._campaign_namespace(target_slot)] = list(self.session.message_history)
            self.session.active_slot = target_slot
            self._flush_history_store()
        return {"slot": target_slot, "state": self.serialize_state()}

    def switch_campaign(self, slot: str) -> dict[str, Any]:
        if not self.state_manager.can_load(slot):
            raise ValueError(f"Save slot '{slot}' not found")
        loaded = self.state_manager.load(slot)
        if loaded is None:
            raise ValueError(f"Save slot '{slot}' is corrupted and could not be loaded")
        self._seed_scene_state(loaded)
        self.session = WebSession(state=loaded, active_slot=slot)
        self.session.message_history = self._history_for_slot(slot)
        self.engine.state_orchestrator.set_scene_visual_state(self.session.state, self._scene_visual_for_slot(slot))
        print(f"[narrator-rules] loaded=true count={len(self.session.state.structured_state.canon.custom_narrator_rules)}")
        print(f"[campaign-load] display_mode={self.session.state.settings.display_mode}")
        print(f"[campaign-switch] display_mode={self.session.state.settings.display_mode}")
        print(f"[web-runtime] switched campaign slot={slot}")
        return {"slot": slot, "state": self.serialize_state()}

    def delete_campaign(self, slot: str) -> dict[str, Any]:
        clean_slot = slot.strip()
        if not clean_slot:
            raise ValueError("No save selected for deletion.")
        if clean_slot == self.session.active_slot:
            raise ValueError("Cannot delete the active campaign. Switch first.")
        path = self.paths.saves / f"{clean_slot}.json"
        if not path.exists():
            raise ValueError(f"Save slot '{clean_slot}' not found")
        path.unlink()
        self.history_store.pop(clean_slot, None)
        self.history_store.pop(self._campaign_namespace(clean_slot), None)
        self._persist_history_store()
        self.scene_visual_store.pop(clean_slot, None)
        self.scene_visual_store.pop(self._campaign_namespace(clean_slot), None)
        self._persist_scene_visual_store()
        return {"deleted": clean_slot}

    def rename_campaign(self, slot: str, new_name: str) -> dict[str, Any]:
        clean_slot = slot.strip()
        if not clean_slot:
            raise ValueError("No save selected for rename.")
        state = self.state_manager.load(clean_slot)
        if state is None:
            raise ValueError(f"Save slot '{clean_slot}' not found or invalid")
        clean = new_name.strip()
        if not clean:
            raise ValueError("new_name cannot be empty")
        state.campaign_name = clean
        self.state_manager.save(state, clean_slot)
        if clean_slot == self.session.active_slot:
            self.session.state.campaign_name = clean
        return {"slot": clean_slot, "campaign_name": clean}

    def _coerce_character_sheets(self, raw_sheets: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_sheets, list):
            return []
        clean: list[dict[str, Any]] = []
        for entry in raw_sheets:
            if isinstance(entry, dict):
                clean.append(entry)
        return clean

    def _clean_text(self, value: Any) -> str:
        return str(value or "").strip()

    def _clean_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    def _append_group(self, groups: list[dict[str, Any]], label: str, entries: list[str]) -> None:
        clean = [entry for entry in entries if str(entry).strip()]
        if clean:
            groups.append({"label": label, "entries": clean})

    def get_world_building_view(self) -> dict[str, Any]:
        state = self.session.state
        runtime = state.structured_state.runtime
        scene_state = runtime.scene_state if isinstance(runtime.scene_state, dict) else {}
        npc_conditions = scene_state.get("npc_conditions", {}) if isinstance(scene_state, dict) else {}
        npc_conditions = npc_conditions if isinstance(npc_conditions, dict) else {}

        npc_profiles: list[dict[str, Any]] = []
        for npc in state.npcs.values():
            profile = npc.personality_profile
            nodes = npc.personality_nodes
            dynamic = npc.dynamic_state
            notes = self._clean_list(npc.notes)
            memory_summaries = self._clean_list([entry.summary for entry in npc.memory_log if getattr(entry, "summary", "")])
            evolution = self._clean_list(npc.applied_evolution_rules)
            conditions = self._clean_list(npc_conditions.get(npc.id, []))
            role_or_archetype = self._clean_text(
                (profile.archetype if profile else "")
                or npc.personality_archetype
                or (nodes.role if nodes else "")
                or "Unknown role"
            )
            personality_summary = self._clean_text(
                (profile.baseline_temperament if profile else "")
                or (nodes.temperament if nodes else "")
                or "No personality summary available yet."
            )
            social_style = self._clean_text((profile.social_style if profile else "") or (nodes.social_style if nodes else ""))
            motivations = self._clean_text((profile.motivations if profile else "") or ", ".join((nodes.desires if nodes else [])[:3]))
            speaking_style = self._clean_text((profile.conversational_tone if profile else "") or (nodes.speech_style if nodes else ""))
            conflict_style = self._clean_text((profile.conflict_response if profile else "") or (nodes.aggression if nodes else ""))
            stance = self._clean_text(dynamic.current_mood if dynamic else "")
            notable_evolution = self._clean_text(evolution[-1] if evolution else (memory_summaries[-1] if memory_summaries else (notes[-1] if notes else "")))

            has_profile_data = any(
                [
                    profile is not None,
                    nodes is not None,
                    notes,
                    memory_summaries,
                    evolution,
                    conditions,
                ]
            )
            if not has_profile_data:
                continue
            npc_profiles.append(
                {
                    "name": self._clean_text(npc.name) or "Unnamed NPC",
                    "role_or_archetype": role_or_archetype,
                    "personality_summary": personality_summary,
                    "social_style": social_style,
                    "likely_motivations": motivations,
                    "speaking_style": speaking_style,
                    "conflict_style": conflict_style,
                    "current_stance_toward_player": stance,
                    "current_persistent_conditions": conditions,
                    "notable_evolution": notable_evolution,
                }
            )

        world_design: list[dict[str, Any]] = []
        self._append_group(world_design, "World Facts", self._clean_list(state.important_world_facts))
        self._append_group(world_design, "Discovered Lore", self._clean_list(state.structured_state.canon.lore))
        discovered_locations = []
        for location_id in self._clean_list(runtime.discovered_locations):
            location = state.locations.get(location_id)
            discovered_locations.append(location.name if location else location_id)
        self._append_group(world_design, "Established Locations", self._clean_list(discovered_locations))
        faction_entries = [
            f"{name}: {value}"
            for name, value in state.faction_reputation.items()
            if isinstance(value, (int, float)) and value != 0
        ]
        persistent_state_entries = [
            f"{flag}: {value}"
            for flag, value in state.world_flags.items()
            if bool(value)
        ]
        persistent_state_entries.extend(
            [
                f"{key}: {value}"
                for key, value in runtime.world_state.items()
                if value not in ("", None, False, [], {})
            ]
        )
        self._append_group(world_design, "Factions & Powers", self._clean_list(faction_entries))
        self._append_group(world_design, "Emerging Tensions", self._clean_list(state.unresolved_plot_threads))
        self._append_group(world_design, "Persistent State", self._clean_list(persistent_state_entries))

        reactive_changes: list[dict[str, Any]] = []
        self._append_group(reactive_changes, "Persistent Environment Changes", self._clean_list(scene_state.get("altered_environment", [])))
        self._append_group(reactive_changes, "Major Scene Consequences", self._clean_list(scene_state.get("recent_consequences", [])))
        self._append_group(reactive_changes, "World State Shifts", self._clean_list(state.world_events))
        self._append_group(reactive_changes, "Ongoing Threats / Aftermath", self._clean_list(scene_state.get("active_effects", [])))
        self._append_group(
            reactive_changes,
            "Resolved / Unresolved Changes",
            self._clean_list(state.structured_state.recent_turn_memory.recent_discoveries),
        )

        return {
            "npc_personalities": npc_profiles,
            "world_design": world_design,
            "reactive_world_changes": reactive_changes,
        }

    def _extract_recent_recalibration_turns(self, state: CampaignState, limit: int = 10) -> list[Any]:
        turns = state.conversation_turns[-max(5, min(limit, 10)) :]
        return [turn for turn in turns if turn]

    def _find_main_character_sheet(self, state: CampaignState) -> CharacterSheet | None:
        for sheet in state.character_sheets:
            if sheet.sheet_type == "main_character":
                return sheet
        return None

    def _recalibration_sync_player_identity(self, state: CampaignState, narration_blob: str) -> None:
        main_sheet = self._find_main_character_sheet(state)
        title_match = re.search(r"\b(captain|sir|lady|warden|magister|commander)\s+([A-Z][a-z]+)\b", narration_blob)
        if title_match and main_sheet is not None:
            title_value = f"{title_match.group(1).title()} {title_match.group(2).title()}"
            if not str(main_sheet.level_or_rank or "").strip():
                main_sheet.level_or_rank = title_value
        intro_patterns = (
            r"\bi am\s+([A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)\b",
            r"\bmy name is\s+([A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)\b",
        )
        for pattern in intro_patterns:
            match = re.search(pattern, narration_blob)
            if not match:
                continue
            discovered_name = str(match.group(1)).strip()
            if discovered_name and not str(state.player.name or "").strip():
                state.player.name = discovered_name
            if main_sheet is not None and not str(main_sheet.name or "").strip():
                main_sheet.name = discovered_name
            break

    def _recalibration_sync_abilities(self, state: CampaignState, turns: list[Any]) -> int:
        if not state.settings.play_style.auto_update_character_sheet_from_actions:
            return 0
        runtime = state.structured_state.runtime
        runtime.spellbook = runtime.spellbook if isinstance(runtime.spellbook, list) else []
        main_sheet = self._find_main_character_sheet(state)
        added = 0
        for turn in turns:
            detected = self.engine._detect_action_ability(str(turn.player_input or ""))
            if detected is None:
                continue
            existing_name = self.engine._find_existing_ability_name(state, detected.normalized_name)
            if existing_name:
                continue
            ability_type = "spell" if detected.category == "magic" else "skill" if detected.category == "skill" else "ability"
            runtime.spellbook.append(
                {
                    "id": f"recal_{int(time.time() * 1000)}_{len(runtime.spellbook)}",
                    "name": detected.normalized_name,
                    "type": ability_type,
                    "description": "Recovered from recent action history during recalibration.",
                    "cost_or_resource": "",
                    "cooldown": "",
                    "tags": ["recalibrated"],
                    "notes": "",
                }
            )
            if main_sheet is not None and not any(
                self.engine._normalize_ability_name(name) == detected.normalized_name for name in main_sheet.abilities
            ):
                main_sheet.abilities.append(detected.normalized_name)
            added += 1
        runtime.spellbook = self.engine.state_orchestrator._normalize_spellbook(runtime.spellbook)
        return added

    def _recalibration_merge_duplicate_npcs(self, state: CampaignState, scene_state: dict[str, Any]) -> int:
        by_name: dict[str, list[str]] = {}
        for npc_id, npc in state.npcs.items():
            normalized = self.engine._normalize_person_name(npc.name)
            if not normalized:
                continue
            by_name.setdefault(normalized, []).append(npc_id)
        merged = 0
        for _, npc_ids in by_name.items():
            if len(npc_ids) < 2:
                continue
            keeper = max(
                npc_ids,
                key=lambda npc_id: (
                    1 if state.npcs[npc_id].personality_profile is not None else 0,
                    len(state.npcs[npc_id].notes),
                    len(state.npcs[npc_id].memory_log),
                ),
            )
            for npc_id in npc_ids:
                if npc_id == keeper or npc_id not in state.npcs:
                    continue
                for actor in scene_state.get("scene_actors", []):
                    if isinstance(actor, dict) and str(actor.get("linked_npc_id", "")).strip() == npc_id:
                        actor["linked_npc_id"] = keeper
                npc_conditions = scene_state.setdefault("npc_conditions", {})
                if npc_id in npc_conditions and keeper not in npc_conditions:
                    npc_conditions[keeper] = npc_conditions.get(npc_id, [])
                npc_conditions.pop(npc_id, None)
                del state.npcs[npc_id]
                merged += 1
        return merged

    def recalibrate_campaign_state(self, state: CampaignState) -> dict[str, Any]:
        print("[recalibration] started")
        scene_state = self.engine._ensure_scene_state(state)
        turns = self._extract_recent_recalibration_turns(state)
        narration_sources: list[str] = []
        generic_label_counts: dict[str, int] = {}
        npc_created_names: list[str] = []
        for turn in turns:
            narration_sources.extend([str(turn.narrator_response or ""), *[str(msg) for msg in turn.system_messages]])
            for label in self.engine._extract_scene_actor_labels(str(turn.narrator_response or "")):
                generic_label_counts[label] = generic_label_counts.get(label, 0) + 1
                self.engine._register_scene_actor(state, scene_state, label)
            for npc_name in self.engine._detect_npc_introductions_from_narration(str(turn.narrator_response or "")):
                before_ids = set(state.npcs.keys())
                npc = self.engine._register_narrative_npc(state, scene_state, npc_name)
                if npc.id not in before_ids:
                    npc_created_names.append(npc.name)
        narration_blob = " ".join(source for source in narration_sources if source.strip())
        self._recalibration_sync_player_identity(state, narration_blob)
        abilities_synced = self._recalibration_sync_abilities(state, turns)

        # Backfill missing personalities only; never overwrite existing profiles.
        for npc in state.npcs.values():
            mention_key = npc.name.lower()
            if npc.location_id != state.current_location_id or mention_key not in narration_blob.lower():
                continue
            self.engine.personality.initialize_npc(state, npc.id)
            if npc.personality_profile is None:
                npc.personality_profile = self.engine.personality.generate_profile(npc_name=npc.name, role_hint="local npc")
                print(f"[recalibration] npc_created={npc.name}")

        # Normalize repeated generic identities into stable named NPC identities.
        for label, count in generic_label_counts.items():
            if count < 2:
                continue
            matched_npc = self.engine._find_existing_npc_by_role(state, label)
            if matched_npc is None:
                stable_name = f"{label.title()} {state.current_location_id.replace('_', ' ').title()}".strip()
                self.engine._register_narrative_npc(state, scene_state, stable_name)
                npc_created_names.append(stable_name)
                continue
            if self.engine._is_generic_identity_label(matched_npc.name):
                stable_name = f"{label.title()} {state.current_location_id.replace('_', ' ').title()}".strip()
                matched_npc.name = stable_name
                if matched_npc.personality_profile is not None and not matched_npc.personality_profile.identity_label:
                    matched_npc.personality_profile.identity_label = stable_name

        world_updates = 0
        extracted = self.engine._extract_consequences_from_narration(narration_blob)
        for turn in turns:
            action_extracted = self.engine._extract_consequences_from_action(str(turn.player_input or ""))
            for key in extracted.keys():
                extracted[key].extend(action_extracted[key])
        for key, values in extracted.items():
            for value in values:
                before = list(scene_state.get(key, []))
                self.engine._merge_scene_consequence(scene_state, key, value)
                if before != scene_state.get(key, []):
                    world_updates += 1
                    if key == "altered_environment":
                        lowered = value.lower()
                        for token in ("frost", "fire", "storm"):
                            if token in lowered and not state.world_flags.get(f"env_{token}_active", False):
                                state.world_flags[f"env_{token}_active"] = True
        lowered_blob = narration_blob.lower()
        for token in ("frost", "fire", "storm"):
            if token in lowered_blob and not state.world_flags.get(f"env_{token}_active", False):
                state.world_flags[f"env_{token}_active"] = True
                world_updates += 1
        for location in state.locations.values():
            if location.name and location.name.lower() in narration_blob.lower():
                if location.id not in state.structured_state.runtime.discovered_locations:
                    state.structured_state.runtime.discovered_locations.append(location.id)
                    world_updates += 1
        merged_npcs = self._recalibration_merge_duplicate_npcs(state, scene_state)
        state.structured_state.runtime.spellbook = self.engine.state_orchestrator._normalize_spellbook(
            state.structured_state.runtime.spellbook
        )
        print(f"[recalibration] abilities_synced={abilities_synced}")
        print(f"[recalibration] world_updates={world_updates}")
        print("[recalibration] complete")
        self.save_active_campaign(self.session.active_slot)
        return {
            "ok": True,
            "npc_created": npc_created_names,
            "abilities_synced": abilities_synced,
            "world_updates": world_updates,
            "npc_merged": merged_npcs,
        }

    def get_inventory_state(self) -> dict[str, Any]:
        runtime = self.session.state.structured_state.runtime
        if not runtime.inventory_state:
            self.engine.state_orchestrator.update_runtime_state(
                self.session.state,
                action="inventory_sync",
                system_messages=[],
                narrative="",
            )
        print(f"[inventory] viewer_opened campaign={self.session.active_slot}")
        return runtime.inventory_state

    def get_spellbook_state(self) -> list[dict[str, Any]]:
        runtime = self.session.state.structured_state.runtime
        if not isinstance(runtime.spellbook, list):
            runtime.spellbook = []
        print(f"[spellbook] viewer_opened campaign={self.session.active_slot}")
        print(f"[spellbook] current_entry_count={len(runtime.spellbook)}")
        return runtime.spellbook

    def upsert_spellbook_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime = self.session.state.structured_state.runtime
        action = str(payload.get("action", "upsert")).strip().lower()
        if not isinstance(runtime.spellbook, list):
            runtime.spellbook = []
        if action == "delete":
            entry_id = str(payload.get("id", "")).strip()
            runtime.spellbook = [entry for entry in runtime.spellbook if str(entry.get("id", "")) != entry_id]
        else:
            entry = {
                "id": str(payload.get("id", "")).strip() or f"sb_{int(time.time() * 1000)}",
                "name": str(payload.get("name", "")).strip(),
                "type": str(payload.get("type", "ability")).strip().lower(),
                "description": str(payload.get("description", "")).strip(),
                "cost_or_resource": str(payload.get("cost_or_resource", "")).strip(),
                "cooldown": str(payload.get("cooldown", "")).strip(),
                "tags": [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
                "notes": str(payload.get("notes", "")).strip(),
            }
            if not entry["name"]:
                raise ValueError("Spellbook entry name is required.")
            if entry["type"] not in {"spell", "skill", "ability", "passive"}:
                entry["type"] = "ability"
            replaced = False
            for index, existing in enumerate(runtime.spellbook):
                if str(existing.get("id", "")) == entry["id"]:
                    runtime.spellbook[index] = entry
                    replaced = True
                    break
            if not replaced:
                runtime.spellbook.append(entry)
        runtime.spellbook = self.engine.state_orchestrator._normalize_spellbook(runtime.spellbook)
        self.save_active_campaign(self.session.active_slot)
        print(f"[spellbook] current_entry_count={len(runtime.spellbook)}")
        return {"spellbook": runtime.spellbook}

    def get_narrator_rules(self) -> list[dict[str, str]]:
        canon = self.session.state.structured_state.canon
        if not isinstance(canon.custom_narrator_rules, list):
            canon.custom_narrator_rules = []
        print(f"[narrator-rules] loaded=true count={len(canon.custom_narrator_rules)}")
        return canon.custom_narrator_rules

    def upsert_character_sheet(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", "create")).strip().lower()
        sheets = list(self.session.state.character_sheets)
        role = str(payload.get("role", "")).strip() or "unspecified"
        print(f"[character-sheets] create_requested role={role}")

        created_id = ""
        if action == "delete":
            target_id = str(payload.get("id", "")).strip()
            sheets = [sheet for sheet in sheets if sheet.id != target_id]
        else:
            base_id = str(payload.get("id", "")).strip() or f"sheet_{int(time.time() * 1000)}"
            taken_ids = {sheet.id for sheet in sheets}
            candidate_id = base_id
            dedupe_index = 1
            while candidate_id in taken_ids:
                candidate_id = f"{base_id}_{dedupe_index}"
                dedupe_index += 1
            sheet_payload = {
                "id": candidate_id,
                "name": str(payload.get("name", "")).strip() or "Unnamed",
                "sheet_type": str(payload.get("sheet_type", "npc_or_mob")).strip() or "npc_or_mob",
                "role": role,
                "archetype": str(payload.get("archetype", "")).strip(),
                "level_or_rank": str(payload.get("level_or_rank", "")).strip(),
                "faction": str(payload.get("faction", "")).strip(),
                "description": str(payload.get("description", "")).strip(),
                "stats": payload.get("stats", {}),
                "classic_attributes": payload.get("classic_attributes", {}),
                "traits": payload.get("traits", []),
                "abilities": payload.get("abilities", []),
                "guaranteed_abilities": payload.get("guaranteed_abilities", []),
                "equipment": payload.get("equipment", []),
                "weaknesses": payload.get("weaknesses", []),
                "temperament": str(payload.get("temperament", "")).strip(),
                "loyalty": str(payload.get("loyalty", "")).strip(),
                "fear": str(payload.get("fear", "")).strip(),
                "desire": str(payload.get("desire", "")).strip(),
                "social_style": str(payload.get("social_style", "")).strip(),
                "speech_style": str(payload.get("speech_style", "")).strip(),
                "notes": str(payload.get("notes", "")).strip(),
                "state": payload.get("state", {}),
                "guidance_strength": str(payload.get("guidance_strength", "light")).strip() or "light",
            }
            sheets.append(CharacterSheet.from_payload(sheet_payload))
            created_id = candidate_id

        self.session.state.character_sheets = sheets
        self.save_active_campaign(self.session.active_slot)
        print(f"[character-sheets] created id={created_id or 'none'} total={len(sheets)}")
        return {
            "character_sheets": self.serialize_state().get("character_sheets", []),
            "created_id": created_id,
        }

    def upsert_narrator_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        canon = self.session.state.structured_state.canon
        if not isinstance(canon.custom_narrator_rules, list):
            canon.custom_narrator_rules = []
        action = str(payload.get("action", "upsert")).strip().lower()
        if action == "delete":
            entry_id = str(payload.get("id", "")).strip()
            canon.custom_narrator_rules = [
                entry
                for entry in canon.custom_narrator_rules
                if str(entry.get("id", "")).strip() != entry_id
            ]
            print(f"[narrator-rules] rule_deleted campaign={self.session.active_slot} count={len(canon.custom_narrator_rules)}")
        else:
            text = str(payload.get("text", "")).strip()
            if not text:
                raise ValueError("Narrator rule text is required.")
            entry_id = str(payload.get("id", "")).strip() or f"nr_{int(time.time() * 1000)}"
            updated = False
            for entry in canon.custom_narrator_rules:
                if str(entry.get("id", "")).strip() == entry_id:
                    entry["text"] = text
                    updated = True
                    break
            if not updated:
                canon.custom_narrator_rules.append({"id": entry_id, "text": text})
            print(f"[narrator-rules] rule_added campaign={self.session.active_slot} count={len(canon.custom_narrator_rules)}")
        self.save_active_campaign(self.session.active_slot)
        print(f"[narrator-rules] persisted=true count={len(canon.custom_narrator_rules)}")
        return {"rules": canon.custom_narrator_rules}

    def get_narrator_debug_packet(self) -> dict[str, Any]:
        state = self.session.state
        return {
            "campaign_slot": self.session.active_slot,
            "campaign_id": state.campaign_id,
            "turn_count": state.turn_count,
            "packet": self.engine.get_last_prompt_debug_packet(state.campaign_id),
        }


    def _build_seed_scene_summary(self, state: CampaignState, location_name: str) -> str:
        world_name = str(state.world_meta.world_name or "").strip()
        world_theme = str(state.world_meta.world_theme or "").strip()
        premise = str(state.world_meta.premise or "").strip()
        parts = [f"You begin at {location_name or 'the starting area'}."]
        if world_name:
            parts.append(f"World: {world_name}.")
        if world_theme:
            parts.append(f"Theme: {world_theme}.")
        if premise:
            parts.append(premise[:160])
        return " ".join(part for part in parts if part).strip()

    def _seed_scene_state(self, state: CampaignState) -> None:
        runtime = state.structured_state.runtime
        scene_state = dict(runtime.scene_state) if isinstance(runtime.scene_state, dict) else {}
        location = state.locations.get(state.current_location_id)
        location_id = str(state.current_location_id or "").strip() or None
        location_name = str(location.name if location else state.world_meta.starting_location_name or "").strip() or None
        visible_entities = [
            npc.name
            for npc in state.npcs.values()
            if npc.location_id == state.current_location_id and str(npc.name).strip()
        ]
        seeded_summary = str(scene_state.get("scene_summary", "")).strip() or self._build_seed_scene_summary(state, location_name or "the starting area")
        scene_state["location_id"] = location_id
        scene_state["location_name"] = location_name
        scene_state["scene_summary"] = seeded_summary
        scene_state["visible_entities"] = [str(v).strip() for v in scene_state.get("visible_entities", visible_entities) if str(v).strip()]
        scene_state.setdefault("altered_environment", [])
        scene_state.setdefault("damaged_objects", [])
        scene_state.setdefault("active_effects", [])
        scene_state.setdefault("recent_consequences", [])
        scene_state.setdefault("last_player_action", "")
        scene_state.setdefault("last_immediate_result", "")
        runtime.scene_state = scene_state
        print("[scene-state] initialized=true")
        print(f"[scene-state] seeded_location={location_id or location_name or 'unknown'}")
        print(f"[scene-state] seeded_summary={seeded_summary}")

    def test_image_pipeline(self, prompt: str = "test fantasy portrait") -> dict[str, Any]:
        print("[image-test] requested")

        def fail(step: str, message: str) -> dict[str, Any]:
            print(f"[image-test] success=false reason={step}")
            return {"success": False, "failing_step": step, "message": message}

        if not self.app_config.image.enabled or self.app_config.image.provider == "null":
            return fail("image_generation_disabled", "Image generation is disabled in global settings.")
        if not self.session.state.settings.image_generation_enabled:
            return fail("campaign_image_generation_disabled", "Image generation is disabled for this campaign.")
        if self.app_config.image.provider != "comfyui":
            return fail("provider_not_comfyui", "Test Image Pipeline requires image provider set to comfyui.")

        path_status = self.get_path_configuration_status().get("image", {})
        for key, step in (("comfyui_root", "comfyui_root"), ("workflow_path", "workflow_path"), ("checkpoint_dir", "checkpoint_dir")):
            section = path_status.get(key, {})
            if not bool(section.get("valid", False)):
                return fail(step, str(section.get("message", "Image pipeline path is not configured.")))

        adapter = ComfyUIAdapter(base_url=self.app_config.image.base_url, output_dir=self.generated_image_dir)

        print("[image-test] step=comfyui_reachable")
        readiness = adapter.check_readiness()
        if not bool(readiness.get("ready", False)):
            return fail("comfyui_reachable", str(readiness.get("user_message", "ComfyUI is not reachable.")))

        workflow_path = Path(str(self.app_config.image.comfyui_workflow_path).strip())
        print("[image-test] step=workflow_load")
        try:
            json.loads(workflow_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return fail("workflow_load", f"Workflow file could not be loaded: {exc}")

        print("[image-test] step=checkpoint_available")
        checkpoints = adapter._list_checkpoints() if hasattr(adapter, "_list_checkpoints") else []
        if not checkpoints:
            return fail("checkpoint_available", "No checkpoints are available in ComfyUI.")
        preferred = str(self.app_config.image.preferred_checkpoint or "").strip()
        if preferred and preferred.lower() not in {item.lower() for item in checkpoints}:
            return fail("checkpoint_available", f"Preferred checkpoint '{preferred}' is not available in ComfyUI.")

        print("[image-test] step=prompt_submission")
        request = ImageGenerationRequest(
            workflow_id=workflow_path.stem or "scene_image",
            prompt=prompt,
            negative_prompt="",
            parameters=({"checkpoint": preferred} if preferred else {}),
        )
        result = adapter.generate(request, WorkflowManager(workflow_path.parent))
        if not result.success:
            error_text = str(result.error or "Image pipeline test failed.")
            failing_step = "prompt_submission"
            if "history" in error_text.lower() or "output" in error_text.lower():
                failing_step = "history_output"
            return fail(failing_step, error_text)

        print("[image-test] step=history_output")
        print("[image-test] success=true")
        return {
            "success": True,
            "failing_step": "",
            "message": "Image pipeline test completed successfully.",
            "workflow_id": result.workflow_id,
            "prompt_id": result.prompt_id,
            "result_path": result.result_path,
        }
    def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode", "custom")).strip().lower() or "custom"
        player_name = str(payload.get("player_name", "Aria")).strip() or "Aria"
        char_class = str(payload.get("char_class", "Ranger")).strip() or "Ranger"
        profile = str(payload.get("profile", "classic_fantasy")).strip() or "classic_fantasy"
        display_mode = str(payload.get("display_mode", "story")).strip().lower() or "story"
        slot = str(payload.get("slot", f"campaign_{len(self.list_saves()) + 1}")).strip() or f"campaign_{len(self.list_saves()) + 1}"
        if mode in {"premade", "sample"}:
            state = self.state_manager.new_from_sample()
            print("[campaign-create] mode=premade")
            print("[campaign-create] using_sample_template=True")
        else:
            play_style_payload = payload.get("play_style", {})
            state = self.state_manager.create_new_campaign(
                player_name=player_name,
                char_class=char_class,
                profile=profile,
                mature_content_enabled=bool(payload.get("mature_content_enabled", False)),
                content_settings_enabled=bool(payload.get("content_settings_enabled", True)),
                campaign_tone=str(payload.get("campaign_tone", "heroic")),
                maturity_level=str(payload.get("maturity_level", "standard")),
                thematic_flags=list(payload.get("thematic_flags", ["adventure", "mystery"])),
                campaign_name=str(payload.get("campaign_name", "")).strip(),
                world_name=str(payload.get("world_name", "")).strip(),
                world_theme=str(payload.get("world_theme", "")).strip(),
                starting_location_name=str(payload.get("starting_location_name", "")).strip(),
                premise=str(payload.get("premise", "")).strip(),
                player_concept=str(payload.get("player_concept", "")).strip(),
                suggested_moves_enabled=bool(payload.get("suggested_moves_enabled", False)),
                display_mode=display_mode,
                character_sheets=self._coerce_character_sheets(payload.get("character_sheets", [])),
                character_sheet_guidance_strength=str(payload.get("character_sheet_guidance_strength", "light")),
            )
            state.settings.play_style.allow_freeform_powers = bool(
                play_style_payload.get("allow_freeform_powers", state.settings.play_style.allow_freeform_powers)
            )
            state.settings.play_style.auto_update_character_sheet_from_actions = bool(
                play_style_payload.get(
                    "auto_update_character_sheet_from_actions", state.settings.play_style.auto_update_character_sheet_from_actions
                )
            )
            state.settings.play_style.strict_sheet_enforcement = bool(
                play_style_payload.get("strict_sheet_enforcement", state.settings.play_style.strict_sheet_enforcement)
            )
            state.settings.play_style.auto_sync_player_declared_identity = bool(
                play_style_payload.get(
                    "auto_sync_player_declared_identity", state.settings.play_style.auto_sync_player_declared_identity
                )
            )
            state.settings.play_style.auto_generate_npc_personalities = bool(
                play_style_payload.get(
                    "auto_generate_npc_personalities", state.settings.play_style.auto_generate_npc_personalities
                )
            )
            state.settings.play_style.auto_evolve_npc_personalities = bool(
                play_style_payload.get("auto_evolve_npc_personalities", state.settings.play_style.auto_evolve_npc_personalities)
            )
            state.settings.play_style.reactive_world_persistence = bool(
                play_style_payload.get("reactive_world_persistence", state.settings.play_style.reactive_world_persistence)
            )
            state.settings.play_style.narration_format_mode = self._normalize_narration_format_mode(
                play_style_payload.get("narration_format_mode", state.settings.play_style.narration_format_mode)
            )
            state.settings.play_style.scene_visual_mode = self._normalize_scene_visual_mode(
                play_style_payload.get("scene_visual_mode", state.settings.play_style.scene_visual_mode)
            )
        self._seed_scene_state(state)
        self.session = WebSession(state=state, active_slot=slot)
        self.session.message_history = []
        self.scene_visual_store.pop(slot, None)
        self.scene_visual_store.pop(self._campaign_namespace(slot), None)
        self._persist_scene_visual_store()
        print(f"[campaign-create] display_mode={self.session.state.settings.display_mode}")
        print(f"[web-runtime] created campaign slot={slot} player={player_name}")
        self.save_active_campaign(slot)
        return {"slot": slot, "state": self.serialize_state()}

    def handle_player_input(self, text: str) -> dict[str, Any]:
        request_started = time.perf_counter()
        request_received_at = datetime.now(timezone.utc).isoformat()
        model_status = self.get_model_status()
        visual_mode = self._normalize_scene_visual_mode(self.session.state.settings.play_style.scene_visual_mode)
        auto_enabled = visual_mode in {"before_narration", "after_narration"}
        image_generation_enabled = bool(self.session.state.settings.image_generation_enabled)
        suggested_moves_enabled = bool(self.session.state.settings.suggested_moves_active())
        auto_timing = visual_mode if visual_mode in {"before_narration", "after_narration"} else "off"
        auto_provider_ready = self.app_config.image.provider == "comfyui" and image_generation_enabled
        print(
            "[campaign-settings] loaded for turn "
            f"campaign={self.session.active_slot} suggested_moves={str(suggested_moves_enabled).lower()} "
            f"auto_visuals={str(auto_enabled).lower()} timing={auto_timing} image_generation={str(image_generation_enabled).lower()}"
        )
        print(
            "[campaign-settings] turn pipeline using persisted settings "
            f"campaign={self.session.active_slot} suggested_moves={str(suggested_moves_enabled).lower()} "
            f"auto_visuals={str(auto_enabled).lower()} timing={auto_timing} auto_provider_ready={str(auto_provider_ready).lower()}"
        )
        print(f"[settings] runtime_auto_visuals={str(auto_enabled).lower()}")
        print(f"[turn-visual] manual_enabled={self.app_config.image.manual_image_generation_enabled}")
        print(f"[turn-visual] auto_enabled={auto_enabled}")
        print(f"[turn-visual] auto_timing={auto_timing}")
        validation_started = time.perf_counter()
        clean_text = text.strip()
        validation_ms = (time.perf_counter() - validation_started) * 1000
        self._append_message("player", clean_text, persist=False)
        message_append_ms = 0.0
        auto_before_ms = 0.0
        if auto_enabled and auto_timing == "before_narration" and auto_provider_ready:
            print("[turn-visual] auto_image_triggered=true timing=before_narration")
            auto_before_started = time.perf_counter()
            self._run_turn_visual_generation(player_action=clean_text, narrator_response="", stage="before_narration", source="auto_before")
            auto_before_ms = (time.perf_counter() - auto_before_started) * 1000
        elif auto_enabled and auto_timing == "before_narration" and not auto_provider_ready:
            print("[turn-visual] auto_image_skipped reason=image_provider_not_ready")

        engine_started = time.perf_counter()
        result = self.engine.run_turn(self.session.state, clean_text)
        engine_ms = (time.perf_counter() - engine_started) * 1000
        message_append_started = time.perf_counter()
        for message in result.messages:
            self._append_message(message["type"], message["text"], persist=False)
        message_append_ms = (time.perf_counter() - message_append_started) * 1000
        narrator_response = self._extract_narrator_response(result)
        background_image_queued = self._maybe_queue_auto_turn_visual(
            auto_enabled=auto_enabled,
            auto_timing=auto_timing,
            player_action=clean_text,
            narrator_response=narrator_response,
            stage="after_narration",
        )
        save_started = time.perf_counter()
        self._flush_history_store()
        self.save_active_campaign(self.session.active_slot)
        save_ms = (time.perf_counter() - save_started) * 1000
        total_ms = (time.perf_counter() - request_started) * 1000
        turn_timing = {
            "request_received_at": request_received_at,
            "action_validation_ms": round(validation_ms, 2),
            "auto_before_image_ms": round(auto_before_ms, 2),
            "engine_turn_ms": round(engine_ms, 2),
            "message_append_ms": round(message_append_ms, 2),
            "save_ms": round(save_ms, 2),
            "total_request_ms": round(total_ms, 2),
            "auto_after_image_queued": background_image_queued,
        }
        print(f"[turn-timing] {json.dumps(turn_timing)}")
        return {
            "narrative": result.narrative,
            "system_messages": result.system_messages,
            "messages": result.messages,
            "should_exit": result.should_exit,
            "metadata": {**(result.metadata or {}), "model_status": model_status, "timing": turn_timing},
            "state": self.serialize_state(),
        }

    def _run_turn_visual_generation(self, player_action: str, narrator_response: str, stage: str, source: str = "automatic") -> None:
        self._request_scene_visual_generation(
            source=source,
            stage=stage,
            player_action=player_action,
            narrator_response=narrator_response,
        )

    def _has_meaningful_scene_content(self, narrator_response: str) -> bool:
        text = " ".join(str(narrator_response or "").split()).strip()
        if len(text) < 24:
            return False
        return bool(re.search(r"[A-Za-z].*[A-Za-z]", text))

    def _maybe_queue_auto_turn_visual(
        self, *, auto_enabled: bool, auto_timing: str, player_action: str, narrator_response: str, stage: str
    ) -> bool:
        narrator_turn_detected = bool(narrator_response.strip())
        print(f"[turn-visual] narrator_turn_detected={narrator_turn_detected}")
        if not auto_enabled:
            print("[turn-visual] auto_image_skipped reason=auto_disabled")
            return False
        if auto_timing != "after_narration":
            print(f"[turn-visual] auto_image_skipped reason=timing_{auto_timing}")
            return False
        if not self._has_meaningful_scene_content(narrator_response):
            print("[turn-visual] auto_image_skipped reason=no_meaningful_narration")
            return False
        print("[turn-visual] auto_image_triggered=true timing=after_narration")
        triggered = self._run_turn_visual_generation_async(
            player_action=player_action,
            narrator_response=narrator_response,
            stage=stage,
            source="auto_after",
        )
        return triggered

    def _extract_narrator_response(self, result: TurnResult) -> str:
        narrative = str(result.narrative or "").strip()
        if narrative:
            return narrative
        for message in reversed(result.messages):
            if str(message.get("type", "")).strip().lower() == "narrator":
                candidate = str(message.get("text", "")).strip()
                if candidate:
                    return candidate
        return ""

    def _request_scene_visual_generation(
        self,
        *,
        source: str,
        stage: str,
        player_action: str,
        narrator_response: str,
        prompt_override: str | None = None,
    ) -> dict[str, Any]:
        log_source = "auto" if source in {"automatic", "auto_before", "auto_after"} else source
        prompt = str(prompt_override or "").strip() or self.turn_image_prompts.build(
            self.session.state,
            player_action=player_action,
            narrator_response=narrator_response,
        )
        prompt_preview = " ".join(prompt.split())[:160]
        print(f"[turn-visual] prompt_preview={prompt_preview}")
        request_payload = {
            "workflow_id": "scene_image",
            "prompt": prompt,
            "parameters": {"checkpoint": self.app_config.image.preferred_checkpoint},
        }
        print(f"[turn-visual] image_request_started source={log_source}")
        result = self.generate_image(request_payload)
        if not result.success:
            print(f"[turn-visual] image_request_failed source={log_source} error={result.error}")
            return {"ok": False, "error": result.error, "result": result}
        public_image_url = self.public_image_path(result.result_path)
        if not public_image_url:
            print(f"[turn-visual] image_request_failed source={log_source} error=missing_public_image_url")
            return {"ok": False, "error": "missing_public_image_url", "result": result}
        self._set_scene_visual(
            slot=self.session.active_slot,
            image_url=public_image_url,
            prompt=prompt,
            source=source,
            stage=stage,
            turn=self.session.state.turn_count,
            metadata={"workflow_id": result.workflow_id, "result_metadata": result.metadata},
        )
        print(f"[turn-visual] image_request_completed source={log_source}")
        return {"ok": True, "result": result, "prompt": prompt, "image_url": public_image_url}

    def _run_turn_visual_generation_async(self, player_action: str, narrator_response: str, stage: str, source: str) -> bool:
        if self.app_config.image.provider != "comfyui" or not self.session.state.settings.image_generation_enabled:
            print("[turn-visual] auto_image_skipped reason=image_provider_not_ready")
            return False
        slot = self.session.active_slot
        turn = int(self.session.state.turn_count)
        job_key = (slot, turn, stage)
        with self._turn_visual_lock:
            if job_key in self._active_turn_visual_jobs:
                return False
            self._active_turn_visual_jobs.add(job_key)

        def _worker() -> None:
            started = time.perf_counter()
            try:
                self._run_turn_visual_generation(player_action=player_action, narrator_response=narrator_response, stage=stage, source=source)
                elapsed_ms = (time.perf_counter() - started) * 1000
                print(
                    f"[turn-timing] {json.dumps({'async_image_stage': stage, 'slot': slot, 'image_generation_ms': round(elapsed_ms, 2)})}"
                )
            except Exception as exc:  # pragma: no cover - defensive runtime logging
                print(f"[turn-timing] async image generation failed stage={stage} slot={slot} error={exc}")
            finally:
                with self._turn_visual_lock:
                    self._active_turn_visual_jobs.discard(job_key)

        threading.Thread(target=_worker, name=f"turn-image-{slot}-{turn}-{stage}", daemon=True).start()
        return True

    def get_global_settings(self) -> dict[str, Any]:
        return {
            "model": {
                "provider": self.app_config.model.provider,
                "model_name": self.app_config.model.model_name,
                "base_url": self.app_config.model.base_url,
                "timeout_seconds": self.app_config.model.timeout_seconds,
                "ollama_path": self.app_config.model.ollama_path,
            },
            "model_status": self.get_model_status(),
            "image": {
                "provider": self.app_config.image.provider,
                "base_url": self.app_config.image.base_url,
                "enabled": self.app_config.image.enabled,
                "comfyui_path": self.app_config.image.comfyui_path,
                "comfyui_workflow_path": self.app_config.image.comfyui_workflow_path,
                "comfyui_output_dir": self.app_config.image.comfyui_output_dir,
                "manual_image_generation_enabled": self.app_config.image.manual_image_generation_enabled,
                "campaign_auto_visual_timing": self._normalize_campaign_auto_visual_timing(
                    self.app_config.image.campaign_auto_visual_timing
                ),
                "checkpoint_source": self.app_config.image.checkpoint_source,
                "checkpoint_model_page": self.app_config.image.checkpoint_model_page,
                "checkpoint_folder": self.app_config.image.checkpoint_folder,
                "preferred_checkpoint": self.app_config.image.preferred_checkpoint,
                "preferred_launcher": self.app_config.image.preferred_launcher,
            },
            "path_config": self.get_path_configuration_status(),
            "dependency_readiness": self.get_dependency_readiness(),
            "supported_models": self.get_supported_model_inventory(refresh=False),
        }

    def set_global_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_payload = payload.get("model", {})
        image_payload = payload.get("image", {})
        model_provider = str(model_payload.get("provider", self.app_config.model.provider)).lower().strip()
        if model_provider not in {"null", "ollama", "gpt4all", "local_template"}:
            raise ValueError("Unsupported model provider")
        image_provider = str(image_payload.get("provider", self.app_config.image.provider)).lower().strip()
        if image_provider not in {"local", "comfyui", "null"}:
            raise ValueError("Unsupported image provider")
        self.app_config.model = ModelRuntimeConfig(
            provider=model_provider,
            model_name=str(model_payload.get("model_name", self.app_config.model.model_name)),
            base_url=str(model_payload.get("base_url", self.app_config.model.base_url)),
            timeout_seconds=int(model_payload.get("timeout_seconds", self.app_config.model.timeout_seconds)),
            ollama_path=str(model_payload.get("ollama_path", self.app_config.model.ollama_path)),
        )
        self.app_config.image = ImageRuntimeConfig(
            provider="null" if image_provider == "null" else image_provider,
            base_url=str(image_payload.get("base_url", self.app_config.image.base_url)),
            enabled=bool(image_payload.get("enabled", self.app_config.image.enabled)),
            comfyui_path=str(image_payload.get("comfyui_path", self.app_config.image.comfyui_path)),
            comfyui_workflow_path=str(image_payload.get("comfyui_workflow_path", self.app_config.image.comfyui_workflow_path)),
            comfyui_output_dir=str(image_payload.get("comfyui_output_dir", self.app_config.image.comfyui_output_dir)),
            manual_image_generation_enabled=bool(
                image_payload.get("manual_image_generation_enabled", self.app_config.image.manual_image_generation_enabled)
            ),
            campaign_auto_visual_timing=self._normalize_campaign_auto_visual_timing(
                image_payload.get(
                    "campaign_auto_visual_timing",
                    image_payload.get("turn_visuals_mode", self.app_config.image.campaign_auto_visual_timing),
                )
            ),
            checkpoint_source=str(image_payload.get("checkpoint_source", self.app_config.image.checkpoint_source)),
            checkpoint_model_page=str(image_payload.get("checkpoint_model_page", self.app_config.image.checkpoint_model_page)),
            checkpoint_folder=str(image_payload.get("checkpoint_folder", self.app_config.image.checkpoint_folder)),
            preferred_checkpoint=str(image_payload.get("preferred_checkpoint", self.app_config.image.preferred_checkpoint)),
            preferred_launcher=str(image_payload.get("preferred_launcher", self.app_config.image.preferred_launcher)),
        )
        self.config_store.save(self.app_config)
        self.engine.model = self._create_model_adapter()
        self.image_adapter = self._create_image_adapter()
        model_status = self.get_model_status()
        print(
            f"[settings] model_provider={self.app_config.model.provider} model={self.app_config.model.model_name} "
            f"image_provider={self.app_config.image.provider} model_ready={model_status.get('ready')}"
        )
        return self.get_global_settings()

    def set_campaign_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = self.session.state
        settings = state.settings
        requested = {
            "campaign": self.session.active_slot,
            "image_generation_enabled": bool(payload.get("image_generation_enabled", settings.image_generation_enabled)),
            "suggested_moves_enabled": bool(payload.get("suggested_moves_enabled", settings.suggested_moves_enabled)),
            "player_suggested_moves_override": payload.get("player_suggested_moves_override", settings.player_suggested_moves_override),
        }
        print(f"[campaign-settings] apply requested {json.dumps(requested)}")
        settings.profile = str(payload.get("profile", settings.profile))
        settings.narration_tone = str(payload.get("narration_tone", settings.narration_tone))
        settings.mature_content_enabled = bool(payload.get("mature_content_enabled", settings.mature_content_enabled))
        settings.image_generation_enabled = bool(payload.get("image_generation_enabled", settings.image_generation_enabled))
        settings.suggested_moves_enabled = bool(payload.get("suggested_moves_enabled", settings.suggested_moves_enabled))
        requested_display_mode = str(payload.get("display_mode", settings.display_mode)).strip().lower()
        if requested_display_mode in {"story", "mud", "rpg"}:
            settings.display_mode = requested_display_mode
        raw_override = payload.get("player_suggested_moves_override", settings.player_suggested_moves_override)
        settings.player_suggested_moves_override = None if raw_override is None else bool(raw_override)
        content = payload.get("content_settings", {})
        settings.content_settings = CampaignSettings.ContentSettings(
            tone=str(content.get("tone", settings.content_settings.tone)),
            maturity_level=str(content.get("maturity_level", settings.content_settings.maturity_level)),
            thematic_flags=list(content.get("thematic_flags", settings.content_settings.thematic_flags)),
        )
        play_style = payload.get("play_style", {})
        requested_scene_visual_mode = play_style.get("scene_visual_mode") if isinstance(play_style, dict) else None
        legacy_auto_visuals_enabled = payload.get("campaign_auto_visuals_enabled")
        if requested_scene_visual_mode is None and legacy_auto_visuals_enabled is not None:
            requested_scene_visual_mode = "after_narration" if bool(legacy_auto_visuals_enabled) else "manual"
        settings.play_style = CampaignSettings.PlayStyleSettings(
            allow_freeform_powers=bool(
                play_style.get("allow_freeform_powers", settings.play_style.allow_freeform_powers)
            ),
            auto_update_character_sheet_from_actions=bool(
                play_style.get(
                    "auto_update_character_sheet_from_actions", settings.play_style.auto_update_character_sheet_from_actions
                )
            ),
            strict_sheet_enforcement=bool(
                play_style.get("strict_sheet_enforcement", settings.play_style.strict_sheet_enforcement)
            ),
            auto_sync_player_declared_identity=bool(
                play_style.get("auto_sync_player_declared_identity", settings.play_style.auto_sync_player_declared_identity)
            ),
            auto_generate_npc_personalities=bool(
                play_style.get("auto_generate_npc_personalities", settings.play_style.auto_generate_npc_personalities)
            ),
            auto_evolve_npc_personalities=bool(
                play_style.get("auto_evolve_npc_personalities", settings.play_style.auto_evolve_npc_personalities)
            ),
            reactive_world_persistence=bool(
                play_style.get("reactive_world_persistence", settings.play_style.reactive_world_persistence)
            ),
            narration_format_mode=self._normalize_narration_format_mode(
                play_style.get("narration_format_mode", settings.play_style.narration_format_mode)
            ),
            scene_visual_mode=self._normalize_scene_visual_mode(
                play_style.get("scene_visual_mode", settings.play_style.scene_visual_mode)
            ),
        )
        self.save_active_campaign(self.session.active_slot)
        print(
            "[settings] persisted_scene_visual_mode="
            f"{self._normalize_scene_visual_mode(settings.play_style.scene_visual_mode)}"
        )
        serialized = self.serialize_state()["settings"]
        print(
            "[campaign-settings] apply succeeded "
            f"campaign={self.session.active_slot} suggested_moves={str(serialized['effective_suggested_moves_enabled']).lower()} "
            f"scene_visual_mode={serialized['play_style']['scene_visual_mode']} "
            f"image_generation={str(serialized['image_generation_enabled']).lower()}"
        )
        return serialized

    def list_available_local_models(self) -> list[str]:
        adapter = self._create_model_adapter()
        if hasattr(adapter, "list_local_models"):
            return getattr(adapter, "list_local_models")()
        return []

    def _list_installed_ollama_model_names(self) -> set[str]:
        adapter = OllamaAdapter(
            model=self.app_config.model.model_name,
            base_url=self.app_config.model.base_url,
            timeout_seconds=self.app_config.model.timeout_seconds,
        )
        names = adapter.list_local_models()
        installed: set[str] = set()
        for name in names:
            clean = str(name or "").strip()
            if not clean:
                continue
            installed.add(clean)
            installed.add(clean.split(":", 1)[0])
        return installed

    def _guided_install_instructions(self, model: dict[str, Any]) -> list[str]:
        display = str(model.get("display_name", model.get("id", "model")))
        return [
            f"{display} requires guided import (not one-click Ollama pull in this build).",
            "1) Download a compatible GGUF file from the source page.",
            "2) Create a Modelfile that points to the GGUF file.",
            "3) Run: ollama create <your-local-name> -f <path-to-Modelfile>",
            "4) Return here and click Refresh inventory.",
        ]

    def get_supported_model_inventory(self, refresh: bool = False) -> dict[str, Any]:
        if refresh:
            print("[model-registry] refresh inventory requested")
        installed_names = self._list_installed_ollama_model_names()
        active_id = self.app_config.model.model_name.strip().lower()
        active_match_id = active_id
        entries: list[dict[str, Any]] = []
        for model in get_supported_models():
            payload = model.to_dict()
            ollama_name = str(payload.get("ollama_name", "")).strip()
            installed = bool(ollama_name and ollama_name in installed_names)
            if not installed and payload.get("id", "") in installed_names:
                installed = True
            if payload.get("id", "") == active_id or (ollama_name and ollama_name == active_id):
                active_match_id = str(payload.get("id", active_id))
            payload["installed"] = installed
            payload["active"] = payload.get("id", "") == active_match_id
            payload["status"] = "active" if payload["active"] else "installed" if installed else "needs_install"
            if payload.get("install_type") == "guided_import":
                payload["install_supported"] = False
                payload["status"] = "needs_import" if not payload["active"] else payload["status"]
                payload["guided_install_steps"] = self._guided_install_instructions(payload)
            elif payload.get("install_type") == "guided_or_ollama_pull":
                payload["install_supported"] = True
                payload["guided_install_steps"] = self._guided_install_instructions(payload)
            entries.append(payload)
        return {"active_model_id": active_match_id, "models": entries}

    def activate_supported_model(self, model_id: str) -> dict[str, Any]:
        model = get_supported_model(model_id)
        if model is None:
            return {"ok": False, "message": f"Unsupported model id: {model_id}"}
        if not model.activate_supported:
            return {"ok": False, "message": f"Model {model.display_name} cannot be activated in this build."}
        target_name = model.ollama_name or model.id
        self.app_config.model = ModelRuntimeConfig(
            provider=model.provider,
            model_name=target_name,
            base_url=self.app_config.model.base_url,
            timeout_seconds=self.app_config.model.timeout_seconds,
            ollama_path=self.app_config.model.ollama_path,
        )
        self.config_store.save(self.app_config)
        self.engine.model = self._create_model_adapter()
        status = self.get_model_status()
        return {
            "ok": True,
            "message": f"Active model switched to {model.display_name}.",
            "active_model_id": model.id,
            "model_status": status,
            "inventory": self.get_supported_model_inventory(refresh=False),
        }

    def install_supported_model(self, model_id: str) -> dict[str, Any]:
        model = get_supported_model(model_id)
        if model is None:
            return {"ok": False, "status": "failed", "message": f"Unsupported model id: {model_id}", "model": model_id}
        if model.install_type == "guided_import":
            return {
                "ok": False,
                "status": "failed",
                "message": f"{model.display_name} requires guided import.",
                "model": model.id,
                "install_type": model.install_type,
                "guided_install_steps": self._guided_install_instructions(model.to_dict()),
            }
        target = model.ollama_name or model.id
        print(f"[model-install] supported model request model_id={model.id} resolved_target={target}")
        result = self._start_model_install(target)
        result["model_id"] = model.id
        if (not result.get("ok", False)) and model.install_type == "guided_or_ollama_pull":
            result["guided_install_steps"] = self._guided_install_instructions(model.to_dict())
        result["inventory"] = self.get_supported_model_inventory(refresh=False)
        return result

    def generate_image(self, payload: dict[str, Any]) -> ImageGenerationResult:
        if not self.session.state.settings.image_generation_enabled:
            return ImageGenerationResult(success=False, workflow_id=str(payload.get("workflow_id", "scene_image")), error="Image generation is disabled for this campaign.")
        path_config = self.get_path_configuration_status()["image"]
        if self.app_config.image.provider == "comfyui":
            if not path_config["comfyui_root"]["valid"]:
                return ImageGenerationResult(
                    success=False,
                    workflow_id=str(payload.get("workflow_id", "scene_image")),
                    error=str(path_config["comfyui_root"]["message"]),
                    metadata={"provider": "comfyui", "status_code": "setup_required"},
                )
            if not path_config["workflow_path"]["valid"]:
                return ImageGenerationResult(
                    success=False,
                    workflow_id=str(payload.get("workflow_id", "scene_image")),
                    error=str(path_config["workflow_path"]["message"]),
                    metadata={"provider": "comfyui", "status_code": "workflow_required"},
                )
        if self.app_config.image.provider == "comfyui":
            image_status = self.get_image_status()
            if not bool(image_status.get("ready", False)):
                return ImageGenerationResult(
                    success=False,
                    workflow_id=str(payload.get("workflow_id", "scene_image")),
                    error=str(image_status.get("user_message", "ComfyUI is not ready.")),
                    metadata={
                        "provider": "comfyui",
                        "status_code": image_status.get("status_code", ""),
                        "next_action": image_status.get("next_action", ""),
                    },
                )
        parameters = dict(payload.get("parameters", {}))
        if self.app_config.image.preferred_checkpoint and "checkpoint" not in parameters:
            parameters["checkpoint"] = self.app_config.image.preferred_checkpoint
        request = ImageGenerationRequest(
            workflow_id=str(payload.get("workflow_id", "scene_image")),
            prompt=str(payload.get("prompt", "")),
            negative_prompt=str(payload.get("negative_prompt", "")),
            parameters=parameters,
        )
        workflow_manager = self.workflow_manager
        configured_workflow = str(self.app_config.image.comfyui_workflow_path or "").strip()
        if configured_workflow:
            workflow_path = Path(configured_workflow)
            request.workflow_id = workflow_path.stem
            workflow_manager = WorkflowManager(workflow_path.parent)
        result = self.image_adapter.generate(request, workflow_manager)
        return result

    def get_comfy_debug_bundle(self) -> dict[str, Any]:
        adapter_snapshot: dict[str, Any] = {}
        if hasattr(self.image_adapter, "get_debug_snapshot"):
            try:
                adapter_snapshot = getattr(self.image_adapter, "get_debug_snapshot")()
            except Exception as exc:
                adapter_snapshot = {"error": str(exc)}
        return {
            "workflow_debug": dict(getattr(self.workflow_manager, "last_debug_info", {})),
            "adapter_debug": adapter_snapshot,
        }

    def public_image_path(self, result_path: str | None) -> str | None:
        if not result_path:
            return None
        local_path = Path(result_path)
        try:
            relative = local_path.resolve().relative_to(self.generated_image_dir.resolve())
        except ValueError:
            return None
        return f"/generated/{relative.as_posix()}"


def _resolve_static_root() -> Path:
    candidates = [static_dir(), project_root() / "static"]
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        candidates.extend([executable_root / "app" / "static", executable_root / "static"])
    for candidate in candidates:
        if candidate.exists() and (candidate / "index.html").exists():
            return candidate
    return static_dir()


def create_web_app(runtime: WebRuntime, static_root: Path) -> Any:
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed")
    app = FastAPI(title="Adventurer Guild AI Web API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=static_root), name="static")
    app.mount("/generated", StaticFiles(directory=runtime.generated_image_dir), name="generated")

    @app.on_event("startup")
    async def _log_server_ready() -> None:
        print("Server ready (health endpoint active)")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

    @app.get("/")
    def root() -> FileResponse:
        index_path = static_root / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="index.html not found")
        return FileResponse(index_path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}


    @app.get("/api/debug/comfyui-last")
    def debug_comfyui_last() -> dict[str, Any]:
        return runtime.get_comfy_debug_bundle()

    @app.get("/api/campaign/state")
    def campaign_state() -> dict[str, Any]:
        return {"state": runtime.serialize_state()}

    @app.get("/api/campaign/messages")
    def campaign_messages(limit: int = 200) -> dict[str, Any]:
        safe_limit = max(limit, 1)
        return {"messages": runtime.session.message_history[-safe_limit:]}

    @app.get("/api/campaign/scene-visual")
    def campaign_scene_visual() -> dict[str, Any]:
        return {"scene_visual": runtime._scene_visual_for_slot()}

    @app.get("/api/campaign/inventory")
    def campaign_inventory() -> dict[str, Any]:
        return {"inventory": runtime.get_inventory_state()}

    @app.get("/api/campaign/spellbook")
    def campaign_spellbook() -> dict[str, Any]:
        return {"spellbook": runtime.get_spellbook_state()}

    @app.get("/api/campaign/narrator-rules")
    def campaign_narrator_rules() -> dict[str, Any]:
        return {"rules": runtime.get_narrator_rules()}

    @app.get("/api/campaign/world-building")
    def campaign_world_building() -> dict[str, Any]:
        return {"world_building": runtime.get_world_building_view()}

    @app.post("/api/campaign/recalibrate")
    def campaign_recalibrate() -> dict[str, Any]:
        return runtime.recalibrate_campaign_state(runtime.session.state)

    @app.get("/api/campaign/debug/narrator-packet")
    def campaign_narrator_packet() -> dict[str, Any]:
        return runtime.get_narrator_debug_packet()

    @app.post("/api/campaign/spellbook")
    def campaign_spellbook_update(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.upsert_spellbook_entry(payload)
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/campaign/character-sheets")
    def campaign_character_sheets_update(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.upsert_character_sheet(payload)
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/campaign/narrator-rules")
    def campaign_narrator_rules_update(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.upsert_narrator_rule(payload)
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.get("/api/campaign/saves")
    def campaign_saves() -> dict[str, Any]:
        return {"saves": runtime.list_saves()}

    @app.get("/api/campaigns")
    def campaigns() -> dict[str, Any]:
        return {"campaigns": runtime.list_campaigns()}

    @app.get("/api/settings/global")
    def settings_global() -> dict[str, Any]:
        return {"settings": runtime.get_global_settings()}

    @app.get("/api/model/options")
    def model_options() -> dict[str, Any]:
        return {"models": runtime.list_available_local_models()}

    @app.get("/api/model/status")
    def model_status() -> dict[str, Any]:
        return {"status": runtime.get_model_status()}

    @app.get("/api/models/supported")
    def supported_models() -> dict[str, Any]:
        return runtime.get_supported_model_inventory(refresh=False)

    @app.get("/api/models/active")
    def active_model() -> dict[str, Any]:
        inventory = runtime.get_supported_model_inventory(refresh=False)
        return {"active_model_id": inventory.get("active_model_id", ""), "model_status": runtime.get_model_status()}

    @app.post("/api/models/refresh")
    def refresh_models() -> dict[str, Any]:
        return runtime.get_supported_model_inventory(refresh=True)

    @app.post("/api/models/install")
    def install_supported_model(payload: dict[str, Any]) -> dict[str, Any]:
        model_id = str(payload.get("model_id", "")).strip().lower()
        print(f"[model-install] route invoked endpoint=/api/models/install model_id={model_id}")
        return runtime.install_supported_model(model_id)

    @app.get("/api/models/install-status")
    def install_supported_model_status(model: str = "") -> dict[str, Any]:
        print(f"[model-install] route invoked endpoint=/api/models/install-status model={model}")
        return runtime.get_model_install_status(model)

    @app.post("/api/models/activate")
    def activate_supported_model(payload: dict[str, Any]) -> dict[str, Any]:
        model_id = str(payload.get("model_id", "")).strip().lower()
        return runtime.activate_supported_model(model_id)

    @app.get("/api/providers/readiness")
    def providers_readiness() -> dict[str, Any]:
        return runtime.get_dependency_readiness()

    @app.post("/api/setup/start-ollama")
    def setup_start_ollama() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/start-ollama")
        return runtime.start_ollama_service()

    @app.post("/api/setup/install-ollama")
    def setup_install_ollama() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/install-ollama")
        return runtime.install_ollama()

    @app.post("/api/setup/install-model")
    def setup_install_model(payload: dict[str, Any]) -> dict[str, Any]:
        model_name = str(payload.get("model", "")).strip() or None
        print(f"[setup-action] route invoked endpoint=/api/setup/install-model model={model_name or runtime.app_config.model.model_name}")
        target_model = model_name or runtime.app_config.model.model_name
        print(f"[model-install] setup route payload model={target_model}")
        return runtime._start_model_install(target_model)


    @app.post("/api/setup/test-image-pipeline")
    def setup_test_image_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt", "test fantasy portrait")).strip() or "test fantasy portrait"
        print("[setup-action] route invoked endpoint=/api/setup/test-image-pipeline")
        return runtime.test_image_pipeline(prompt=prompt)

    @app.post("/api/setup/install-image-engine")
    def setup_install_image_engine() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/install-image-engine")
        return runtime.install_image_engine()

    @app.post("/api/setup/start-image-engine")
    def setup_start_image_engine() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/start-image-engine")
        return runtime.start_image_engine()

    @app.post("/api/setup/orchestrate-text")
    def setup_orchestrate_text(payload: dict[str, Any]) -> dict[str, Any]:
        model_name = str(payload.get("model", "")).strip() or None
        print(f"[setup-action] route invoked endpoint=/api/setup/orchestrate-text model={model_name or runtime.app_config.model.model_name}")
        return runtime.orchestrate_setup_text_ai(model_name)

    @app.post("/api/setup/orchestrate-image")
    def setup_orchestrate_image() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/orchestrate-image")
        return runtime.orchestrate_setup_image_ai()

    @app.post("/api/setup/orchestrate-everything")
    def setup_orchestrate_everything(payload: dict[str, Any]) -> dict[str, Any]:
        model_name = str(payload.get("model", "")).strip() or None
        print(f"[setup-action] route invoked endpoint=/api/setup/orchestrate-everything model={model_name or runtime.app_config.model.model_name}")
        return runtime.orchestrate_setup_everything(model_name)

    @app.post("/api/setup/pick-folder")
    def setup_pick_folder(payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title", "Select folder"))
        initial_path = str(payload.get("initial_path", ""))
        return runtime.pick_folder(title=title, initial_path=initial_path)

    @app.post("/api/setup/pick-file")
    def setup_pick_file(payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title", "Select file"))
        initial_path = str(payload.get("initial_path", ""))
        filters = payload.get("filters", [".json"])
        safe_filters = [str(item) for item in filters if str(item).startswith(".")] if isinstance(filters, list) else [".json"]
        return runtime.pick_file(title=title, initial_path=initial_path, filters=safe_filters or [".json"])

    @app.post("/api/setup/connect-ollama-path")
    def setup_connect_ollama_path(payload: dict[str, Any]) -> dict[str, Any]:
        selected_path = str(payload.get("path", ""))
        return runtime.connect_ollama_path(selected_path)

    @app.post("/api/setup/connect-comfyui-path")
    def setup_connect_comfyui_path(payload: dict[str, Any]) -> dict[str, Any]:
        selected_path = str(payload.get("path", ""))
        return runtime.connect_comfyui_path(selected_path)

    @app.get("/api/setup/comfyui-models")
    def setup_comfyui_models() -> dict[str, Any]:
        return runtime.get_comfyui_model_status()

    @app.post("/api/campaign/input")
    def campaign_input(payload: dict[str, Any]) -> dict[str, Any]:
        player_text = str(payload.get("text", "")).strip()
        if not player_text:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="'text' is required")
        return runtime.handle_player_input(player_text)

    @app.post("/api/campaign/start")
    def campaign_start(payload: dict[str, Any]) -> dict[str, Any]:
        mode = payload.get("mode", "load")
        try:
            if mode == "new":
                return {"mode": "new", **runtime.create_campaign(payload)}
            slot = str(payload.get("slot", "autosave"))
            return {"mode": "load", **runtime.switch_campaign(slot)}
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/campaign/save")
    def campaign_save(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.save_active_campaign(str(payload.get("slot", "")).strip() or None)
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/campaign/delete")
    def campaign_delete(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.delete_campaign(str(payload.get("slot", "")))
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/campaign/rename")
    def campaign_rename(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.rename_campaign(str(payload.get("slot", "")), str(payload.get("new_name", "")))
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/settings/global")
    def settings_global_update(payload: dict[str, Any]) -> dict[str, Any]:
        return {"settings": runtime.set_global_settings(payload)}

    @app.post("/api/settings/visual-pipeline/validate")
    def settings_visual_pipeline_validate(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "path_config": runtime.validate_visual_pipeline_config(payload)}

    @app.post("/api/settings/visual-pipeline")
    def settings_visual_pipeline_update(payload: dict[str, Any]) -> dict[str, Any]:
        return runtime.apply_visual_pipeline_settings(payload)

    @app.post("/api/settings/campaign")
    def settings_campaign_update(payload: dict[str, Any]) -> dict[str, Any]:
        return {"settings": runtime.set_campaign_settings(payload)}

    @app.post("/api/images/generate")
    def image_generate(payload: dict[str, Any]) -> dict[str, Any]:
        if not runtime.app_config.image.manual_image_generation_enabled:
            return JSONResponse(
                status_code=HTTPStatus.BAD_REQUEST,
                content={
                    "ok": False,
                    "error": "Manual image generation is disabled in global settings.",
                    "workflow_id": str(payload.get("workflow_id", "scene_image")),
                },
            )
        print("[image-pipeline] request started")
        shared_result = runtime._request_scene_visual_generation(
            source="manual",
            stage="manual",
            player_action="",
            narrator_response="",
            prompt_override=str(payload.get("prompt", "")),
        )
        result = shared_result["result"]
        response_payload = result.to_dict()
        if shared_result.get("ok"):
            image_meta = {}
            if isinstance(result.metadata, dict):
                image_meta = dict(result.metadata.get("image", {}) or result.metadata.get("image_info", {}) or {})
            response_payload["ok"] = True
            response_payload["prompt"] = shared_result.get("prompt", payload.get("prompt", ""))
            response_payload["image"] = {
                "filename": image_meta.get("filename", ""),
                "subfolder": image_meta.get("subfolder", ""),
                "type": image_meta.get("type", "output"),
                "url": shared_result.get("image_url"),
            }
            response_payload["scene_visual"] = runtime._scene_visual_for_slot()
            print("[image-pipeline] image display updated")
        if not shared_result.get("ok"):
            reason = result.metadata.get("error_category", "unknown") if isinstance(result.metadata, dict) else "unknown"
            status_code = result.metadata.get("status_code", 400) if isinstance(result.metadata, dict) else 400
            print(f"[image-pipeline] request failed status={status_code} reason={reason}")
            response_payload["ok"] = False
            return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content=response_payload)
        return response_payload

    return app
