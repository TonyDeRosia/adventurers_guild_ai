"""Local web chat runtime and HTTP API for Adventurer Guild AI."""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.pathing import initialize_user_data_paths, project_root, static_dir
from app.runtime_config import AppRuntimeConfig, ImageRuntimeConfig, ModelRuntimeConfig, RuntimeConfigStore
from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignSettings, CampaignState
from engine.game_state_manager import GameStateManager
from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter, NullImageAdapter
from images.comfyui_adapter import ComfyUIAdapter
from images.local_adapter import LocalPlaceholderImageAdapter
from images.workflow_manager import WorkflowManager
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
        self._append_message("system", "Web session initialized. GUI mode is active.")

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
        self._append_message("system", f"Switched to campaign slot '{slot}'.")
        return {"slot": slot, "state": self.serialize_state()}

    def delete_campaign(self, slot: str) -> dict[str, Any]:
        if slot == self.session.active_slot:
            raise ValueError("Cannot delete the active campaign. Switch first.")
        path = self.paths.saves / f"{slot}.json"
        if not path.exists():
            raise ValueError(f"Save slot '{slot}' not found")
        path.unlink()
        self.history_store.pop(slot, None)
        self._persist_history_store()
        return {"deleted": slot}

    def rename_campaign(self, slot: str, new_name: str) -> dict[str, Any]:
        state = self.state_manager.load(slot)
        if state is None:
            raise ValueError(f"Save slot '{slot}' not found or invalid")
        clean = new_name.strip()
        if not clean:
            raise ValueError("new_name cannot be empty")
        state.campaign_name = clean
        self.state_manager.save(state, slot)
        if slot == self.session.active_slot:
            self.session.state.campaign_name = clean
        return {"slot": slot, "campaign_name": clean}

    def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        player_name = str(payload.get("player_name", "Aria"))
        char_class = str(payload.get("char_class", "Ranger"))
        profile = str(payload.get("profile", "classic_fantasy"))
        slot = str(payload.get("slot", f"campaign_{len(self.list_saves()) + 1}"))
        state = self.state_manager.create_new_campaign(
            player_name=player_name,
            char_class=char_class,
            profile=profile,
            mature_content_enabled=bool(payload.get("mature_content_enabled", False)),
            content_settings_enabled=bool(payload.get("content_settings_enabled", True)),
            campaign_tone=str(payload.get("campaign_tone", "heroic")),
            maturity_level=str(payload.get("maturity_level", "standard")),
            thematic_flags=list(payload.get("thematic_flags", ["adventure", "mystery"])),
        )
        self.session = WebSession(state=state, active_slot=slot)
        self.session.message_history = []
        self._append_message("system", f"Started new campaign for {player_name} in slot '{slot}'.")
        self.save_active_campaign(slot)
        return {"slot": slot, "state": self.serialize_state()}

    def handle_player_input(self, text: str) -> dict[str, Any]:
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
            "metadata": result.metadata or {},
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
            "image": {
                "provider": self.app_config.image.provider,
                "base_url": self.app_config.image.base_url,
                "enabled": self.app_config.image.enabled,
            },
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
        )
        self.config_store.save(self.app_config)
        self.engine.model = self._create_model_adapter()
        self.image_adapter = self._create_image_adapter()
        self._append_message("system", "Global runtime settings updated.")
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


