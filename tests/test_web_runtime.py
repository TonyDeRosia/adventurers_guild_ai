from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

import pytest

from app.web import WebRuntime, create_web_app
from images.base import ImageGenerationResult
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


def test_create_campaign_persists_world_metadata(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "player_name": "Aria",
            "char_class": "Ranger",
            "slot": "slot_world",
            "campaign_name": "Aria in the Ashen Realm",
            "world_name": "Vel Astren",
            "world_theme": "dark fantasy",
            "starting_location_name": "Black Harbor",
            "campaign_tone": "grim heroic",
            "premise": "the old gods vanished and the sea is haunted",
            "player_concept": "exiled ranger searching for her brother",
        }
    )
    assert created["state"]["campaign_name"] == "Aria in the Ashen Realm"
    assert created["state"]["world_meta"]["world_name"] == "Vel Astren"
    assert created["state"]["world_meta"]["starting_location_name"] == "Black Harbor"

    runtime.switch_campaign("slot_world")
    assert runtime.session.state.world_meta.world_theme == "dark fantasy"
    assert runtime.session.state.locations[runtime.session.state.current_location_id].name == "Black Harbor"


def test_new_campaign_uses_preferred_visual_and_suggested_move_defaults(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"player_name": "DefaultCheck", "slot": "slot_defaults"})

    assert created["state"]["settings"]["campaign_auto_visuals_enabled"] is True
    assert created["state"]["settings"]["suggested_moves_enabled"] is False
    assert created["state"]["settings"]["effective_suggested_moves_enabled"] is False

    global_settings = runtime.get_global_settings()
    assert global_settings["image"]["manual_image_generation_enabled"] is True
    assert global_settings["image"]["campaign_auto_visual_timing"] == "after_narration"


def test_existing_campaign_settings_are_preserved_on_load(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "KeepMe", "slot": "slot_keep"})
    runtime.set_campaign_settings(
        {
            "campaign_auto_visuals_enabled": False,
            "suggested_moves_enabled": True,
            "player_suggested_moves_override": True,
        }
    )
    runtime.save_active_campaign("slot_keep")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_keep")
    settings = reloaded.serialize_state()["settings"]
    assert settings["campaign_auto_visuals_enabled"] is False
    assert settings["suggested_moves_enabled"] is True
    assert settings["effective_suggested_moves_enabled"] is True


def test_custom_campaign_starts_without_sample_npcs_or_quests(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "mode": "custom",
            "player_name": "Nova",
            "char_class": "Mage",
            "slot": "slot_clean",
            "world_name": "Starreach",
            "starting_location_name": "Glass Docks",
        }
    )
    assert created["state"]["world_meta"]["world_name"] == "Starreach"
    assert runtime.session.state.npcs == {}
    assert runtime.session.state.quests == {}


def test_premade_campaign_mode_explicitly_loads_sample(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"mode": "premade", "slot": "slot_premade"})
    assert created["state"]["world_meta"]["world_name"] == "Moonfall"
    assert "elder_thorne" in runtime.session.state.npcs


def test_campaign_rename_and_delete_require_selection(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    try:
        runtime.rename_campaign("", "Nope")
        assert False, "Expected ValueError for empty rename slot"
    except ValueError as exc:
        assert "No save selected" in str(exc)

    try:
        runtime.delete_campaign(" ")
        assert False, "Expected ValueError for empty delete slot"
    except ValueError as exc:
        assert "No save selected" in str(exc)


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
            "suggested_moves_enabled": False,
            "player_suggested_moves_override": False,
            "content_settings": {"tone": "noir", "maturity_level": "mature", "thematic_flags": ["horror"]},
        }
    )

    config_path = runtime.paths.config / "app_config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["model"]["model_name"] == "llama3.2"
    assert payload["image"]["enabled"] is False
    assert runtime.session.state.settings.content_settings.tone == "noir"
    assert runtime.session.state.settings.suggested_moves_active() is False


def test_turn_flow_persists_memory_and_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    out = runtime.handle_player_input("summarize")
    assert out["messages"]
    assert runtime.session.state.conversation_turns
    assert runtime.session.state.recent_memory

    runtime.save_active_campaign("slot_memory")
    runtime.switch_campaign("slot_memory")
    assert runtime.session.state.conversation_turns[-1].player_input == "summarize"


