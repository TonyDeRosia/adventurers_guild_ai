"""Local web chat scaffold for Adventurer Guild AI.

This module is additive and keeps the terminal app fully intact.
"""

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

from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignState
from engine.game_state_manager import GameStateManager
from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter, NullImageAdapter
from images.local_adapter import LocalPlaceholderImageAdapter
from images.workflow_manager import WorkflowManager
from models.registry import create_model_adapter
from app.pathing import initialize_user_data_paths, project_root, static_dir
from app.runtime_config import ModelRuntimeConfig, RuntimeConfigStore


@dataclass
class WebSession:
    state: CampaignState
    message_history: list[dict[str, Any]] = field(default_factory=list)


class WebRuntime:
    """Owns campaign state and lightweight message history for the web UI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.paths = initialize_user_data_paths()
        self.data_dir = self.paths.user_data
        self.state_manager = GameStateManager(self.paths.content_data, self.paths.saves, self.paths.user_data)
        self.config_store = RuntimeConfigStore(self.paths.config / "app_config.json")
        self.model_config = self.config_store.load()
        self.engine = CampaignEngine(self._create_model_adapter(), data_dir=self.paths.content_data)
        self.workflow_manager = WorkflowManager(self.paths.workflows)
        self.generated_image_dir = self.paths.generated_images
        self.image_adapter = self._create_image_adapter()
        self.session = WebSession(state=self._default_state())
        self._append_message("system", "Web session initialized. GUI mode is active.")

    def _create_image_adapter(self) -> ImageGeneratorAdapter:
        if self.workflow_manager.list_templates():
            return LocalPlaceholderImageAdapter(self.generated_image_dir)
        return NullImageAdapter()

    def _create_model_adapter(self):
        return create_model_adapter(
            self.model_config.provider,
            model=self.model_config.model_name,
            base_url=self.model_config.base_url,
            timeout_seconds=self.model_config.timeout_seconds,
        )

    def _default_state(self) -> CampaignState:
        if self.state_manager.can_load("autosave"):
            loaded = self.state_manager.load("autosave")
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

    def _append_message(self, message_type: str, text: str, **extra: Any) -> None:
        entry = {
            "id": f"m_{len(self.session.message_history) + 1}",
            "type": self._normalize_message_type(message_type, text),
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        entry.update(extra)
        self.session.message_history.append(entry)

    def _normalize_message_type(self, message_type: str, text: str) -> str:
        if message_type in {"player", "narrator", "npc", "quest", "image", "system"}:
            return message_type
        lowered = text.lower()
        if "quest" in lowered:
            return "quest"
        if lowered.startswith('"') or "relationship tier" in lowered:
            return "npc"
        return "system"

    def handle_player_input(self, text: str) -> dict[str, Any]:
        self._append_message("player", text)
        result = self.engine.run_turn(self.session.state, text)

        for message in result.messages:
            self._append_message(message["type"], message["text"])

        if result.should_exit:
            self.state_manager.save(self.session.state, "autosave")
            self._append_message("system", "Session flagged for exit; autosave written.")

        return {
            "narrative": result.narrative,
            "system_messages": result.system_messages,
            "messages": result.messages,
            "should_exit": result.should_exit,
            "metadata": result.metadata or {},
            "state": self.serialize_state(),
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
                "hp": state.player.hp,
                "max_hp": state.player.max_hp,
            },
            "active_enemy_id": state.active_enemy_id,
            "active_enemy_hp": state.active_enemy_hp,
            "faction_reputation": state.faction_reputation,
            "quest_status": {qid: quest.status for qid, quest in state.quests.items()},
            "conversation_turn_count": len(state.conversation_turns),
        }

    def get_model_config(self) -> dict[str, Any]:
        return {
            "provider": self.model_config.provider,
            "model_name": self.model_config.model_name,
            "base_url": self.model_config.base_url,
            "timeout_seconds": self.model_config.timeout_seconds,
        }

    def set_model_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = str(payload.get("provider", self.model_config.provider)).strip().lower()
        if provider not in {"null", "ollama"}:
            raise ValueError("provider must be 'null' or 'ollama'")
        model_name = str(payload.get("model_name", self.model_config.model_name)).strip() or self.model_config.model_name
        base_url = str(payload.get("base_url", self.model_config.base_url)).strip() or self.model_config.base_url
        timeout_seconds = int(payload.get("timeout_seconds", self.model_config.timeout_seconds))
        self.model_config = ModelRuntimeConfig(
            provider=provider,
            model_name=model_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        self.config_store.save(self.model_config)
        self.engine.model = self._create_model_adapter()
        self._append_message("system", f"Model configuration updated ({provider}:{model_name}).")
        return self.get_model_config()

    def list_available_local_models(self) -> list[str]:
        adapter = self._create_model_adapter()
        if hasattr(adapter, "list_local_models"):
            return getattr(adapter, "list_local_models")()
        return []

    def list_saves(self) -> list[str]:
        save_dir = self.paths.saves
        if not save_dir.exists():
            return []
        return sorted(path.stem for path in save_dir.glob("*.json"))

    def start_or_load_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = payload.get("mode", "load")
        if mode == "load":
            slot = payload.get("slot", "autosave")
            if not self.state_manager.can_load(slot):
                raise ValueError(f"Save slot '{slot}' not found")
            self.session = WebSession(state=self.state_manager.load(slot))
            self._append_message("system", f"Loaded campaign slot '{slot}'.")
            return {"mode": "load", "slot": slot, "state": self.serialize_state()}

        player_name = str(payload.get("player_name", "Aria"))
        char_class = str(payload.get("char_class", "Ranger"))
        profile = str(payload.get("profile", "classic_fantasy"))
        self.session = WebSession(
            state=self.state_manager.create_new_campaign(
                player_name=player_name,
                char_class=char_class,
                profile=profile,
                mature_content_enabled=False,
            )
        )
        self._append_message("system", f"Started new campaign for {player_name}.")
        return {"mode": "new", "state": self.serialize_state()}

    def generate_image(self, payload: dict[str, Any]) -> ImageGenerationResult:
        request = ImageGenerationRequest(
            workflow_id=str(payload.get("workflow_id", "scene_image")),
            prompt=str(payload.get("prompt", "")),
            negative_prompt=str(payload.get("negative_prompt", "")),
            parameters=dict(payload.get("parameters", {})),
        )
        return self.image_adapter.generate(request, self.workflow_manager)

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
            relative = parsed.path.replace("/static/", "", 1)
            return self._serve_static(relative)
        if parsed.path.startswith("/generated/"):
            relative = parsed.path.replace("/generated/", "", 1)
            return self._serve_generated(relative)

        if parsed.path == "/api/campaign/state":
            return self._json_response({"state": self.runtime.serialize_state()})

        if parsed.path == "/api/campaign/messages":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["200"])[0])
            history = self.runtime.session.message_history[-max(limit, 1) :]
            return self._json_response({"messages": history})

        if parsed.path == "/api/campaign/saves":
            return self._json_response({"saves": self.runtime.list_saves()})
        if parsed.path == "/api/model/config":
            return self._json_response({"config": self.runtime.get_model_config()})
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
                response = self.runtime.handle_player_input(player_text)
                self.runtime.state_manager.save(self.runtime.session.state, "autosave")
                return self._json_response(response)

            if self.path == "/api/campaign/start":
                return self._json_response(self.runtime.start_or_load_campaign(payload))

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
            if self.path == "/api/model/config":
                return self._json_response({"config": self.runtime.set_model_config(payload)})

            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive API boundary
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
    root = project_root()
    runtime = WebRuntime(root)

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