class WebHandler(BaseHTTPRequestHandler):
    runtime: WebRuntime
    static_root: Path

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._serve_file("index.html", "text/html; charset=utf-8")
        if parsed.path.startswith("/static/"):
            return self._serve_static(parsed.path.replace("/static/", "", 1))
        if parsed.path.startswith("/generated/"):
            return self._serve_generated(parsed.path.replace("/generated/", "", 1))
        if parsed.path == "/api/campaign/state":
            return self._json_response({"state": self.runtime.serialize_state()})
        if parsed.path == "/api/campaign/messages":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["200"])[0])
            return self._json_response({"messages": self.runtime.session.message_history[-max(limit, 1) :]})
        if parsed.path == "/api/campaign/saves":
            return self._json_response({"saves": self.runtime.list_saves()})
        if parsed.path == "/api/campaigns":
            return self._json_response({"campaigns": self.runtime.list_campaigns()})
        if parsed.path == "/api/settings/global":
            return self._json_response({"settings": self.runtime.get_global_settings()})
        if parsed.path == "/api/model/options":
            return self._json_response({"models": self.runtime.list_available_local_models()})
        self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        payload = self._parse_json_body()
        if payload is None:
            return
        try:
            if self.path == "/api/campaign/input":
                player_text = str(payload.get("text", "")).strip()
                if not player_text:
                    raise ValueError("'text' is required")
                return self._json_response(self.runtime.handle_player_input(player_text))
            if self.path == "/api/campaign/start":
                mode = payload.get("mode", "load")
                if mode == "new":
                    return self._json_response({"mode": "new", **self.runtime.create_campaign(payload)})
                slot = str(payload.get("slot", "autosave"))
                return self._json_response({"mode": "load", **self.runtime.switch_campaign(slot)})
            if self.path == "/api/campaign/save":
                return self._json_response(self.runtime.save_active_campaign(str(payload.get("slot", "")).strip() or None))
            if self.path == "/api/campaign/delete":
                return self._json_response(self.runtime.delete_campaign(str(payload.get("slot", ""))))
            if self.path == "/api/campaign/rename":
                return self._json_response(self.runtime.rename_campaign(str(payload.get("slot", "")), str(payload.get("new_name", ""))))
            if self.path == "/api/settings/global":
                return self._json_response({"settings": self.runtime.set_global_settings(payload)})
            if self.path == "/api/settings/campaign":
                return self._json_response({"settings": self.runtime.set_campaign_settings(payload)})
            if self.path == "/api/images/generate":
                result = self.runtime.generate_image(payload)
                if result.success:
                    public_image_url = self.runtime.public_image_path(result.result_path)
                    self.runtime._append_message(
                        "image",
                        payload.get("prompt", "Image generated"),
                        image={"url": public_image_url, "metadata": result.metadata, "workflow_id": result.workflow_id},
                    )
                return self._json_response(result.to_dict(), status=HTTPStatus.OK if result.success else HTTPStatus.BAD_REQUEST)
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            self._json_response({"error": f"Internal server error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _parse_json_body(self) -> dict[str, Any] | None:
        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON payload"}, status=HTTPStatus.BAD_REQUEST)
            return None

    def _serve_static(self, relative: str) -> None:
        file_path = self.static_root / relative
        if not file_path.exists() or not file_path.is_file():
            return self._json_response({"error": "Asset not found"}, status=HTTPStatus.NOT_FOUND)
        mime = "text/plain; charset=utf-8"
        if file_path.suffix == ".css":
            mime = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            mime = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".html":
            mime = "text/html; charset=utf-8"
        self._serve_file(relative, mime)

    def _serve_generated(self, relative: str) -> None:
        file_path = (self.runtime.generated_image_dir / relative).resolve()
        root = self.runtime.generated_image_dir.resolve()
        if root not in file_path.parents and file_path != root:
            return self._json_response({"error": "Invalid image path"}, status=HTTPStatus.BAD_REQUEST)
        if not file_path.exists() or not file_path.is_file():
            return self._json_response({"error": "Image not found"}, status=HTTPStatus.NOT_FOUND)
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, relative: str, content_type: str) -> None:
        file_path = self.static_root / relative
        if not file_path.exists():
            return self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_web_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    runtime = WebRuntime(project_root())

    class _BoundHandler(WebHandler):
        pass

    _BoundHandler.runtime = runtime
    _BoundHandler.static_root = static_dir()

    server = ThreadingHTTPServer((host, port), _BoundHandler)
    print(f"Web UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server...")
    finally:
        server.server_close()


def main() -> None:
    run_web_server()


if __name__ == "__main__":
    main()