def test_history_and_scene_visual_are_campaign_namespaced(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "Mira", "slot": "slot_iso"})
    runtime.handle_player_input("look")
    runtime._set_scene_visual(
        slot="slot_iso",
        image_url="/generated/a.png",
        prompt="scene a",
        source="test",
        stage="after_narration",
        turn=1,
    )
    first_key = runtime._campaign_namespace("slot_iso")
    assert first_key in runtime.history_store
    assert first_key in runtime.scene_visual_store

    runtime.create_campaign({"player_name": "Aric", "slot": "slot_iso"})
    runtime.handle_player_input("status")
    second_key = runtime._campaign_namespace("slot_iso")
    assert second_key in runtime.history_store
    assert second_key != first_key


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


class _SuggestedMoveProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Fog hugs the road as distant bells ring. Suggested next move: question the nearest guard."


class _AdvisoryPhraseProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Rain glitters on the cobblestones. You could follow the footprints into the alley."


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


def test_recommendations_only_show_when_player_explicitly_requests_guidance(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _SuggestedMoveProvider()

    runtime.set_campaign_settings({"player_suggested_moves_override": True})
    normal_turn = runtime.handle_player_input("look")
    assert "Suggested next move:" not in normal_turn["narrative"]

    guidance_turn = runtime.handle_player_input("what should I do next?")
    assert "Suggested next move:" in guidance_turn["narrative"]


def test_recommendations_are_hard_removed_when_campaign_setting_is_disabled(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _SuggestedMoveProvider()
    runtime.set_campaign_settings({"player_suggested_moves_override": False})

    guidance_turn = runtime.handle_player_input("what should I do next?")
    assert "Suggested next move:" not in guidance_turn["narrative"]
    assert guidance_turn["metadata"]["recommendation_cleanup_applied"] is True


def test_recommendation_cleanup_removes_generic_advisory_phrasing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _AdvisoryPhraseProvider()
    runtime.set_campaign_settings({"player_suggested_moves_override": False})

    out = runtime.handle_player_input("look")
    assert "You could" not in out["narrative"]
    assert out["metadata"]["recommendation_cleanup_applied"] is True


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


def test_image_generation_requires_comfyui_readiness(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"image_generation_enabled": True})
    runtime.set_global_settings({"image": {"provider": "comfyui", "base_url": "http://127.0.0.1:9", "enabled": True}})

    result = runtime.generate_image({"workflow_id": "scene_image", "prompt": "Moonlit ruins"})
    assert result.success is False
    assert "comfyui" in (result.error or "").lower()
    assert result.metadata.get("provider") == "comfyui"


def test_auto_after_visual_updates_scene_panel_without_image_chat_message(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui", "campaign_auto_visual_timing": "after_narration"}})
    runtime.set_campaign_settings({"image_generation_enabled": True, "campaign_auto_visuals_enabled": True})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    output_file = runtime.generated_image_dir / "turn_visual.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake")
    monkeypatch.setattr(
        runtime,
        "generate_image",
        lambda payload: ImageGenerationResult(
            success=True,
            workflow_id="scene_image",
            result_path=str(output_file),
            metadata={"image": {"filename": "turn_visual.png", "type": "output"}},
        ),
    )

    runtime._run_turn_visual_generation(
        player_action="inspect the rune",
        narrator_response="Blue sparks arc across the old stone and illuminate hidden glyphs.",
        stage="after_narration",
    )

    assert not any(message.get("type") == "image" for message in runtime.session.message_history)
    scene_visual = runtime._scene_visual_for_slot()
    assert scene_visual is not None
    assert scene_visual["image_url"].endswith("/generated/turn_visual.png")
    assert scene_visual["source"] == "automatic"


def test_campaign_auto_visual_timing_aliases_normalize_to_supported_values(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    settings = runtime.set_global_settings({"image": {"campaign_auto_visual_timing": "auto_after"}})
    assert settings["image"]["campaign_auto_visual_timing"] == "after_narration"


def test_auto_after_turn_visual_only_queues_for_meaningful_narration(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    queued: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        runtime,
        "_run_turn_visual_generation_async",
        lambda player_action, narrator_response, stage, source: queued.append((player_action, narrator_response, stage, source)) or True,
    )

    not_queued = runtime._maybe_queue_auto_turn_visual(
        auto_enabled=True,
        auto_timing="after_narration",
        player_action="look around",
        narrator_response="...",
        stage="after_narration",
    )
    assert not_queued is False
    assert queued == []

    queued_ok = runtime._maybe_queue_auto_turn_visual(
        auto_enabled=True,
        auto_timing="after_narration",
        player_action="look around",
        narrator_response="The torchlight reveals wet stone arches and a narrow bridge over dark water.",
        stage="after_narration",
    )
    assert queued_ok is True
    assert len(queued) == 1


def test_auto_turn_visual_async_dedupes_same_slot_turn_and_stage(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui", "campaign_auto_visual_timing": "after_narration"}})
    runtime.set_campaign_settings({"image_generation_enabled": True, "campaign_auto_visuals_enabled": True})
    monkeypatch.setattr(runtime, "_run_turn_visual_generation", lambda *args, **kwargs: time.sleep(0.1))

    first = runtime._run_turn_visual_generation_async("inspect", "A vivid chamber blooms with blue witchlight.", "after_narration", "auto_after")
    second = runtime._run_turn_visual_generation_async("inspect", "A vivid chamber blooms with blue witchlight.", "after_narration", "auto_after")

    assert first is True
    assert second is False


def test_dependency_readiness_ollama_offline(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    runtime.app_config.model.model_name = "llama3"
    monkeypatch.setattr("shutil.which", lambda name: "C:/Ollama/ollama.exe")
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
    readiness = runtime.get_dependency_readiness()
    model_provider = readiness["items"][0]
    assert model_provider["provider_type"] == "model_provider"
    assert model_provider["reachable"] is False
    assert "ollama serve" in model_provider["next_action"]


def test_dependency_readiness_ollama_online_model_missing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    runtime.app_config.model.model_name = "llama3"
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": True,
            "model_exists": False,
            "ready": False,
            "user_message": "Model llama3 is not installed in Ollama. Run: ollama pull llama3",
            "fallback_reason": "missing model",
        },
    )
    readiness = runtime.get_dependency_readiness()
    model_item = readiness["items"][1]
    assert model_item["provider_type"] == "selected_model"
    assert model_item["model_exists"] is False
    assert "ollama pull llama3" in model_item["next_action"]


def test_dependency_readiness_ollama_online_model_present(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": True,
            "model_exists": True,
            "ready": True,
            "user_message": "Ollama is ready with model llama3.",
            "fallback_reason": "",
        },
    )
    readiness = runtime.get_dependency_readiness()
    assert readiness["items"][0]["status_level"] == "ready"
    assert readiness["items"][1]["status_level"] == "ready"


def test_dependency_readiness_comfyui_offline(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: Path("/fake/ComfyUI"))
    monkeypatch.setattr(
        "images.comfyui_adapter.ComfyUIAdapter.check_readiness",
        lambda self: {
            "provider": "comfyui",
            "base_url": self.base_url,
            "reachable": False,
            "ready": False,
            "status_level": "error",
            "user_message": "ComfyUI is not reachable at the configured address.",
            "next_action": "Start ComfyUI, then click Recheck.",
            "error": "connection refused",
        },
    )
    readiness = runtime.get_dependency_readiness()
    image_item = readiness["items"][2]
    assert image_item["provider_type"] == "image_provider"
    assert image_item["reachable"] is False
    assert image_item["status_code"] == "not_running"
    assert image_item["actions"][0]["id"] == "start_image_engine"


def test_dependency_readiness_does_not_pollute_story_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    _ = runtime.get_dependency_readiness()
    messages_before = len(runtime.session.message_history)
    runtime.handle_player_input("look")
    messages_after = [message["text"] for message in runtime.session.message_history]
    assert len(messages_after) > messages_before


def test_start_ollama_logs_setup_action(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr("shutil.which", lambda _: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(
        runtime,
        "get_model_status",
        lambda: {"provider": "ollama", "reachable": True, "model_exists": True, "ready": True},
    )

    result = runtime.start_ollama_service()
    captured = capsys.readouterr()
    assert result["ok"] is True
    assert "[setup-action] start-ollama requested" in captured.out
    assert "[setup-action] start-ollama success" in captured.out


def test_install_model_logs_setup_action(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda _: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout="already exists", stderr=""),
    )

    result = runtime.install_story_model("llama3")
    captured = capsys.readouterr()
    assert result["ok"] is True
    assert "[setup-action] install-model requested model=llama3" in captured.out
    assert "[setup-action] install-model success model=llama3" in captured.out
    assert result["message"] == "Story model installed. Text generation is ready."


def test_setup_endpoints_invoke_backend_actions(tmp_path: Path, monkeypatch, capsys) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)

    monkeypatch.setattr(runtime, "start_ollama_service", lambda: {"ok": True, "message": "started"})
    monkeypatch.setattr(runtime, "install_ollama", lambda: {"ok": True, "message": "installed ollama"})
    monkeypatch.setattr(runtime, "install_story_model", lambda model_name=None: {"ok": True, "message": f"installed {model_name}"})
    monkeypatch.setattr(runtime, "install_image_engine", lambda: {"ok": True, "message": "installed comfyui"})
    monkeypatch.setattr(runtime, "start_image_engine", lambda: {"ok": True, "message": "started comfyui"})
    monkeypatch.setattr(runtime, "orchestrate_setup_text_ai", lambda model_name=None: {"ok": True, "message": f"orchestrated text {model_name}"})
    monkeypatch.setattr(runtime, "orchestrate_setup_image_ai", lambda: {"ok": True, "message": "orchestrated image"})
    monkeypatch.setattr(runtime, "orchestrate_setup_everything", lambda model_name=None: {"ok": True, "message": f"orchestrated all {model_name}"})

    start_response = client.post("/api/setup/start-ollama", json={})
    install_ollama_response = client.post("/api/setup/install-ollama", json={})
    install_response = client.post("/api/setup/install-model", json={"model": "llama3"})
    install_image_response = client.post("/api/setup/install-image-engine", json={})
    start_image_response = client.post("/api/setup/start-image-engine", json={})
    orchestrate_text_response = client.post("/api/setup/orchestrate-text", json={"model": "llama3"})
    orchestrate_image_response = client.post("/api/setup/orchestrate-image", json={})
    orchestrate_everything_response = client.post("/api/setup/orchestrate-everything", json={"model": "llama3"})
    captured = capsys.readouterr()

    assert start_response.status_code == 200
    assert install_ollama_response.status_code == 200
    assert install_response.status_code == 200
    assert start_response.json()["ok"] is True
    assert install_ollama_response.json()["ok"] is True
    assert install_response.json()["ok"] is True
    assert install_image_response.json()["ok"] is True
    assert start_image_response.json()["ok"] is True
    assert orchestrate_text_response.json()["ok"] is True
    assert orchestrate_image_response.json()["ok"] is True
    assert orchestrate_everything_response.json()["ok"] is True
    assert "[setup-action] route invoked endpoint=/api/setup/start-ollama" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-ollama" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-model model=llama3" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-image-engine" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/start-image-engine" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/orchestrate-text model=llama3" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/orchestrate-image" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/orchestrate-everything model=llama3" in captured.out


def test_dependency_readiness_comfyui_not_installed(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: None)
    monkeypatch.setattr(
        "images.comfyui_adapter.ComfyUIAdapter.check_readiness",
        lambda self: {"provider": "comfyui", "base_url": self.base_url, "reachable": False, "ready": False, "status_level": "error", "user_message": "offline", "next_action": "n/a", "error": "connection refused"},
    )
    readiness = runtime.get_dependency_readiness()
    image_item = readiness["items"][2]
    assert image_item["status_code"] == "not_installed"
    assert image_item["actions"][0]["id"] == "install_image_engine"


def test_validate_comfyui_install_reports_missing_launcher(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_dir = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)

    validation = runtime.validate_comfyui_install(comfy_dir)
    assert validation["ok"] is False
    assert "run_cpu.bat|run_nvidia_gpu.bat" in validation["missing_files"]


def test_install_image_engine_repairs_missing_launcher(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.setattr("webbrowser.open", lambda *_args, **_kwargs: True)

    def _fake_download(target_dir: Path) -> tuple[bool, str]:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "main.py").write_text("print('ok')", encoding="utf-8")
        (target_dir / "custom_nodes").mkdir(exist_ok=True)
        (target_dir / "models").mkdir(exist_ok=True)
        return True, "ok"

    monkeypatch.setattr(runtime, "_download_and_extract_comfyui", _fake_download)
    result = runtime.install_image_engine()
    assert result["ok"] is True
    comfy_dir = Path(runtime.app_config.image.comfyui_path)
    assert (comfy_dir / "run_cpu.bat").exists()


def test_start_image_engine_repairs_launcher_before_failing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    runtime.app_config.image.comfyui_path = str(comfy_dir)

    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: comfy_dir)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False})
    monkeypatch.setattr("shutil.which", lambda _name: "python")

    launch_calls = {"count": 0}

    def _fake_popen(*_args, **_kwargs):
        launch_calls["count"] += 1
        raise OSError("simulated launch failure")

    monkeypatch.setattr("subprocess.Popen", _fake_popen)
    result = runtime.start_image_engine()
    assert (comfy_dir / "run_cpu.bat").exists()
    assert launch_calls["count"] == 1
    assert result["ok"] is False
    assert result["failure_stage"] == "launch-engine"


