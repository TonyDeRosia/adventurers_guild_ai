"""Local web chat runtime and HTTP API for Adventurer Guild AI."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import sys
import urllib.error
import urllib.request
import zipfile
from difflib import SequenceMatcher
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

from app.pathing import (
    bundled_comfyui_dir,
    bundled_workflow_dir,
    initialize_user_data_paths,
    project_root,
    static_dir,
)
from app.comfy_manager import ComfyProcessManager
from app.desktop_capabilities import DesktopIntegration
from app.installer_layout import InstallerLayoutValidator
from app.npc_identity import NPCIdentityRegistry
from app.runtime_config import AppRuntimeConfig, ImageRuntimeConfig, ModelRuntimeConfig, RuntimeConfigStore
from engine.campaign_engine import CampaignEngine, TurnResult
from engine.character_sheets import CharacterSheet, CharacterSheetAbilityEntry
from engine.entities import CampaignSettings, CampaignState
from engine.game_state_manager import GameStateManager
from engine.spellbook import normalize_spellbook_entry
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
        self.comfy_manager = ComfyProcessManager()
        self.desktop = DesktopIntegration()

        self.engine = CampaignEngine(self._create_model_adapter(), data_dir=self.paths.content_data)
        self.image_adapter = self._create_image_adapter()
        default_slot = "autosave" if self.state_manager.can_load("autosave") else "campaign_1"
        self.session = WebSession(state=self._load_or_create(default_slot), active_slot=default_slot)
        self.session.message_history = self._history_for_slot(self.session.active_slot)
        self.image_startup_status: dict[str, Any] = {}
        self._image_startup_lock = threading.Lock()
        self._image_bootstrap_thread: threading.Thread | None = None
        self._image_bootstrap_active = False
        self._image_engine_state = "installed"
        self._image_engine_last_error = ""
        self._image_engine_last_health_check = ""
        self._history_lock = threading.Lock()
        self._turn_visual_lock = threading.Lock()
        self._active_turn_visual_jobs: set[tuple[str, int, str]] = set()
        self._npc_portrait_lock = threading.Lock()
        self._active_npc_portrait_jobs: set[tuple[str, str]] = set()
        self._model_install_lock = threading.Lock()
        self._model_install_jobs: dict[str, dict[str, Any]] = {}
        self._apply_managed_image_engine_defaults()
        print("[web-runtime] session initialized")

    def _set_image_startup_status(self, **payload: Any) -> None:
        with self._image_startup_lock:
            self.image_startup_status = payload

    def _update_image_bootstrap_progress(self, *, state: str, step: str, summary: str, **extra: Any) -> None:
        payload = {
            "state": state,
            "stage": step,
            "current_step": step,
            "summary": summary,
            **extra,
        }
        self._set_image_startup_status(**payload)
        print(f"[image-bootstrap] state={state} step={step} summary={summary}")

    def shutdown_managed_services(self) -> None:
        """Shutdown managed local subprocesses owned by this runtime."""
        self.comfy_manager.clear_if_exited()
        if self.comfy_manager.snapshot().running:
            print("[shutdown] stopping managed ComfyUI process...")
            stopped = self.comfy_manager.shutdown()
            if stopped:
                print("[shutdown] managed ComfyUI process stopped")
            else:
                print("[shutdown] managed ComfyUI process could not be stopped cleanly")

    def auto_start_image_backend_if_needed(self) -> None:
        """Best-effort startup for packaged desktop mode.

        If image generation is enabled with ComfyUI and paths are valid, attempt
        to launch and manage ComfyUI automatically. Failures are surfaced via
        normal readiness APIs so the UI can guide first-run setup.
        """
        if not self.app_config.image.enabled or self.app_config.image.provider != "comfyui":
            return
        if self.get_image_status().get("reachable", False):
            return
        path_status = self.get_path_configuration_status().get("image", {})
        if str(path_status.get("mode", "managed")) != "managed":
            return
        if bool(path_status.get("pipeline_ready", False)):
            print("[startup] managed ComfyUI configured; scheduling background startup")
        else:
            print("[startup] managed ComfyUI incomplete; scheduling background bootstrap/repair")
        self.start_image_bootstrap_background(trigger="startup")

    def start_image_bootstrap_background(self, *, trigger: str = "manual") -> dict[str, Any]:
        if not self.app_config.image.enabled or self.app_config.image.provider != "comfyui":
            return {"ok": False, "message": "Image provider is not set to comfyui."}
        with self._image_startup_lock:
            if self._image_bootstrap_thread is not None and self._image_bootstrap_thread.is_alive():
                return {"ok": True, "status": "running", "message": "Image bootstrap is already running."}
            self._image_bootstrap_active = True
            self.image_startup_status = {
                "state": "queued",
                "stage": "queued",
                "current_step": "queued",
                "summary": "Image AI bootstrap queued.",
                "trigger": trigger,
            }

        def _runner() -> None:
            print(f"[startup] background image bootstrap started trigger={trigger}")
            self._update_image_bootstrap_progress(
                state="repairing install",
                step="repair-install",
                summary="Preparing managed ComfyUI install in background.",
                trigger=trigger,
            )
            result = self.start_image_engine(startup_mode="background")
            if result.get("ok", False):
                self._update_image_bootstrap_progress(
                    state="ready",
                    step="ready",
                    summary=str(result.get("message", "Image AI is ready.")),
                    trigger=trigger,
                )
                print("[startup] background image bootstrap completed")
            else:
                self._update_image_bootstrap_progress(
                    state="failed",
                    step=str(result.get("failure_stage", "failed")),
                    summary=str(result.get("message", "Image AI bootstrap failed.")),
                    trigger=trigger,
                    next_step=str(result.get("next_step", "Retry setup from AI Setup.")),
                    failure_stage=str(result.get("failure_stage", "")),
                )
                print(f"[startup] background image bootstrap failed reason={result.get('message', 'unknown')}")
            with self._image_startup_lock:
                self._image_bootstrap_active = False

        thread = threading.Thread(target=_runner, daemon=True, name=f"image-bootstrap-{trigger}")
        with self._image_startup_lock:
            self._image_bootstrap_thread = thread
        thread.start()
        return {"ok": True, "status": "queued", "message": "Image bootstrap queued in background."}

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
            if turn.display_messages:
                print(f"[npc-dialogue-card] replay_structured_messages turn={turn.turn} count={len(turn.display_messages)}")
                for message in turn.display_messages:
                    msg_type = str(message.get("type", "")).strip().lower()
                    msg_text = str(message.get("text", "")).strip()
                    if not msg_type or not msg_text:
                        continue
                    extra = {k: v for k, v in message.items() if k not in {"type", "text"}}
                    replayed.append(self._message(msg_type, msg_text, **extra))
                continue
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
        managed_running = self.comfy_manager.snapshot().running
        if provider == "comfyui":
            path_config = self.get_path_configuration_status()
            image_paths = path_config["image"]
            checkpoint_state = image_paths["checkpoint_dir"]
            model_ready = bool(checkpoint_state.get("model_ready", checkpoint_state.get("valid", False)))
            model_message = str(checkpoint_state.get("model_message") or checkpoint_state.get("message") or "")
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
                    "user_message": str(image_paths["comfyui_root"].get("message", "ComfyUI path is not configured.")),
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
                    "user_message": str(image_paths["workflow_path"].get("message", "Workflow path is invalid.")),
                    "next_action": "Set your workflow JSON file in AI Setup, then click Recheck.",
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
                    "ready": model_ready,
                    "status_code": "reachable" if model_ready else "model_required",
                    "status_level": "ready" if model_ready else "warning",
                    "user_message": "ComfyUI engine is ready." if model_ready else model_message,
                    "next_action": "No action needed." if model_ready else "Choose a valid checkpoint or clear preferred checkpoint, then click Recheck.",
                    "comfyui_path": str(comfyui_root or ""),
                    "launcher_mode": self._determine_launcher_mode(comfyui_root),
                    "managed_process": managed_running,
                    "engine_ready": True,
                    "model_ready": model_ready,
                    "model_status_code": str(checkpoint_state.get("model_status_code", "")),
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
                    "managed_process": managed_running,
                    "engine_ready": False,
                    "model_ready": model_ready,
                    "model_status_code": str(checkpoint_state.get("model_status_code", "")),
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
                "managed_process": managed_running,
                "engine_ready": False,
                "model_ready": model_ready,
                "model_status_code": str(checkpoint_state.get("model_status_code", "")),
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
                "managed_process": managed_running,
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
            "managed_process": managed_running,
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
            "first_run_status": self.get_first_run_status(),
            "desktop_capabilities": self.desktop.capabilities.to_dict(),
            "primary_actions": [
                {"id": "setup_text_ai", "label": "Set Up Text AI"},
                {"id": "setup_image_ai", "label": "Set Up Image AI"},
                {"id": "setup_everything", "label": "Set Up Everything"},
            ],
            "setup_checklist": [
                "Primary onboarding actions:",
                "1) Click Set Up Text AI to install/start Ollama and install the selected model.",
                "2) (Optional) Click Set Up Image AI to enable image generation with bundled ComfyUI.",
                "3) Click Set Up Everything to run both in sequence.",
                "Fallback actions:",
                "Use Recheck and Copy command if a step fails and manual intervention is needed.",
                "Fallback story mode stays available even when providers are missing.",
            ],
            "setup_guidance": [
                "Adventurer Guild AI is the platform; external tools/models are user-managed dependencies.",
                "Ollama is used for story narration when model provider is set to ollama.",
                "Start Ollama before playing: ollama serve",
                f"Install a missing model with: ollama pull {self.app_config.model.model_name}",
                "ComfyUI is used when image provider is set to comfyui for image generation requests and is bundled in end-user installers.",
                "Image models/checkpoints are not bundled; use an existing model folder or download from official model pages.",
                "If providers are unavailable, the app still runs with local narrator fallback mode.",
            ],
        }

    def _image_readiness_actions(self, image_status: dict[str, Any]) -> list[dict[str, str]]:
        if self.app_config.image.provider != "comfyui":
            return [{"id": "recheck", "label": "Recheck"}]
        status_code = str(image_status.get("status_code", ""))
        if status_code in {"setup_required", "workflow_required", "checkpoint_required", "model_required"}:
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
        return self.desktop.pick_folder(title=title, initial_path=initial_path or str(self.paths.user_data))

    def pick_file(self, title: str, initial_path: str = "", filters: list[str] | None = None) -> dict[str, Any]:
        return self.desktop.pick_file(title=title, initial_path=initial_path or str(self.paths.user_data), filters=filters)

    def get_desktop_capabilities(self) -> dict[str, Any]:
        return {"ok": True, "desktop": self.desktop.capabilities.to_dict()}

    def open_external_url(self, url: str) -> dict[str, Any]:
        return self.desktop.open_external_url(url)

    def open_local_path(self, path: str) -> dict[str, Any]:
        return self.desktop.open_local_path(path)

    def get_image_setup_snapshot(self) -> dict[str, Any]:
        path_status = self.get_path_configuration_status().get("image", {})
        image_status = self.get_image_status()
        layout_status = self.get_installer_layout_status()
        bundled_runtime = layout_status.get("checks", {}).get("bundled_image_runtime", {})
        bundled_available = bool(bundled_runtime.get("present", False))
        bundled_path = str(bundled_runtime.get("path", "")) if bundled_available else ""
        checkpoint_dir = path_status.get("checkpoint_dir", {})
        first_run = self.get_first_run_status()
        return {
            "ok": True,
            "image_provider": self.app_config.image.provider,
            "image_readiness_state": {
                "ready": bool(image_status.get("ready", False)),
                "engine_ready": bool(image_status.get("engine_ready", False)),
                "model_ready": bool(image_status.get("model_ready", False)),
                "status_code": str(image_status.get("status_code", "")),
                "message": str(image_status.get("user_message", "")),
            },
            "bundled_comfyui_available": bundled_available,
            "bundled_comfyui_path": bundled_path,
            "checkpoint_folder_configured": bool(checkpoint_dir.get("configured", False) or checkpoint_dir.get("path", "")),
            "checkpoint_folder_valid": bool(checkpoint_dir.get("valid", False)),
            "checkpoint_folder_message": str(checkpoint_dir.get("message", "")),
            "checkpoint_model_ready": bool(checkpoint_dir.get("model_ready", False)),
            "checkpoint_model_message": str(checkpoint_dir.get("model_message", "")),
            "text_only_fallback_available": True,
            "text_only_mode_active": self.app_config.image.provider == "null",
            "recommended_model_page": str(self.app_config.image.checkpoint_model_page or "").strip(),
            "installer_layout": layout_status,
            "first_run_status": first_run,
        }

    def get_image_backend_diagnostics(self) -> dict[str, Any]:
        path_status = self.get_path_configuration_status().get("image", {})
        image_status = self.get_image_status()
        managed_state = self.comfy_manager.snapshot()
        provider = str(self.app_config.image.provider or "").strip() or "null"
        comfy_root = path_status.get("comfyui_root", {})
        workflow_status = path_status.get("workflow_path", {})
        output_status = path_status.get("output_dir", {})
        checkpoint_status = path_status.get("checkpoint_dir", {})
        resolved_comfy_path = str(comfy_root.get("resolved_path") or comfy_root.get("path") or "").strip()
        install_validation = (
            self.validate_comfyui_install(Path(resolved_comfy_path))
            if resolved_comfy_path and Path(resolved_comfy_path).exists()
            else {"ok": False, "missing_files": ["comfyui-root"], "python_runtime_found": False}
        )
        runtime_pip = {"checked": False, "available": False, "version": "", "detail": "", "runtime_command": []}
        runtime_dependency_probe = {"checked": False, "ok": False, "detail": "", "module": "sqlalchemy"}
        if install_validation.get("ok", False) and resolved_comfy_path:
            launch_command, launcher_type = self._build_comfy_launch_command(Path(resolved_comfy_path), "127.0.0.1", 8188)
            runtime_resolution = self._resolve_comfy_python_runtime(launch_command, launcher_type)
            if runtime_resolution.get("ok", False):
                runtime_command = list(runtime_resolution.get("runtime_command", []))
                try:
                    pip_check = self._run_runtime_python_capture(runtime_command, ["-m", "pip", "--version"], timeout_seconds=20)
                    runtime_pip = {
                        "checked": True,
                        "available": pip_check.returncode == 0,
                        "version": (pip_check.stdout or pip_check.stderr or "").strip() if pip_check.returncode == 0 else "",
                        "detail": self._command_output_snippet(pip_check),
                        "runtime_command": runtime_command,
                    }
                except (OSError, subprocess.SubprocessError) as exc:
                    runtime_pip = {
                        "checked": True,
                        "available": False,
                        "version": "",
                        "detail": str(exc),
                        "runtime_command": runtime_command,
                    }
                if runtime_pip.get("available", False):
                    try:
                        dep_probe = self._run_runtime_python_capture(runtime_command, ["-c", "import sqlalchemy"], timeout_seconds=20)
                        runtime_dependency_probe = {
                            "checked": True,
                            "ok": dep_probe.returncode == 0,
                            "detail": self._command_output_snippet(dep_probe),
                            "module": "sqlalchemy",
                        }
                    except (OSError, subprocess.SubprocessError) as exc:
                        runtime_dependency_probe = {
                            "checked": True,
                            "ok": False,
                            "detail": str(exc),
                            "module": "sqlalchemy",
                        }
        runtime_missing_items = list(install_validation.get("missing_files", []))
        if runtime_pip.get("checked") and not runtime_pip.get("available"):
            runtime_missing_items.append("pip")
        if runtime_dependency_probe.get("checked") and not runtime_dependency_probe.get("ok"):
            runtime_missing_items.append(f"dependency:{runtime_dependency_probe.get('module', 'unknown')}")
        startup_status = dict(self.image_startup_status or {})
        workflow_parse_valid = None
        workflow_parse_message = "Workflow parse was not checked."
        resolved_workflow = str(workflow_status.get("resolved_path") or workflow_status.get("path") or "").strip()
        if resolved_workflow:
            try:
                payload = json.loads(Path(resolved_workflow).read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    workflow_parse_valid = True
                    workflow_parse_message = "Workflow JSON parsed successfully."
                else:
                    workflow_parse_valid = False
                    workflow_parse_message = "Workflow JSON root must be an object."
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                workflow_parse_valid = False
                workflow_parse_message = f"Workflow JSON could not be parsed: {exc}"

        diagnostics = {
            "provider_selected": provider,
            "image_backend_mode": str(path_status.get("mode", "managed")),
            "managed_mode_active": str(path_status.get("mode", "managed")) == "managed",
            "image_generation_enabled": bool(self.app_config.image.enabled),
            "text_only_mode_active": provider == "null" or not bool(self.app_config.image.enabled),
            "comfyui_path_configured": bool(comfy_root.get("configured", False)),
            "comfyui_path": str(comfy_root.get("resolved_path") or comfy_root.get("path") or ""),
            "managed_comfyui_root": str(path_status.get("resolved_paths", {}).get("managed_comfyui_root", "")),
            "comfyui_path_exists": bool(comfy_root.get("valid", False)),
            "comfyui_detected": bool(comfy_root.get("valid", False)),
            "comfyui_process_running": bool(image_status.get("reachable", False) or managed_state.running),
            "managed_process_running": bool(managed_state.running),
            "managed_process_pid": managed_state.pid,
            "api_reachable": bool(image_status.get("reachable", False)),
            "workflow_path_configured": bool(workflow_status.get("configured", False) or workflow_status.get("resolved_path")),
            "workflow_path": resolved_workflow,
            "workflow_files_found": bool(workflow_status.get("valid", False)),
            "workflow_parse_valid": workflow_parse_valid,
            "workflow_parse_message": workflow_parse_message,
            "output_path": str(output_status.get("resolved_path") or output_status.get("path") or ""),
            "output_path_valid": bool(output_status.get("valid", False)),
            "checkpoint_configured": bool(checkpoint_status.get("configured", False) or checkpoint_status.get("resolved_path")),
            "checkpoint_path": str(checkpoint_status.get("resolved_path") or checkpoint_status.get("path") or ""),
            "checkpoint_present": bool(checkpoint_status.get("valid", False)),
            "model_ready": bool(checkpoint_status.get("model_ready", checkpoint_status.get("valid", False))),
            "model_status_code": str(checkpoint_status.get("model_status_code", "")),
            "model_status_message": str(checkpoint_status.get("model_message", "")),
            "preferred_checkpoint": str(checkpoint_status.get("preferred_checkpoint", "")),
            "preferred_checkpoint_found": checkpoint_status.get("preferred_checkpoint_found"),
            "preferred_checkpoint_match": str(checkpoint_status.get("preferred_checkpoint_match", "")),
            "custom_node_checks_supported": False,
            "custom_node_checks_passed": None,
            "custom_node_message": "Custom node checks are not currently defined by this app.",
            "status_code": str(image_status.get("status_code", "")),
            "status_message": str(image_status.get("user_message", "")),
            "last_error": str(image_status.get("error", "")).strip() or str(startup_status.get("summary", "")).strip(),
            "recommended_next_action": str(image_status.get("next_action", "Recheck setup and diagnostics.")),
            "startup_status": startup_status,
            "resolved_paths": path_status.get("resolved_paths", {}),
            "python_runtime_path": str((Path(resolved_comfy_path) / ".venv" / "Scripts" / "python.exe") if resolved_comfy_path else ""),
            "python_runtime_found": bool(install_validation.get("python_runtime_found", False)),
            "pip_available": bool(runtime_pip.get("available", False)),
            "pip_version": str(runtime_pip.get("version", "")),
            "pip_check_detail": str(runtime_pip.get("detail", "")),
            "dependency_probe_checked": bool(runtime_dependency_probe.get("checked", False)),
            "dependency_probe_module": str(runtime_dependency_probe.get("module", "")),
            "dependency_probe_ok": bool(runtime_dependency_probe.get("ok", False)),
            "dependency_probe_detail": str(runtime_dependency_probe.get("detail", "")),
            "runtime_complete": bool(
                install_validation.get("ok", False)
                and (not runtime_pip.get("checked") or runtime_pip.get("available"))
                and (not runtime_dependency_probe.get("checked") or runtime_dependency_probe.get("ok"))
            ),
            "runtime_missing_items": runtime_missing_items,
            "install_repairable": bool(
                "main.py" in install_validation.get("missing_files", [])
                or "python-runtime" in install_validation.get("missing_files", [])
                or "pip" in runtime_missing_items
            ),
            "comfyui_root_exists": bool(Path(str(comfy_root.get("resolved_path") or comfy_root.get("path") or "")).exists())
            if str(comfy_root.get("resolved_path") or comfy_root.get("path") or "").strip()
            else False,
            "comfyui_root_structurally_valid": bool(comfy_root.get("valid", False)),
            "last_launch_target": managed_state.launch_target,
        }
        state = "Not Configured"
        if diagnostics["text_only_mode_active"]:
            state = "Disabled"
        elif diagnostics["api_reachable"] and diagnostics["model_ready"]:
            state = "Running"
        elif diagnostics["api_reachable"] and not diagnostics["model_ready"]:
            state = "Engine Ready, Model Pending"
        elif diagnostics["comfyui_detected"] and diagnostics["workflow_files_found"] and diagnostics["checkpoint_present"]:
            state = "Ready"
        elif diagnostics["comfyui_detected"] or diagnostics["workflow_files_found"] or diagnostics["checkpoint_present"]:
            state = "Partially Configured"
        if diagnostics["status_code"] in {"setup_required", "workflow_required", "checkpoint_required"}:
            state = "Partially Configured"
        if diagnostics["status_code"] in {"not_installed"}:
            state = "Not Configured"
        diagnostics["overall_state"] = state
        return {"ok": True, "diagnostics": diagnostics}

    def get_image_engine_service_status(self) -> dict[str, Any]:
        path_status = self.get_path_configuration_status().get("image", {})
        managed_state = self.comfy_manager.snapshot()
        image_status = self.get_image_status() if self.app_config.image.provider == "comfyui" else {}
        install_path = str(
            self.app_config.image.managed_install_path
            or path_status.get("comfyui_root", {}).get("resolved_path")
            or path_status.get("comfyui_root", {}).get("path")
            or self._default_comfyui_path()
        )
        api_url = str(self.app_config.image.base_url or "http://localhost:8188")
        state = self._image_engine_state
        if managed_state.running:
            state = "running"
        elif state not in {"starting", "stopping", "error"}:
            installed = bool(path_status.get("comfyui_root", {}).get("valid", False))
            state = "installed" if installed else "not_installed"
        self._image_engine_last_health_check = datetime.now(timezone.utc).isoformat()
        startup_status = dict(self.image_startup_status or {})
        return {
            "ok": True,
            "state": state,
            "install_path": install_path,
            "process_id": managed_state.pid,
            "api_url": api_url,
            "last_error": self._image_engine_last_error,
            "last_health_check": self._image_engine_last_health_check,
            "managed_process": managed_state.running,
            "workflow_available": bool(path_status.get("workflow_path", {}).get("valid", False)),
            "model_available": bool(path_status.get("checkpoint_dir", {}).get("model_ready", False)),
            "api_reachable": bool(image_status.get("reachable", False)),
            "startup_status": startup_status,
            "bootstrap_active": bool(self._image_bootstrap_active),
        }

    def use_bundled_image_engine(self) -> dict[str, Any]:
        self.app_config.image.provider = "comfyui"
        self.app_config.image.enabled = True
        self.app_config.image.comfyui_path = ""
        self.app_config.image.managed_install_path = str(self._default_comfyui_path())
        self.app_config.image.comfyui_output_dir = str(self.generated_image_dir)
        default_workflow = self._default_workflow_path()
        if default_workflow.exists() and default_workflow.is_file():
            self.app_config.image.comfyui_workflow_path = str(default_workflow)
        self.config_store.save(self.app_config)
        self.image_adapter = self._create_image_adapter()
        return {
            "ok": True,
            "message": "Managed image engine selected. Install or start ComfyUI to finish setup.",
            "path_config": self.get_path_configuration_status(),
            "snapshot": self.get_image_setup_snapshot(),
        }

    def save_checkpoint_folder(self, selected_path: str) -> dict[str, Any]:
        candidate = str(selected_path or "").strip()
        comfyui_status = self.get_path_configuration_status().get("image", {}).get("comfyui_root", {})
        comfyui_path = str(comfyui_status.get("resolved_path") or comfyui_status.get("path") or "")
        validation = self._validate_checkpoint_dir_config(candidate, comfyui_path)
        if not validation.get("valid", False):
            return {
                "ok": False,
                "message": str(validation.get("message", "Checkpoint folder is invalid.")),
                "path_config": self.get_path_configuration_status(),
                "snapshot": self.get_image_setup_snapshot(),
            }
        self.app_config.image.checkpoint_folder = candidate
        self.config_store.save(self.app_config)
        self.image_adapter = self._create_image_adapter()
        return {
            "ok": True,
            "message": "Checkpoint folder saved and validated.",
            "path_config": self.get_path_configuration_status(),
            "snapshot": self.get_image_setup_snapshot(),
        }

    def skip_images_for_now(self) -> dict[str, Any]:
        self.app_config.image.provider = "null"
        self.app_config.image.enabled = False
        self.config_store.save(self.app_config)
        self.image_adapter = self._create_image_adapter()
        return {
            "ok": True,
            "message": "Image setup skipped. Text-only mode is active.",
            "snapshot": self.get_image_setup_snapshot(),
        }

    def get_first_run_status(self) -> dict[str, Any]:
        model_status = self.get_model_status()
        image_status = self.get_image_status()
        path_status = self.get_path_configuration_status().get("image", {})
        layout_status = self.get_installer_layout_status()
        checks = layout_status.get("checks", {})
        bundled_runtime = checks.get("bundled_image_runtime", {})
        bundled_available = bool(bundled_runtime.get("present", False))
        checkpoint_dir = path_status.get("checkpoint_dir", {})
        text_ai_ready = bool(model_status.get("ready", False))
        text_only_mode = self.app_config.image.provider == "null" or not self.app_config.image.enabled
        return {
            "app_installed": {
                "state": "ready" if self.desktop.capabilities.mode.startswith("desktop_") else "not_packaged",
                "message": (
                    "Desktop packaged runtime detected."
                    if self.desktop.capabilities.mode.startswith("desktop_")
                    else "Running from source/developer mode."
                ),
            },
            "text_ai": {
                "state": "ready" if text_ai_ready else "not_ready",
                "message": str(model_status.get("user_message", "")),
            },
            "image_engine_bundle": {
                "state": "ready" if bundled_available else "missing",
                "message": (
                    "Bundled ComfyUI runtime detected."
                    if bundled_available
                    else "Bundled ComfyUI runtime not found in install/runtime_bundle/comfyui."
                ),
                "path": str(bundled_runtime.get("path", "")) if bundled_available else "",
            },
            "bundled_workflows": {
                "state": "ready" if bool(layout_status.get("bundled_workflows_present", False)) else "missing",
                "message": (
                    "Bundled workflow templates are present."
                    if bool(layout_status.get("bundled_workflows_present", False))
                    else "Bundled workflows are missing required files (scene_image.json and/or character_portrait.json)."
                ),
            },
            "venv_runtime": {
                "state": "ready" if bool(layout_status.get("venv_runtime_present", False)) else "missing",
                "message": (
                    "Managed ComfyUI virtual environment runtime is present."
                    if bool(layout_status.get("venv_runtime_present", False))
                    else "Managed ComfyUI virtual environment runtime is missing."
                ),
            },
            "installer_layout": {
                "state": str(layout_status.get("state", "invalid")),
                "valid": bool(layout_status.get("valid", False)),
                "message": str(layout_status.get("summary", "")),
                "missing_required": list(layout_status.get("missing_required", [])),
            },
            "model_folder": {
                "state": "ready" if bool(checkpoint_dir.get("valid", False)) else "missing",
                "message": str(checkpoint_dir.get("message", "Checkpoint folder is required.")),
                "path": str(checkpoint_dir.get("resolved_path") or checkpoint_dir.get("path") or ""),
            },
            "text_only_mode": {
                "state": "active" if text_only_mode else "inactive",
                "message": "Text-only mode is active." if text_only_mode else "Image pipeline mode is active.",
            },
            "image_runtime": {
                "state": "ready" if bool(image_status.get("ready", False)) else "not_ready",
                "message": str(image_status.get("user_message", "")),
            },
            "packaged_app_files": {
                "state": "ready" if bool(layout_status.get("packaged_app_files_present", False)) else "missing",
                "message": str(checks.get("runtime_bundle", {}).get("message", "Packaged runtime bundle status unavailable.")),
            },
        }

    def get_installer_layout_status(self) -> dict[str, Any]:
        validation = InstallerLayoutValidator().validate()
        packaged_mode = self.desktop.capabilities.mode == "desktop_packaged"
        if packaged_mode:
            return validation
        return {
            **validation,
            "state": "not_packaged",
            "valid": False,
            "summary": "Installer layout checks are informational in source/developer mode.",
            "packaged_mode": False,
        }

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
        if self._looks_like_checkpoint_folder(candidate):
            return {
                "ok": False,
                "message": "Selected folder looks like a checkpoint folder, not a ComfyUI root.",
                "next_step": "Select the ComfyUI root folder that contains main.py.",
            }
        validation = self.validate_comfyui_install(candidate)
        if not validation.get("ok", False):
            missing = ", ".join(validation.get("missing_files", []))
            return {
                "ok": False,
                "message": f"ComfyUI folder is missing required files: {missing}.",
                "validation": validation,
            }
        self.app_config.image.comfyui_path = str(candidate)
        self.app_config.image.managed_install_path = str(self._default_comfyui_path())
        self.app_config.image.provider = "comfyui"
        self.app_config.image.enabled = True
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
        print("[setup-orchestrator] setup-image step=detect-install-path")
        steps.append({"step": "detect-install-path", "state": "ready", "message": f"Managed install path: {self._default_comfyui_path()}"})
        print("[setup-orchestrator] setup-image step=install-or-repair")
        install_result = self.install_image_engine()
        if not install_result.get("ok", False):
            steps.append({"step": "install-or-repair", "state": "failed", "message": str(install_result.get("message", "Install failed."))})
            return {
                "ok": False,
                "message": str(install_result.get("message", "Failed to install image engine.")),
                "next_step": install_result.get("next_step"),
                "steps": steps,
                "summary": "Image AI failed: detect/install step failed.",
            }
        steps.append({"step": "install-or-repair", "state": "ready", "message": str(install_result.get("message", "ComfyUI install detected."))})

        path_status = self.get_path_configuration_status().get("image", {})
        comfyui_root = self._resolve_image_engine_root_for_launch(path_status)
        print("[setup-orchestrator] setup-image step=verify-main-py")
        if comfyui_root is None:
            steps.append({"step": "verify-main-py", "state": "failed", "message": "ComfyUI failed: main.py not found."})
            return {"ok": False, "message": "ComfyUI failed: main.py not found.", "next_step": "Reinstall ComfyUI and retry setup.", "steps": steps, "summary": "Image AI failed during install validation."}
        steps.append({"step": "verify-main-py", "state": "ready", "message": "ComfyUI launch script main.py is present."})
        validation = self.validate_comfyui_install(comfyui_root)
        if not validation.get("ok", False):
            missing = ", ".join(validation.get("missing_files", []))
            steps.append({"step": "verify-embedded-python", "state": "failed", "message": f"ComfyUI failed: missing {missing}."})
            return {"ok": False, "message": f"ComfyUI failed: missing {missing}.", "next_step": "Repair ComfyUI install/runtime, then retry.", "steps": steps, "summary": "Image AI failed during install validation."}
        steps.append({"step": "verify-embedded-python", "state": "ready", "message": "Embedded/runtime Python was found in managed install."})

        print("[setup-orchestrator] setup-image step=resolve-paths")
        steps.append({"step": "resolve-paths", "state": "ready", "message": f"Using ComfyUI root: {comfyui_root}"})
        launch_command, launcher_type = self._build_comfy_launch_command(comfyui_root, "127.0.0.1", 8188)
        runtime_resolution = self._resolve_comfy_python_runtime(launch_command, launcher_type)
        if not runtime_resolution.get("ok", False):
            steps.append({"step": "resolve-python-runtime", "state": "failed", "message": str(runtime_resolution.get("message", "Python runtime resolution failed."))})
            return {
                "ok": False,
                "message": str(runtime_resolution.get("message", "Python runtime resolution failed.")),
                "next_step": "Repair ComfyUI Python runtime, then retry.",
                "steps": steps,
                "summary": "Image AI failed during Python runtime resolution.",
            }
        steps.append(
            {
                "step": "resolve-python-runtime",
                "state": "ready",
                "message": f"ComfyUI Python runtime: {runtime_resolution.get('executable', '')}",
            }
        )
        print("[setup-orchestrator] setup-image step=dependency-bootstrap")
        dep_result = self._bootstrap_comfy_python_dependencies(comfyui_root, launch_command, launcher_type)
        if not dep_result.get("ok", False):
            detail = str(dep_result.get("detail", "")).strip()
            message = str(dep_result.get("message", "Dependency bootstrap failed."))
            if detail:
                message = f"{message} Detail: {detail.splitlines()[-1][:280]}"
            steps.append({"step": "install-requirements", "state": "failed", "message": message})
            return {
                "ok": False,
                "message": message,
                "next_step": "Install/repair the reported Python dependency in the ComfyUI runtime, then retry.",
                "steps": steps,
                "summary": "Image AI failed during dependency bootstrap.",
                "detail": detail,
                "pip_command": dep_result.get("pip_command", ""),
                "requirements_file": dep_result.get("requirements_file", ""),
                "working_directory": dep_result.get("working_directory", ""),
            }
        dep_installed = list(dep_result.get("installed_packages", []))
        dep_message = "Dependencies verified."
        if dep_installed:
            dep_message = f"Dependencies installed/updated: {', '.join(dep_installed)}."
        dep_degraded = bool(dep_result.get("degraded", False))
        if dep_degraded:
            degraded_detail = " ".join(str(item) for item in dep_result.get("degraded_details", []) if str(item).strip())
            steps.append({
                "step": "install-requirements",
                "state": "warning",
                "message": f"{dep_message} Optional dependency issues detected. {degraded_detail}".strip(),
            })
        else:
            steps.append({"step": "install-requirements", "state": "ready", "message": dep_message})
        workflow_status = path_status.get("workflow_path", {})
        print("[setup-orchestrator] setup-image step=validate-workflow")
        if not bool(workflow_status.get("valid", False)):
            message = str(workflow_status.get("message", "Workflow JSON is invalid."))
            steps.append({"step": "validate-workflow", "state": "failed", "message": message})
            return {"ok": False, "message": message, "next_step": "Set a valid workflow JSON, then retry.", "steps": steps, "summary": "Image AI failed during workflow validation."}
        steps.append({"step": "validate-workflow", "state": "ready", "message": "Workflow JSON is present and loadable."})
        checkpoint_status = path_status.get("checkpoint_dir", {})
        if bool(checkpoint_status.get("model_ready", False)):
            steps.append({"step": "validate-checkpoint", "state": "ready", "message": "Checkpoint model validation passed."})
        else:
            steps.append(
                {
                    "step": "validate-checkpoint",
                    "state": "warning",
                    "message": str(checkpoint_status.get("model_message") or "Checkpoint model is not ready yet."),
                }
            )

        print("[setup-orchestrator] setup-image step=start-engine")
        result = self.start_image_engine()
        if result.get("ok"):
            steps.extend(result.get("steps", []))
        else:
            steps.extend(result.get("steps", []))
            if not steps or steps[-1].get("step") != "start-engine":
                steps.append({"step": "start-engine", "state": "failed", "message": str(result.get("message", "Failed to start image engine."))})
            return {"ok": False, "message": str(result.get("message", "Failed to start image engine.")), "next_step": result.get("next_step"), "steps": steps, "summary": str(result.get("message", "Image AI failed to start."))}

        image_status = self.get_image_status()
        engine_ready = bool(image_status.get("reachable", False))
        model_ready = bool(image_status.get("model_ready", checkpoint_status.get("model_ready", False)))
        ready = bool(engine_ready)
        return {
            "ok": ready,
            "message": "Image AI setup complete." if ready and model_ready and not dep_degraded else "Image AI setup complete in degraded mode." if ready and dep_degraded else "ComfyUI engine is ready, but model setup still needs attention." if ready else "Image AI setup did not complete.",
            "steps": steps,
            "summary": "Image AI ready (degraded mode)." if ready and dep_degraded else "Image AI engine ready." if ready and not model_ready else "Image AI ready." if ready else "Image AI setup did not complete.",
            "readiness": self._refresh_readiness_snapshot(),
            "engine_ready": engine_ready,
            "model_ready": model_ready,
            "degraded": dep_degraded,
            "degraded_details": dep_result.get("degraded_details", []),
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

    def _is_managed_install_root(self, path: Path) -> bool:
        try:
            return path.resolve() == Path(str(self.app_config.image.managed_install_path or self._default_comfyui_path())).resolve()
        except OSError:
            return False

    def _default_workflow_path(self) -> Path:
        user_default = self.paths.workflows / "scene_image.json"
        if user_default.exists():
            return user_default
        return bundled_workflow_dir() / "scene_image.json"

    def _apply_managed_image_engine_defaults(self) -> None:
        changed = False
        if not str(self.app_config.image.managed_install_path or "").strip():
            self.app_config.image.managed_install_path = str(self._default_comfyui_path())
            changed = True
        if not str(self.app_config.image.managed_logs_path or "").strip():
            self.app_config.image.managed_logs_path = str(self.paths.logs / "image_engine_startup.log")
            changed = True
        if changed:
            self.config_store.save(self.app_config)

    def validate_comfyui_install(self, path: Path) -> dict[str, Any]:
        missing_files: list[str] = []
        required_dirs = ["custom_nodes", "models", "output", "input", "user"]
        if not path.exists() or not path.is_dir():
            missing_files.append("comfyui-root")
        if not (path / "main.py").is_file():
            missing_files.append("main.py")
        for required in required_dirs:
            if not (path / required).is_dir():
                missing_files.append(f"{required}/")
        runtime_details = "python runtime not checked"
        python_runtime_found = True
        launch_target_resolvable = True
        launch_target = ""
        if os.name == "nt":
            venv_python = path / ".venv" / "Scripts" / "python.exe"
            python_runtime_found = bool(venv_python.exists())
            runtime_details = (
                f"venv runtime found at {venv_python}"
                if venv_python.exists()
                else "python runtime missing (expected ComfyUI .venv runtime)"
            )
            if not python_runtime_found:
                missing_files.append("python-runtime")
            launch_command, _launcher_type = self._build_comfy_launch_command(path, "127.0.0.1", 8188)
            launch_target_resolvable = bool(launch_command)
            launch_target = " ".join(launch_command)
            if not launch_target_resolvable:
                missing_files.append("launch-target")
        valid = len(missing_files) == 0
        return {
            "ok": valid,
            "valid": valid,
            "missing_files": missing_files,
            "required_dirs": required_dirs,
            "python_runtime_found": python_runtime_found,
            "runtime_details": runtime_details,
            "launch_target_resolvable": launch_target_resolvable,
            "launch_target": launch_target,
        }

    def _ensure_comfyui_runtime_folders(self, target_dir: Path) -> None:
        for folder in ("custom_nodes", "models", "output", "input", "user"):
            (target_dir / folder).mkdir(parents=True, exist_ok=True)

    def _install_embedded_python_runtime(self, target_dir: Path) -> tuple[bool, str]:
        """Compatibility shim: managed runtime now uses a local .venv."""
        venv_dir = target_dir / ".venv"
        venv_python = venv_dir / "Scripts" / "python.exe"
        if venv_python.exists():
            self._update_image_bootstrap_progress(
                state="verifying pip",
                step="verifying-pip",
                summary="Managed .venv detected. Verifying pip availability.",
            )
            pip_check = self._run_command_capture([str(venv_python), "-m", "pip", "--version"], timeout_seconds=30)
            if pip_check.returncode == 0:
                return True, f"venv runtime ready: {venv_python}"
        if venv_dir.exists():
            shutil.rmtree(venv_dir, ignore_errors=True)
        python_exe = shutil.which("python") or shutil.which("py")
        if not python_exe:
            return False, "System Python is required to create ComfyUI .venv runtime."
        self._update_image_bootstrap_progress(
            state="creating venv",
            step="creating-venv",
            summary="Creating managed ComfyUI .venv runtime.",
        )
        create_cmd = [python_exe, "-m", "venv", str(venv_dir)]
        if Path(python_exe).name.lower() in {"py", "py.exe"}:
            create_cmd = [python_exe, "-3", "-m", "venv", str(venv_dir)]
        create = self._run_command_capture(create_cmd, timeout_seconds=180)
        if create.returncode != 0:
            detail = self._command_output_snippet(create)
            return False, f"Failed to create ComfyUI .venv runtime: {detail}"
        if not venv_python.exists():
            return False, "ComfyUI .venv creation did not produce Scripts/python.exe."
        self._update_image_bootstrap_progress(
            state="verifying pip",
            step="verifying-pip",
            summary="ComfyUI .venv created. Verifying pip installation.",
        )
        pip_check = self._run_command_capture([str(venv_python), "-m", "pip", "--version"], timeout_seconds=30)
        if pip_check.returncode != 0:
            detail = self._command_output_snippet(pip_check)
            return False, f"ComfyUI .venv was created, but pip is unavailable: {detail}"
        return True, f"venv runtime ready: {venv_python}"

    def _repair_managed_comfyui_install(self, target_dir: Path) -> tuple[bool, str]:
        self._update_image_bootstrap_progress(
            state="repairing install",
            step="repairing-install",
            summary="Repairing managed ComfyUI installation.",
        )
        self._ensure_comfyui_runtime_folders(target_dir)
        if (target_dir / "main.py").exists() and (target_dir / ".venv" / "Scripts" / "python.exe").exists():
            return True, "Managed ComfyUI runtime already complete."
        if not (target_dir / "main.py").exists():
            bundled_root = bundled_comfyui_dir()
            if bundled_root.exists() and bundled_root.is_dir() and (bundled_root / "main.py").exists():
                try:
                    if target_dir.exists():
                        shutil.rmtree(target_dir, ignore_errors=True)
                    shutil.copytree(bundled_root, target_dir)
                    self._ensure_comfyui_runtime_folders(target_dir)
                except OSError:
                    pass
            if (target_dir / "main.py").exists() and (target_dir / ".venv" / "Scripts" / "python.exe").exists():
                return True, "Installed managed ComfyUI from bundled runtime."
            ok, msg = self._download_and_extract_comfyui(target_dir)
            if not ok:
                return False, msg
            self._ensure_comfyui_runtime_folders(target_dir)
        python_ok, python_msg = self._install_embedded_python_runtime(target_dir)
        if not python_ok:
            return False, python_msg
        return True, python_msg

    def _write_comfyui_cpu_launcher(self, comfyui_root: Path) -> bool:
        launcher = comfyui_root / "run_cpu.bat"
        if (comfyui_root / ".venv" / "Scripts" / "python.exe").exists():
            command = ".\\.venv\\Scripts\\python.exe main.py"
        else:
            command = "REM Missing .venv\\Scripts\\python.exe"
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

    def _validate_image_launch_requirements(self, comfyui_root: Path, path_config: dict[str, Any]) -> dict[str, Any]:
        workflow_item = path_config.get("workflow_path", {})
        output_item = path_config.get("output_dir", {})
        resolved_workflow = str(workflow_item.get("resolved_path") or workflow_item.get("path") or "").strip()
        resolved_output = str(output_item.get("resolved_path") or output_item.get("path") or self.generated_image_dir).strip()
        if not comfyui_root.exists():
            return {"ok": False, "message": "ComfyUI root does not exist.", "failure_stage_message": "missing ComfyUI root"}
        main_py = comfyui_root / "main.py"
        if not main_py.exists():
            return {"ok": False, "message": "ComfyUI launcher main.py is missing.", "failure_stage_message": "missing main.py"}
        if not resolved_workflow or not Path(resolved_workflow).exists():
            return {"ok": False, "message": "Workflow file is missing.", "failure_stage_message": "missing workflow file"}
        try:
            Path(resolved_output).mkdir(parents=True, exist_ok=True)
        except OSError:
            return {"ok": False, "message": "Output folder is not writable.", "failure_stage_message": "output directory not writable"}
        parsed = urlparse(str(self.app_config.image.base_url or "http://127.0.0.1:8188"))
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8188
        if port < 1 or port > 65535:
            return {"ok": False, "message": f"Configured ComfyUI port is invalid: {port}.", "failure_stage_message": "invalid port"}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if probe.connect_ex((host, port)) == 0:
                return {"ok": False, "message": f"ComfyUI port is already in use at {host}:{port}.", "failure_stage_message": "port already in use"}
        launch_command, launcher_type = self._build_comfy_launch_command(comfyui_root, host, port)
        if not launch_command:
            return {"ok": False, "message": "No usable Python runtime was found.", "failure_stage_message": "missing python runtime"}
        runtime_check = self._validate_python_runtime(launch_command[0], launcher_type)
        if not runtime_check.get("ok", False):
            return {
                "ok": False,
                "message": str(runtime_check.get("message", "Python runtime is not usable.")),
                "failure_stage_message": "python runtime check failed",
            }
        return {
            "ok": True,
            "host": host,
            "port": port,
            "main_py": str(main_py),
            "launch_command": launch_command,
            "launcher_type": launcher_type,
        }

    def _build_comfy_launch_command(self, comfyui_root: Path, host: str, port: int) -> tuple[list[str], str]:
        venv_python = comfyui_root / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt" and venv_python.exists():
            return [str(venv_python), "main.py", "--listen", host, "--port", str(port)], "venv_python"
        return [], "python_runtime_not_found"

    def _validate_python_runtime(self, executable: str, launcher_type: str) -> dict[str, Any]:
        command = [executable, "--version"]
        if launcher_type == "py_launcher":
            command = [executable, "-3", "--version"]
        try:
            completed = self._run_command_capture(command, timeout_seconds=10)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "message": f"Python runtime could not be executed: {exc}"}
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            tail = details.splitlines()[-1] if details else ""
            suffix = f" ({tail})" if tail else ""
            return {"ok": False, "message": f"Python runtime check failed with exit code {completed.returncode}{suffix}"}
        return {"ok": True}

    def _resolve_comfy_python_runtime(self, launch_command: list[str], launcher_type: str) -> dict[str, Any]:
        if not launch_command:
            return {"ok": False, "message": "ComfyUI launch command is empty."}
        executable = str(launch_command[0]).strip()
        if not executable:
            return {"ok": False, "message": "ComfyUI Python executable is empty."}
        runtime_command = [executable]
        if launcher_type == "py_launcher":
            runtime_command.append("-3")
        runtime_kind = "venv" if launcher_type == "venv_python" else "unknown"
        return {
            "ok": True,
            "executable": executable,
            "launcher_type": launcher_type,
            "runtime_command": runtime_command,
            "runtime_kind": runtime_kind,
        }

    def _required_comfyui_python_packages(self, comfyui_root: Path) -> dict[str, Any]:
        requirements_file = comfyui_root / "requirements.txt"
        baseline_packages = ["sqlalchemy"]
        requirements_from_file: list[str] = []
        if requirements_file.exists() and requirements_file.is_file():
            try:
                for raw_line in requirements_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    normalized = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
                    if normalized:
                        requirements_from_file.append(normalized.lower())
            except OSError:
                pass
        required = sorted(set([*baseline_packages, *requirements_from_file]))
        return {
            "requirements_file": str(requirements_file),
            "requirements_file_present": requirements_file.exists(),
            "required_packages": required,
            "baseline_packages": baseline_packages,
        }

    def _run_runtime_python_capture(
        self,
        runtime_command: list[str],
        args: list[str],
        timeout_seconds: int = 60,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [*runtime_command, *args]
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )

    @staticmethod
    def _command_output_snippet(result: subprocess.CompletedProcess[str], max_chars: int = 400) -> str:
        text = (result.stderr or result.stdout or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...(truncated)"

    @staticmethod
    def _format_command(command: list[str]) -> str:
        def _quote(token: str) -> str:
            if not token:
                return '""'
            if any(ch in token for ch in (' ', "\t", '"')):
                escaped = token.replace('"', '\\"')
                return f"\"{escaped}\""
            return token

        return " ".join(_quote(str(item)) for item in command)

    @staticmethod
    def _classify_pip_install_error(detail_text: str) -> dict[str, str]:
        detail = str(detail_text or "").strip()
        lowered = detail.lower()
        summary = "Dependency installation failed."
        category = "unknown"
        matched_line = next((line.strip() for line in detail.splitlines() if line.strip()), "")

        if "no matching distribution found for" in lowered:
            category = "distribution-not-found"
            summary = "A package could not be installed because no compatible distribution was found."
            marker = "No matching distribution found for"
            matched_line = next((line.strip() for line in detail.splitlines() if marker.lower() in line.lower()), matched_line)
        elif "could not find a version that satisfies the requirement" in lowered:
            category = "version-unsatisfied"
            summary = "A package version constraint could not be satisfied."
            marker = "Could not find a version that satisfies the requirement"
            matched_line = next((line.strip() for line in detail.splitlines() if marker.lower() in line.lower()), matched_line)
        elif "connection" in lowered or "timed out" in lowered or "temporary failure in name resolution" in lowered:
            category = "network"
            summary = "Dependency download failed due to a network error."
        elif "access is denied" in lowered or "permission denied" in lowered:
            category = "permission"
            summary = "Dependency installation failed due to a filesystem permission error."
        elif "failed building wheel" in lowered or "could not build wheels" in lowered:
            category = "build-wheel-failed"
            summary = "Dependency installation failed while building a wheel."
        elif "invalid requirement" in lowered:
            category = "invalid-requirement"
            summary = "requirements.txt contains an invalid requirement entry."

        return {"category": category, "summary": summary, "matched_line": matched_line}

    def _run_pip_install_with_retries(
        self,
        runtime_command: list[str],
        pip_args: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        attempts: int = 2,
    ) -> dict[str, Any]:
        pip_command = [*runtime_command, "-m", "pip", *pip_args]
        attempt_outputs: list[str] = []
        last_result: subprocess.CompletedProcess[str] | None = None
        for attempt in range(1, attempts + 1):
            try:
                try:
                    result = self._run_runtime_python_capture(
                        runtime_command,
                        ["-m", "pip", *pip_args],
                        timeout_seconds=timeout_seconds,
                        cwd=cwd,
                    )
                except TypeError:
                    result = self._run_runtime_python_capture(
                        runtime_command,
                        ["-m", "pip", *pip_args],
                        timeout_seconds=timeout_seconds,
                    )
            except subprocess.TimeoutExpired:
                detail = f"pip timed out after {timeout_seconds}s on attempt {attempt}/{attempts}."
                attempt_outputs.append(detail)
                if attempt < attempts:
                    continue
                classification = self._classify_pip_install_error(detail)
                return {
                    "ok": False,
                    "detail": "\n\n".join(attempt_outputs),
                    "error_category": classification["category"] or "network",
                    "error_line": detail,
                    "pip_command": self._format_command(pip_command),
                    "returncode": None,
                    "attempts": attempts,
                }
            last_result = result
            output_text = (result.stderr or result.stdout or "").strip()
            if output_text:
                attempt_outputs.append(f"[attempt {attempt}/{attempts}]\n{output_text}")
            if result.returncode == 0:
                return {
                    "ok": True,
                    "detail": "\n\n".join(attempt_outputs),
                    "pip_command": self._format_command(pip_command),
                    "returncode": 0,
                    "attempts": attempt,
                }
        detail = "\n\n".join(attempt_outputs).strip()
        classification = self._classify_pip_install_error(detail)
        return {
            "ok": False,
            "detail": detail,
            "error_category": classification["category"],
            "error_line": classification["matched_line"],
            "pip_command": self._format_command(pip_command),
            "returncode": last_result.returncode if last_result else None,
            "attempts": attempts,
        }

    def _bootstrap_runtime_pip(self, runtime_command: list[str], *, python_executable: str) -> dict[str, Any]:
        self._update_image_bootstrap_progress(
            state="verifying pip",
            step="verifying-pip",
            summary="Checking pip in managed ComfyUI runtime.",
        )
        pip_check = self._run_runtime_python_capture(runtime_command, ["-m", "pip", "--version"], timeout_seconds=30)
        pip_initially_available = pip_check.returncode == 0
        print(
            f"[setup-deps] pip-check-initial available={pip_initially_available} "
            f"python={python_executable}"
        )
        if pip_initially_available:
            pip_version = (pip_check.stdout or pip_check.stderr or "").strip()
            print(f"[setup-deps] pip-ready version={pip_version}")
            return {
                "ok": True,
                "pip_initially_available": True,
                "ensurepip_attempted": False,
                "fallback_attempted": False,
                "pip_version": pip_version,
            }

        return {
            "ok": False,
            "stage": "dependency-bootstrap",
            "message": "ComfyUI .venv is missing pip",
            "detail": self._command_output_snippet(pip_check),
            "python_executable": python_executable,
            "pip_initially_available": False,
            "ensurepip_attempted": False,
            "fallback_attempted": False,
            "pip_version": "",
        }

    def _bootstrap_comfy_python_dependencies(self, comfyui_root: Path, launch_command: list[str], launcher_type: str) -> dict[str, Any]:
        runtime = self._resolve_comfy_python_runtime(launch_command, launcher_type)
        if not runtime.get("ok", False):
            return runtime
        runtime_command = list(runtime["runtime_command"])
        python_executable = str(runtime.get("executable", ""))
        print(
            f"[setup-deps] resolved-python executable={python_executable} "
            f"launcher_type={launcher_type} runtime_kind={runtime.get('runtime_kind', 'unknown')}"
        )
        pip_bootstrap = self._bootstrap_runtime_pip(runtime_command, python_executable=python_executable)
        if not pip_bootstrap.get("ok", False):
            return pip_bootstrap
        print(
            "[setup-deps] pip-bootstrap-status "
            f"initial={pip_bootstrap.get('pip_initially_available')} "
            f"ensurepip_attempted={pip_bootstrap.get('ensurepip_attempted')} "
            f"fallback_attempted={pip_bootstrap.get('fallback_attempted')}"
        )

        package_info = self._required_comfyui_python_packages(comfyui_root)
        requirements_file = Path(str(package_info.get("requirements_file", "")))
        installed_packages: list[str] = []
        degraded_details: list[str] = []

        self._update_image_bootstrap_progress(
            state="upgrading pip",
            step="upgrading-pip",
            summary="Upgrading pip, setuptools, and wheel in the managed ComfyUI runtime.",
        )
        pip_upgrade = self._run_pip_install_with_retries(
            runtime_command,
            ["install", "--upgrade", "pip", "setuptools", "wheel"],
            cwd=comfyui_root,
            timeout_seconds=180,
            attempts=2,
        )
        if not pip_upgrade.get("ok", False):
            degraded_details.append(
                f"pip tooling upgrade failed; continuing with existing pip. error_line={str(pip_upgrade.get('error_line', '')).strip()}"
            )
        else:
            installed_packages.append("pip setuptools wheel (upgraded)")

        critical_dependencies = ["sqlalchemy"]
        for package_name in critical_dependencies:
            self._update_image_bootstrap_progress(
                state="installing requirements",
                step="installing-critical-dependencies",
                summary=f"Installing critical dependency: {package_name}.",
            )
            install_critical = self._run_pip_install_with_retries(
                runtime_command,
                ["install", package_name],
                cwd=comfyui_root,
                timeout_seconds=240,
                attempts=2,
            )
            if not install_critical.get("ok", False):
                detail = str(install_critical.get("detail", "")).strip()
                classification = self._classify_pip_install_error(detail)
                return {
                    "ok": False,
                    "stage": "dependency-bootstrap",
                    "message": f"Failed to install dependency: {package_name}",
                    "detail": detail,
                    "error_category": str(install_critical.get("error_category") or classification["category"]),
                    "error_line": str(install_critical.get("error_line") or classification["matched_line"]),
                    "pip_command": str(install_critical.get("pip_command", "")),
                    "working_directory": str(comfyui_root),
                    "returncode": install_critical.get("returncode"),
                    "python_executable": python_executable,
                    "missing_dependency": package_name,
                }
            installed_packages.append(package_name)

        if bool(package_info.get("requirements_file_present", False)) and requirements_file.exists():
            self._update_image_bootstrap_progress(
                state="installing requirements",
                step="installing-requirements",
                summary=f"Installing ComfyUI requirements from {requirements_file.name}.",
            )
            print(f"[setup-deps] installing requirements file={requirements_file}")
            install_requirements = self._run_pip_install_with_retries(
                runtime_command,
                ["install", "-r", str(requirements_file)],
                timeout_seconds=60 * 10,
                cwd=comfyui_root,
                attempts=2,
            )
            if not install_requirements.get("ok", False):
                detail = str(install_requirements.get("detail", "")).strip()
                classification = self._classify_pip_install_error(detail)
                error_line = str(install_requirements.get("error_line") or classification["matched_line"])
                optional_markers = ("xformers", "triton", "onnxruntime-gpu", "insightface", "opencv-contrib-python")
                is_optional_failure = any(marker in error_line.lower() for marker in optional_markers)
                if not is_optional_failure:
                    return {
                        "ok": False,
                        "stage": "dependency-bootstrap",
                        "message": (
                            f"{classification['summary']} "
                            f"pip exited with code {install_requirements.get('returncode')} while installing {requirements_file.name}."
                        ),
                        "detail": detail,
                        "error_category": str(install_requirements.get("error_category") or classification["category"]),
                        "error_line": error_line,
                        "pip_command": str(install_requirements.get("pip_command", "")),
                        "working_directory": str(comfyui_root),
                        "requirements_file": str(requirements_file),
                        "returncode": install_requirements.get("returncode"),
                        "python_executable": python_executable,
                    }
                degraded_details.append(
                    f"{classification['summary']} requirements install had optional package failures; continuing in degraded mode."
                )
                degraded_details.append(f"error_line={error_line}")
            else:
                installed_packages.append(f"-r {requirements_file.name}")

        import_targets = {"sqlalchemy": "sqlalchemy"}
        missing_imports: list[str] = []
        for module_name, package_name in import_targets.items():
            probe = self._run_runtime_python_capture(runtime_command, ["-c", f"import {module_name}"], timeout_seconds=20)
            if probe.returncode != 0:
                missing_imports.append(package_name)
        for package_name in missing_imports:
            self._update_image_bootstrap_progress(
                state="installing requirements",
                step="installing-requirements",
                summary=f"Installing missing Python package: {package_name}.",
            )
            print(f"[setup-deps] installing missing package={package_name}")
            install_one = self._run_runtime_python_capture(runtime_command, ["-m", "pip", "install", package_name], timeout_seconds=180)
            if install_one.returncode != 0:
                detail = (install_one.stderr or install_one.stdout or "").strip()
                return {
                    "ok": False,
                    "stage": "dependency-bootstrap",
                    "message": f"Failed to install dependency: {package_name}",
                    "detail": detail,
                    "python_executable": python_executable,
                    "missing_dependency": package_name,
                }
            installed_packages.append(package_name)

        for module_name, package_name in import_targets.items():
            probe = self._run_runtime_python_capture(runtime_command, ["-c", f"import {module_name}"], timeout_seconds=20)
            if probe.returncode != 0:
                detail = (probe.stderr or probe.stdout or "").strip()
                return {
                    "ok": False,
                    "stage": "dependency-validation",
                    "message": f"Missing dependency in ComfyUI runtime: {package_name}",
                    "detail": detail,
                    "python_executable": python_executable,
                    "missing_dependency": package_name,
                }
        print(f"[setup-deps] dependency validation passed installed={installed_packages}")
        return {
            "ok": True,
            "python_executable": python_executable,
            "runtime_command": runtime_command,
            "installed_packages": installed_packages,
            "required_packages": package_info.get("required_packages", []),
            "pip_initially_available": pip_bootstrap.get("pip_initially_available"),
            "pip_version": pip_bootstrap.get("pip_version", ""),
            "ensurepip_attempted": pip_bootstrap.get("ensurepip_attempted"),
            "fallback_attempted": pip_bootstrap.get("fallback_attempted"),
            "degraded": bool(degraded_details),
            "degraded_details": degraded_details,
        }

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
            self._ensure_comfyui_runtime_folders(target_dir)
            return True, "ok"
        except OSError as exc:
            print(f"[setup-action] install-image-engine failure reason={exc}")
            return False, "Failed to download or unpack ComfyUI bootstrap files."
        except zipfile.BadZipFile:
            print("[setup-action] install-image-engine failure reason=invalid-archive")
            return False, "ComfyUI archive download was invalid."

    def _find_comfyui_root(self) -> Path | None:
        resolved = self._resolve_image_backend_paths()
        comfy = Path(resolved["comfyui_root"]) if resolved.get("comfyui_root") else None
        if comfy and (comfy / "main.py").exists():
            return comfy
        return None

    def _resolve_image_backend_mode(self, payload: dict[str, Any] | None = None) -> str:
        source = payload or {}
        configured_root = str(source.get("comfyui_path", self.app_config.image.comfyui_path) or "").strip()
        return "external" if configured_root else "managed"

    def _resolve_image_backend_paths(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        source = payload or {}
        configured_root = str(source.get("comfyui_path", self.app_config.image.comfyui_path) or "").strip()
        configured_workflow = str(source.get("comfyui_workflow_path", self.app_config.image.comfyui_workflow_path) or "").strip()
        configured_output = str(source.get("comfyui_output_dir", self.app_config.image.comfyui_output_dir) or "").strip()
        configured_checkpoint = str(source.get("checkpoint_folder", self.app_config.image.checkpoint_folder) or "").strip()
        managed_root = Path(str(self.app_config.image.managed_install_path or "").strip() or str(self._default_comfyui_path()))
        mode = self._resolve_image_backend_mode(source)
        comfyui_root = Path(configured_root) if configured_root else managed_root
        workflow_path = Path(configured_workflow) if configured_workflow else self._default_workflow_path()
        output_dir = Path(configured_output) if configured_output else self.generated_image_dir
        checkpoint_dir = Path(configured_checkpoint) if configured_checkpoint else (comfyui_root / "models" / "checkpoints")
        return {
            "mode": mode,
            "comfyui_root": str(comfyui_root),
            "managed_comfyui_root": str(managed_root),
            "external_comfyui_root": configured_root,
            "workflow_path": str(workflow_path),
            "output_dir": str(output_dir),
            "checkpoint_dir": str(checkpoint_dir),
            "external_checkpoint_dir": configured_checkpoint,
        }

    def _resolve_image_engine_root_for_launch(self, path_config: dict[str, Any]) -> Path | None:
        comfy_item = path_config.get("comfyui_root", {}) if isinstance(path_config, dict) else {}
        resolved = str(comfy_item.get("resolved_path") or comfy_item.get("path") or "").strip()
        if resolved and (Path(resolved) / "main.py").exists():
            return Path(resolved)
        return None

    def _detect_install_path_status(self, path_config: dict[str, Any]) -> dict[str, Any]:
        image_config = path_config if isinstance(path_config, dict) else {}
        resolved_paths = image_config.get("resolved_paths", {}) if isinstance(image_config.get("resolved_paths", {}), dict) else {}
        comfy_item = image_config.get("comfyui_root", {}) if isinstance(image_config.get("comfyui_root", {}), dict) else {}
        mode = str(image_config.get("mode", "managed"))
        configured_root = str(resolved_paths.get("external_comfyui_root", "")).strip() if mode == "external" else ""
        resolved_root = str(comfy_item.get("resolved_path") or comfy_item.get("path") or "").strip()

        if mode == "external" and not configured_root:
            return {
                "ok": False,
                "mode": mode,
                "status_code": "no_path_configured",
                "message": "No external ComfyUI install path is configured.",
                "failure_stage_message": "no install path configured",
                "next_step": "Locate an existing ComfyUI folder or select Use Bundled Image Engine.",
                "resolved_root": resolved_root,
                "configured_root": configured_root,
            }
        if not resolved_root:
            return {
                "ok": False,
                "mode": mode,
                "status_code": "no_path_resolved",
                "message": "ComfyUI install path could not be resolved.",
                "failure_stage_message": "install path could not be resolved",
                "next_step": "Re-select bundled or external ComfyUI path, then retry.",
                "resolved_root": resolved_root,
                "configured_root": configured_root,
            }
        candidate = Path(resolved_root)
        if not candidate.exists() or not candidate.is_dir():
            return {
                "ok": False,
                "mode": mode,
                "status_code": "configured_path_missing",
                "message": f"Configured ComfyUI root does not exist: {candidate}",
                "failure_stage_message": "configured root missing",
                "next_step": "Repair the path or reinstall ComfyUI.",
                "resolved_root": resolved_root,
                "configured_root": configured_root,
            }
        validation = self.validate_comfyui_install(candidate)
        if not validation.get("ok", False):
            missing = ", ".join(validation.get("missing_files", []))
            return {
                "ok": False,
                "mode": mode,
                "status_code": "invalid_root_structure",
                "message": f"Configured ComfyUI root is invalid: missing {missing}.",
                "failure_stage_message": "invalid ComfyUI root structure",
                "next_step": "Select a valid ComfyUI root folder (the one containing main.py), then retry.",
                "resolved_root": resolved_root,
                "configured_root": configured_root,
                "validation": validation,
            }
        return {
            "ok": True,
            "mode": mode,
            "status_code": "valid_root",
            "message": f"Using install path: {candidate}",
            "resolved_root": str(candidate),
            "configured_root": configured_root,
            "validation": validation,
        }

    @staticmethod
    def _looks_like_checkpoint_folder(path: Path) -> bool:
        lowered_parts = {part.lower() for part in path.parts}
        if "checkpoints" in lowered_parts:
            return True
        model_suffixes = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
        try:
            for item in path.iterdir():
                if item.is_file() and item.suffix.lower() in model_suffixes:
                    return True
        except OSError:
            return False
        return False

    def _validate_comfyui_root_config(self, configured_path: str, managed_root: str = "") -> dict[str, Any]:
        raw = str(configured_path or "").strip()
        if not raw:
            default_root = Path(str(managed_root or self._resolve_image_backend_paths().get("managed_comfyui_root", "")))
            if (default_root / "main.py").exists():
                print("[path-config] comfyui_root configured=false using=managed")
                return {
                    "configured": False,
                    "valid": True,
                    "path": "",
                    "resolved_path": str(default_root),
                    "message": "Using managed ComfyUI runtime.",
                }
            print("[path-config] comfyui_root configured=false")
            return {"configured": False, "valid": False, "path": "", "resolved_path": str(default_root), "message": "Managed ComfyUI runtime is not installed."}
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
            default_workflow = self._default_workflow_path()
            if default_workflow.exists() and default_workflow.is_file():
                print("[path-config] workflow_path configured=false using=managed")
                return {
                    "configured": False,
                    "valid": True,
                    "path": "",
                    "resolved_path": str(default_workflow),
                    "message": "Using managed workflow template.",
                }
            print("[path-config] workflow_path configured=false")
            return {"configured": False, "valid": False, "path": "", "message": "Workflow file is not available."}
        candidate = Path(raw)
        if not candidate.exists() or not candidate.is_file():
            print("[path-config] workflow_path valid=false")
            return {"configured": True, "valid": False, "path": raw, "message": "Workflow path does not exist."}
        if candidate.suffix.lower() != ".json":
            print("[path-config] workflow_path valid=false")
            return {"configured": True, "valid": False, "path": raw, "message": "Workflow file must be a .json file."}
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                print("[path-config] workflow_path valid=false")
                return {"configured": True, "valid": False, "path": str(candidate), "message": "Workflow JSON root must be an object."}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("[path-config] workflow_path valid=false")
            return {"configured": True, "valid": False, "path": str(candidate), "message": f"Workflow JSON is invalid: {exc}"}
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

    def _match_preferred_checkpoint(self, preferred_checkpoint: str, available_models: list[str]) -> str | None:
        preferred = str(preferred_checkpoint or "").strip()
        if not preferred:
            return None
        preferred_lower = preferred.lower()
        for model in available_models:
            if model.lower() == preferred_lower:
                return model
        preferred_stem = Path(preferred).stem.lower()
        for model in available_models:
            if Path(model).stem.lower() == preferred_stem:
                return model
        normalized = re.sub(r"[^a-z0-9]+", "", preferred_stem)
        if normalized:
            for model in available_models:
                model_normalized = re.sub(r"[^a-z0-9]+", "", Path(model).stem.lower())
                if model_normalized.startswith(normalized):
                    return model
        return None

    def _validate_checkpoint_dir_config(self, configured_path: str, comfyui_path: str = "") -> dict[str, Any]:
        raw = str(configured_path or "").strip()
        model_suffixes = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
        preferred = str(self.app_config.image.preferred_checkpoint or "").strip()

        def _discover_models(folder: Path) -> list[str]:
            if not folder.exists() or not folder.is_dir():
                return []
            return sorted([item.name for item in folder.iterdir() if item.is_file() and item.suffix.lower() in model_suffixes])

        def _status(
            *,
            configured: bool,
            valid: bool,
            path: str,
            resolved_path: str = "",
            message: str,
            detected_models: list[str] | None = None,
        ) -> dict[str, Any]:
            models = detected_models or []
            matched_preferred = self._match_preferred_checkpoint(preferred, models) if preferred else None
            preferred_found = bool(matched_preferred) if preferred else None
            model_ready = bool(models) and (not preferred or bool(matched_preferred))
            model_status_code = "model_ready" if model_ready else "no_models_detected"
            model_message = "Checkpoint models are available."
            if not models:
                model_message = "No checkpoint found. Select a model folder or download one."
            elif preferred and not matched_preferred:
                model_status_code = "preferred_checkpoint_missing"
                model_message = f"Preferred checkpoint '{preferred}' was not found in the selected checkpoint folder."
            elif preferred and matched_preferred:
                model_message = f"Preferred checkpoint '{preferred}' matched '{matched_preferred}'."
            return {
                "configured": configured,
                "valid": valid,
                "path": path,
                "resolved_path": resolved_path,
                "message": message,
                "detected_models": models,
                "model_ready": model_ready,
                "model_status_code": model_status_code,
                "model_message": model_message,
                "preferred_checkpoint": preferred,
                "preferred_checkpoint_found": preferred_found,
                "preferred_checkpoint_match": matched_preferred or "",
            }

        if not raw:
            comfy_root = Path(str(comfyui_path or "").strip()) if str(comfyui_path or "").strip() else None
            inferred = (comfy_root / "models" / "checkpoints") if comfy_root else None
            if inferred and inferred.exists() and inferred.is_dir():
                models = _discover_models(inferred)
                if not models:
                    return _status(
                        configured=False,
                        valid=True,
                        path="",
                        resolved_path=str(inferred),
                        message="Using ComfyUI default checkpoints folder.",
                        detected_models=[],
                    )
                return _status(
                    configured=False,
                    valid=True,
                    path="",
                    resolved_path=str(inferred),
                    message="Using ComfyUI default checkpoints folder.",
                    detected_models=models,
                )
            return _status(
                configured=False,
                valid=False,
                path="",
                message="Checkpoint folder not configured.",
                detected_models=[],
            )
        candidate = Path(raw)
        if not candidate.exists() or not candidate.is_dir():
            return _status(configured=True, valid=False, path=raw, message="Folder not found.", detected_models=[])
        models = _discover_models(candidate)
        return _status(
            configured=True,
            valid=True,
            path=str(candidate),
            resolved_path=str(candidate),
            message="Checkpoint folder is valid.",
            detected_models=models,
        )

    def get_path_configuration_status(self) -> dict[str, Any]:
        resolved = self._resolve_image_backend_paths()
        mode = str(resolved.get("mode", "managed"))
        configured_root = str(resolved.get("external_comfyui_root", "")) if mode == "external" else ""
        comfyui_root = self._validate_comfyui_root_config(configured_root, str(resolved.get("managed_comfyui_root", "")))
        workflow_path = self._validate_workflow_path_config(self.app_config.image.comfyui_workflow_path)
        output_dir = self._validate_output_dir_config(self.app_config.image.comfyui_output_dir)
        comfy_for_checkpoints = str(comfyui_root.get("resolved_path") or comfyui_root.get("path") or "")
        checkpoint_dir = self._validate_checkpoint_dir_config(
            self.app_config.image.checkpoint_folder,
            comfy_for_checkpoints,
        )
        engine_ready = bool(comfyui_root["valid"] and workflow_path["valid"] and output_dir["valid"])
        model_ready = bool(checkpoint_dir.get("model_ready", False))
        pipeline_ready = bool(engine_ready and model_ready)
        return {
            "image": {
                "mode": str(resolved.get("mode", "managed")),
                "resolved_paths": resolved,
                "comfyui_root": comfyui_root,
                "workflow_path": workflow_path,
                "checkpoint_dir": checkpoint_dir,
                "output_dir": output_dir,
                "engine_ready": engine_ready,
                "model_ready": model_ready,
                "pipeline_ready": pipeline_ready,
            }
        }

    def validate_visual_pipeline_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolve_image_backend_paths(payload)
        print("[path-config] apply_requested")
        mode = str(resolved.get("mode", "managed"))
        configured_root = str(resolved.get("external_comfyui_root", "")) if mode == "external" else ""
        comfy_status = self._validate_comfyui_root_config(configured_root, str(resolved.get("managed_comfyui_root", "")))
        resolved_comfy_for_checkpoints = str(comfy_status.get("resolved_path") or comfy_status.get("path") or "")
        status = {
            "image": {
                "mode": str(resolved.get("mode", "managed")),
                "resolved_paths": resolved,
                "comfyui_root": comfy_status,
                "workflow_path": self._validate_workflow_path_config(str(payload.get("comfyui_workflow_path", "")).strip()),
                "output_dir": self._validate_output_dir_config(str(payload.get("comfyui_output_dir", "")).strip()),
                "checkpoint_dir": self._validate_checkpoint_dir_config(str(payload.get("checkpoint_folder", "")).strip(), resolved_comfy_for_checkpoints),
            }
        }
        image_status = status["image"]
        image_status["engine_ready"] = bool(
            image_status["comfyui_root"]["valid"]
            and image_status["workflow_path"]["valid"]
            and image_status["output_dir"]["valid"]
        )
        image_status["model_ready"] = bool(image_status["checkpoint_dir"].get("model_ready", False))
        image_status["pipeline_ready"] = bool(image_status["engine_ready"] and image_status["model_ready"])
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
        invalid_key = next(
            (
                key
                for key in ("comfyui_root", "workflow_path", "output_dir")
                if not bool(image_status.get(key, {}).get("valid", False))
            ),
            None,
        )
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
        self._image_engine_state = "starting"
        self._image_engine_last_error = ""
        if not self._is_windows():
            reason = "windows-only flow"
            print(f"[setup-action] install-image-engine failure reason={reason}")
            self._image_engine_state = "error"
            self._image_engine_last_error = reason
            return {
                "ok": False,
                "message": "Automatic ComfyUI setup is currently supported on Windows only.",
                "next_step": "Install ComfyUI manually and set image provider to comfyui.",
            }
        target_dir = self._default_comfyui_path()
        existing = target_dir if (target_dir / "main.py").exists() else None
        if existing is not None:
            validation = self.validate_comfyui_install(existing)
            if validation.get("ok"):
                print(f"[setup-action] install-image-engine success reason=already-installed path={existing}")
                self.app_config.image.comfyui_path = ""
                self.app_config.image.managed_install_path = str(existing)
                self.config_store.save(self.app_config)
                self._image_engine_state = "installed"
                return {"ok": True, "message": "ComfyUI is already installed.", "readiness_refreshed": True}
            print(f"[setup-orchestrator] comfyui install repair reason=existing-install-invalid missing={validation.get('missing_files')}")
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        print("[setup-orchestrator] comfyui install start")
        ok, install_message = self._repair_managed_comfyui_install(target_dir)
        if not ok:
            self._image_engine_state = "error"
            self._image_engine_last_error = install_message
            return {
                "ok": False,
                "message": install_message,
                "next_step": "Retry setup to recreate the ComfyUI .venv runtime.",
            }
        validation = self.validate_comfyui_install(target_dir)
        if not validation.get("ok"):
            self._image_engine_state = "error"
            self._image_engine_last_error = ",".join(validation.get("missing_files", []))
            return {
                "ok": False,
                "message": f"ComfyUI install is incomplete: missing {', '.join(validation.get('missing_files', []))}.",
                "next_step": "Retry setup to repair missing runtime files, or install ComfyUI portable manually.",
                "validation": validation,
            }
        self.app_config.image.comfyui_path = ""
        self.app_config.image.managed_install_path = str(target_dir)
        self.config_store.save(self.app_config)
        print("[setup-orchestrator] comfyui install success")
        print("[setup-action] install-image-engine success")
        self._image_engine_state = "installed"
        return {
            "ok": True,
            "message": "ComfyUI install verified, including .venv runtime.",
            "next_step": "Click Start Image Engine to run preflight validation and launch ComfyUI.",
            "readiness_refreshed": True,
        }

    def start_image_engine(self, *, startup_mode: str = "manual") -> dict[str, Any]:
        print("[setup-action] start-image-engine requested")
        self._image_engine_state = "starting"
        self._image_engine_last_error = ""
        startup_log_lines: list[str] = []
        startup_log_file = Path(str(self.app_config.image.managed_logs_path or "")).expanduser()
        if not str(startup_log_file).strip() or str(startup_log_file) == ".":
            startup_log_file = self.paths.logs / "image_engine_startup.log"
        self.app_config.image.managed_logs_path = str(startup_log_file)
        startup_log_file.parent.mkdir(parents=True, exist_ok=True)
        if startup_mode != "background":
            with self._image_startup_lock:
                if self._image_bootstrap_thread is not None and self._image_bootstrap_thread.is_alive():
                    return {
                        "ok": True,
                        "message": "Image bootstrap is already running in background.",
                        "startup_status": dict(self.image_startup_status),
                    }
            self._set_image_startup_status()
        self.comfy_manager.clear_if_exited()
        if self.app_config.image.provider != "comfyui":
            print("[setup-action] start-image-engine failure reason=image provider is not comfyui")
            self._image_engine_state = "error"
            self._image_engine_last_error = "provider_not_comfyui"
            return {
                "ok": False,
                "message": "Image provider is not set to comfyui.",
                "next_step": "Set image provider to comfyui, then retry.",
                "failure_stage": "provider-check",
                "failure_stage_message": "image provider is not comfyui",
                "steps": [{"step": "provider-check", "state": "failed", "message": "Image provider is not set to comfyui."}],
            }
        if self.get_image_status().get("reachable", False):
            print("[setup-action] start-image-engine success reason=already running")
            managed_state = self.comfy_manager.snapshot()
            self._set_image_startup_status(
                state="ready",
                stage="wait-for-readiness",
                reason="already-reachable",
                summary="ComfyUI is already running.",
                current_step="wait-for-readiness",
                log_text="",
                log_available=False,
                log_file=str(startup_log_file),
                managed_process=managed_state.running,
            )
            return {
                "ok": True,
                "message": "ComfyUI is already running.",
                "managed_process": managed_state.running,
                "steps": [{"step": "wait-for-readiness", "state": "ready", "message": "Engine is already reachable."}],
            }
        path_config = self.get_path_configuration_status().get("image", {})
        self._update_image_bootstrap_progress(state="repairing install", step="detect-install-path", summary="Detecting managed ComfyUI install path.")
        print("[setup-orchestrator] setup-image step=detect-install-path")
        install_status = self._detect_install_path_status(path_config)
        comfyui_root = Path(str(install_status.get("resolved_root", "")).strip()) if install_status.get("ok") else None
        if comfyui_root is None:
            if str(path_config.get("mode", "managed")) == "managed":
                repair = self.install_image_engine()
                if repair.get("ok", False):
                    path_config = self.get_path_configuration_status().get("image", {})
                    install_status = self._detect_install_path_status(path_config)
                    comfyui_root = Path(str(install_status.get("resolved_root", "")).strip()) if install_status.get("ok") else None
                    if comfyui_root is not None:
                        self._append_image_startup_log(startup_log_lines, "Managed install was incomplete and was repaired before launch.")
            if comfyui_root is None:
                print("[setup-action] start-image-engine failure reason=install-path-missing")
                print("[setup-orchestrator] setup-image failure stage=detect-install-path")
                self._image_engine_state = "error"
                self._image_engine_last_error = str(install_status.get("status_code", "install_path_missing"))
                return {
                    "ok": False,
                    "message": str(install_status.get("message", "ComfyUI install path was not found.")),
                    "next_step": str(install_status.get("next_step", "Install Image Engine first.")),
                    "failure_stage": "detect-install-path",
                    "failure_stage_message": str(install_status.get("failure_stage_message", "install path missing")),
                    "status_code": str(install_status.get("status_code", "install_path_missing")),
                    "steps": [{"step": "detect-install-path", "state": "failed", "message": str(install_status.get("message", "ComfyUI install path was not found."))}],
                }
        launch_mode = self._resolve_image_backend_mode()
        if launch_mode == "managed":
            self.app_config.image.comfyui_path = ""
            self.app_config.image.managed_install_path = str(comfyui_root)
        else:
            self.app_config.image.comfyui_path = str(comfyui_root)
            if not str(self.app_config.image.managed_install_path or "").strip():
                self.app_config.image.managed_install_path = str(self._default_comfyui_path())
        resolved_workflow = str(path_config.get("workflow_path", {}).get("resolved_path") or self.app_config.image.comfyui_workflow_path).strip()
        if resolved_workflow:
            self.app_config.image.comfyui_workflow_path = resolved_workflow
        self.config_store.save(self.app_config)
        self._append_image_startup_log(startup_log_lines, f"Using install path: {comfyui_root}")
        if not bool(path_config.get("workflow_path", {}).get("valid")):
            self._image_engine_state = "error"
            self._image_engine_last_error = "invalid_workflow_path"
            message = str(path_config.get("workflow_path", {}).get("message") or "Workflow JSON path is invalid.")
            return {
                "ok": False,
                "message": message,
                "next_step": "Choose a valid workflow .json file and apply settings.",
                "failure_stage": "validate-workflow",
                "failure_stage_message": "workflow json invalid",
                "steps": [{"step": "validate-workflow", "state": "failed", "message": message}],
            }
        bundled_root = bundled_comfyui_dir()
        if self.desktop.capabilities.mode == "desktop_packaged" and comfyui_root.resolve() == bundled_root.resolve():
            layout_status = self.get_installer_layout_status()
            if not bool(layout_status.get("valid", False)):
                missing_required = list(layout_status.get("missing_required", []))
                return {
                    "ok": False,
                    "message": "Bundled image runtime layout is incomplete.",
                    "next_step": "Reinstall or repair packaged runtime_bundle files, then retry Start Image Engine.",
                    "failure_stage": "layout-validation",
                    "failure_stage_message": "bundled runtime layout invalid",
                    "missing_required": missing_required,
                    "installer_layout": layout_status,
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                        {"step": "layout-validation", "state": "failed", "message": f"Missing packaged assets: {', '.join(missing_required) or 'unknown'}"},
                    ],
                }
        self._update_image_bootstrap_progress(state="repairing install", step="verify-install", summary="Verifying ComfyUI install integrity.")
        print("[setup-orchestrator] setup-image step=verify-install")
        validation = self.validate_comfyui_install(comfyui_root)
        if not validation.get("ok"):
            if str(path_config.get("mode", "managed")) == "managed":
                repair = self.install_image_engine()
                if repair.get("ok", False):
                    validation = self.validate_comfyui_install(comfyui_root)
            missing = ", ".join(validation.get("missing_files", []))
            if not validation.get("ok"):
                return {
                    "ok": False,
                    "message": f"ComfyUI failed: missing {missing}.",
                    "next_step": "Repair the install/runtime, then retry Start Image Engine.",
                    "failure_stage": "verify-install",
                    "failure_stage_message": "required files/runtime missing",
                    "steps": [
                        {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                        {"step": "verify-install", "state": "failed", "message": f"Missing: {missing}"},
                    ],
                }
        launch_command, launcher_type = self._build_comfy_launch_command(comfyui_root, "127.0.0.1", 8188)
        runtime_resolution = self._resolve_comfy_python_runtime(launch_command, launcher_type)
        if not runtime_resolution.get("ok", False):
            return {
                "ok": False,
                "message": str(runtime_resolution.get("message", "No usable Python runtime was found.")),
                "next_step": "Install/repair Python runtime for ComfyUI and retry setup.",
                "failure_stage": "resolve-python-runtime",
                "failure_stage_message": "python runtime resolution failed",
                "steps": [
                    {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                    {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                    {"step": "resolve-python-runtime", "state": "failed", "message": str(runtime_resolution.get("message", "Python runtime resolution failed."))},
                ],
            }
        self._append_image_startup_log(
            startup_log_lines,
            (
                "Resolved ComfyUI Python runtime: "
                f"{runtime_resolution.get('executable', '')} "
                f"(type={runtime_resolution.get('runtime_kind', 'unknown')})"
            ),
        )

        checkpoint_status = path_config.get("checkpoint_dir", {})
        if not bool(checkpoint_status.get("model_ready", False)):
            self._append_image_startup_log(
                startup_log_lines,
                f"Checkpoint validation warning: {checkpoint_status.get('model_message', 'Checkpoint model is not ready.')}",
            )
        preflight = self._validate_image_launch_requirements(comfyui_root, path_config)
        if not preflight.get("ok", False):
            self._image_engine_state = "error"
            self._image_engine_last_error = str(preflight.get("failure_stage_message", "preflight failed"))
            return {
                "ok": False,
                "message": str(preflight.get("message", "ComfyUI validation failed before launch.")),
                "next_step": "Fix the reported path/runtime issue, then retry.",
                "failure_stage": "preflight-validation",
                "failure_stage_message": str(preflight.get("failure_stage_message", "preflight validation failed")),
            }
        launch_command = list(preflight.get("launch_command", []))
        launcher_type = str(preflight.get("launcher_type", "unknown"))
        self._update_image_bootstrap_progress(state="verifying pip", step="dependency-bootstrap", summary="Bootstrapping Python dependencies for ComfyUI.")
        print("[setup-orchestrator] setup-image step=dependency-bootstrap")
        dependency_bootstrap = self._bootstrap_comfy_python_dependencies(comfyui_root, launch_command, launcher_type)
        if not dependency_bootstrap.get("ok", False):
            message = str(dependency_bootstrap.get("message", "Dependency bootstrap failed for ComfyUI runtime."))
            detail = str(dependency_bootstrap.get("detail", "")).strip()
            missing_dep = str(dependency_bootstrap.get("missing_dependency", "")).strip()
            pip_command = str(dependency_bootstrap.get("pip_command", "")).strip()
            requirements_file = str(dependency_bootstrap.get("requirements_file", "")).strip()
            working_directory = str(dependency_bootstrap.get("working_directory", "")).strip()
            returncode = dependency_bootstrap.get("returncode")
            error_category = str(dependency_bootstrap.get("error_category", "")).strip()
            error_line = str(dependency_bootstrap.get("error_line", "")).strip()
            if missing_dep and "missing dependency" not in message.lower():
                message = f"Missing dependency in ComfyUI runtime: {missing_dep}"
            self._image_engine_state = "error"
            self._image_engine_last_error = missing_dep or "dependency_bootstrap_failed"
            if detail:
                self._append_image_startup_log(startup_log_lines, f"Dependency bootstrap error: {detail}")
            if pip_command:
                self._append_image_startup_log(startup_log_lines, f"pip command: {pip_command}")
            if working_directory:
                self._append_image_startup_log(startup_log_lines, f"pip working directory: {working_directory}")
            if requirements_file:
                self._append_image_startup_log(startup_log_lines, f"requirements file: {requirements_file}")
            if error_line:
                self._append_image_startup_log(startup_log_lines, f"pip error line: {error_line}")
            self._set_image_startup_status(
                state="failed",
                stage="dependency-bootstrap",
                reason="dependency-bootstrap-failed",
                summary=message,
                current_step="dependency-bootstrap",
                failure_detail=detail[:2000],
                pip_command=pip_command,
                requirements_file=requirements_file,
                working_directory=working_directory,
                returncode=returncode,
                error_category=error_category,
                error_line=error_line,
                startup_log=self._sanitize_image_startup_log(startup_log_lines),
            )
            return {
                "ok": False,
                "message": message,
                "next_step": "Install/repair the reported dependency in the ComfyUI runtime, then retry.",
                "failure_stage": "dependency-bootstrap",
                "failure_stage_message": "python dependency bootstrap failed",
                "missing_dependency": missing_dep,
                "python_executable": dependency_bootstrap.get("python_executable", ""),
                "detail": detail,
                "pip_command": pip_command,
                "requirements_file": requirements_file,
                "working_directory": working_directory,
                "returncode": returncode,
                "error_category": error_category,
                "error_line": error_line,
                "steps": [
                    {"step": "detect-install-path", "state": "ready", "message": f"Using install path: {comfyui_root}"},
                    {"step": "verify-install", "state": "ready", "message": "Install verification completed."},
                    {"step": "resolve-python-runtime", "state": "ready", "message": f"Resolved runtime: {runtime_resolution.get('executable', '')}"},
                    {"step": "dependency-bootstrap", "state": "failed", "message": message},
                ],
            }
        installed_packages = dependency_bootstrap.get("installed_packages", [])
        if installed_packages:
            self._append_image_startup_log(startup_log_lines, f"Dependency bootstrap installed: {', '.join(installed_packages)}")
        else:
            self._append_image_startup_log(startup_log_lines, "Dependency bootstrap verified required modules are already available.")
        if bool(dependency_bootstrap.get("degraded", False)):
            degraded_detail = " ".join(str(item) for item in dependency_bootstrap.get("degraded_details", []) if str(item).strip())
            self._append_image_startup_log(startup_log_lines, f"Dependency bootstrap degraded: {degraded_detail}")
        self._update_image_bootstrap_progress(state="starting ComfyUI", step="launch-engine", summary="Starting ComfyUI process.")
        print("[setup-orchestrator] setup-image step=launch-engine")
        process: subprocess.Popen[str] | None = None
        log_handle = None
        launch_target = " ".join(launch_command)
        try:
            self._append_image_startup_log(startup_log_lines, f"Launching mode: {launcher_type}")
            self._append_image_startup_log(startup_log_lines, f"Launching command: {launch_target}")
            self._append_image_startup_log(startup_log_lines, f"Working directory: {comfyui_root}")
            with startup_log_file.open("w", encoding="utf-8") as handle:
                handle.write("")
            log_handle = startup_log_file.open("a", encoding="utf-8")
            kwargs: dict[str, Any] = {
                "cwd": str(comfyui_root),
                "stdout": log_handle,
                "stderr": subprocess.STDOUT,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            else:
                kwargs["start_new_session"] = True
            process = subprocess.Popen(launch_command, **kwargs)
        except OSError as exc:
            print(f"[setup-action] start-image-engine failure reason={exc}")
            print("[setup-orchestrator] setup-image failure stage=launch-engine")
            self._image_engine_state = "error"
            self._image_engine_last_error = str(exc)
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
            self._image_engine_state = "error"
            self._image_engine_last_error = "process_launch_uninitialized"
            return {"ok": False, "message": "ComfyUI process launch did not initialize.", "failure_stage": "launch-engine", "failure_stage_message": "process launch failed"}
        if log_handle is not None:
            self.comfy_manager.bind_log_handle(log_handle)
        self.comfy_manager.register(process, launch_target=launch_target, startup_log_file=startup_log_file)
        print(f"[setup-action] start-image-engine launch command={launch_target}")
        self._update_image_bootstrap_progress(state="starting ComfyUI", step="wait-for-readiness", summary="Waiting for ComfyUI readiness endpoint.")
        print("[setup-orchestrator] setup-image step=wait-for-readiness")
        expected_base = self.app_config.image.base_url
        expected = urlparse(expected_base)
        for _ in range(20):
            time.sleep(0.75)
            if process.poll() is not None:
                exit_code = process.poll()
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
                self._set_image_startup_status(
                    state="failed",
                    stage="wait-for-readiness",
                    reason="process-exited-immediately",
                    summary=f"Image AI failed: ComfyUI exited during startup (exit code {exit_code}).",
                    current_step="wait-for-readiness",
                    runtime_error_hint=runtime_error,
                    exit_code=exit_code,
                    last_log_lines=tail_lines[-20:],
                    last_error_line=tail_lines[-1] if tail_lines else "",
                    log_text=startup_log_text,
                    log_available=bool(startup_log_text),
                    log_file=str(startup_log_file),
                    managed_process=False,
                )
                self.comfy_manager.clear_if_exited()
                self._image_engine_state = "error"
                self._image_engine_last_error = "process_exited_immediately"
                last_error_line = tail_lines[-1] if tail_lines else ""
                detail = f", last error: {last_error_line}" if last_error_line else ""
                return {
                    "ok": False,
                    "message": f"ComfyUI failed: Process exited (code {exit_code}){detail}",
                    "next_step": "Open setup details to review startup log and fix the runtime/dependency issue.",
                    "failure_stage": "wait-for-readiness",
                    "failure_stage_message": "process exited during startup",
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
                dependency_degraded = bool(dependency_bootstrap.get("degraded", False))
                degraded_details = list(dependency_bootstrap.get("degraded_details", []))
                self._set_image_startup_status(
                    state="ready",
                    stage="wait-for-readiness",
                    reason="ready",
                    summary="ComfyUI started and is reachable." if not dependency_degraded else "ComfyUI started (degraded dependency mode).",
                    current_step="ready",
                    log_text=self._sanitize_image_startup_log(startup_log_lines + self._read_startup_log_tail(startup_log_file)),
                    log_available=True,
                    log_file=str(startup_log_file),
                    managed_process=self.comfy_manager.snapshot().running,
                    degraded=dependency_degraded,
                    degraded_details=degraded_details,
                )
                self._image_engine_state = "running"
                return {
                    "ok": True,
                    "message": "ComfyUI started and is reachable." if not dependency_degraded else "ComfyUI started (degraded dependency mode).",
                    "managed_process": self.comfy_manager.snapshot().running,
                    "readiness_refreshed": True,
                    "degraded": dependency_degraded,
                    "degraded_details": degraded_details,
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
        self._set_image_startup_status(
            state="failed",
            stage="wait-for-readiness",
            reason=reason,
            summary=message,
            current_step="wait-for-readiness",
            runtime_error_hint=runtime_error,
            detected_bind_urls=bound_urls,
            expected_base_url=expected_base,
            log_text=startup_log_text,
            log_available=bool(startup_log_text),
            log_file=str(startup_log_file),
            managed_process=self.comfy_manager.snapshot().running,
        )
        print("[setup-action] start-image-engine failure reason=timeout-waiting-for-comfyui")
        print("[setup-orchestrator] setup-image failure stage=wait-for-readiness")
        self._image_engine_state = "error"
        self._image_engine_last_error = reason
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

    def stop_image_engine(self) -> dict[str, Any]:
        self._image_engine_state = "stopping"
        self.comfy_manager.clear_if_exited()
        snapshot = self.comfy_manager.snapshot()
        if not snapshot.running:
            self._image_engine_state = "installed"
            return {"ok": True, "message": "Image engine is not running.", "managed_process": False}
        stopped = self.comfy_manager.shutdown()
        if not stopped:
            self._image_engine_state = "error"
            self._image_engine_last_error = "stop_failed"
            return {"ok": False, "message": "Image engine process could not be stopped cleanly.", "managed_process": True}
        self._set_image_startup_status(
            state="stopped",
            stage="stopped",
            reason="stopped-by-user",
            summary="ComfyUI process stopped from setup controls.",
            current_step="stopped",
            managed_process=False,
        )
        self._image_engine_state = "installed"
        return {"ok": True, "message": "Image engine stopped.", "managed_process": False, "readiness_refreshed": True}

    def open_image_engine_debug_ui(self) -> dict[str, Any]:
        base_url = str(self.app_config.image.base_url or "").strip() or "http://localhost:8188"
        return self.open_external_url(base_url)

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
        if message_type in {"player", "narrator", "npc", "quest", "image", "system", "error", "ooc_player", "ooc_gm"}:
            return message_type
        lowered = text.lower()
        if "quest" in lowered:
            return "quest"
        if lowered.startswith('"') or "relationship tier" in lowered:
            return "npc"
        return "system"

    @staticmethod
    def _avatar_fallback(name: str) -> str:
        parts = [part for part in str(name or "").split() if part]
        initials = "".join(part[0].upper() for part in parts[:2])
        return initials or "NPC"

    def get_play_view(self, limit: int = 200) -> dict[str, Any]:
        state = self.session.state
        runtime = state.structured_state.runtime
        scene_state = runtime.scene_state if isinstance(runtime.scene_state, dict) else {}
        history = self.session.message_history[-max(limit, 1):]

        latest_narration = next(
            (str(entry.get("text", "")).strip() for entry in reversed(history) if str(entry.get("type", "")).lower() == "narrator"),
            "",
        )
        location = state.locations.get(state.current_location_id)
        location_name = str(location.name if location else state.current_location_id or "Unknown location")
        location_description = str(location.description if location else "")
        scene_summary = "; ".join(self._clean_list(scene_state.get("recent_consequences", []))[:2])
        scene_payload = {
            "location_id": state.current_location_id,
            "location_name": location_name,
            "atmosphere": str(state.world_meta.tone or "").strip(),
            "narration": latest_narration or location_description or "No scene narration yet.",
            "summary": scene_summary,
            "turn": state.turn_count,
        }

        registry = self._sync_npc_identities()
        visible_ids: list[str] = []

        def add_visible(npc_id: str) -> None:
            clean_id = str(npc_id or "").strip()
            if clean_id and clean_id not in visible_ids:
                visible_ids.append(clean_id)

        for npc in state.npcs.values():
            if npc.location_id == state.current_location_id:
                add_visible(npc.id)
        for actor in scene_state.get("scene_actors", []) if isinstance(scene_state, dict) else []:
            if isinstance(actor, dict):
                add_visible(str(actor.get("linked_npc_id", "")))
        for lite in scene_state.get("lightweight_npcs", []) if isinstance(scene_state, dict) else []:
            if isinstance(lite, dict):
                add_visible(str(lite.get("npc_id", "")))
        for entry in history[-20:]:
            if str(entry.get("type", "")).lower() == "npc":
                add_visible(str(entry.get("speaker_npc_id", "")))

        visible_npcs: list[dict[str, Any]] = []
        for npc_id in visible_ids[:12]:
            record = registry.records.get(npc_id, {}) if isinstance(registry.records, dict) else {}
            npc = state.npcs.get(npc_id)
            display_name = str(record.get("display_name") or (npc.name if npc else npc_id) or npc_id).strip() or "Unknown NPC"
            descriptor = str(record.get("role_or_archetype") or (npc.personality_archetype if npc else "") or "").strip()
            portrait_url = str(record.get("portrait_path", "")).strip()
            relationship = str(getattr(npc, "relationship_tier", "")).strip() if npc else ""
            portrait_status = str(record.get("portrait_status", "none")).strip() or "none"
            state_tags = [tag for tag in [relationship, portrait_status] if tag and tag != "none"]
            notable = bool(record.get("important", False))
            visible_npcs.append(
                {
                    "npc_id": npc_id,
                    "display_name": display_name,
                    "portrait_url": portrait_url,
                    "avatar_fallback": self._avatar_fallback(display_name),
                    "role_or_archetype": descriptor,
                    "notable": notable,
                    "state_tags": state_tags,
                }
            )

        dialogue_entries = [
            dict(entry)
            for entry in history
            if str(entry.get("type", "")).lower() in {"npc", "player", "ooc_player", "ooc_gm", "system", "error", "narrator"}
        ]
        for entry in dialogue_entries:
            if str(entry.get("type", "")).lower() == "npc":
                name = str(entry.get("speaker_name") or "NPC")
                entry["avatar_fallback"] = self._avatar_fallback(name)

        return {
            "scene_state": scene_payload,
            "visible_npcs": visible_npcs,
            "dialogue_entries": dialogue_entries,
        }

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
            "abilities": getattr(state.structured_state.runtime, "abilities", state.structured_state.runtime.spellbook),
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
        # Ownership rule: spellbook remains player-managed. Recalibration should not
        # auto-generate abilities from gameplay history.
        return 0

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
        ooc_backfill = self._recalibration_backfill_ooc_structured_data(state)

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
        runtime = state.structured_state.runtime
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        removed_invalid_spell_entries = self._cleanup_invalid_spell_text_entries(state)
        print(f"[recalibration] abilities_synced={abilities_synced}")
        print(f"[recalibration] ooc_spellbook_backfill={ooc_backfill['spellbook_entries_added']}")
        print(f"[recalibration] cleaned_invalid_spell_entries={removed_invalid_spell_entries}")
        print(f"[recalibration] world_updates={world_updates}")
        print("[recalibration] complete")
        self.save_active_campaign(self.session.active_slot)
        return {
            "ok": True,
            "npc_created": npc_created_names,
            "abilities_synced": abilities_synced,
            "world_updates": world_updates,
            "npc_merged": merged_npcs,
            "ooc_backfill_spellbook_entries": ooc_backfill["spellbook_entries_added"],
            "ooc_backfill_character_sheet_updated": ooc_backfill["character_sheet_updated"],
            "ooc_backfill_world_entries": ooc_backfill["world_entries_added"],
            "cleaned_invalid_spell_entries": removed_invalid_spell_entries,
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
        self._normalize_inventory_state(runtime.inventory_state)
        print(f"[inventory] viewer_opened campaign={self.session.active_slot}")
        return runtime.inventory_state

    def upsert_inventory_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime = self.session.state.structured_state.runtime
        inventory_state = self.get_inventory_state()
        # Ownership rule: inventory is player-managed by default; system writes are
        # only allowed through explicit OOC structured-authoring requests.
        self._normalize_inventory_state(inventory_state)
        action = str(payload.get("action", "upsert")).strip().lower()
        entries = list(inventory_state.get("entries", []))
        if action == "delete":
            entry_id = str(payload.get("id", "")).strip()
            entries = [entry for entry in entries if str(entry.get("id", "")).strip() != entry_id]
        else:
            entry_id = str(payload.get("id", "")).strip() or f"inv_{int(time.time() * 1000)}"
            normalized_entry = {
                "id": entry_id,
                "name": str(payload.get("name", "")).strip(),
                "category": str(payload.get("category", "items")).strip().lower() or "items",
                "quantity": max(1, int(payload.get("quantity", 1) or 1)),
                "notes": str(payload.get("notes", payload.get("description", ""))).strip(),
            }
            if not normalized_entry["name"]:
                raise ValueError("Inventory entry name is required.")
            replaced = False
            for index, existing in enumerate(entries):
                if str(existing.get("id", "")).strip() == entry_id:
                    entries[index] = normalized_entry
                    replaced = True
                    break
            if not replaced:
                entries.append(normalized_entry)
        inventory_state["entries"] = entries
        self._normalize_inventory_state(inventory_state)
        runtime.inventory = [str(entry.get("name", "")).strip() for entry in inventory_state.get("entries", []) if str(entry.get("name", "")).strip()]
        self.save_active_campaign(self.session.active_slot)
        return {"inventory": inventory_state}

    def _normalize_inventory_state(self, inventory_state: dict[str, Any]) -> None:
        entries = inventory_state.get("entries", [])
        normalized_entries: list[dict[str, Any]] = []
        if isinstance(entries, list):
            for index, raw in enumerate(entries):
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name", "")).strip()
                if not name:
                    continue
                normalized_entries.append(
                    {
                        "id": str(raw.get("id", "")).strip() or f"inv_{index}_{name.lower().replace(' ', '_')}",
                        "name": name,
                        "category": str(raw.get("category", "items")).strip().lower() or "items",
                        "quantity": max(1, int(raw.get("quantity", 1) or 1)),
                        "notes": str(raw.get("notes", raw.get("description", ""))).strip(),
                    }
                )
        if not normalized_entries:
            legacy: list[dict[str, Any]] = []
            for category in ("items", "weapons", "armor", "consumables", "key_items"):
                values = inventory_state.get(category, [])
                if not isinstance(values, list):
                    continue
                for value in values:
                    name = str(value).strip()
                    if not name:
                        continue
                    legacy.append(
                        {
                            "id": f"inv_{len(legacy)}_{name.lower().replace(' ', '_')}",
                            "name": name,
                            "category": category,
                            "quantity": 1,
                            "notes": "",
                        }
                    )
            normalized_entries = legacy
        inventory_state["entries"] = normalized_entries
        grouped: dict[str, list[str]] = {"items": [], "weapons": [], "armor": [], "consumables": [], "key_items": []}
        for entry in normalized_entries:
            category = str(entry.get("category", "items")).strip().lower()
            if category not in grouped:
                category = "items"
            grouped[category].append(str(entry.get("name", "")).strip())
        inventory_state.update(grouped)
        currency = inventory_state.get("currency")
        if not isinstance(currency, dict):
            inventory_state["currency"] = {"gold": 0, "silver": 0, "copper": 0}
        equipped = inventory_state.get("equipped")
        if not isinstance(equipped, dict):
            inventory_state["equipped"] = {"equipped_item_id": self.session.state.player.equipped_item_id}

    def get_spellbook_state(self) -> list[dict[str, Any]]:
        runtime = self.session.state.structured_state.runtime
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        print(f"[spellbook] viewer_opened campaign={self.session.active_slot}")
        print(f"[spellbook] current_entry_count={len(runtime.abilities)}")
        return runtime.abilities

    def upsert_spellbook_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime = self.session.state.structured_state.runtime
        action = str(payload.get("action", "upsert")).strip().lower()
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        if action == "delete":
            entry_id = str(payload.get("id", "")).strip()
            runtime.abilities = [entry for entry in runtime.abilities if str(entry.get("id", "")) != entry_id]
        else:
            raw_entry = {
                "id": str(payload.get("id", "")).strip() or f"sb_{int(time.time() * 1000)}",
                "name": str(payload.get("name", "")).strip(),
                "category": str(payload.get("category", payload.get("type", ""))).strip().lower(),
                "description": str(payload.get("description", "")).strip(),
                "cost_or_resource": str(payload.get("cost_or_resource", "")).strip(),
                "cooldown": str(payload.get("cooldown", "")).strip(),
                "tags": [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
                "flags": [str(flag).strip() for flag in payload.get("flags", []) if str(flag).strip()],
                "notes": str(payload.get("notes", "")).strip(),
                "source_metadata": dict(payload.get("source_metadata", {})) if isinstance(payload.get("source_metadata"), dict) else {},
            }
            entry = normalize_spellbook_entry(raw_entry, index=len(runtime.abilities)) or {}
            if not entry.get("name"):
                raise ValueError("Spellbook entry name is required.")
            replaced = False
            for index, existing in enumerate(runtime.abilities):
                if str(existing.get("id", "")) == entry["id"]:
                    runtime.abilities[index] = entry
                    replaced = True
                    break
            if not replaced:
                runtime.abilities.append(entry)
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(runtime.abilities)
        runtime.spellbook = list(runtime.abilities)
        self.save_active_campaign(self.session.active_slot)
        print(f"[spellbook] current_entry_count={len(runtime.abilities)}")
        return {"abilities": runtime.abilities, "spellbook": runtime.spellbook}

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
                    entry["source"] = str(payload.get("source", entry.get("source", "manual"))).strip() or "manual"
                    updated = True
                    break
            if not updated:
                canon.custom_narrator_rules.append(
                    {
                        "id": entry_id,
                        "text": text,
                        "source": str(payload.get("source", "manual")).strip() or "manual",
                    }
                )
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
        matched_preferred = self._match_preferred_checkpoint(preferred, checkpoints) if preferred else None
        if preferred and not matched_preferred:
            return fail("checkpoint_available", f"Preferred checkpoint '{preferred}' is not available in ComfyUI.")

        print("[image-test] step=prompt_submission")
        request = ImageGenerationRequest(
            workflow_id=workflow_path.stem or "scene_image",
            prompt=prompt,
            negative_prompt="",
            parameters=({"checkpoint": matched_preferred} if matched_preferred else {}),
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
        registry = self._sync_npc_identities()
        self._maybe_queue_npc_portraits(registry)
        engine_ms = (time.perf_counter() - engine_started) * 1000
        message_append_started = time.perf_counter()
        split_messages = self._build_turn_display_segments(
            result.messages,
            player_input=clean_text,
            registry=registry,
        )
        routed_messages = [registry.route_npc_dialogue_message(message) for message in split_messages]
        self._persist_turn_display_messages(routed_messages)
        for message in routed_messages:
            extra = {k: v for k, v in message.items() if k not in {"type", "text"}}
            self._append_message(message["type"], message["text"], persist=False, **extra)
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
            "messages": routed_messages,
            "should_exit": result.should_exit,
            "metadata": {**(result.metadata or {}), "model_status": model_status, "timing": turn_timing},
            "state": self.serialize_state(),
        }

    def _build_turn_display_segments(
        self,
        messages: list[dict[str, Any]],
        *,
        player_input: str,
        registry: NPCIdentityRegistry,
    ) -> list[dict[str, Any]]:
        split: list[dict[str, Any]] = []
        default_speaker_npc_id, resolution_source = self._resolve_turn_speaker_npc_id(registry)
        print(f"[npc-dialogue-card] speaker_resolution source={resolution_source} npc_id={default_speaker_npc_id or 'none'}")
        for message in messages:
            msg_type = str(message.get("type", "")).strip().lower()
            if msg_type != "narrator":
                split.append(dict(message))
                continue
            text = str(message.get("text", "")).strip()
            if not text:
                continue
            speaker_npc_id = self._resolve_message_speaker_npc_id(
                message=message,
                registry=registry,
                default_speaker_npc_id=default_speaker_npc_id,
            )
            split_segments = self._extract_npc_speech_segments(
                text=text,
                player_input=player_input,
                speaker_npc_id=speaker_npc_id,
            )
            for segment in split_segments:
                segment_type = str(segment.get("type", "")).strip().lower()
                segment_text = str(segment.get("text", "")).strip()
                if not segment_type or not segment_text:
                    continue
                if segment_type == "npc":
                    npc_payload: dict[str, Any] = {"type": "npc", "text": segment_text}
                    if speaker_npc_id:
                        npc_payload["speaker_npc_id"] = speaker_npc_id
                    print(f"[npc-dialogue-card] speech_detected speaker={speaker_npc_id or 'unresolved'}")
                    split.append(npc_payload)
                else:
                    split.append({"type": "narrator", "text": segment_text})
        return split

    def _resolve_message_speaker_npc_id(
        self,
        *,
        message: dict[str, Any],
        registry: NPCIdentityRegistry,
        default_speaker_npc_id: str,
    ) -> str:
        explicit_npc_id = str(message.get("speaker_npc_id", "")).strip()
        if explicit_npc_id and explicit_npc_id in registry.records:
            return explicit_npc_id
        explicit_actor_npc_id = str(message.get("actor_npc_id", "")).strip() or str(message.get("npc_id", "")).strip()
        if explicit_actor_npc_id and explicit_actor_npc_id in registry.records:
            return explicit_actor_npc_id
        explicit_actor_id = str(message.get("actor_id", "")).strip()
        if explicit_actor_id:
            scene_state = self.session.state.structured_state.runtime.scene_state
            scene_actors = scene_state.get("scene_actors", []) if isinstance(scene_state, dict) else []
            for actor in scene_actors:
                if not isinstance(actor, dict) or str(actor.get("actor_id", "")).strip() != explicit_actor_id:
                    continue
                linked_npc_id = str(actor.get("linked_npc_id", "")).strip()
                if linked_npc_id and linked_npc_id in registry.records:
                    return linked_npc_id
        if default_speaker_npc_id:
            return default_speaker_npc_id
        explicit_name = str(message.get("speaker_name", "")).strip().lower()
        if explicit_name:
            for npc_id, record in registry.records.items():
                if str(record.get("display_name", "")).strip().lower() == explicit_name:
                    return npc_id
        return ""

    def _resolve_turn_speaker_npc_id(self, registry: NPCIdentityRegistry) -> tuple[str, str]:
        active_id = str(self.session.state.active_dialogue_npc_id or "").strip()
        if active_id and active_id in registry.records:
            return active_id, "active_dialogue_npc_id"
        scene_state = self.session.state.structured_state.runtime.scene_state
        if isinstance(scene_state, dict):
            target_actor_id = str(scene_state.get("last_target_actor_id", "")).strip()
            if target_actor_id:
                for actor in scene_state.get("scene_actors", []):
                    if not isinstance(actor, dict):
                        continue
                    if str(actor.get("actor_id", "")).strip() != target_actor_id:
                        continue
                    linked_npc_id = str(actor.get("linked_npc_id", "")).strip()
                    if linked_npc_id and linked_npc_id in registry.records:
                        return linked_npc_id, "scene_target_actor"
        if len(registry.records) == 1:
            single_id = next(iter(registry.records.keys()))
            return single_id, "single_known_npc"
        return "", "unresolved"

    def _extract_npc_speech_segments(self, *, text: str, player_input: str, speaker_npc_id: str) -> list[dict[str, str]]:
        if not speaker_npc_id:
            print("[npc-dialogue-card] left_in_narrator reason=no_resolved_speaker")
            return [{"type": "narrator", "text": text}]
        normalized = re.sub(r"\s+", " ", text.strip())
        quote_pattern = r"[\"“]([^\"”]{2,280})[\"”]|(?<![A-Za-z0-9])[\'‘]([^\'’]{2,280})[\'’](?![A-Za-z0-9])"
        matches = list(re.finditer(quote_pattern, normalized))
        if not matches:
            print("[npc-dialogue-card] left_in_narrator reason=no_quoted_dialogue")
            return [{"type": "narrator", "text": text}]
        player_quoted_segments = [
            str(m.group(1) or m.group(2) or "").strip().lower()
            for m in re.finditer(quote_pattern, player_input)
            if str(m.group(1) or m.group(2) or "").strip()
        ]
        npc_spans: list[tuple[int, int, str]] = []
        cue_tokens = ("says", "said", "replies", "asks", "answers", "whispers", "murmurs", "growls", "calls")
        for match in matches:
            quoted = str(match.group(1) or match.group(2) or "").strip()
            if not quoted:
                continue
            before = normalized[max(0, match.start() - 48):match.start()].lower()
            after = normalized[match.end():min(len(normalized), match.end() + 48)].lower()
            has_dialogue_cue = any(token in before or token in after for token in cue_tokens)
            pure_quote_turn = normalized.startswith(("“", '"')) and match.start() == 0 and len(matches) == 1
            if not has_dialogue_cue and not pure_quote_turn:
                print("[npc-dialogue-card] left_in_narrator reason=missing_dialogue_cue")
                return [{"type": "narrator", "text": text}]
            if "you say" in before or "you ask" in before or "you say" in after or "you ask" in after:
                print("[npc-dialogue-card] left_in_narrator reason=player_attributed_quote")
                return [{"type": "narrator", "text": text}]
            if quoted.lower() in player_quoted_segments:
                print("[npc-dialogue-card] left_in_narrator reason=matches_player_quote")
                return [{"type": "narrator", "text": text}]
            npc_spans.append((match.start(), match.end(), quoted))
        if not npc_spans:
            return [{"type": "narrator", "text": text}]
        output: list[dict[str, str]] = []
        cursor = 0
        for start, end, quoted in npc_spans:
            narrator_chunk = normalized[cursor:start].strip(" ,:;-")
            if narrator_chunk:
                output.append({"type": "narrator", "text": narrator_chunk})
            output.append({"type": "npc", "text": quoted})
            cursor = end
        trailing = normalized[cursor:].strip(" ,:;-")
        if trailing:
            output.append({"type": "narrator", "text": trailing})
        return output or [{"type": "narrator", "text": text}]

    def _persist_turn_display_messages(self, messages: list[dict[str, Any]]) -> None:
        if not self.session.state.conversation_turns:
            return
        normalized: list[dict[str, Any]] = []
        for message in messages:
            msg_type = str(message.get("type", "")).strip().lower()
            msg_text = str(message.get("text", "")).strip()
            if not msg_type or not msg_text:
                continue
            entry: dict[str, Any] = {"type": msg_type, "text": msg_text}
            for key, value in message.items():
                if key in {"type", "text"}:
                    continue
                if isinstance(value, (str, int, float, bool)) or value is None:
                    entry[key] = value
            normalized.append(entry)
        self.session.state.conversation_turns[-1].display_messages = normalized

    def _build_ooc_context(self) -> str:
        state = self.session.state
        location = state.locations.get(state.current_location_id)
        location_name = location.name if location else "Unknown location"
        location_description = location.description if location else ""
        recent_history = self.session.message_history[-10:]
        recent_lines = [f"{entry.get('type', 'system').upper()}: {str(entry.get('text', '')).strip()}" for entry in recent_history]
        recent_chat = "\n".join(line for line in recent_lines if line.strip()) or "No recent chat yet."
        recent_turns = state.conversation_turns[-3:]
        recent_turn_text = "\n".join(
            f"Turn {turn.turn}: Player={turn.player_input} | Narrator={turn.narrator_response}"
            for turn in recent_turns
            if str(turn.player_input or "").strip() or str(turn.narrator_response or "").strip()
        ) or "No canon turns have been completed yet."
        npc_names = sorted({npc.name for npc in state.npcs.values() if str(npc.name).strip()})
        npc_preview = ", ".join(npc_names[:8]) if npc_names else "None recorded"
        return (
            f"Campaign: {state.campaign_name}\n"
            f"Turn Count: {state.turn_count}\n"
            f"Current Scene: {location_name}\n"
            f"Scene Description: {location_description}\n"
            f"Known NPCs: {npc_preview}\n\n"
            f"[RECENT CANON TURNS]\n{recent_turn_text}\n\n"
            f"[RECENT CHAT]\n{recent_chat}"
        )


    def _detect_ooc_mode(self, text: str) -> str:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return "clarify"
        if self._is_ooc_behavior_rule_request(lowered):
            return "behavior_rule"
        authoring_verbs = {"add", "create", "generate", "make", "update", "set", "give", "write", "build"}
        correction_verbs = {"should be", "correct", "fix", "change"}
        structured_targets = {
            "spellbook",
            "spell",
            "character sheet",
            "abilities",
            "ability",
            "world building",
            "world notes",
            "world note",
            "npc personality",
            "npc personalities",
            "inventory",
            "title",
            "identity",
        }
        has_authoring_verb = any(token in lowered for token in authoring_verbs)
        has_target = any(token in lowered for token in structured_targets)
        has_correction_verb = any(token in lowered for token in correction_verbs)
        return "structured_authoring" if (has_authoring_verb or has_correction_verb) and has_target else "clarify"

    def _is_ooc_behavior_rule_request(self, lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        if text.endswith("?") and not any(token in text for token in ("always", "never", "stop", "avoid", "prefer", "when i", "do not", "don't")):
            return False
        authoring_targets = ("spellbook", "character sheet", "world notes", "world note", "title", "identity", "inventory")
        if any(target in text for target in authoring_targets):
            return False
        direct_patterns = (
            r"\bstop\b.+",
            r"\bdon['’]?t\b.+",
            r"\bdo not\b.+",
            r"\balways\b.+",
            r"\bnever\b.+",
            r"\bavoid\b.+",
            r"\bprefer\b.+",
            r"\bprioriti(?:ze|s)e?\b.+",
            r"\bkeep\b.+(?:short|brief|concise|longer|clear|focused)",
            r"\bwhen\b.+\b(?:resolve|do|focus|prioritize|prefer)\b",
        )
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in direct_patterns)

    def _normalize_behavior_rule_text(self, request_text: str) -> str:
        text = str(request_text or "").strip()
        text = re.sub(r"^\s*ooc[\s:,\-]*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^(please|pls)\s+", "", text, flags=re.IGNORECASE).strip()
        lowered = text.lower()

        if re.search(r"\bskip over\b.*\b(investigat\w*|inspect\w*)\b", lowered):
            return "When the player explicitly investigates a target, resolve that investigation directly before shifting focus elsewhere."
        if re.search(r"\bhooded figure", lowered):
            return "Avoid repeatedly introducing generic mysterious hooded figures. Prefer more varied and distinct NPC introductions."
        if re.search(r"\bguarded by default\b", lowered):
            return "Do not make strangers guarded by default; vary initial NPC demeanor based on context."
        if re.search(r"\b(dialogue|dialog)\b.*\b(short|shorter|brief|concise)\b", lowered):
            return "Keep NPC dialogue concise unless the scene clearly calls for extended speech."
        if re.search(r"\bprioriti(?:ze|s)e?\b.*\b(investigat\w*|inspect\w*)\b", lowered):
            return "Prioritize resolving the player's direct investigation before introducing new distractions."

        compact = re.sub(r"\s+", " ", text).strip(" .!?")
        compact = compact[0].upper() + compact[1:] if compact else "Adjust narration behavior based on the latest player instruction."
        if not compact.endswith("."):
            compact += "."
        if len(compact) > 220:
            compact = compact[:217].rstrip() + "..."
        return compact

    def _upsert_ooc_behavior_rule(self, request_text: str) -> tuple[dict[str, Any], bool, bool]:
        normalized_rule = self._normalize_behavior_rule_text(request_text)
        print(f'[narrator-rules] normalized_rule="{normalized_rule}"')
        canon = self.session.state.structured_state.canon
        if not isinstance(canon.custom_narrator_rules, list):
            canon.custom_narrator_rules = []
        normalized_key = re.sub(r"[^a-z0-9]+", "", normalized_rule.lower())
        for entry in canon.custom_narrator_rules:
            existing_text = str(entry.get("text", "")).strip()
            if not existing_text:
                continue
            existing_key = re.sub(r"[^a-z0-9]+", "", existing_text.lower())
            if existing_key == normalized_key:
                return entry, False, True
            if existing_key and normalized_key and SequenceMatcher(None, existing_key, normalized_key).ratio() >= 0.93:
                entry["text"] = normalized_rule
                entry["source"] = "ooc_behavior_rule"
                return entry, False, True
        entry = {
            "id": f"nr_{int(time.time() * 1000)}",
            "text": normalized_rule,
            "source": "ooc_behavior_rule",
        }
        canon.custom_narrator_rules.append(entry)
        return entry, True, False

    def _is_valid_structured_spell_name(self, candidate: str) -> bool:
        name = str(candidate or "").strip()
        lowered = name.lower()
        invalid_phrases = (
            "what would you like",
            "do you have",
            "please provide",
            "let's get started",
            "i’d be happy to help",
            "i'd be happy to help",
        )
        compact = re.sub(r"\s+", " ", name)
        is_valid = bool(
            compact
            and len(compact) <= 48
            and "?" not in compact
            and len(compact.split()) <= 6
            and not any(phrase in lowered for phrase in invalid_phrases)
            and not re.search(r"[.!]{1,}", compact)
            and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9' \-]{1,47}", compact))
            and not re.search(r"\b(you|your|we|let|please|would|could|should)\b", lowered)
        )
        print(f'[ooc-sync] candidate_spell_name="{compact}" valid={str(is_valid).lower()}')
        return is_valid

    def _extract_ooc_structured_payload(self, response_text: str) -> dict[str, Any]:
        content = str(response_text or "")
        marker_pattern = re.compile(
            r"\[STRUCTURED_SYNC_PAYLOAD\](.*?)\[/STRUCTURED_SYNC_PAYLOAD\]",
            flags=re.IGNORECASE | re.DOTALL,
        )
        marker_match = marker_pattern.search(content)
        candidate_json = marker_match.group(1).strip() if marker_match else ""
        if not candidate_json:
            fenced = re.search(r"```json\s*(\{.*?\})\s*```", content, flags=re.IGNORECASE | re.DOTALL)
            candidate_json = fenced.group(1).strip() if fenced else ""
        if not candidate_json:
            return {}
        try:
            payload = json.loads(candidate_json)
        except (json.JSONDecodeError, TypeError, ValueError):
            print("[ooc-sync] structured_payload_parse_failed=true")
            return {}
        return payload if isinstance(payload, dict) else {}

    def _validate_structured_spell_entries(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_entries = payload.get("spellbook_entries", [])
        if not isinstance(raw_entries, list):
            return []
        validated: list[dict[str, Any]] = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip()
            if not self._is_valid_structured_spell_name(name):
                continue
            normalized = normalize_spellbook_entry(
                {
                    "name": name,
                    "category": str(raw.get("category", raw.get("type", ""))).strip().lower(),
                    "description": str(raw.get("description", "")).strip(),
                    "cost_or_resource": str(raw.get("cost_or_resource", raw.get("cost", raw.get("resource", "")))).strip(),
                    "cooldown": str(raw.get("cooldown", "")).strip(),
                    "tags": [str(tag).strip() for tag in raw.get("tags", []) if str(tag).strip()] if isinstance(raw.get("tags", []), list) else [],
                    "flags": [str(flag).strip() for flag in raw.get("flags", []) if str(flag).strip()] if isinstance(raw.get("flags", []), list) else [],
                    "notes": str(raw.get("notes", "")).strip(),
                    "source_metadata": {"source_type": "learned_ooc"},
                },
                index=len(validated),
            )
            if normalized:
                validated.append(normalized)
        return validated

    def _validate_structured_inventory_entries(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_entries = payload.get("inventory_entries", payload.get("inventory_items", []))
        if not isinstance(raw_entries, list):
            return []
        validated: list[dict[str, Any]] = []
        for raw in raw_entries:
            if isinstance(raw, str):
                candidate = {"name": raw}
            elif isinstance(raw, dict):
                candidate = raw
            else:
                continue
            name = str(candidate.get("name", "")).strip()
            if not name:
                continue
            validated.append(
                {
                    "id": str(candidate.get("id", "")).strip() or f"inv_ooc_{len(validated)}_{name.lower().replace(' ', '_')}",
                    "name": name,
                    "category": str(candidate.get("category", candidate.get("type", "items"))).strip().lower() or "items",
                    "quantity": max(1, int(candidate.get("quantity", 1) or 1)),
                    "notes": str(candidate.get("notes", candidate.get("description", ""))).strip(),
                }
            )
        return validated

    def _extract_world_entries_from_ooc_response(self, text: str) -> list[str]:
        entries: list[str] = []
        for raw_line in str(text or "").splitlines():
            line = str(raw_line).strip()
            if not line:
                continue
            if line.startswith(("-", "*")):
                line = line[1:].strip()
            line = re.sub(r"^\d+\.\s*", "", line).strip()
            if not line or line.lower().startswith("ooc"):
                continue
            entries.append(line[:220])
        return entries[:10]

    def _sync_ooc_spellbook_and_sheet(self, state: CampaignState, entries: list[dict[str, Any]]) -> dict[str, Any]:
        runtime = state.structured_state.runtime
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        entries = [entry for entry in entries if self._is_valid_structured_spell_name(str(entry.get("name", "")))]
        before_count = len(runtime.abilities)
        runtime.abilities.extend(entries)
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(runtime.abilities)
        runtime.spellbook = list(runtime.abilities)
        spellbook_added = max(0, len(runtime.abilities) - before_count)
        main_sheet = self._find_main_character_sheet(state)
        character_sheet_updated = False
        if main_sheet is not None:
            existing_names = {self.engine._normalize_ability_name(name) for name in main_sheet.abilities}
            existing_guaranteed = {self.engine._normalize_ability_name(entry.name) for entry in main_sheet.guaranteed_abilities}
            for entry in runtime.abilities:
                name = str(entry.get("name", "")).strip()
                if not name:
                    continue
                if not self._is_valid_structured_spell_name(name):
                    continue
                normalized = self.engine._normalize_ability_name(name)
                if normalized not in existing_names:
                    main_sheet.abilities.append(name)
                    existing_names.add(normalized)
                    character_sheet_updated = True
                if normalized not in existing_guaranteed:
                    main_sheet.guaranteed_abilities.append(CharacterSheetAbilityEntry.from_payload(entry))
                    existing_guaranteed.add(normalized)
                    character_sheet_updated = True
        return {"spellbook_entries_added": spellbook_added, "character_sheet_updated": character_sheet_updated}

    def _sync_ooc_inventory_entries(self, state: CampaignState, entries: list[dict[str, Any]]) -> dict[str, Any]:
        runtime = state.structured_state.runtime
        if not isinstance(runtime.inventory_state, dict):
            runtime.inventory_state = {}
        self._normalize_inventory_state(runtime.inventory_state)
        current_entries = list(runtime.inventory_state.get("entries", []))
        by_name = {str(entry.get("name", "")).strip().lower(): entry for entry in current_entries if str(entry.get("name", "")).strip()}
        added = 0
        updated = 0
        for entry in entries:
            key = str(entry.get("name", "")).strip().lower()
            if not key:
                continue
            if key in by_name:
                merged = dict(by_name[key])
                merged.update(entry)
                by_name[key] = merged
                updated += 1
            else:
                by_name[key] = entry
                added += 1
        runtime.inventory_state["entries"] = list(by_name.values())
        self._normalize_inventory_state(runtime.inventory_state)
        runtime.inventory = [str(entry.get("name", "")).strip() for entry in runtime.inventory_state.get("entries", []) if str(entry.get("name", "")).strip()]
        return {"inventory_entries_added": added, "inventory_entries_updated": updated}

    def _cleanup_invalid_spell_text_entries(self, state: CampaignState) -> int:
        removed = 0
        runtime = state.structured_state.runtime
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        cleaned_spellbook: list[dict[str, Any]] = []
        for entry in runtime.abilities:
            if isinstance(entry, dict) and self._is_valid_structured_spell_name(str(entry.get("name", ""))):
                cleaned_spellbook.append(entry)
            else:
                removed += 1
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(cleaned_spellbook)
        runtime.spellbook = list(runtime.abilities)

        main_sheet = self._find_main_character_sheet(state)
        if main_sheet is None:
            print(f"[cleanup] removed_invalid_spell_entries={removed}")
            return removed

        valid_abilities: list[str] = []
        for ability in list(main_sheet.abilities):
            if self._is_valid_structured_spell_name(ability):
                valid_abilities.append(str(ability).strip())
            else:
                removed += 1
        main_sheet.abilities = valid_abilities

        valid_guaranteed: list[CharacterSheetAbilityEntry] = []
        for ability in list(main_sheet.guaranteed_abilities):
            if self._is_valid_structured_spell_name(ability.name):
                valid_guaranteed.append(ability)
            else:
                removed += 1
        main_sheet.guaranteed_abilities = valid_guaranteed
        print(f"[cleanup] removed_invalid_spell_entries={removed}")
        return removed

    def _apply_ooc_spellbook_category_correction(self, state: CampaignState, text: str) -> int:
        runtime = state.structured_state.runtime
        runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        pattern = re.compile(
            r"['\"]?(?P<name>[a-z0-9][a-z0-9 '\-]{1,60})['\"]?\s+should be\s+(?:a|an)\s+(?P<category>spell|skill|ability|passive|technique|trait|item_power)\b",
            flags=re.IGNORECASE,
        )
        match = pattern.search(text or "")
        if not match:
            return 0
        target_name = str(match.group("name") or "").strip().lower()
        target_category = str(match.group("category") or "").strip().lower()
        updated = 0
        for index, entry in enumerate(runtime.abilities):
            if str(entry.get("name", "")).strip().lower() != target_name:
                continue
            merged_tags = sorted(set([str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip()] + ["corrected_by_gm", "learned_ooc"]))
            normalized = normalize_spellbook_entry(
                {
                    **entry,
                    "category": target_category,
                    "tags": merged_tags,
                    "source_metadata": {"source_type": "corrected_by_gm"},
                },
                index=index,
            )
            if normalized:
                runtime.abilities[index] = normalized
                updated += 1
        if updated:
            runtime.abilities = self.engine.state_orchestrator._normalize_spellbook(runtime.abilities)
            runtime.spellbook = list(runtime.abilities)
        return updated

    def _apply_ooc_structured_updates(self, request_text: str, response_text: str, structured_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        lowered_request = str(request_text or "").lower()
        state = self.session.state
        payload = structured_payload if isinstance(structured_payload, dict) else {}
        summary = {
            "spellbook_entries_added": 0,
            "character_sheet_updated": False,
            "world_entries_added": 0,
            "inventory_entries_added": 0,
            "inventory_entries_updated": 0,
            "mutated": False,
        }
        if any(token in lowered_request for token in {"spellbook", "spell", "abilities", "ability", "character sheet"}):
            parsed_entries = self._validate_structured_spell_entries(payload)
            if parsed_entries:
                sync_summary = self._sync_ooc_spellbook_and_sheet(state, parsed_entries)
                summary["spellbook_entries_added"] = int(sync_summary["spellbook_entries_added"])
                summary["character_sheet_updated"] = bool(sync_summary["character_sheet_updated"])
            else:
                corrected = self._apply_ooc_spellbook_category_correction(state, request_text)
                summary["character_sheet_updated"] = bool(summary["character_sheet_updated"] or corrected > 0)
        if any(token in lowered_request for token in {"title", "identity"}):
            main_sheet = self._find_main_character_sheet(state)
            title_match = re.search(r"(?:title|identity)[^A-Za-z0-9]*[:=]?\s*([A-Za-z][A-Za-z '\-]{2,60})", request_text, flags=re.I)
            if title_match and main_sheet is not None:
                next_title = title_match.group(1).strip(" .")
                if next_title and next_title != main_sheet.level_or_rank:
                    main_sheet.level_or_rank = next_title
                    summary["character_sheet_updated"] = True
        if any(token in lowered_request for token in {"world building", "world notes", "world note"}):
            world_entries = self._extract_world_entries_from_ooc_response(response_text)
            if world_entries:
                lore = state.structured_state.canon.lore
                existing = {str(entry).strip().lower() for entry in lore}
                for entry in world_entries:
                    key = entry.strip().lower()
                    if key and key not in existing:
                        lore.append(entry)
                        existing.add(key)
                        summary["world_entries_added"] += 1
        if "inventory" in lowered_request:
            inventory_entries = self._validate_structured_inventory_entries(payload)
            if inventory_entries:
                inventory_sync = self._sync_ooc_inventory_entries(state, inventory_entries)
                summary["inventory_entries_added"] = int(inventory_sync["inventory_entries_added"])
                summary["inventory_entries_updated"] = int(inventory_sync["inventory_entries_updated"])
        summary["mutated"] = bool(
            summary["spellbook_entries_added"] > 0
            or summary["character_sheet_updated"]
            or summary["world_entries_added"] > 0
            or summary["inventory_entries_added"] > 0
            or summary["inventory_entries_updated"] > 0
        )
        return summary

    def _recalibration_backfill_ooc_structured_data(self, state: CampaignState) -> dict[str, Any]:
        summary = {"spellbook_entries_added": 0, "character_sheet_updated": False, "world_entries_added": 0}
        for index, entry in enumerate(self.session.message_history):
            if str(entry.get("type", "")).strip() != "ooc_player":
                continue
            request_text = str(entry.get("text", "")).strip()
            if self._detect_ooc_mode(request_text) != "structured_authoring":
                continue
            if index + 1 >= len(self.session.message_history):
                continue
            reply = self.session.message_history[index + 1]
            if str(reply.get("type", "")).strip() != "ooc_gm":
                continue
            payload = reply.get("structured_sync_payload", {})
            if not isinstance(payload, dict) or not payload:
                print("[recalibration] skipped_unstructured_ooc_text=true")
                continue
            sync = self._apply_ooc_structured_updates(request_text, str(reply.get("text", "")), payload)
            summary["spellbook_entries_added"] += int(sync.get("spellbook_entries_added", 0))
            summary["character_sheet_updated"] = bool(summary["character_sheet_updated"] or sync.get("character_sheet_updated"))
            summary["world_entries_added"] += int(sync.get("world_entries_added", 0))
        return summary

    def handle_ooc_input(self, text: str) -> dict[str, Any]:
        request_received_at = datetime.now(timezone.utc).isoformat()
        clean_text = text.strip()
        ooc_mode = self._detect_ooc_mode(clean_text)
        model_status = self.get_model_status()
        self._append_message("ooc_player", clean_text, persist=False)
        print(f"[ooc] mode={ooc_mode}")
        if ooc_mode == "behavior_rule":
            sync_summary = {"spellbook_entries_added": 0, "character_sheet_updated": False, "world_entries_added": 0, "mutated": False}
            rule_entry, added, deduped = self._upsert_ooc_behavior_rule(clean_text)
            print(f"[narrator-rules] added_custom_rule={str(added).lower()}")
            print(f"[narrator-rules] dedupe_reused={str(deduped).lower()}")
            self.save_active_campaign(self.session.active_slot)
            acknowledgement = f"Got it. I’ll apply this narrator rule for this campaign: {rule_entry.get('text', '').strip()}"
            self._append_message("ooc_gm", acknowledgement, persist=False)
            self._flush_history_store()
            return {
                "narrative": acknowledgement,
                "system_messages": [],
                "messages": [{"type": "ooc_gm", "text": acknowledgement}],
                "should_exit": False,
                "metadata": {
                    "mode": "ooc",
                    "ooc_mode": ooc_mode,
                    "ooc_sync": sync_summary,
                    "model_status": model_status,
                    "behavior_rule": {
                        "id": str(rule_entry.get("id", "")).strip(),
                        "text": str(rule_entry.get("text", "")).strip(),
                        "added": added,
                    },
                    "timing": {
                        "request_received_at": request_received_at,
                        "ooc_generation_ms": 0.0,
                    },
                },
                "state": self.serialize_state(),
            }
        context_prompt = self._build_ooc_context()
        system_prompt = (
            "You are the Adventure Guild AI GM brain responding in OOC mode.\n"
            "Answer using campaign context, clarify continuity, and acknowledge uncertainty when relevant.\n"
            "Do not advance canon, do not declare gameplay consequences.\n"
            "If the user explicitly asks to create or update structured campaign data (spellbook, character sheet, world notes), "
            "you may provide structured content suitable for persistence.\n"
            "When providing structured content, include a machine-only JSON object between "
            "[STRUCTURED_SYNC_PAYLOAD] and [/STRUCTURED_SYNC_PAYLOAD] with keys like spellbook_entries or inventory_entries.\n"
            "Never include conversational text inside this JSON payload."
        )
        started = time.perf_counter()
        try:
            response_text = self.engine.model.generate(
                prompt=f"{context_prompt}\n\n[OOC PLAYER MESSAGE]\n{clean_text}",
                system_prompt=system_prompt,
            )
        except ProviderUnavailableError:
            response_text = (
                "OOC note: The model provider is currently unavailable, so I cannot fully analyze continuity right now. "
                "No canon state has changed."
            )
        except Exception as exc:  # pragma: no cover - defensive guard for provider-specific failures
            response_text = (
                f"OOC note: I hit an error while processing that question ({exc}). "
                "No canon state was changed."
            )
        generation_ms = (time.perf_counter() - started) * 1000
        structured_payload = self._extract_ooc_structured_payload(response_text) if ooc_mode == "structured_authoring" else {}
        sync_summary = {"spellbook_entries_added": 0, "character_sheet_updated": False, "world_entries_added": 0, "mutated": False}
        if ooc_mode == "structured_authoring":
            sync_summary = self._apply_ooc_structured_updates(clean_text, response_text, structured_payload)
            print(f"[ooc-sync] spellbook_entries_added={sync_summary['spellbook_entries_added']}")
            print(f"[ooc-sync] character_sheet_updated={str(sync_summary['character_sheet_updated']).lower()}")
            print(f"[ooc-sync] world_entries_added={sync_summary['world_entries_added']}")
            if sync_summary["mutated"]:
                self.save_active_campaign(self.session.active_slot)
        self._append_message("ooc_gm", response_text, persist=False, structured_sync_payload=structured_payload)
        self._flush_history_store()
        return {
            "narrative": response_text,
            "system_messages": [],
            "messages": [{"type": "ooc_gm", "text": response_text}],
            "should_exit": False,
            "metadata": {
                "mode": "ooc",
                "ooc_mode": ooc_mode,
                "ooc_sync": sync_summary,
                "model_status": model_status,
                "timing": {
                    "request_received_at": request_received_at,
                    "ooc_generation_ms": round(generation_ms, 2),
                },
            },
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

    def _sync_npc_identities(self) -> NPCIdentityRegistry:
        registry = NPCIdentityRegistry(self.session.state)
        registry.ensure_for_state()
        return registry

    def _maybe_queue_npc_portraits(self, registry: NPCIdentityRegistry) -> None:
        if not self.session.state.settings.image_generation_enabled:
            return
        if self.app_config.image.provider != "comfyui":
            return
        for npc_id in list(registry.records.keys()):
            should_generate, reason = registry.should_generate_portrait(npc_id)
            if not should_generate:
                if reason not in {"not_important", "portrait_ready", "portrait_requested", "visual_locked"}:
                    print(f"[npc-portrait] generation_skipped npc_id={npc_id} reason={reason}")
                continue
            self._queue_npc_portrait_generation(npc_id=npc_id)

    def _queue_npc_portrait_generation(self, *, npc_id: str) -> bool:
        slot = self.session.active_slot
        job_key = (slot, npc_id)
        with self._npc_portrait_lock:
            if job_key in self._active_npc_portrait_jobs:
                return False
            self._active_npc_portrait_jobs.add(job_key)
        registry = self._sync_npc_identities()
        if npc_id in registry.records:
            registry.records[npc_id]["portrait_status"] = "queued"
        print(f"[npc-portrait] generation_requested npc_id={npc_id}")

        def _worker() -> None:
            try:
                self._generate_npc_portrait(npc_id=npc_id)
            finally:
                with self._npc_portrait_lock:
                    self._active_npc_portrait_jobs.discard(job_key)

        threading.Thread(target=_worker, name=f"npc-portrait-{slot}-{npc_id}", daemon=True).start()
        return True

    def _generate_npc_portrait(self, *, npc_id: str) -> None:
        registry = self._sync_npc_identities()
        if npc_id not in registry.records:
            return
        prompt = registry.portrait_prompt(npc_id)
        registry.records[npc_id]["portrait_status"] = "requested"
        registry.records[npc_id]["portrait_prompt"] = prompt
        request_payload = {
            "workflow_id": "character_portrait",
            "prompt": prompt,
            "negative_prompt": "full body, scene composition, environment panorama, text watermark",
            "parameters": {"checkpoint": self.app_config.image.preferred_checkpoint},
        }
        result = self.generate_image(request_payload)
        if not result.success:
            print(f"[npc-portrait] generation_failed npc_id={npc_id} reason={result.error}")
            registry.bind_portrait_failure(npc_id, str(result.error or "portrait_generation_failed"))
            return
        public_image_url = self.public_image_path(result.result_path)
        if not public_image_url:
            print(f"[npc-portrait] generation_failed npc_id={npc_id} reason=missing_public_image_url")
            registry.bind_portrait_failure(npc_id, "missing_public_image_url")
            return
        registry.bind_portrait_success(npc_id, portrait_path=public_image_url, prompt=prompt)
        print(f"[npc-portrait] generation_succeeded npc_id={npc_id}")

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
        prompt = str(prompt_override or "").strip()
        negative_prompt = ""
        if not prompt:
            # Boundary: prompt extraction/composition happens in TurnImagePromptBuilder.
            # Workflow token replacement/patching remains in WorkflowManager.
            packet = self.turn_image_prompts.build_packet(
                self.session.state,
                player_action=player_action,
                narrator_response=narrator_response,
                stage=stage,
                negative_prompt_additions=self.app_config.image.auto_negative_prompt_additions,
            )
            prompt = packet.prompt
            negative_prompt = packet.negative_prompt
            runtime_scene_state = self.session.state.structured_state.runtime.scene_state
            if isinstance(runtime_scene_state, dict):
                runtime_scene_state["visual_continuity"] = dict(packet.continuity_state)
        prompt_preview = " ".join(prompt.split())[:160]
        print(f"[turn-visual] prompt_preview={prompt_preview}")
        request_payload = {
            "workflow_id": "scene_image",
            "prompt": prompt,
            "negative_prompt": negative_prompt,
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
        path_status = self.get_path_configuration_status()
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
                "auto_negative_prompt_additions": list(self.app_config.image.auto_negative_prompt_additions),
                "managed_service_enabled": self.app_config.image.managed_service_enabled,
                "managed_install_path": self.app_config.image.managed_install_path,
                "managed_logs_path": self.app_config.image.managed_logs_path,
            },
            "path_config": path_status,
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
            auto_negative_prompt_additions=[
                str(v).strip()
                for v in image_payload.get("auto_negative_prompt_additions", self.app_config.image.auto_negative_prompt_additions)
                if str(v).strip()
            ]
            if isinstance(
                image_payload.get("auto_negative_prompt_additions", self.app_config.image.auto_negative_prompt_additions), list
            )
            else list(self.app_config.image.auto_negative_prompt_additions),
            managed_service_enabled=bool(image_payload.get("managed_service_enabled", self.app_config.image.managed_service_enabled)),
            managed_install_path=str(image_payload.get("managed_install_path", self.app_config.image.managed_install_path)),
            managed_logs_path=str(image_payload.get("managed_logs_path", self.app_config.image.managed_logs_path)),
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
            if not bool(path_config.get("checkpoint_dir", {}).get("model_ready", False)):
                model_message = str(
                    path_config.get("checkpoint_dir", {}).get("model_message")
                    or "No checkpoint found. Select a model folder or download one."
                )
                return ImageGenerationResult(
                    success=False,
                    workflow_id=str(payload.get("workflow_id", "scene_image")),
                    error=model_message,
                    metadata={"provider": "comfyui", "status_code": "model_required"},
                )
        if self.app_config.image.provider == "comfyui":
            image_status = self.get_image_status()
            if not bool(image_status.get("engine_ready", image_status.get("ready", False))):
                print("[image-pipeline] request blocked reason=comfyui_service_unavailable")
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
        requested_workflow_id = str(payload.get("workflow_id", "scene_image")).strip() or "scene_image"
        request = ImageGenerationRequest(
            workflow_id=requested_workflow_id,
            prompt=str(payload.get("prompt", "")),
            negative_prompt=str(payload.get("negative_prompt", "")),
            parameters=parameters,
        )
        workflow_manager = self.workflow_manager
        resolved_workflow = str(path_config.get("workflow_path", {}).get("resolved_path") or self.app_config.image.comfyui_workflow_path).strip()
        if resolved_workflow and requested_workflow_id in {"", "scene_image"}:
            workflow_path = Path(resolved_workflow)
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
        runtime.auto_start_image_backend_if_needed()

    @app.on_event("shutdown")
    async def _shutdown_managed_backends() -> None:
        runtime.shutdown_managed_services()

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

    @app.get("/api/campaign/play-view")
    def campaign_play_view(limit: int = 200) -> dict[str, Any]:
        return runtime.get_play_view(limit=limit)

    @app.get("/api/campaign/scene-visual")
    def campaign_scene_visual() -> dict[str, Any]:
        return {"scene_visual": runtime._scene_visual_for_slot()}

    @app.get("/api/campaign/inventory")
    def campaign_inventory() -> dict[str, Any]:
        return {"inventory": runtime.get_inventory_state()}

    @app.post("/api/campaign/inventory")
    def campaign_inventory_update(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.upsert_inventory_entry(payload)
        except ValueError as exc:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    @app.get("/api/campaign/spellbook")
    def campaign_spellbook() -> dict[str, Any]:
        abilities = runtime.get_spellbook_state()
        return {"abilities": abilities, "spellbook": abilities}

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

    @app.get("/api/desktop/capabilities")
    def desktop_capabilities() -> dict[str, Any]:
        return runtime.get_desktop_capabilities()

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

    @app.post("/api/setup/stop-image-engine")
    def setup_stop_image_engine() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/stop-image-engine")
        return runtime.stop_image_engine()

    @app.get("/api/setup/image-engine-status")
    def setup_image_engine_status() -> dict[str, Any]:
        return runtime.get_image_engine_service_status()

    @app.post("/api/setup/open-image-engine-ui")
    def setup_open_image_engine_ui() -> dict[str, Any]:
        return runtime.open_image_engine_debug_ui()

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

    @app.post("/api/setup/open-external-url")
    def setup_open_external_url(payload: dict[str, Any]) -> dict[str, Any]:
        url = str(payload.get("url", "")).strip()
        return runtime.open_external_url(url)

    @app.post("/api/setup/open-local-path")
    def setup_open_local_path(payload: dict[str, Any]) -> dict[str, Any]:
        path = str(payload.get("path", "")).strip()
        return runtime.open_local_path(path)

    @app.post("/api/setup/connect-ollama-path")
    def setup_connect_ollama_path(payload: dict[str, Any]) -> dict[str, Any]:
        selected_path = str(payload.get("path", ""))
        return runtime.connect_ollama_path(selected_path)

    @app.post("/api/setup/connect-comfyui-path")
    def setup_connect_comfyui_path(payload: dict[str, Any]) -> dict[str, Any]:
        selected_path = str(payload.get("path", ""))
        return runtime.connect_comfyui_path(selected_path)

    @app.get("/api/setup/image-readiness-card")
    def setup_image_readiness_card() -> dict[str, Any]:
        return runtime.get_image_setup_snapshot()

    @app.get("/api/setup/image-backend-diagnostics")
    def setup_image_backend_diagnostics() -> dict[str, Any]:
        return runtime.get_image_backend_diagnostics()

    @app.post("/api/setup/use-bundled-image-engine")
    def setup_use_bundled_image_engine() -> dict[str, Any]:
        return runtime.use_bundled_image_engine()

    @app.post("/api/setup/save-checkpoint-folder")
    def setup_save_checkpoint_folder(payload: dict[str, Any]) -> dict[str, Any]:
        selected_path = str(payload.get("path", ""))
        return runtime.save_checkpoint_folder(selected_path)

    @app.post("/api/setup/skip-images")
    def setup_skip_images() -> dict[str, Any]:
        return runtime.skip_images_for_now()

    @app.get("/api/setup/comfyui-models")
    def setup_comfyui_models() -> dict[str, Any]:
        return runtime.get_comfyui_model_status()

    @app.post("/api/campaign/input")
    def campaign_input(payload: dict[str, Any]) -> dict[str, Any]:
        player_text = str(payload.get("text", "")).strip()
        mode = str(payload.get("mode", "ic")).strip().lower()
        if not player_text:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="'text' is required")
        if mode not in {"ic", "ooc"}:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="'mode' must be 'ic' or 'ooc'")
        if mode == "ooc":
            return runtime.handle_ooc_input(player_text)
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
