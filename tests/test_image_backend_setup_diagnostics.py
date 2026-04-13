from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.web import WebRuntime


def _runtime(tmp_path: Path, monkeypatch) -> WebRuntime:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    return WebRuntime(Path.cwd())


def test_image_backend_diagnostics_reports_missing_comfyui_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.comfyui_path = str(tmp_path / "missing_comfyui")
    runtime.app_config.image.comfyui_workflow_path = ""
    runtime.app_config.image.checkpoint_folder = ""

    payload = runtime.get_image_backend_diagnostics()

    assert payload["ok"] is True
    diagnostics = payload["diagnostics"]
    assert diagnostics["comfyui_detected"] is False
    assert diagnostics["overall_state"] in {"Not Configured", "Partially Configured"}
    assert diagnostics["recommended_next_action"]


def test_image_backend_diagnostics_reports_running_when_api_reachable(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "comfyui_root": {"configured": True, "valid": True, "path": "C:/ComfyUI"},
                "workflow_path": {"configured": True, "valid": True, "path": "C:/ComfyUI/workflows/scene_image.json", "resolved_path": "C:/ComfyUI/workflows/scene_image.json"},
                "checkpoint_dir": {"configured": True, "valid": True, "path": "C:/ComfyUI/models/checkpoints"},
                "output_dir": {"configured": True, "valid": True, "path": "C:/ComfyUI/output"},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(
        runtime,
        "get_image_status",
        lambda: {
            "provider": "comfyui",
            "reachable": True,
            "ready": True,
            "status_code": "reachable",
            "user_message": "ComfyUI is reachable.",
            "next_action": "No action needed.",
        },
    )

    payload = runtime.get_image_backend_diagnostics()

    diagnostics = payload["diagnostics"]
    assert diagnostics["api_reachable"] is True
    assert diagnostics["overall_state"] == "Running"


def test_start_image_engine_returns_already_running_without_spawning_duplicate(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "workflow_path": {"valid": True, "configured": True},
                "comfyui_root": {"valid": True, "configured": True},
                "checkpoint_dir": {"valid": True, "configured": True},
                "output_dir": {"valid": True, "configured": True},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": True})
    monkeypatch.setattr(runtime.comfy_manager, "register", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not spawn")))

    result = runtime.start_image_engine()

    assert result["ok"] is True
    assert "already running" in result["message"].lower()


def test_start_image_engine_reports_missing_workflow_cleanly(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "workflow_path": {"valid": False, "configured": True},
                "comfyui_root": {"valid": True, "configured": True},
                "checkpoint_dir": {"valid": True, "configured": True},
                "output_dir": {"valid": True, "configured": True},
                "pipeline_ready": False,
            }
        },
    )

    result = runtime.start_image_engine()

    assert result["ok"] is False
    assert "workflow" in result["message"].lower()


def test_image_engine_service_status_reports_not_installed_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.comfyui_path = str(tmp_path / "missing")
    runtime.app_config.image.comfyui_workflow_path = ""
    runtime.app_config.image.checkpoint_folder = ""

    payload = runtime.get_image_engine_service_status()

    assert payload["ok"] is True
    assert payload["state"] == "not_installed"
    assert payload["api_url"].startswith("http://")


def test_install_image_engine_does_not_force_browser_launch(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    target_dir = tmp_path / "managed" / "ComfyUI"
    monkeypatch.setattr(runtime, "_default_comfyui_path", lambda: target_dir)
    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: None)
    monkeypatch.setattr(runtime, "_download_and_extract_comfyui", lambda _target: (True, "ok"))
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "valid": True, "missing_files": []})
    monkeypatch.setattr(runtime, "open_external_url", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not open browser")))

    result = runtime.install_image_engine()

    assert result["ok"] is True


def test_managed_mode_resolves_to_app_managed_paths(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.comfyui_path = ""
    status = runtime.get_path_configuration_status()["image"]
    resolved = status["resolved_paths"]
    assert status["mode"] == "managed"
    assert resolved["external_comfyui_root"] == ""
    assert str(tmp_path / "user_data") in resolved["managed_comfyui_root"]


def test_external_mode_uses_selected_external_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "external" / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models").mkdir(exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    runtime.app_config.image.comfyui_path = str(comfy_root)
    status = runtime.get_path_configuration_status()["image"]
    assert status["mode"] == "external"
    assert status["comfyui_root"]["path"] == str(comfy_root)


def test_managed_install_keeps_mode_managed(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)

    def _fake_download(target_dir: Path) -> tuple[bool, str]:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "main.py").write_text("print('ok')", encoding="utf-8")
        (target_dir / "custom_nodes").mkdir(exist_ok=True)
        (target_dir / "models").mkdir(exist_ok=True)
        return True, "ok"

    monkeypatch.setattr(runtime, "_download_and_extract_comfyui", _fake_download)
    assert runtime.install_image_engine()["ok"] is True
    status = runtime.get_path_configuration_status()["image"]
    assert status["mode"] == "managed"
    assert runtime.app_config.image.comfyui_path == ""


def test_windows_py_launcher_command_adds_python3_flag(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))
    monkeypatch.setattr("shutil.which", lambda _name: "py")
    command, launcher = runtime._build_comfy_launch_command(comfy_root, "127.0.0.1", 8188)
    assert launcher == "py_launcher"
    assert command[:3] == ["py", "-3", "main.py"]


def test_diagnostics_resolved_path_matches_launch_path_source_of_truth(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.comfyui_path = ""
    runtime.app_config.image.managed_install_path = str(tmp_path / "managed" / "ComfyUI")
    managed = Path(runtime.app_config.image.managed_install_path)
    managed.mkdir(parents=True, exist_ok=True)
    (managed / "main.py").write_text("print('ok')", encoding="utf-8")
    (managed / "custom_nodes").mkdir(exist_ok=True)
    (managed / "models").mkdir(exist_ok=True)
    (managed / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    payload = runtime.get_image_backend_diagnostics()
    diagnostics = payload["diagnostics"]
    assert diagnostics["image_backend_mode"] == "managed"
    assert diagnostics["comfyui_path"] == str(managed)
    assert diagnostics["resolved_paths"]["comfyui_root"] == str(managed)