def test_start_image_engine_detects_early_exit_and_exposes_startup_log(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "run_cpu.bat").write_text("@echo off\r\npython main.py\r\n", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)

    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: comfy_dir)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False})
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    class _Proc:
        stdout = True

        def poll(self):
            return 1

        def communicate(self, timeout=0.0):
            return ("Traceback (most recent call last):\nModuleNotFoundError: x\n", "")

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: _Proc())
    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert result["failure_stage_message"] == "ComfyUI exited during startup"
    assert result["startup_status"]["reason"] == "process-exited-immediately"
    assert "modulenotfounderror" in result["startup_status"]["runtime_error_hint"]


def test_dependency_readiness_includes_image_startup_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.image_startup_status = {"reason": "runtime-error-in-launcher-output", "summary": "runtime error", "log_text": "error line"}
    readiness = runtime.get_dependency_readiness()
    image_item = readiness["items"][2]
    assert image_item["startup_status"]["reason"] == "runtime-error-in-launcher-output"
    assert "runtime error" in image_item["startup_status"]["summary"]


def test_dependency_readiness_reports_missing_ollama_install(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running.",
            "fallback_reason": "offline",
            "error": "connection refused",
        },
    )
    readiness = runtime.get_dependency_readiness()
    provider_item = readiness["items"][0]
    assert "not installed" in provider_item["user_message"].lower()
    assert provider_item["actions"][0]["id"] == "install_ollama"


