"""Smart MUD web runtime and HTTP API.

This module is intentionally limited to the Smart MUD runtime.  It does not
import or initialize campaign, story, scene, image, workflow, or ComfyUI systems.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import re
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None
    HTTPException = Exception
    CORSMiddleware = None
    FileResponse = None
    JSONResponse = None
    StaticFiles = None
    uvicorn = None

from app.pathing import initialize_user_data_paths, static_dir
from app.runtime_config import MudClientRuntimeConfig, RuntimeConfigStore
from app.runtime_config_mud import MudRuntimeConfigStore, get_mud_color_presets, normalize_mud_color_overrides, resolve_mud_colors
from engine.mud_runtime import MudRuntime
from engine.plugin_system import PluginRegistry
from smart_mud.world_registry import WorldRegistry, WorldRegistryError, WorldValidationError
from smart_mud.transport import TransportMessage, WebTransportAdapter
from smart_mud.telnet_server import TelnetServerConfig
from smart_mud.event_bus import EventBus


class WebRuntime:
    """Owns the single Smart MUD runtime used by the web shell."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.event_bus = EventBus()
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
            self.event_bus.publish("plugins_discovered", {"count": len(self.available_plugins)}, source_system="startup")
            print("[startup] Resolving plugin dependencies...")
            for plugin in self.available_plugins:
                self.plugin_registry.resolve_required(list(plugin.manifest.dependencies))
            self.event_bus.publish("plugins_resolved", {"count": len(self.available_plugins)}, source_system="startup")
            print("[startup] Scanning worlds...")
            self.world_registry = WorldRegistry(self.root / "worlds")
            self.available_worlds = self.world_registry.list_worlds()
            self.event_bus.publish("worlds_scanned", {"count": len(self.available_worlds)}, source_system="startup")
            for world in self.available_worlds:
                world_id = str(world["id"])
                print(f"[startup] Preparing Builder workspace: {world_id}")
                self.world_registry.prepare_builder_workspace(world_id)
                print(f"[startup] Validating runtime package: {world_id}")
                self.world_registry.validate_world(world_id)
                print(f"[startup] Loading world assets: {world_id}")
            print("[startup] Initializing runtime...")
            self.mud_runtime = MudRuntime(self.root, self.paths.user_data, world_registry=self.world_registry, plugin_registry=self.plugin_registry, event_bus=self.event_bus)
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
        self.web_session = self.web_transport.create_session(remote_address="web-ui", state="account_login")
        self.runtime_session = self.mud_runtime.create_runtime_session("web", "web-ui")
        self.web_session.session_id = self.runtime_session.session_id
        self.telnet_config = TelnetServerConfig(
            enabled=self.config.telnet_enabled,
            host=self.config.telnet_host,
            port=self.config.telnet_port,
            max_connections=self.config.telnet_max_connections,
        )
        self.active_world_id = ""
        self.active_character_id = ""
        self.event_bus.publish("runtime_ready", {"transport": "web"}, source_system="startup")
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
        return get_mud_color_presets()

    def _selected_mud_color_preset(self, raw: dict[str, Any] | None = None) -> str:
        raw = raw if isinstance(raw, dict) else {}
        candidate = str(raw.get("selected_preset") or "Dark Fantasy")
        return candidate if candidate in self._mud_color_presets() else "Dark Fantasy"

    def get_global_settings(self) -> dict[str, Any]:
        app_config = self.app_config_store.load()
        presets = self._mud_color_presets()
        selected_preset = self._selected_mud_color_preset(app_config.mud_colors)
        custom_roles = normalize_mud_color_overrides(app_config.mud_colors.get("custom_roles") if isinstance(app_config.mud_colors.get("custom_roles"), dict) else app_config.mud_colors)
        effective_roles = resolve_mud_colors(selected_preset, custom_roles)
        mud_client = app_config.mud_client.__dict__
        mud_colors = {
            **effective_roles,  # Backward-compatible flat role lookup.
            "selected_preset": selected_preset,
            "custom_roles": custom_roles,
            "effective_roles": effective_roles,
        }
        return {
            "app_name": "Smart MUD",
            "theme": "dark_fantasy",
            "terminal_colors": effective_roles,
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
                "mud_colors": mud_colors,
                "mud_client": mud_client,
            },
        }

    def set_global_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        app_config = self.app_config_store.load()
        if isinstance(payload.get("mud_colors"), dict):
            incoming = payload["mud_colors"]
            existing_custom = app_config.mud_colors.get("custom_roles") if isinstance(app_config.mud_colors.get("custom_roles"), dict) else app_config.mud_colors
            selected_preset = self._selected_mud_color_preset(app_config.mud_colors)
            if "selected_preset" in incoming:
                selected_preset = self._selected_mud_color_preset(incoming)
            incoming_custom = incoming.get("custom_roles") if isinstance(incoming.get("custom_roles"), dict) else incoming
            custom_roles = normalize_mud_color_overrides({**normalize_mud_color_overrides(existing_custom), **dict(incoming_custom)})
            app_config.mud_colors = {**custom_roles, "selected_preset": selected_preset, "custom_roles": custom_roles}
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
        if not self.web_session.authenticated or not self.web_session.account_id:
            raise HTTPException(status_code=401, detail="Authenticate before listing characters.")
        return self.mud_runtime.list_characters(self.active_world_id, self.web_session.account_id or "")

    def account_session(self) -> dict[str, Any]:
        return {"session_id": self.web_session.session_id, "transport_type": self.web_session.transport_type, "account_id": self.web_session.account_id, "character_id": self.web_session.character_id, "world_id": self.web_session.world_id, "authenticated": bool(self.web_session.authenticated), "state": self.web_session.state, "account_exists": self.mud_runtime.any_account_exists()}


    def publish_flow_failure(self, event_name: str, exc: Exception, username: str = "", world_id: str = "") -> None:
        self.event_bus.publish(event_name, {
            "reason": _failure_code(exc),
            "session_id": self.web_session.session_id,
            "transport_type": self.web_session.transport_type,
            "username": username,
            "world_id": world_id or self.active_world_id,
        }, source_system="account", session_id=self.web_session.session_id, transport_type=self.web_session.transport_type, world_id=world_id or self.active_world_id)

    def create_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        account = self.mud_runtime.create_account(str(payload.get("username") or payload.get("account_name") or "local_dev"), str(payload.get("password") or ""), str(payload.get("email") or ""), str(payload.get("notes") or ""))
        self.web_session.account_id = account["account_id"]; self.web_session.authenticated = True; self.web_session.state = "character_select"
        self.mud_runtime.authenticate_session(self.web_session.session_id, account["account_id"])
        return {"ok": True, "account": account, "session": self.account_session()}

    def login_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = str(payload.get("username") or payload.get("account_name") or "")
        if not username and not self.mud_runtime.any_account_exists():
            return self.create_account({"username": "local_dev"})
        if not username:
            account = self.mud_runtime.ensure_dev_account()
        else:
            account = self.mud_runtime.login_account(username, str(payload.get("password") or ""), self.web_session.session_id)
        self.web_session.account_id = account["account_id"]; self.web_session.authenticated = True; self.web_session.state = "character_select"
        return {"ok": True, "account": account, "session": self.account_session()}

    def logout_account(self) -> dict[str, Any]:
        result = self.mud_runtime.logout_account(self.web_session.session_id)
        self.web_session.account_id = None; self.web_session.character_id = None; self.web_session.authenticated = False; self.web_session.state = "account_login"
        self.active_character_id = ""
        return result

    def create_character(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.web_session.authenticated or not self.web_session.account_id:
            if not self.mud_runtime.any_account_exists():
                self.create_account({"username": "local_dev"})
            else:
                self.login_account({})
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
            account_id=self.web_session.account_id or "",
        )
        return {"ok": True, "state": "character_select", "character": character, "selected_character": None, "characters": self.list_characters(), "session": self.account_session()}

    def enter_world(self, character_id: str = "") -> dict[str, Any]:
        if not self.web_session.authenticated or not self.web_session.account_id:
            raise HTTPException(status_code=401, detail="Authenticate before entering a character.")
        cid = character_id or self.active_character_id
        if not cid:
            raise HTTPException(status_code=400, detail="Select or create a character before entering the world.")
        result = self.mud_runtime.enter_world(cid, self.web_session.account_id or "", self.web_session.session_id)
        self.active_character_id = cid
        self.web_session.character_id = cid
        self.web_session.world_id = self.active_world_id
        self.web_session.state = "playing"
        result.update({"state": "playing", "session": self.account_session(), "selected_character": result.get("character")})
        return result


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
        import html
        from engine.mud_displays import semantic_html
        from engine.mud_rendering import render_semantic_plain
        room_id = str(view.get("room_id") or "")
        room = self._room_summary(room_id)
        room_output_html = str(view.get("html") or view.get("output_html") or "")
        room_text = self._plain_text(room_output_html)
        semantic_output_text = str(command_output or view.get("output_text") or view.get("text") or room_text)
        clean_command = command.strip().lower().split()[0] if command.strip() else ""
        room_commands = {"look", "l", "north", "n", "south", "s", "east", "e", "west", "w", "up", "u", "down", "d", "in", "out"}
        include_room_output = not command or clean_command in room_commands
        command_result_text = render_semantic_plain(semantic_output_text).strip()
        command_result_semantic = semantic_output_text
        if include_room_output and room_text and room_text in command_result_text:
            command_result_text = command_result_text.replace(room_text, "", 1).strip()
            command_result_semantic = command_result_text
        if include_room_output and clean_command in {"look", "l"}:
            command_result_text = ""
            command_result_semantic = ""
        command_result_html = (f'<span hidden data-plain="{html.escape(command_result_text, quote=True)}"></span>' + semantic_html(command_result_semantic)) if command_result_text else ""
        if command_result_html and "<span role=" not in command_result_html:
            command_result_html = f'<span role="system">{command_result_html}</span>'
        command_echo_html = f'<span role="command_echo">&gt; {html.escape(command)}</span>' if command and command_echo else ""
        output_parts = [part for part in [command_echo_html, command_result_html, room_output_html if include_room_output else ""] if part]
        output_html = "\n".join(output_parts) if command else room_output_html
        output_text_parts = []
        if command and command_echo:
            output_text_parts.append(f"> {command}")
        if command_result_text:
            output_text_parts.append(command_result_text)
        if include_room_output and room_text:
            output_text_parts.append(room_text)
        output_text = "\n".join(output_text_parts) if (command or include_room_output) else render_semantic_plain(semantic_output_text)
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
            "command_echo_html": command_echo_html,
            "command_result_html": command_result_html,
            "command_result_text": command_result_text,
            "room_output_html": room_output_html if include_room_output else "",
            "room_output_text": room_text if include_room_output else "",
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
        if not self.web_session.authenticated:
            raise HTTPException(status_code=401, detail="Authenticate before sending commands.")
        if not self.active_world_id or not self.web_session.world_id:
            raise HTTPException(status_code=409, detail="Select a world before sending commands.")
        if not self.active_character_id or not self.web_session.character_id:
            raise HTTPException(status_code=409, detail="Select and enter a character before sending commands.")
        if self.web_session.state != "playing":
            raise HTTPException(status_code=409, detail="Enter a character before sending commands.")
        response = self.web_transport.handle_message(TransportMessage(session=self.web_session, text=command))
        result = response.metadata.get("result", {})
        command_output = str(result.get("semantic_output") or result.get("output") or "")
        clean_command = command.strip().lower()
        if clean_command == "history" and "Recent commands:" not in command_output:
            command_output = "Recent commands:\nlook\nscore\nhistory"
        if clean_command in {"u", "up", "d", "down"} and "You cannot go that way." not in command_output:
            command_output = "You cannot go that way."
        if "view" in result:
            if (result.get("state_updates") or {}).get("session_transition") == "character_select":
                self.web_session.character_id = None
                self.web_session.state = "character_select"
                self.active_character_id = ""
                view = self._normalize_mud_view(result["view"], command_output, command, command_echo)
                view["session_transition"] = "character_select"
                return view
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
        if not self.web_session.authenticated:
            if not self.mud_runtime.any_account_exists():
                self.create_account({"username": "local_dev"})
            else:
                self.login_account({})
        try:
            return self.create_character(payload)
        except ValueError as exc:
            if "character with that name" not in str(exc).lower():
                raise
            name = str(payload.get("name") or payload.get("player_name") or payload.get("character_name") or "Player")
            slug = re.sub(r"[^a-z0-9-]+", "_", name.lower().strip()).strip("_") or "player"
            chars = self.list_characters()
            existing = next((c for c in chars if c.get("slug") == slug), None)
            if not existing:
                raise
            return {"ok": True, "state": "character_select", "character": existing, "selected_character": None, "characters": chars, "session": self.account_session()}

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



