"""Smart MUD web runtime and HTTP API.

This module is intentionally limited to the Smart MUD runtime.  It does not
import or initialize campaign, story, scene, image, workflow, or ComfyUI systems.
"""
from __future__ import annotations

from pathlib import Path
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
from app.runtime_config_mud import MudRuntimeConfigStore
from engine.mud_runtime import MudRuntime
from engine.plugin_system import PluginRegistry
from smart_mud.world_registry import WorldRegistry, WorldRegistryError, WorldValidationError


class WebRuntime:
    """Owns the single Smart MUD runtime used by the web shell."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        print("[startup] Loading configuration...")
        self.paths = initialize_user_data_paths()
        self.config_store = MudRuntimeConfigStore(self.paths.config / "mud_config.json")
        self.config = self.config_store.load()
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

    def list_worlds(self) -> list[dict[str, Any]]:
        return self.available_worlds

    def select_world(self, world_id: str) -> dict[str, Any]:
        world = self.world_registry.load_world(world_id)
        self.active_world_id = world.id
        self.mud_runtime.load_world(world.id)
        return {"ok": True, "world": world.manifest}

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
            name=str(payload.get("name") or payload.get("player_name") or "Player"),
            race_id=str(payload.get("race_id") or payload.get("race") or ""),
            class_id=str(payload.get("class_id") or payload.get("class") or payload.get("char_class") or ""),
        )
        self.active_character_id = character["character_id"]
        return {"ok": True, "character": character}

    def enter_world(self, character_id: str = "") -> dict[str, Any]:
        cid = character_id or self.active_character_id
        if not cid:
            created = self.create_character({"name": "Player"})
            cid = created["character"]["character_id"]
        self.active_character_id = cid
        return self.mud_runtime.enter_world(cid)

    def play_view(self) -> dict[str, Any]:
        return self.mud_runtime.play_view(self.active_character_id)

    def handle_input(self, command: str) -> dict[str, Any]:
        if not self.active_character_id:
            self.enter_world()
        return self.mud_runtime.handle_input(self.active_character_id, command)


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
        return runtime.handle_input(str(payload.get("command") or payload.get("text") or ""))

    if static_root.exists():
        app.mount("/static", StaticFiles(directory=str(static_root)), name="static")

    @app.get("/")
    def index() -> Any:
        index_path = static_root / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"runtime": "smart_mud", "message": "Smart MUD Ready"}

    return app