def test_start_ollama_reports_missing_cli(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr("shutil.which", lambda name: None)
    result = runtime.start_ollama_service()
    assert result["ok"] is False
    assert "not installed" in result["message"].lower()


def test_install_story_model_runs_pull_and_returns_success(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: "/bin/ollama")

    monkeypatch.setattr(runtime, "get_model_status", lambda: {"reachable": True})

    def _fake_run(*args, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        return subprocess.CompletedProcess(args=["ollama", "pull", "llama3"], returncode=0, stdout="pulled", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)
    result = runtime.install_story_model("llama3")
    assert result["ok"] is True
    assert "installed" in result["message"].lower()


def test_orchestrate_text_ai_from_missing_model_to_ready(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    states = iter(
        [
            {"reachable": False, "model_exists": False},
            {"reachable": True, "model_exists": False},
            {"reachable": True, "model_exists": True},
        ]
    )
    monkeypatch.setattr(runtime, "get_model_status", lambda: next(states))
    monkeypatch.setattr(runtime, "_find_ollama_cli", lambda: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(runtime, "start_ollama_service", lambda: {"ok": True, "message": "started"})
    monkeypatch.setattr(runtime, "install_story_model", lambda model_name=None: {"ok": True, "message": "installed model"})
    monkeypatch.setattr(runtime, "_refresh_readiness_snapshot", lambda: {"items": []})
    result = runtime.orchestrate_setup_text_ai("llama3")
    assert result["ok"] is True
    assert result["summary"] == "Text AI ready."


def test_orchestrate_everything_combines_text_and_image_results(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "orchestrate_setup_text_ai", lambda model_name=None: {"ok": True, "message": "text ok"})
    monkeypatch.setattr(runtime, "orchestrate_setup_image_ai", lambda: {"ok": True, "message": "image ok"})
    monkeypatch.setattr(runtime, "_refresh_readiness_snapshot", lambda: {"items": []})
    result = runtime.orchestrate_setup_everything("llama3")
    assert result["ok"] is True
    assert "Text AI ready. Image AI ready." in result["summary"]


def test_install_story_model_requires_running_ollama(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: "/bin/ollama")
    monkeypatch.setattr(runtime, "get_model_status", lambda: {"reachable": False})
    result = runtime.install_story_model("llama3")
    assert result["ok"] is False
    assert "not running" in result["message"].lower()


def test_install_ollama_windows_flow_logs(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    states = iter([None, "C:/Ollama/ollama.exe"])
    monkeypatch.setattr(runtime, "_find_ollama_cli", lambda: next(states))
    monkeypatch.setattr(runtime, "_resolve_ollama_windows_installer_url", lambda: "https://ollama.com/download/OllamaSetup.exe")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"fake-exe"

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Resp())
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(wait=lambda timeout=None: 0))
    monkeypatch.setattr(runtime, "start_ollama_service", lambda: {"ok": True, "message": "started"})

    result = runtime.install_ollama()
    captured = capsys.readouterr()
    assert result["ok"] is True
    assert "[setup-action] install-ollama requested" in captured.out
    assert "[setup-action] downloading installer url=https://ollama.com/download/OllamaSetup.exe" in captured.out
    assert "[setup-action] installer launched" in captured.out
    assert "[setup-action] install-ollama success" in captured.out

def test_create_campaign_with_character_sheets_persists_and_restores(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    payload = {
        "player_name": "Kael",
        "char_class": "Summoner",
        "slot": "slot_sheets",
        "character_sheet_guidance_strength": "strong",
        "character_sheets": [
            {
                "id": "mc_1",
                "name": "Kael",
                "sheet_type": "main_character",
                "role": "leader",
                "archetype": "stormbound tactician",
                "level_or_rank": "5",
                "faction": "Guild",
                "description": "Carries a living rune blade.",
                "stats": {"health": 14, "energy_or_mana": 20, "attack": 11, "defense": 9, "speed": 10, "magic": 15, "willpower": 13, "presence": 12},
                "traits": ["curious", "focused"],
                "abilities": ["storm sigil", "binding chain"],
                "equipment": ["rune blade"],
                "weaknesses": ["pride"],
                "temperament": "measured",
                "loyalty": "guild",
                "social_style": "direct",
                "speech_style": "precise",
                "state": {"morale": 8, "bond_to_player": 10, "current_condition": "steady"},
            }
        ],
    }
    created = runtime.create_campaign(payload)
    assert created["state"]["character_sheet_guidance_strength"] == "strong"
    assert len(created["state"]["character_sheets"]) == 1
    assert created["state"]["character_sheets"][0]["sheet_type"] == "main_character"
    assert created["state"]["player"]["hp"] == 14
    assert created["state"]["player"]["max_hp"] == 14
    assert created["state"]["player"]["attack"] == 11
    assert created["state"]["player"]["defense"] == 9
    assert created["state"]["player"]["magic"] == 15
    assert created["state"]["player"]["class"] == "leader"

    runtime.switch_campaign("slot_sheets")
    assert runtime.session.state.character_sheet_guidance_strength == "strong"
    assert runtime.session.state.character_sheets[0].name == "Kael"
    assert runtime.session.state.player.hp == 14
    assert runtime.session.state.player.max_hp == 14


def test_create_campaign_without_character_sheets_keeps_defaults(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"player_name": "Aria", "char_class": "Ranger", "slot": "slot_default"})
    assert created["state"]["player"]["hp"] == 20
    assert created["state"]["player"]["max_hp"] == 20
    assert created["state"]["player"]["class"] == "Ranger"
