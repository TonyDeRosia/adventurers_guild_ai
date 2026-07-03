from __future__ import annotations

import sys
from pathlib import Path

from app.web import WebRuntime


def test_normal_startup_initializes_only_smart_mud(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    for name in list(sys.modules):
        if name.startswith(("images", "memory.campaign_memory", "engine.campaign_engine", "engine.scene_simulation")):
            del sys.modules[name]

    runtime = WebRuntime(Path.cwd())
    health = runtime.health()

    assert health["runtime"] == "smart_mud"
    assert health["sqlite_ready"] is True
    assert health["world_registry_ready"] is True
    assert health["campaign_runtime_started"] is False
    assert health["comfyui_initialized"] is False
    assert health["campaign_memory_loaded"] is False
    assert health["legacy_play_view_used"] is False
    assert "engine.campaign_engine" not in sys.modules
    assert "memory.campaign_memory" not in sys.modules
    assert not any(name.startswith("images.comfyui_adapter") for name in sys.modules)


def test_smart_mud_world_character_and_command_flow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    world_id = runtime.list_worlds()[0]["id"]
    runtime.select_world(world_id)
    created = runtime.create_character({"name": "Aria", "race_id": "human", "class_id": "mage"})
    entered = runtime.enter_world(created["character"]["character_id"])
    assert entered["ok"] is True
    assert created["character"]["health"]["current"] == 100
    result = runtime.handle_input("score")
    assert result["ok"] is True
    assert "Aria" in result["output"]
