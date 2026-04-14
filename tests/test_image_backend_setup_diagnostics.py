from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import subprocess

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


def test_image_backend_diagnostics_includes_managed_runtime_details(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_root = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_root / folder).mkdir(exist_ok=True)
    (comfy_root / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    runtime.app_config.image.managed_install_path = str(comfy_root)

    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))
    payload = runtime.get_image_backend_diagnostics()
    diagnostics = payload["diagnostics"]
    assert diagnostics["managed_mode_active"] is True
    assert diagnostics["managed_comfyui_root"] == str(comfy_root)
    assert diagnostics["python_runtime_found"] is True
    assert "run_nvidia_gpu.bat" not in diagnostics["runtime_missing_items"]


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


def test_image_backend_diagnostics_exposes_launch_strategy_details(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.image_startup_status = {
        "launch_diagnostics": {
            "primary_launch_attempt": "nvidia_gpu",
            "fallback_launch_used": "cpu",
            "nvidia_failure_reason": "torch-cuda-disabled",
            "final_running_mode": "cpu",
        }
    }
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "mode": "managed",
                "comfyui_root": {"configured": False, "valid": False, "path": ""},
                "workflow_path": {"configured": False, "valid": False, "path": ""},
                "output_dir": {"configured": False, "valid": True, "path": ""},
                "checkpoint_dir": {"configured": False, "valid": False, "path": "", "model_ready": False},
                "resolved_paths": {},
            }
        },
    )
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False, "status_code": "setup_required", "user_message": "", "next_action": ""})
    payload = runtime.get_image_backend_diagnostics()
    diagnostics = payload["diagnostics"]
    assert diagnostics["primary_launch_attempt"] == "nvidia_gpu"
    assert diagnostics["fallback_launch_used"] == "cpu"
    assert diagnostics["nvidia_failure_reason"] == "torch-cuda-disabled"
    assert diagnostics["final_running_mode"] == "cpu"


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
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_dir / folder).mkdir(exist_ok=True)
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "workflow_path": {"valid": False, "configured": True},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True},
                "output_dir": {"valid": True, "configured": True},
                "pipeline_ready": False,
            }
        },
    )
    monkeypatch.setattr(
        runtime,
        "_bootstrap_comfy_python_dependencies",
        lambda *_args, **_kwargs: {"ok": True, "installed_packages": [], "python_executable": "python"},
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
    monkeypatch.setattr(runtime, "_install_embedded_python_runtime", lambda _target: (True, "venv runtime ready"))
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
    assert Path(resolved["managed_comfyui_root"]).name == "ComfyUI"
    assert Path(resolved["managed_comfyui_root"]).parent.name == "tools"


def test_external_mode_uses_selected_external_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "external" / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_root / folder).mkdir(exist_ok=True)
    runtime_exe = comfy_root / ".venv" / "Scripts" / "python.exe"
    runtime_exe.parent.mkdir(parents=True, exist_ok=True)
    runtime_exe.write_text("", encoding="utf-8")
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    runtime.app_config.image.comfyui_path = str(comfy_root)
    status = runtime.get_path_configuration_status()["image"]
    assert status["mode"] == "external"
    assert status["comfyui_root"]["path"] == str(comfy_root)


def test_external_mode_persists_selected_root_across_restart(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "external" / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_root / folder).mkdir(exist_ok=True)
    runtime_exe = comfy_root / ".venv" / "Scripts" / "python.exe"
    runtime_exe.parent.mkdir(parents=True, exist_ok=True)
    runtime_exe.write_text("", encoding="utf-8")
    connect = runtime.connect_comfyui_path(str(comfy_root))
    assert connect["ok"] is True

    restarted = _runtime(tmp_path, monkeypatch)
    status = restarted.get_path_configuration_status()["image"]
    assert status["mode"] == "external"
    assert status["resolved_paths"]["external_comfyui_root"] == str(comfy_root)
    assert status["comfyui_root"]["path"] == str(comfy_root)


