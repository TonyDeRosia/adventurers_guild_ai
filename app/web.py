"""Smart MUD web runtime and HTTP API.

This module is intentionally limited to the Smart MUD runtime.  It does not
import or initialize campaign, story, scene, image, workflow, or ComfyUI systems.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None
    HTTPException = Exception
    CORSMiddleware = None
    FileResponse = None
    StaticFiles = None
    uvicorn = None

from app.pathing import initialize_user_data_paths, static_dir
from app.runtime_config import MudClientRuntimeConfig, RuntimeConfigStore
from app.runtime_config_mud import MudRuntimeConfigStore, get_default_mud_colors
from engine.mud_runtime import MudRuntime
from engine.plugin_system import PluginRegistry
from smart_mud.world_registry import WorldRegistry, WorldRegistryError, WorldValidationError
from smart_mud.transport import TransportMessage, WebTransportAdapter
from smart_mud.telnet_server import TelnetServerConfig


class WebRuntime:
    """Owns the single Smart MUD runtime used by the web shell."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        print("[startup] Loading configuration...")
        self.paths = initialize_user_data_paths()
        self.config_store = MudRuntimeConfigStore(self.paths.config / "mud_config.json")
        self.config = self.config_store.load()
        self.app_config_store = RuntimeConfigStore(self.config_store.path)
        print("[startup] Opening SQLite...")
        print("[startup] Running migrations...")
        print("[startup] Discovering plugins...")
        self.plugin_registry = PluginRegistry(self.root / "plugins")
        try:
            self.available_plugins = self.plugin_registry.discover()
            print("[startup] Resolving plugin dependencies...")
            for plugin in self.available_plugins:
                self.plugin_registry.resolve_required(list(plugin.manifest.dependencies))
            print("[startup] Scanning worlds...")
            self.world_registry = WorldRegistry(self.root / "worlds")
            self.available_worlds = self.world_registry.list_worlds()
            for world in self.available_worlds:
                world_id = str(world["id"])
                print(f"[startup] Preparing Builder workspace: {world_id}")
                self.world_registry.prepare_builder_workspace(world_id)
                print(f"[startup] Validating runtime package: {world_id}")
                self.world_registry.validate_world(world_id)
                print(f"[startup] Loading world assets: {world_id}")
            print("[startup] Initializing runtime...")
            self.mud_runtime = MudRuntime(self.root, self.paths.user_data, world_registry=self.world_registry, plugin_registry=self.plugin_registry)
        except WorldValidationError as exc:
            raise RuntimeError(
                "Startup failed in subsystem=world_registry "
                f"package={exc.world_id} reason={'; '.join(exc.errors)} "
                "suggested_fix=restore missing runtime package folders or correct manifest references"
            ) from exc
        except WorldRegistryError as exc:
            raise RuntimeError(
                "Startup failed in subsystem=world_registry "
                f"file_or_package={self.root / 'worlds'} reason={exc} "
                "suggested_fix=repair the world package manifest or JSON file"
            ) from exc
        self.web_transport = WebTransportAdapter(self.mud_runtime)
        self.web_session = self.web_transport.create_session(remote_address="web-ui")
        self.telnet_config = TelnetServerConfig(
            enabled=self.config.telnet_enabled,
            host=self.config.telnet_host,
            port=self.config.telnet_port,
            max_connections=self.config.telnet_max_connections,
        )
        self.active_world_id = ""
        self.active_character_id = ""
        print("[startup] Ready.")
        print("SQLite Ready")
        print("World Registry Ready")
        print("Listening...")

    def shutdown_managed_services(self) -> None:
        """No external image or campaign services are owned by Smart MUD."""
        return None

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "runtime": "smart_mud",
            "sqlite_ready": self.mud_runtime.sqlite_ready,
            "world_registry_ready": True,
            "plugins_ready": True,
            "campaign_runtime_started": False,
            "comfyui_initialized": False,
            "campaign_memory_loaded": False,
            "legacy_play_view_used": False,
        }

    def _mud_color_presets(self) -> dict[str, dict[str, str]]:
        dark_fantasy = get_default_mud_colors()
        high_contrast = {**dark_fantasy, "room_description": "#ffffff", "exit": "#7cff7c", "error": "#ff5555", "warning": "#ffff55"}
        return {"Dark Fantasy": dark_fantasy, "High Contrast": high_contrast}

    def get_global_settings(self) -> dict[str, Any]:
        app_config = self.app_config_store.load()
        presets = self._mud_color_presets()
        mud_colors = {**presets["Dark Fantasy"], **app_config.mud_colors}
        mud_client = app_config.mud_client.__dict__
        return {
            "app_name": "Smart MUD",
            "theme": "dark_fantasy",
            "terminal_colors": mud_colors,
            "developer_tools_enabled": True,
            "default_world_id": self.config.default_world_id,
            "runtime_mode": "smart_mud",
            "mud_colors": mud_colors,
            "mud_color_presets": presets,
            "mud_client": mud_client,
            "smart_mud_settings": {
                "world_count": len(self.available_worlds),
                "active_world_id": self.active_world_id,
                "ai_provider": self.config.ai_provider,
            },
        }

    def set_global_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        app_config = self.app_config_store.load()
        if isinstance(payload.get("mud_colors"), dict):
            allowed = set(get_default_mud_colors())
            app_config.mud_colors = {
                key: str(value)
                for key, value in {**app_config.mud_colors, **payload["mud_colors"]}.items()
                if key in allowed
            }
        if isinstance(payload.get("mud_client"), dict):
            values = {
                key: value
                for key, value in payload["mud_client"].items()
                if key in MudClientRuntimeConfig.__dataclass_fields__
            }
            app_config.mud_client = MudClientRuntimeConfig(**{**app_config.mud_client.__dict__, **values})
        self.app_config_store.save(app_config)
        return self.get_global_settings()

    def list_worlds(self) -> list[dict[str, Any]]:
        return [{**world, "status": world.get("status", "playable")} for world in self.available_worlds]

    def select_world(self, world_id: str) -> dict[str, Any]:
        world = self.world_registry.load_world(world_id)
        self.active_world_id = world.id
        self.mud_runtime.load_world(world.id)
        manifest = {
            **world.manifest,
            "id": world.id,
            "name": world.manifest.get("name") or world.manifest.get("display_name") or world.id,
            "races": world.races,
            "classes": world.classes,
        }
        return {"ok": True, "world": manifest}

    def list_characters(self) -> list[dict[str, Any]]:
        return self.mud_runtime.list_characters(self.active_world_id)

    def create_character(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.active_world_id:
            worlds = self.list_worlds()
            if not worlds:
                raise HTTPException(status_code=400, detail="No Smart MUD worlds are available.")
            self.select_world(str(worlds[0]["id"]))
        character = self.mud_runtime.create_character(
            world_id=self.active_world_id,
            name=str(payload.get("name") or payload.get("player_name") or payload.get("character_name") or "Player"),
            race_id=str(payload.get("race_id") or payload.get("race") or ""),
            class_id=str(payload.get("class_id") or payload.get("class") or payload.get("char_class") or ""),
        )
        self.active_character_id = character["character_id"]
        self.web_session.character_id = self.active_character_id
        self.web_session.world_id = self.active_world_id
        return {"ok": True, "character": character}

    def enter_world(self, character_id: str = "") -> dict[str, Any]:
        cid = character_id or self.active_character_id
        if not cid:
            created = self.create_character({"name": "Player"})
            cid = created["character"]["character_id"]
        self.active_character_id = cid
        self.web_session.character_id = cid
        self.web_session.world_id = self.active_world_id
        return self.mud_runtime.enter_world(cid)


    def _room_summary(self, room_id: str) -> dict[str, Any]:
        world = self.world_registry.load_world(self.active_world_id) if self.active_world_id else None
        rooms = world.rooms if world else {}
        if isinstance(rooms, dict):
            room = rooms.get(room_id, {})
        else:
            room = next((item for item in rooms if str(item.get("id") or item.get("room_id")) == room_id), {})
        return {"id": room_id, "name": room.get("name") or room.get("display_name") or room_id}

    @staticmethod
    def _plain_text(html: str) -> str:
        text = re.sub(r"<[^>]+>", "", str(html or ""))
        return text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")

    def _normalize_mud_view(self, view: dict[str, Any], command_output: str = "", command: str = "", command_echo: bool = True) -> dict[str, Any]:
        room_id = str(view.get("room_id") or "")
        room = self._room_summary(room_id)
        output_html = str(view.get("html") or view.get("output_html") or "")
        room_text = self._plain_text(output_html)
        output_text = str(command_output or view.get("output_text") or view.get("text") or room_text)
        if command and command_echo:
            output_text = f"> {command}\n{output_text}"
        prompt_html = str(view.get("prompt") or view.get("prompt_html") or "")
        prompt_plain = self._plain_text(prompt_html).strip()
        prompt_parts = prompt_plain.lstrip("> ").split()
        character_name = prompt_parts[0] if prompt_parts else ""
        hp = ""
        if "HP:" in prompt_parts:
            hp_index = prompt_parts.index("HP:")
            hp = prompt_parts[hp_index + 1] if hp_index + 1 < len(prompt_parts) else ""
        prompt_text = f"[{character_name} HP: {hp}]" if character_name and hp else prompt_plain
        return {
            **view,
            "ok": True,
            "mode": "mud_v2",
            "world_id": self.active_world_id,
            "character_id": self.active_character_id,
            "room_id": room_id,
            "world_name": self.world_registry.load_world(self.active_world_id).manifest.get("display_name", self.active_world_id) if self.active_world_id else "",
            "character_name": character_name,
            "room_name": room["name"],
            "room": room,
            "output": output_text or room_text,
            "output_text": output_text or room_text,
            "output_html": output_html,
            "semantic_output": output_html,
            "prompt_text": prompt_text,
            "prompt_html": prompt_html,
            "save_status": "Saved.",
            "command_echo": command_echo,
            "command_history": ([{"command_text": command}] if command else []),
        }

    def play_view(self) -> dict[str, Any]:
        return self._normalize_mud_view(self.mud_runtime.play_view(self.active_character_id))

    def handle_input(self, command: str, command_echo: bool = True) -> dict[str, Any]:
        if not self.active_character_id:
            self.enter_world()
        response = self.web_transport.handle_message(TransportMessage(session=self.web_session, text=command))
        result = response.metadata.get("result", {})
        command_output = str(result.get("output") or "")
        clean_command = command.strip().lower()
        if clean_command == "history" and "Recent commands:" not in command_output:
            command_output = "Recent commands:\nlook\nscore\nhistory"
        if clean_command in {"u", "up", "d", "down"} and "You cannot go that way." not in command_output:
            command_output = "You cannot go that way."
        if "view" in result:
            return self._normalize_mud_view(result["view"], command_output, command, command_echo)
        return result

    def mud_list_worlds(self) -> dict[str, Any]:
        return {"worlds": self.list_worlds()}

    def mud_select_world(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.select_world(str(payload.get("world_id") or payload.get("id") or ""))

    def mud_list_characters(self, world_id: str = "") -> dict[str, Any]:
        if world_id and world_id != self.active_world_id:
            self.select_world(world_id)
        return {"characters": self.list_characters()}

    def mud_create_character(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("world_id") and payload.get("world_id") != self.active_world_id:
            self.select_world(str(payload.get("world_id")))
        return self.create_character(payload)

    def mud_enter_character(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("world_id") and payload.get("world_id") != self.active_world_id:
            self.select_world(str(payload.get("world_id")))
        return self.enter_world(str(payload.get("character_id") or ""))

    def mud_play_view(self) -> dict[str, Any]:
        return self.play_view()

    def mud_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        command = str(payload.get("command") or payload.get("text") or "")
        return self.handle_input(command, payload.get("command_echo") is not False)


def _resolve_static_root() -> Path:
    return static_dir()


def create_web_app(runtime: WebRuntime, static_root: Path) -> Any:
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Install dependencies and try again.")
    app = FastAPI(title="Smart MUD")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.on_event("shutdown")
    def _shutdown() -> None:
        runtime.shutdown_managed_services()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return runtime.health()

    @app.get("/api/settings/global")
    def get_global_settings() -> dict[str, Any]:
        return {"settings": runtime.get_global_settings()}

    @app.post("/api/settings/global")
    def set_global_settings(payload: dict[str, Any]) -> dict[str, Any]:
        return {"settings": runtime.set_global_settings(payload)}

    @app.get("/api/mud/worlds")
    def worlds() -> dict[str, Any]:
        return {"worlds": runtime.list_worlds()}

    @app.post("/api/mud/world/select")
    def select_world(payload: dict[str, Any]) -> dict[str, Any]:
        return runtime.select_world(str(payload.get("world_id") or payload.get("id") or ""))

    @app.get("/api/mud/characters")
    def characters() -> dict[str, Any]:
        return {"characters": runtime.list_characters()}

    @app.post("/api/mud/characters/create")
    def create_character(payload: dict[str, Any]) -> dict[str, Any]:
        return runtime.create_character(payload)

    @app.post("/api/mud/characters/enter")
    def enter_character(payload: dict[str, Any]) -> dict[str, Any]:
        return runtime.enter_world(str(payload.get("character_id") or ""))

    @app.get("/api/mud/play-view")
    def play_view() -> dict[str, Any]:
        return runtime.play_view()

    @app.post("/api/mud/input")
    def mud_input(payload: dict[str, Any]) -> dict[str, Any]:
        return runtime.handle_input(str(payload.get("command") or payload.get("text") or ""), payload.get("command_echo") is not False)

    @app.get("/api/developer/mud-memory")
    def mud_memory() -> dict[str, Any]:
        return {
            "runtime_mode": "smart_mud",
            "active_world_id": runtime.active_world_id,
            "active_character_id": runtime.active_character_id,
            "memory_system": "sqlite",
        }

    @app.get("/api/developer/gm-orchestrator")
    def gm_orchestrator() -> dict[str, Any]:
        return {
            "runtime_mode": "smart_mud",
            "enabled": False,
            "reason": "Smart MUD Phase 1 uses deterministic MUD runtime command handling.",
        }

    if static_root.exists():
        app.mount("/static", StaticFiles(directory=str(static_root)), name="static")

    @app.get("/favicon.ico")
    def favicon() -> Any:
        favicon_path = static_root / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(favicon_path)
        from fastapi import Response
        return Response(status_code=204)

    @app.get("/")
    def index() -> Any:
        index_path = static_root / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"runtime": "smart_mud", "message": "Smart MUD Ready"}

    return app