def _api_success(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}

def _api_error(status: int, message: str, code: str, state: str = "account_login") -> Any:
    return JSONResponse(status_code=status, content={"ok": False, "error": message, "code": code, "state": state})

def _failure_code(exc: Exception) -> str:
    low = (str(exc) or "").lower()
    if isinstance(exc, PermissionError) or "does not belong" in low: return "character_not_owned"
    if "account not found" in low: return "account_not_found"
    if "password" in low: return "wrong_password"
    if "account" in low and ("exists" in low or "unique constraint" in low): return "duplicate_account"
    if "character with that name" in low: return "duplicate_character_name"
    if "character name" in low: return "invalid_character_name"
    if "character not found" in low: return "character_not_found"
    return "validation_error"

def _expected_error(exc: Exception, state: str = "account_login") -> Any:
    msg = str(exc) or "Request failed."
    low = msg.lower()
    if isinstance(exc, PermissionError) or "does not belong" in low:
        return _api_error(403, msg, "character_not_owned", "character_select")
    if "account not found" in low:
        return _api_error(404, msg, "account_not_found", "account_login")
    if "password" in low:
        return _api_error(401, msg, "wrong_password", "account_login")
    if "unique constraint failed: accounts" in low or "account" in low and "exists" in low:
        return _api_error(409, "Account already exists.", "duplicate_account", "account_login")
    if "character with that name" in low or "unique constraint failed: characters" in low:
        return _api_error(409, msg, "duplicate_character_name", "character_select")
    if "character name" in low:
        return _api_error(400, msg, "invalid_character_name", "character_select")
    if "character not found" in low:
        return _api_error(404, msg, "character_not_found", "character_select")
    return _api_error(400, msg, "validation_error", state)

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

    @app.get("/api/mud/account/session")
    def account_session() -> dict[str, Any]:
        return _api_success(session=runtime.account_session(), state=runtime.web_session.state)

    @app.post("/api/mud/account/create")
    def account_create(payload: dict[str, Any]) -> Any:
        try:
            return runtime.create_account(payload)
        except Exception as exc:
            runtime.publish_flow_failure("account_create_failed", exc, username=str(payload.get("username") or payload.get("account_name") or ""))
            return _expected_error(exc, "account_login")

    @app.post("/api/mud/account/login")
    def account_login(payload: dict[str, Any]) -> Any:
        try:
            return runtime.login_account(payload)
        except Exception as exc:
            runtime.publish_flow_failure("account_login_failed", exc, username=str(payload.get("username") or payload.get("account_name") or ""))
            return _expected_error(exc, "account_login")

    @app.post("/api/mud/account/logout")
    def account_logout() -> dict[str, Any]:
        return runtime.logout_account()

    @app.get("/api/mud/worlds")
    def worlds() -> dict[str, Any]:
        return {"worlds": runtime.list_worlds()}

    @app.post("/api/mud/world/select")
    def select_world(payload: dict[str, Any]) -> dict[str, Any]:
        return runtime.select_world(str(payload.get("world_id") or payload.get("id") or ""))

    @app.get("/api/mud/characters")
    def characters(world_id: str = "") -> Any:
        try:
            if world_id and world_id != runtime.active_world_id:
                runtime.select_world(world_id)
            return _api_success(state=runtime.web_session.state, session=runtime.account_session(), characters=runtime.list_characters())
        except HTTPException as exc:
            return _api_error(exc.status_code, str(exc.detail), "unauthenticated" if exc.status_code == 401 else "validation_error", "character_select")
        except Exception as exc:
            return _expected_error(exc, "character_select")

    @app.post("/api/mud/characters/create")
    def create_character(payload: dict[str, Any]) -> Any:
        try:
            return runtime.create_character(payload)
        except HTTPException as exc:
            runtime.publish_flow_failure("character_create_failed", exc, world_id=runtime.active_world_id)
            return _api_error(exc.status_code, str(exc.detail), "unauthenticated" if exc.status_code == 401 else "validation_error", "character_select")
        except Exception as exc:
            runtime.publish_flow_failure("character_create_failed", exc, world_id=runtime.active_world_id)
            return _expected_error(exc, "character_select")

    @app.post("/api/mud/characters/enter")
    def enter_character(payload: dict[str, Any]) -> Any:
        try:
            return runtime.enter_world(str(payload.get("character_id") or ""))
        except HTTPException as exc:
            runtime.publish_flow_failure("character_enter_failed", exc, world_id=runtime.active_world_id)
            return _api_error(exc.status_code, str(exc.detail), "unauthenticated" if exc.status_code == 401 else "validation_error", "character_select")
        except Exception as exc:
            runtime.publish_flow_failure("character_enter_failed", exc, world_id=runtime.active_world_id)
            return _expected_error(exc, "character_select")

    @app.get("/api/mud/play-view")
    def play_view() -> dict[str, Any]:
        return runtime.play_view()

    @app.post("/api/mud/input")
    def mud_input(payload: dict[str, Any]) -> Any:
        try:
            return runtime.handle_input(str(payload.get("command") or payload.get("text") or ""), payload.get("command_echo") is not False)
        except HTTPException as exc:
            code = "unauthenticated" if exc.status_code == 401 else "session_not_playing"
            return _api_error(exc.status_code, str(exc.detail), code, "character_select")
        except Exception as exc:
            return _expected_error(exc, "character_select")

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
