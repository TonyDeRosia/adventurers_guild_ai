from __future__ import annotations

import json
from pathlib import Path

from app.web import WebRuntime


def _runtime(tmp_path: Path, monkeypatch) -> WebRuntime:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    return WebRuntime(Path.cwd())


def test_campaign_management_create_save_switch_rename_delete(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    created = runtime.create_campaign({"player_name": "Mira", "char_class": "Mage", "slot": "slot_mira"})
    assert created["slot"] == "slot_mira"

    runtime.handle_player_input("look")
    runtime.save_active_campaign("slot_mira")
    runtime.create_campaign({"player_name": "Aric", "char_class": "Rogue", "slot": "slot_aric"})
    runtime.save_active_campaign("slot_aric")

    switched = runtime.switch_campaign("slot_mira")
    assert switched["state"]["player"]["name"] == "Mira"
    assert any("look" in msg["text"].lower() for msg in runtime.session.message_history)

    renamed = runtime.rename_campaign("slot_mira", "Mira Renamed")
    assert renamed["campaign_name"] == "Mira Renamed"

    deleted = runtime.delete_campaign("slot_aric")
    assert deleted["deleted"] == "slot_aric"


def test_settings_persistence_and_runtime_effects(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    runtime.set_global_settings(
        {
            "model": {"provider": "null", "model_name": "llama3.2"},
            "image": {"provider": "null", "enabled": False},
        }
    )
    runtime.set_campaign_settings(
        {
            "narration_tone": "grim",
            "mature_content_enabled": True,
            "image_generation_enabled": False,
            "content_settings": {"tone": "noir", "maturity_level": "mature", "thematic_flags": ["horror"]},
        }
    )

    config_path = runtime.paths.config / "app_config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["model"]["model_name"] == "llama3.2"
    assert payload["image"]["enabled"] is False
    assert runtime.session.state.settings.content_settings.tone == "noir"


def test_turn_flow_persists_memory_and_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    out = runtime.handle_player_input("summarize")
    assert out["messages"]
    assert runtime.session.state.conversation_turns
    assert runtime.session.state.recent_memory

    runtime.save_active_campaign("slot_memory")
    runtime.switch_campaign("slot_memory")
    assert runtime.session.state.conversation_turns[-1].player_input == "summarize"


def test_image_fallback_from_comfyui_to_local_placeholder(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"image_generation_enabled": True})
    runtime.set_global_settings({"image": {"provider": "comfyui", "base_url": "http://127.0.0.1:9", "enabled": True}})

    result = runtime.generate_image({"workflow_id": "scene_image", "prompt": "Moonlit ruins"})
    assert result.success is True
    assert result.metadata.get("fallback_adapter") == "local_placeholder"
    assert result.result_path and result.result_path.endswith(".svg")
