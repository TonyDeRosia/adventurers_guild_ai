from __future__ import annotations

from pathlib import Path

from app.installer_layout import InstallerLayoutValidator


def test_installer_layout_reports_missing_required_assets(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime_bundle"
    workflow_root = runtime_root / "workflows"

    monkeypatch.setattr("app.installer_layout.bundled_runtime_dir", lambda: runtime_root)
    monkeypatch.setattr("app.installer_layout.bundled_comfyui_dir", lambda: runtime_root / "comfyui")
    monkeypatch.setattr("app.installer_layout.bundled_workflow_dir", lambda: workflow_root)

    status = InstallerLayoutValidator().validate()

    assert status["valid"] is False
    assert "runtime_bundle" in status["missing_required"]
    assert "bundled_image_runtime" in status["missing_required"]
    assert "workflow_scene_image" in status["missing_required"]
    assert "workflow_character_portrait" in status["missing_required"]
    assert status["checks"]["venv_runtime"]["required"] is False
    assert status["venv_runtime_present"] is False


def test_installer_layout_reports_valid_when_required_assets_exist(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime_bundle"
    comfy_root = runtime_root / "comfyui"
    workflow_root = runtime_root / "workflows"
    embedded_python = comfy_root / ".venv" / "Scripts" / "python.exe"

    comfy_root.mkdir(parents=True, exist_ok=True)
    workflow_root.mkdir(parents=True, exist_ok=True)
    embedded_python.parent.mkdir(parents=True, exist_ok=True)

    (workflow_root / "scene_image.json").write_text("{}", encoding="utf-8")
    (workflow_root / "character_portrait.json").write_text("{}", encoding="utf-8")
    embedded_python.write_text("", encoding="utf-8")

    monkeypatch.setattr("app.installer_layout.bundled_runtime_dir", lambda: runtime_root)
    monkeypatch.setattr("app.installer_layout.bundled_comfyui_dir", lambda: comfy_root)
    monkeypatch.setattr("app.installer_layout.bundled_workflow_dir", lambda: workflow_root)

    status = InstallerLayoutValidator().validate()

    assert status["valid"] is True
    assert status["state"] == "valid"
    assert status["missing_required"] == []
    assert status["packaged_app_files_present"] is True
    assert status["bundled_image_runtime_present"] is True
    assert status["bundled_workflows_present"] is True
    assert status["venv_runtime_present"] is True
