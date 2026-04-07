from __future__ import annotations

import json
from pathlib import Path

from app.web import WebRuntime
from models.base import NarrationModelAdapter, ProviderUnavailableError


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


def test_runtime_does_not_add_session_boilerplate_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    texts = [message["text"] for message in runtime.session.message_history]
    assert "Web session initialized. GUI mode is active." not in texts


class _FailingProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        raise ProviderUnavailableError("simulated connection failure")


class _ScaffoldLeakProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return """[Requested Mode]
play
[Conversation Context]
Recent chat turns: You: look || Narrator: none
[Memory Context]
Recent memory: none
[Scene Context]
Location: Moonfall
[Player State Summary]
HP: 20/20
The lantern-light flickers across the gate as unseen footsteps circle your flank."""


def test_turn_fallback_is_clean_when_provider_fails(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FailingProvider()
    out = runtime.handle_player_input("look")
    assert out["metadata"]["fallback_used"] is True
    assert out["metadata"]["fallback_reason"] == "simulated connection failure"
    assert "[Local template narrator]" not in out["narrative"]
    assert "[Requested Mode]" not in out["narrative"]


def test_turn_sanitizer_removes_prompt_scaffold_leaks(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _ScaffoldLeakProvider()
    out = runtime.handle_player_input("look")
    assert "Recent chat turns:" not in out["narrative"]
    assert "Recent memory:" not in out["narrative"]
    assert "[Requested Mode]" not in out["narrative"]
    assert "lantern-light flickers" in out["narrative"]


def test_settings_include_ollama_unavailable_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running. Start Ollama to use this model provider.",
            "fallback_reason": "offline",
        },
    )
    settings = runtime.set_global_settings({"model": {"provider": "ollama", "model_name": "llama3"}})
    assert settings["model_status"]["ready"] is False
    assert settings["model_status"]["user_message"] == "Ollama is not running. Start Ollama to use this model provider."


def test_turn_metadata_surfaces_model_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FailingProvider()
    runtime.app_config.model.provider = "ollama"
    runtime.app_config.model.model_name = "llama3"
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running. Start Ollama to use this model provider.",
            "fallback_reason": "offline",
        },
    )
    out = runtime.handle_player_input("look")
    assert out["metadata"]["model_status"]["ready"] is False
    assert out["metadata"]["model_status"]["provider"] == "ollama"


def test_image_fallback_from_comfyui_to_local_placeholder(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"image_generation_enabled": True})
    runtime.set_global_settings({"image": {"provider": "comfyui", "base_url": "http://127.0.0.1:9", "enabled": True}})

    result = runtime.generate_image({"workflow_id": "scene_image", "prompt": "Moonlit ruins"})
    assert result.success is True
    assert result.metadata.get("fallback_adapter") == "local_placeholder"
    assert result.result_path and result.result_path.endswith(".svg")