def test_checkpoint_folder_is_rejected_as_comfyui_root(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    checkpoint_dir = tmp_path / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (checkpoint_dir / "dreamshaper.safetensors").write_text("", encoding="utf-8")

    result = runtime.connect_comfyui_path(str(checkpoint_dir))

    assert result["ok"] is False
    assert "checkpoint folder" in result["message"].lower()


def test_start_image_engine_reports_missing_root_with_precise_error(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.comfyui_path = str(tmp_path / "missing_external" / "ComfyUI")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    runtime.app_config.image.comfyui_workflow_path = str(workflow)

    result = runtime.start_image_engine()

    assert result["ok"] is False
    assert result["failure_stage"] == "detect-install-path"
    assert result["status_code"] == "configured_path_missing"
    assert "does not exist" in result["message"].lower()


def test_detect_install_path_passes_for_valid_root(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = runtime._coerce_managed_install_path()
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_root / folder).mkdir(exist_ok=True)
    (comfy_root / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    status = runtime._detect_install_path_status(
        {
            "mode": "managed",
            "resolved_paths": {"external_comfyui_root": ""},
            "comfyui_root": {"resolved_path": str(comfy_root), "path": str(comfy_root)},
        }
    )

    assert status["ok"] is True
    assert status["status_code"] == "valid_root"
    assert status["resolved_root"] == str(comfy_root)


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
    monkeypatch.setattr(runtime, "_install_embedded_python_runtime", lambda _target: (True, "venv runtime ready"))
    assert runtime.install_image_engine()["ok"] is True
    status = runtime.get_path_configuration_status()["image"]
    assert status["mode"] == "managed"
    assert runtime.app_config.image.comfyui_path == ""


def test_windows_venv_python_command_is_preferred(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))
    command, launcher = runtime._build_comfy_launch_command(comfy_root, "127.0.0.1", 8188)
    assert launcher == "portable_nvidia_launcher"
    assert command == ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat", "--listen", "127.0.0.1", "--port", "8188"]


def test_windows_system_python_requires_explicit_setting(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))
    monkeypatch.setattr("shutil.which", lambda _name: "py")

    command, launcher = runtime._build_comfy_launch_command(comfy_root, "127.0.0.1", 8188)
    assert command == []
    assert launcher == "python_runtime_not_found"

    command, launcher = runtime._build_comfy_launch_command(comfy_root, "127.0.0.1", 8188)
    assert command == []
    assert launcher == "python_runtime_not_found"


def test_resolve_comfy_python_runtime_uses_py_launcher_prefix(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    resolved = runtime._resolve_comfy_python_runtime(["py", "-3", "main.py"], "py_launcher")
    assert resolved["ok"] is True
    assert resolved["runtime_command"] == ["py", "-3"]


def test_dependency_bootstrap_reports_missing_sqlalchemy_when_install_fails(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    result = runtime._bootstrap_comfy_python_dependencies(Path("."), ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat"], "portable_nvidia_launcher")
    assert result["ok"] is True
    assert result["dependency_management"] == "skipped"


def test_dependency_bootstrap_reports_precise_requirements_context_on_pip_failure(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    result = runtime._bootstrap_comfy_python_dependencies(Path("."), ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat"], "portable_nvidia_launcher")
    assert result["ok"] is True
    assert result["installed_packages"] == []


def test_dependency_bootstrap_missing_pip_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    result = runtime._bootstrap_comfy_python_dependencies(Path("."), ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat"], "portable_nvidia_launcher")
    assert result["ok"] is True
    assert result["dependency_management"] == "skipped"


def test_dependency_bootstrap_pip_available_sets_pip_version(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    result = runtime._bootstrap_comfy_python_dependencies(Path("."), ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat"], "portable_nvidia_launcher")
    assert result["ok"] is True
    assert result["dependency_management"] == "skipped"


def test_dependency_bootstrap_reports_precise_error_when_pip_missing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    def _fake_run(runtime_command: list[str], args: list[str], timeout_seconds: int = 60):
        if args[:3] == ["-m", "pip", "--version"]:
            return subprocess.CompletedProcess([*runtime_command, *args], 1, stdout="", stderr="No module named pip")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(runtime, "_run_runtime_python_capture", _fake_run)
    result = runtime._bootstrap_runtime_pip(["python"], python_executable="python")
    assert result["ok"] is False
    assert result["message"] == "ComfyUI .venv is missing pip"
    assert "No module named pip" in result["detail"]


def test_dependency_bootstrap_does_not_install_requirements_if_pip_unavailable(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    result = runtime._bootstrap_comfy_python_dependencies(Path("."), ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat"], "portable_nvidia_launcher")
    assert result["ok"] is True
    assert result["dependency_management"] == "skipped"


def test_diagnostics_include_pip_availability_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_root = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_root / folder).mkdir(exist_ok=True)
    embedded = comfy_root / ".venv" / "Scripts" / "python.exe"
    embedded.parent.mkdir(parents=True, exist_ok=True)
    embedded.write_text("", encoding="utf-8")
    runtime.app_config.image.managed_install_path = str(comfy_root)

    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(runtime, "_build_comfy_launch_command", lambda *_args, **_kwargs: ([str(embedded), "main.py"], "venv_python"))
    monkeypatch.setattr(runtime, "_resolve_comfy_python_runtime", lambda *_args, **_kwargs: {"ok": True, "runtime_command": [str(embedded)], "executable": str(embedded)})
    monkeypatch.setattr(
        runtime,
        "_run_runtime_python_capture",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["python", "-m", "pip", "--version"], 1, stdout="", stderr="No module named pip"),
    )

    payload = runtime.get_image_backend_diagnostics()
    diagnostics = payload["diagnostics"]
    assert diagnostics["pip_available"] is False
    assert "pip" in diagnostics["runtime_missing_items"]
    assert diagnostics["runtime_complete"] is False


def test_diagnostics_dependency_probe_failure_marks_runtime_incomplete(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_root = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_root / folder).mkdir(exist_ok=True)
    embedded = comfy_root / ".venv" / "Scripts" / "python.exe"
    embedded.parent.mkdir(parents=True, exist_ok=True)
    embedded.write_text("", encoding="utf-8")
    runtime.app_config.image.managed_install_path = str(comfy_root)

    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(runtime, "_build_comfy_launch_command", lambda *_args, **_kwargs: ([str(embedded), "main.py"], "venv_python"))
    monkeypatch.setattr(runtime, "_resolve_comfy_python_runtime", lambda *_args, **_kwargs: {"ok": True, "runtime_command": [str(embedded)], "executable": str(embedded)})

    def _fake_run(runtime_command: list[str], args: list[str], timeout_seconds: int = 60, cwd: Path | None = None):
        if args[:3] == ["-m", "pip", "--version"]:
            return subprocess.CompletedProcess([*runtime_command, *args], 0, stdout="pip 24.0", stderr="")
        if args[:2] == ["-c", "import sqlalchemy"]:
            return subprocess.CompletedProcess([*runtime_command, *args], 1, stdout="", stderr="No module named sqlalchemy")
        return subprocess.CompletedProcess([*runtime_command, *args], 0, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_run_runtime_python_capture", _fake_run)

    payload = runtime.get_image_backend_diagnostics()
    diagnostics = payload["diagnostics"]
    assert diagnostics["dependency_probe_checked"] is True
    assert diagnostics["dependency_probe_ok"] is False
    assert diagnostics["runtime_complete"] is False
    assert "dependency:sqlalchemy" in diagnostics["runtime_missing_items"]


def test_start_image_engine_skips_launch_when_dependency_bootstrap_fails(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "workflow_path": {"valid": True, "configured": True, "resolved_path": str(workflow)},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True, "model_ready": True},
                "output_dir": {"valid": True, "configured": True, "resolved_path": str(tmp_path / "output")},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False})
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "missing_files": []})
    monkeypatch.setattr(runtime, "_build_comfy_launch_command", lambda *_args, **_kwargs: (["python", "main.py"], "system_python"))
    monkeypatch.setattr(runtime, "_validate_python_runtime", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(runtime, "_bootstrap_comfy_python_dependencies", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dependency bootstrap should not run")))
    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not launch")))

    result = runtime.start_image_engine()

    assert result["ok"] is False
    assert result["failure_stage"] == "launch-engine"


def test_start_image_engine_recreates_runtime_once_on_exit_106_dependency_failure(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_dir / folder).mkdir(exist_ok=True)
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "mode": "managed",
                "workflow_path": {"valid": True, "configured": True, "resolved_path": str(workflow)},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True, "model_ready": True},
                "output_dir": {"valid": True, "configured": True, "resolved_path": str(output_dir)},
                "pipeline_ready": True,
            }
        },
    )
    reachable = {"value": False}
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": reachable["value"], "status_code": "reachable" if reachable["value"] else "setup_required"})
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "missing_files": []})
    monkeypatch.setattr(runtime, "_build_comfy_launch_command", lambda *_args, **_kwargs: (["python", "main.py"], "venv_python"))
    monkeypatch.setattr(runtime, "_validate_python_runtime", lambda *_args, **_kwargs: {"ok": True})

    calls = {"count": 0}

    def _bootstrap(*_args, **_kwargs):
        calls["count"] += 1
        return {"ok": True}

    monkeypatch.setattr(runtime, "_bootstrap_comfy_python_dependencies", _bootstrap)
    monkeypatch.setattr(runtime, "_build_managed_launch_attempts", lambda *_args, **_kwargs: [{"mode": "python_main", "command": ["python", "main.py"], "launcher_type": "venv_python", "label": "python_main"}])
    monkeypatch.setattr("app.web.time.sleep", lambda *_args, **_kwargs: None)

    class _FakeProcess:
        stdout = None
        pid = 1234

        def poll(self):
            return None

    def _fake_popen(*_args, **_kwargs):
        reachable["value"] = True
        return _FakeProcess()

    monkeypatch.setattr("subprocess.Popen", _fake_popen)
    monkeypatch.setattr(runtime.comfy_manager, "register", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime.comfy_manager, "bind_log_handle", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "_read_startup_log_tail", lambda *_args, **_kwargs: [])
    result = runtime.start_image_engine()
    assert result["failure_stage"] in {"wait-for-readiness", "launch-engine"}
    assert calls["count"] == 0


def test_diagnostics_resolved_path_matches_launch_path_source_of_truth(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.comfyui_path = ""
    managed = Path(runtime._coerce_managed_install_path())
    managed.mkdir(parents=True, exist_ok=True)
    (managed / "main.py").write_text("print('ok')", encoding="utf-8")
    (managed / "custom_nodes").mkdir(exist_ok=True)
    (managed / "models").mkdir(exist_ok=True)
    (managed / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    payload = runtime.get_image_backend_diagnostics()
    diagnostics = payload["diagnostics"]
    assert diagnostics["image_backend_mode"] == "managed"
    assert diagnostics["comfyui_path"] == diagnostics["resolved_paths"]["comfyui_root"]
    assert diagnostics["resolved_paths"]["comfyui_root"] == str(managed)


def test_managed_launch_attempts_use_only_nvidia_gpu_launcher(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "run_nvidia_gpu.bat").write_text("@echo off\r\npython main.py --windows-standalone-build", encoding="utf-8")
    (comfy_root / "run_cpu.bat").write_text("@echo off\r\npython main.py --cpu", encoding="utf-8")
    runtime_python = comfy_root / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("", encoding="utf-8")
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt"))

    runtime.app_config.image.preferred_launcher = "auto"
    attempts = runtime._build_managed_launch_attempts(
        comfy_root,
        "127.0.0.1",
        8188,
        launch_command=["python", "main.py"],
        launcher_type="venv_python",
    )
    assert [attempt["mode"] for attempt in attempts] == ["nvidia_gpu", "cpu"]
    assert attempts[0]["command"][0] == str(runtime_python)


def test_classify_nvidia_launch_failure_cuda_patterns_disable_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    cases = [
        "AssertionError: Torch not compiled with CUDA enabled",
        "RuntimeError: CUDA initialization error",
        "RuntimeError: No NVIDIA driver found",
        "ImportError: cudnn64_9.dll missing",
    ]
    for detail in cases:
        classification = runtime._classify_nvidia_launch_failure(detail, exit_code=1, launcher_exists=True)
        assert classification["fallback_eligible"] == "false"


def test_start_image_engine_nvidia_failure_returns_structured_error_without_cpu_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.preferred_launcher = "auto"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    (comfy_dir / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    (comfy_dir / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime.app_config.image.managed_install_path = str(comfy_dir)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "mode": "managed",
                "workflow_path": {"valid": True, "configured": True, "resolved_path": str(workflow)},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True, "model_ready": True},
                "output_dir": {"valid": True, "configured": True, "resolved_path": str(output_dir)},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "missing_files": []})
    monkeypatch.setattr(runtime, "_build_comfy_launch_command", lambda *_args, **_kwargs: (["python", "main.py"], "venv_python"))
    monkeypatch.setattr(runtime, "_validate_python_runtime", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(runtime, "_bootstrap_comfy_python_dependencies", lambda *_args, **_kwargs: {"ok": True, "installed_packages": []})
    monkeypatch.setattr("app.web.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.web.subprocess.CREATE_NEW_PROCESS_GROUP", 0, raising=False)
    monkeypatch.setattr("app.web.subprocess.CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(
        runtime,
        "_read_startup_log_tail",
        lambda *_args, **_kwargs: ["AssertionError: Torch not compiled with CUDA enabled"],
    )

    launched_modes: list[str] = []
    reachable_state = {"ready": False}

    class _FakeProcess:
        def __init__(self, mode: str) -> None:
            self.mode = mode
            self.stdout = None
            self._poll_calls = 0
            self.pid = 1234 if mode == "cpu" else 1233

        def poll(self):
            self._poll_calls += 1
            if self.mode == "nvidia_gpu":
                return 1
            return None

        def communicate(self, timeout: float | None = None):
            return ("", "")

    def _fake_popen(command, **kwargs):
        mode = "nvidia_gpu" if "run_nvidia_gpu.bat" in " ".join(command) else "cpu"
        launched_modes.append(mode)
        if mode == "cpu":
            reachable_state["ready"] = True
        return _FakeProcess(mode)

    monkeypatch.setattr("subprocess.Popen", _fake_popen)
    monkeypatch.setattr(
        runtime,
        "get_image_status",
        lambda: {"reachable": reachable_state["ready"], "status_code": "reachable" if reachable_state["ready"] else "setup_required"},
    )

    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert launched_modes == ["nvidia_gpu"]
    assert "requires NVIDIA GPU mode" in result["message"]
    assert "CPU fallback is disabled" in result["message"]
    assert result["selected_launcher"] == "nvidia_gpu"
    assert result["no_cpu_fallback"] is True
    assert result["failure_reason"] == "torch-cuda-disabled"
    launch_diagnostics = result["startup_status"]["launch_diagnostics"]
    assert launch_diagnostics["primary_launch_attempt"] == "nvidia_gpu"
    assert launch_diagnostics["selected_launcher"] == "nvidia_gpu"
    assert launch_diagnostics["fallback_launch_used"] == ""
    assert launch_diagnostics["no_cpu_fallback"] is True
    assert launch_diagnostics["nvidia_failure_reason"] == "torch-cuda-disabled"
    assert launch_diagnostics["final_running_mode"] == ""


def test_start_image_engine_missing_nvidia_launcher_fails_fast_without_cpu_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.preferred_launcher = "auto"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    (comfy_dir / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime.app_config.image.managed_install_path = str(comfy_dir)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "mode": "managed",
                "workflow_path": {"valid": True, "configured": True, "resolved_path": str(workflow)},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True, "model_ready": True},
                "output_dir": {"valid": True, "configured": True, "resolved_path": str(output_dir)},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "missing_files": []})
    monkeypatch.setattr(runtime, "_build_comfy_launch_command", lambda *_args, **_kwargs: (["python", "main.py"], "venv_python"))
    monkeypatch.setattr(runtime, "_validate_python_runtime", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(runtime, "_bootstrap_comfy_python_dependencies", lambda *_args, **_kwargs: {"ok": True, "installed_packages": []})
    monkeypatch.setattr("app.web.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.web.subprocess.CREATE_NEW_PROCESS_GROUP", 0, raising=False)
    monkeypatch.setattr("app.web.subprocess.CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False, "status_code": "setup_required"})
    monkeypatch.setattr(
        runtime,
        "_read_startup_log_tail",
        lambda *_args, **_kwargs: ["AssertionError: Torch not compiled with CUDA enabled"],
    )

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not launch")))

    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert result["failure_stage"] == "launch-engine"
    assert "requires NVIDIA GPU mode" in result["message"]
    assert result["failure_reason"] == "launcher-file-missing"
    assert result["no_cpu_fallback"] is True
    assert result["startup_status"]["launch_diagnostics"]["selected_launcher"] == "nvidia_gpu"
    assert result["startup_status"]["launch_diagnostics"]["no_cpu_fallback"] is True


def test_text_gameplay_remains_usable_after_image_ai_nvidia_failure(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "start_image_engine", lambda: {"ok": False, "message": "Image AI requires NVIDIA GPU mode and CPU fallback is disabled."})

    image_result = runtime.start_image_engine()
    runtime.create_campaign({"player_name": "TextOnly", "slot": "slot_text_only"})
    turn_result = runtime.handle_player_input("look around")

    assert image_result["ok"] is False
    assert "state" in turn_result
    assert turn_result["messages"]


def test_start_image_engine_nvidia_waits_for_delayed_readiness(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    (comfy_dir / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime.app_config.image.managed_install_path = str(comfy_dir)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr("app.web.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.web.subprocess.CREATE_NEW_PROCESS_GROUP", 0, raising=False)
    monkeypatch.setattr("app.web.subprocess.CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "mode": "managed",
                "workflow_path": {"valid": True, "configured": True, "resolved_path": str(workflow)},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True, "model_ready": True},
                "output_dir": {"valid": True, "configured": True, "resolved_path": str(output_dir)},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "missing_files": []})
    monkeypatch.setattr(runtime, "_read_startup_log_tail", lambda *_args, **_kwargs: ["ComfyUI startup..."])

    class _FakeProcess:
        pid = 1001
        stdout = None

        def poll(self):
            return None

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: _FakeProcess())
    probe_calls = {"count": 0}

    def _fake_probe(_expected_base: str, _startup_log_text: str, timeout_seconds: float = 1.0):
        probe_calls["count"] += 1
        return (probe_calls["count"] >= 18, "http://127.0.0.1:8188" if probe_calls["count"] >= 18 else "")

    monkeypatch.setattr(runtime, "_probe_comfy_readiness", _fake_probe)
    monkeypatch.setattr(runtime, "_detect_comfy_child_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False, "status_code": "setup_required"})

    result = runtime.start_image_engine()
    assert result["ok"] is True
    assert probe_calls["count"] >= 18
    assert result["startup_status"]["ready_base_url"] == "http://127.0.0.1:8188"


def test_start_image_engine_timeout_includes_launcher_output_tail(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    (comfy_dir / "run_nvidia_gpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime.app_config.image.managed_install_path = str(comfy_dir)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr("app.web.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.web.subprocess.CREATE_NEW_PROCESS_GROUP", 0, raising=False)
    monkeypatch.setattr("app.web.subprocess.CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {
            "image": {
                "mode": "managed",
                "workflow_path": {"valid": True, "configured": True, "resolved_path": str(workflow)},
                "comfyui_root": {"valid": True, "configured": True, "path": str(comfy_dir), "resolved_path": str(comfy_dir)},
                "checkpoint_dir": {"valid": True, "configured": True, "model_ready": True},
                "output_dir": {"valid": True, "configured": True, "resolved_path": str(output_dir)},
                "pipeline_ready": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "validate_comfyui_install", lambda _path: {"ok": True, "missing_files": []})
    monkeypatch.setattr(runtime, "_read_startup_log_tail", lambda *_args, **_kwargs: ["loading cuda kernels", "still initializing..."])

    class _FakeProcess:
        pid = 2002
        stdout = None

        def poll(self):
            return None

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: _FakeProcess())
    monkeypatch.setattr(runtime, "_probe_comfy_readiness", lambda *_args, **_kwargs: (False, ""))
    monkeypatch.setattr(runtime, "_detect_comfy_child_process", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False, "status_code": "setup_required"})

    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert result["failure_stage"] == "wait-for-readiness"
    assert "Last output: still initializing..." in result["message"]
    assert result["exact_error"] == "still initializing..."
    assert result["launcher_output_tail"][-1] == "still initializing..."
