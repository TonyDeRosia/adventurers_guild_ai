"""Local web chat runtime and HTTP API for Adventurer Guild AI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import sys
import urllib.request
import zipfile
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
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
from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignSettings, CampaignState
from engine.game_state_manager import GameStateManager
from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter, NullImageAdapter
from images.comfyui_adapter import ComfyUIAdapter
from images.local_adapter import LocalPlaceholderImageAdapter
from images.workflow_manager import WorkflowManager
from models.ollama_adapter import OllamaAdapter
from models.registry import create_model_adapter


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
        self.history_store_path = self.paths.campaign_memory / "web_message_history.json"
        self.history_store = self._load_history_store()

        self.engine = CampaignEngine(self._create_model_adapter(), data_dir=self.paths.content_data)
        self.image_adapter = self._create_image_adapter()
        default_slot = "autosave" if self.state_manager.can_load("autosave") else "campaign_1"
        self.session = WebSession(state=self._load_or_create(default_slot), active_slot=default_slot)
        self.session.message_history = self._history_for_slot(self.session.active_slot)
        print("[web-runtime] session initialized")

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

    def _history_for_slot(self, slot: str) -> list[dict[str, Any]]:
        existing = self.history_store.get(slot)
        if isinstance(existing, list) and existing:
            return existing
        replayed: list[dict[str, Any]] = []
        for turn in self.session.state.conversation_turns:
            replayed.append(self._message("player", turn.player_input))
            replayed.extend(self._message(self._normalize_message_type("system", msg), msg) for msg in turn.system_messages)
            if turn.narrator_response:
                replayed.append(self._message("narrator", turn.narrator_response))
        self.history_store[slot] = replayed
        return replayed

    def _load_or_create(self, slot: str) -> CampaignState:
        if self.state_manager.can_load(slot):
            loaded = self.state_manager.load(slot)
            if loaded is not None:
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
        return {
            "items": [model_provider_item, model_item, image_item],
            "setup_checklist": [
                "Text generation setup:",
                "1) Install Ollama (https://ollama.com/download).",
                "2) Start the Ollama service: ollama serve",
                f"3) Install the story model: ollama pull {self.app_config.model.model_name}",
                "4) Click Recheck dependencies in the app.",
                "Image generation setup:",
                "1) Install ComfyUI from the in-app Install Image Engine action.",
                "2) Start ComfyUI from the in-app Start Image Engine action.",
                "3) Keep image provider set to local if ComfyUI is unavailable.",
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
        if status_code == "not_installed":
            return [{"id": "install_image_engine", "label": "Install Image Engine"}, {"id": "recheck", "label": "Recheck"}]
        if status_code == "not_running":
            return [{"id": "start_image_engine", "label": "Start Image Engine"}, {"id": "recheck", "label": "Recheck"}]
        return [{"id": "recheck", "label": "Recheck"}]

    def _find_ollama_cli(self) -> str | None:
        if os.name == "nt":
            return shutil.which("ollama.exe") or shutil.which("ollama")
        return shutil.which("ollama")

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
        if not model:
            print("[setup-action] install-model failure reason=model name missing")
            return {"ok": False, "message": "Model name is required."}
        ollama_cli = self._find_ollama_cli()
        if not ollama_cli:
            print("[setup-action] install-model failure reason=ollama cli not found")
            return {
                "ok": False,
                "message": "Ollama is not installed (CLI not found on PATH).",
                "next_step": "Install Ollama from https://ollama.com/download first.",
            }
        if not self.get_model_status().get("reachable", False):
            print("[setup-action] install-model failure reason=ollama service not reachable")
            return {
                "ok": False,
                "message": "Ollama is installed but not running.",
                "next_step": "Start Ollama first, then install the model.",
            }
        try:
            completed = subprocess.run(
                [ollama_cli, "pull", model],
                capture_output=True,
                text=True,
                timeout=60 * 60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(f"[setup-action] install-model failure reason=timeout model={model}")
            return {
                "ok": False,
                "message": f"Model install timed out for {model}.",
                "next_step": f"Run `ollama pull {model}` manually, then click Recheck.",
            }
        output = (completed.stdout or completed.stderr or "").strip()
        snippet = output[-300:] if output else ""
        if completed.returncode != 0:
            print(f"[setup-action] install-model failure reason=exit_{completed.returncode} model={model}")
            return {
                "ok": False,
                "message": f"Failed to install model {model}.",
                "details": snippet,
                "next_step": f"Run `ollama pull {model}` manually and retry.",
            }
        print(f"[setup-action] install-model success model={model}")
        return {
            "ok": True,
            "message": "Story model installed. Text generation is ready.",
            "details": snippet,
            "readiness_refreshed": True,
        }

    def _default_comfyui_path(self) -> Path:
        return self.paths.user_data / "tools" / "ComfyUI"

    def _find_comfyui_root(self) -> Path | None:
        candidates: list[Path] = []
        configured = str(self.app_config.image.comfyui_path or "").strip()
        if configured:
            candidates.append(Path(configured))
        candidates.append(self._default_comfyui_path())
        if os.name == "nt":
            user_profile = os.environ.get("USERPROFILE", "")
            if user_profile:
                candidates.append(Path(user_profile) / "ComfyUI_windows_portable" / "ComfyUI")
                candidates.append(Path(user_profile) / "ComfyUI")
        for candidate in candidates:
            if (candidate / "main.py").exists():
                return candidate
        return None

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
            print(f"[setup-action] install-image-engine success reason=already-installed path={existing}")
            self.app_config.image.comfyui_path = str(existing)
            self.config_store.save(self.app_config)
            return {"ok": True, "message": "ComfyUI is already installed.", "readiness_refreshed": True}
        target_dir = self._default_comfyui_path()
        target_dir.parent.mkdir(parents=True, exist_ok=True)
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
        except OSError as exc:
            print(f"[setup-action] install-image-engine failure reason={exc}")
            return {
                "ok": False,
                "message": "Failed to download or unpack ComfyUI bootstrap files.",
                "next_step": "Open https://github.com/comfyanonymous/ComfyUI and install manually.",
            }
        except zipfile.BadZipFile:
            print("[setup-action] install-image-engine failure reason=invalid-archive")
            return {
                "ok": False,
                "message": "ComfyUI archive download was invalid.",
                "next_step": "Retry installation, or install manually from the official repository.",
            }
        self.app_config.image.comfyui_path = str(target_dir)
        self.config_store.save(self.app_config)
        webbrowser.open("https://github.com/comfyanonymous/ComfyUI")
        print("[setup-action] install-image-engine success")
        return {
            "ok": True,
            "message": "ComfyUI bootstrap downloaded. Complete dependency setup, then start the engine.",
            "next_step": "Install Python dependencies in ComfyUI, then click Start Image Engine.",
            "readiness_refreshed": True,
        }

    def start_image_engine(self) -> dict[str, Any]:
        print("[setup-action] start-image-engine requested")
        if self.app_config.image.provider != "comfyui":
            print("[setup-action] start-image-engine failure reason=image provider is not comfyui")
            return {"ok": False, "message": "Image provider is not set to comfyui.", "next_step": "Set image provider to comfyui, then retry."}
        if self.get_image_status().get("reachable", False):
            print("[setup-action] start-image-engine success reason=already running")
            return {"ok": True, "message": "ComfyUI is already running."}
        comfyui_root = self._find_comfyui_root()
        if comfyui_root is None:
            print("[setup-action] start-image-engine failure reason=not-installed")
            return {"ok": False, "message": "ComfyUI is not installed.", "next_step": "Install Image Engine first."}
        self.app_config.image.comfyui_path = str(comfyui_root)
        self.config_store.save(self.app_config)
        run_script = comfyui_root / "run_nvidia_gpu.bat"
        fallback_script = comfyui_root / "run_cpu.bat"
        try:
            if os.name == "nt" and run_script.exists():
                subprocess.Popen(
                    [str(run_script)],
                    cwd=str(comfyui_root),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif os.name == "nt" and fallback_script.exists():
                subprocess.Popen(
                    [str(fallback_script)],
                    cwd=str(comfyui_root),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,  # type: ignore[attr-defined]
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                python_exe = shutil.which("python") or shutil.which("py")
                if not python_exe:
                    print("[setup-action] start-image-engine failure reason=python-not-found")
                    return {"ok": False, "message": "Python was not found on PATH.", "next_step": "Install Python and retry, or start ComfyUI manually."}
                command = [python_exe, "main.py"]
                subprocess.Popen(
                    command,
                    cwd=str(comfyui_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except OSError as exc:
            print(f"[setup-action] start-image-engine failure reason={exc}")
            return {"ok": False, "message": f"Could not start ComfyUI: {exc}", "next_step": "Start ComfyUI manually, then click Recheck."}
        for _ in range(8):
            time.sleep(0.75)
            if self.get_image_status().get("reachable", False):
                print("[setup-action] start-image-engine success")
                return {"ok": True, "message": "ComfyUI started and is reachable.", "readiness_refreshed": True}
        print("[setup-action] start-image-engine failure reason=not-reachable-after-start")
        return {
            "ok": False,
            "message": "ComfyUI start command was sent, but it is not reachable yet.",
            "next_step": "Wait for startup to finish, then click Recheck.",
        }

    def _create_image_adapter(self) -> ImageGeneratorAdapter:
        cfg = self.app_config.image
        if not cfg.enabled:
            return NullImageAdapter()
        if cfg.provider == "comfyui":
            return ComfyUIAdapter(base_url=cfg.base_url)
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

    def _append_message(self, message_type: str, text: str, **extra: Any) -> None:
        entry = self._message(message_type, text, **extra)
        self.session.message_history.append(entry)
        self.history_store[self.session.active_slot] = self.session.message_history
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
            "player": {"name": state.player.name, "class": state.player.char_class, "hp": state.player.hp, "max_hp": state.player.max_hp},
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
                "content_settings": {
                    "tone": state.settings.content_settings.tone,
                    "maturity_level": state.settings.content_settings.maturity_level,
                    "thematic_flags": state.settings.content_settings.thematic_flags,
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
            "active_slot": self.session.active_slot,
        }

    def list_saves(self) -> list[str]:
        return sorted(path.stem for path in self.paths.saves.glob("*.json")) if self.paths.saves.exists() else []

    def list_campaigns(self) -> list[dict[str, Any]]:
        campaigns = []
        for slot in self.list_saves():
            state = self.state_manager.load(slot)
            if state is None:
                continue
            campaigns.append(
                {
                    "slot": slot,
                    "campaign_id": state.campaign_id,
                    "campaign_name": state.campaign_name,
                    "world_name": state.world_meta.world_name,
                    "turn_count": state.turn_count,
                    "updated": (self.paths.saves / f"{slot}.json").stat().st_mtime,
                }
            )
        return sorted(campaigns, key=lambda item: item["updated"], reverse=True)

    def save_active_campaign(self, slot: str | None = None) -> dict[str, Any]:
        target_slot = (slot or self.session.active_slot or "autosave").strip()
        if not target_slot:
            raise ValueError("save slot cannot be empty")
        self.state_manager.save(self.session.state, target_slot)
        if target_slot != self.session.active_slot:
            self.history_store[target_slot] = list(self.session.message_history)
            self.session.active_slot = target_slot
            self._persist_history_store()
        return {"slot": target_slot, "state": self.serialize_state()}

    def switch_campaign(self, slot: str) -> dict[str, Any]:
        if not self.state_manager.can_load(slot):
            raise ValueError(f"Save slot '{slot}' not found")
        loaded = self.state_manager.load(slot)
        if loaded is None:
            raise ValueError(f"Save slot '{slot}' is corrupted and could not be loaded")
        self.session = WebSession(state=loaded, active_slot=slot)
        self.session.message_history = self._history_for_slot(slot)
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
        self._persist_history_store()
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

    def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        player_name = str(payload.get("player_name", "Aria")).strip() or "Aria"
        char_class = str(payload.get("char_class", "Ranger")).strip() or "Ranger"
        profile = str(payload.get("profile", "classic_fantasy")).strip() or "classic_fantasy"
        slot = str(payload.get("slot", f"campaign_{len(self.list_saves()) + 1}")).strip() or f"campaign_{len(self.list_saves()) + 1}"
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
        )
        self.session = WebSession(state=state, active_slot=slot)
        self.session.message_history = []
        print(f"[web-runtime] created campaign slot={slot} player={player_name}")
        self.save_active_campaign(slot)
        return {"slot": slot, "state": self.serialize_state()}

    def handle_player_input(self, text: str) -> dict[str, Any]:
        model_status = self.get_model_status()
        self._append_message("player", text)
        result = self.engine.run_turn(self.session.state, text)
        for message in result.messages:
            self._append_message(message["type"], message["text"])
        self.save_active_campaign(self.session.active_slot)
        return {
            "narrative": result.narrative,
            "system_messages": result.system_messages,
            "messages": result.messages,
            "should_exit": result.should_exit,
            "metadata": {**(result.metadata or {}), "model_status": model_status},
            "state": self.serialize_state(),
        }

    def get_global_settings(self) -> dict[str, Any]:
        return {
            "model": {
                "provider": self.app_config.model.provider,
                "model_name": self.app_config.model.model_name,
                "base_url": self.app_config.model.base_url,
                "timeout_seconds": self.app_config.model.timeout_seconds,
            },
            "model_status": self.get_model_status(),
            "image": {
                "provider": self.app_config.image.provider,
                "base_url": self.app_config.image.base_url,
                "enabled": self.app_config.image.enabled,
                "comfyui_path": self.app_config.image.comfyui_path,
            },
            "dependency_readiness": self.get_dependency_readiness(),
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
        )
        self.app_config.image = ImageRuntimeConfig(
            provider="null" if image_provider == "null" else image_provider,
            base_url=str(image_payload.get("base_url", self.app_config.image.base_url)),
            enabled=bool(image_payload.get("enabled", self.app_config.image.enabled)),
            comfyui_path=str(image_payload.get("comfyui_path", self.app_config.image.comfyui_path)),
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
        settings.profile = str(payload.get("profile", settings.profile))
        settings.narration_tone = str(payload.get("narration_tone", settings.narration_tone))
        settings.mature_content_enabled = bool(payload.get("mature_content_enabled", settings.mature_content_enabled))
        settings.image_generation_enabled = bool(payload.get("image_generation_enabled", settings.image_generation_enabled))
        content = payload.get("content_settings", {})
        settings.content_settings = CampaignSettings.ContentSettings(
            tone=str(content.get("tone", settings.content_settings.tone)),
            maturity_level=str(content.get("maturity_level", settings.content_settings.maturity_level)),
            thematic_flags=list(content.get("thematic_flags", settings.content_settings.thematic_flags)),
        )
        self.save_active_campaign(self.session.active_slot)
        return self.serialize_state()["settings"]

    def list_available_local_models(self) -> list[str]:
        adapter = self._create_model_adapter()
        if hasattr(adapter, "list_local_models"):
            return getattr(adapter, "list_local_models")()
        return []

    def generate_image(self, payload: dict[str, Any]) -> ImageGenerationResult:
        if not self.session.state.settings.image_generation_enabled:
            return ImageGenerationResult(success=False, workflow_id=str(payload.get("workflow_id", "scene_image")), error="Image generation is disabled for this campaign.")
        request = ImageGenerationRequest(
            workflow_id=str(payload.get("workflow_id", "scene_image")),
            prompt=str(payload.get("prompt", "")),
            negative_prompt=str(payload.get("negative_prompt", "")),
            parameters=dict(payload.get("parameters", {})),
        )
        result = self.image_adapter.generate(request, self.workflow_manager)
        if not result.success and self.app_config.image.provider == "comfyui":
            fallback = LocalPlaceholderImageAdapter(self.generated_image_dir)
            result = fallback.generate(request, self.workflow_manager)
            result.metadata["fallback_reason"] = "ComfyUI unavailable"
            result.metadata["fallback_adapter"] = "local_placeholder"
        return result

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

    @app.get("/api/campaign/state")
    def campaign_state() -> dict[str, Any]:
        return {"state": runtime.serialize_state()}

    @app.get("/api/campaign/messages")
    def campaign_messages(limit: int = 200) -> dict[str, Any]:
        safe_limit = max(limit, 1)
        return {"messages": runtime.session.message_history[-safe_limit:]}

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
        return runtime.install_story_model(model_name)

    @app.post("/api/setup/install-image-engine")
    def setup_install_image_engine() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/install-image-engine")
        return runtime.install_image_engine()

    @app.post("/api/setup/start-image-engine")
    def setup_start_image_engine() -> dict[str, Any]:
        print("[setup-action] route invoked endpoint=/api/setup/start-image-engine")
        return runtime.start_image_engine()

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

    @app.post("/api/settings/campaign")
    def settings_campaign_update(payload: dict[str, Any]) -> dict[str, Any]:
        return {"settings": runtime.set_campaign_settings(payload)}

    @app.post("/api/images/generate")
    def image_generate(payload: dict[str, Any]) -> dict[str, Any]:
        result = runtime.generate_image(payload)
        if result.success:
            public_image_url = runtime.public_image_path(result.result_path)
            runtime._append_message(
                "image",
                payload.get("prompt", "Image generated"),
                image={"url": public_image_url, "metadata": result.metadata, "workflow_id": result.workflow_id},
            )
        if not result.success:
            return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content=result.to_dict())
        return result.to_dict()

    return app
