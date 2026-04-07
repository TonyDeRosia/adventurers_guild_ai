from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from app.web import WebRuntime, create_web_app
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

    start_response = client.post("/api/setup/start-ollama", json={})
    install_ollama_response = client.post("/api/setup/install-ollama", json={})
    install_response = client.post("/api/setup/install-model", json={"model": "llama3"})
    install_image_response = client.post("/api/setup/install-image-engine", json={})
    start_image_response = client.post("/api/setup/start-image-engine", json={})
    captured = capsys.readouterr()

    assert start_response.status_code == 200
    assert install_ollama_response.status_code == 200
    assert install_response.status_code == 200
    assert start_response.json()["ok"] is True
    assert install_ollama_response.json()["ok"] is True
    assert install_response.json()["ok"] is True
    assert install_image_response.json()["ok"] is True
    assert start_image_response.json()["ok"] is True
    assert "[setup-action] route invoked endpoint=/api/setup/start-ollama" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-ollama" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-model model=llama3" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-image-engine" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/start-image-engine" in captured.out


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
        return subprocess.CompletedProcess(args=["ollama", "pull", "llama3"], returncode=0, stdout="pulled", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)
    result = runtime.install_story_model("llama3")
    assert result["ok"] is True
    assert "installed" in result["message"].lower()


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
