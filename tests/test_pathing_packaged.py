from __future__ import annotations

from pathlib import Path

from app import pathing


def test_bundled_runtime_dir_prefers_install_dir_in_frozen_mode(tmp_path: Path, monkeypatch) -> None:
    install_root = tmp_path / "install"
    meipass = tmp_path / "_meipass"
    (install_root / "runtime_bundle").mkdir(parents=True)
    (meipass / "runtime_bundle").mkdir(parents=True)

    fake_exe = install_root / "AdventurerGuildAI.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(pathing.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pathing.sys, "executable", str(fake_exe), raising=False)
    monkeypatch.setattr(pathing.sys, "_MEIPASS", str(meipass), raising=False)

    assert pathing.bundled_runtime_dir() == install_root / "runtime_bundle"


def test_bundled_runtime_dir_falls_back_to_meipass_layout_when_needed(tmp_path: Path, monkeypatch) -> None:
    install_root = tmp_path / "install"
    meipass = tmp_path / "_meipass"
    install_root.mkdir(parents=True)
    (meipass / "runtime_bundle").mkdir(parents=True)

    fake_exe = install_root / "AdventurerGuildAI.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(pathing.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pathing.sys, "executable", str(fake_exe), raising=False)
    monkeypatch.setattr(pathing.sys, "_MEIPASS", str(meipass), raising=False)

    assert pathing.bundled_runtime_dir() == meipass / "runtime_bundle"


def test_bundled_workflow_dir_falls_back_to_content_data_workflows(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    (root / "data" / "workflows").mkdir(parents=True)
    (root / "data" / "workflows" / "scene_image.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(pathing.sys, "frozen", False, raising=False)
    monkeypatch.setattr(pathing, "project_root", lambda: root)

    assert pathing.bundled_workflow_dir() == root / "data" / "workflows"
