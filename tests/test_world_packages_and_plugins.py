from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.plugin_system import HookRegistry, PluginRegistry
from smart_mud.world_registry import WorldRegistry, WorldValidationError


def test_world_registry_discovers_validates_and_loads_installed_worlds() -> None:
    registry = WorldRegistry(Path.cwd() / "worlds")
    worlds = registry.list_worlds()
    assert any(world["id"] == "shattered_realms" for world in worlds)
    registry.validate_world("shattered_realms")
    package = registry.load_world("shattered_realms")
    assert package.id == "shattered_realms"
    assert package.default_starting_room["id"] == package.default_starting_room_id


def test_invalid_world_reports_descriptive_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad_world"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({"world_id": "bad_world"}), encoding="utf-8")
    registry = WorldRegistry(tmp_path)
    with pytest.raises(WorldValidationError) as exc:
        registry.validate_world("bad_world")
    message = str(exc.value)
    assert "Missing required runtime folder" in message
    assert "Manifest missing required field" in message


def test_plugins_discover_resolve_and_hooks_dispatch(tmp_path: Path) -> None:
    plug = tmp_path / "Weather"
    plug.mkdir()
    (plug / "manifest.json").write_text(json.dumps({
        "id": "Weather", "name": "Weather", "version": "1.0.0",
        "registers": {"runtime_hooks": ["room_enter"], "commands": ["weather"]},
    }), encoding="utf-8")
    registry = PluginRegistry(tmp_path)
    registry.discover()
    assert registry.resolve_required(["Weather"])[0].manifest.id == "Weather"
    assert ("Weather", "weather") in registry.registrations["commands"]

    hooks = HookRegistry()
    seen = []
    hooks.register("room_enter", lambda **payload: seen.append(payload["room_id"]))
    hooks.emit("room_enter", room_id="r1")
    assert seen == ["r1"]


def test_builder_workspace_is_auto_created_and_not_fatal(tmp_path: Path) -> None:
    import shutil
    source = Path.cwd() / "worlds" / "shattered_realms"
    target = tmp_path / "shattered_realms"
    shutil.copytree(source, target)
    shutil.rmtree(target / "builder", ignore_errors=True)

    registry = WorldRegistry(tmp_path)
    registry.validate_world("shattered_realms")

    for dirname in ("audit", "history", "snapshots", "imports", "exports", "templates"):
        assert (target / "builder" / dirname).is_dir()


def test_missing_runtime_gameplay_folder_still_fails(tmp_path: Path) -> None:
    import shutil
    source = Path.cwd() / "worlds" / "shattered_realms"
    target = tmp_path / "shattered_realms"
    shutil.copytree(source, target)
    shutil.rmtree(target / "rooms")

    registry = WorldRegistry(tmp_path)
    with pytest.raises(WorldValidationError) as exc:
        registry.validate_world("shattered_realms")
    assert "Missing required runtime folder: rooms/" in str(exc.value)


def test_engine_world_registry_is_compatibility_reexport() -> None:
    import engine.world_registry as engine_registry
    import smart_mud.world_registry as canonical_registry

    assert engine_registry.WorldRegistry is canonical_registry.WorldRegistry
    assert engine_registry.REQUIRED_WORLD_DIRS == canonical_registry.REQUIRED_RUNTIME_DIRS
    assert "builder" not in canonical_registry.REQUIRED_RUNTIME_DIRS
