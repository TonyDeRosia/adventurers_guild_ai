from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from app.web import WebRuntime


def _runtime(tmp_path: Path, monkeypatch) -> WebRuntime:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    return WebRuntime(Path.cwd())


def _comfy_root(tmp_path: Path) -> Path:
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    for folder in ("custom_nodes", "models", "output", "input", "user"):
        (comfy_dir / folder).mkdir(exist_ok=True)
    (comfy_dir / "run_nvidia_gpu.bat").write_text("@echo off\npython main.py --windows-standalone-build", encoding="utf-8")
    runtime_python = comfy_dir / ".venv" / "Scripts" / "python.exe"
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.write_text("", encoding="utf-8")
    return comfy_dir


def test_build_launch_command_uses_direct_python_without_batch_wrapper(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_dir = _comfy_root(tmp_path)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt", path=os.path))

    command, launcher = runtime._build_comfy_launch_command(comfy_dir, "127.0.0.1", 8188)

    assert launcher == "portable_python_direct"
    assert command[0].endswith("python.exe")
    assert command[1] == "main.py"
    assert "--windows-standalone-build" in command
    assert "--listen" in command and "127.0.0.1" in command
    assert "--port" in command and "8188" in command


def test_detect_child_process_uses_port_probe(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    class _FakeProcess:
        def poll(self):
            return 1

    monkeypatch.setattr(runtime, "_is_port_listening", lambda *_args, **_kwargs: True)
    assert runtime._detect_comfy_child_process(_FakeProcess(), ["http://127.0.0.1:8188"]) is True


def test_start_image_engine_reports_immediate_launcher_exit_with_output(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = _comfy_root(tmp_path)
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
    monkeypatch.setattr(runtime, "_read_startup_log_tail", lambda *_args, **_kwargs: ["Traceback", "ModuleNotFoundError: xyz"])
    monkeypatch.setattr(runtime, "_quick_comfy_readiness_probe", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(runtime, "_detect_comfy_child_process", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False, "status_code": "setup_required"})
    monkeypatch.setattr(runtime, "_bootstrap_comfy_python_dependencies", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")))

    class _FakeProcess:
        pid = 99
        stdout = None

        def poll(self):
            return 1

        def communicate(self, timeout=None):
            return ("", "")

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: _FakeProcess())

    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert result["failure_stage"] == "wait-for-readiness"
    assert "Error: ModuleNotFoundError: xyz" in result["message"]
    assert "ModuleNotFoundError: xyz" in result["launcher_output"]
    assert result["exact_error"] == "ModuleNotFoundError: xyz"


def test_validate_install_does_not_require_venv_runtime(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_dir = _comfy_root(tmp_path)
    monkeypatch.setattr("app.web.os", SimpleNamespace(name="nt", path=os.path))

    status = runtime.validate_comfyui_install(comfy_dir)
    assert status["ok"] is True
    assert "python-runtime" not in status["missing_files"]


def test_dependency_bootstrap_is_skipped_for_portable_runtime(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    result = runtime._bootstrap_comfy_python_dependencies(Path("."), ["cmd.exe", "/d", "/c", "run_nvidia_gpu.bat"], "portable_nvidia_launcher")
    assert result["ok"] is True
    assert result["dependency_management"] == "skipped"
    assert result["installed_packages"] == []
