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


def test_copy_tree_missing_copies_file_when_destination_directory_exists(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "character_portrait.json").write_text('{"id":"portrait"}', encoding="utf-8")

    pathing._copy_tree_missing(src, dst)

    copied = dst / "character_portrait.json"
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == '{"id":"portrait"}'


def test_copy_tree_missing_creates_nested_parents_for_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "nested" / "deep").mkdir(parents=True)
    (src / "nested" / "deep" / "scene_image.json").write_text("{}", encoding="utf-8")

    pathing._copy_tree_missing(src, dst)

    assert (dst / "nested" / "deep" / "scene_image.json").exists()


def test_copy_tree_missing_does_not_overwrite_existing_destination_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "scene_image.json").write_text('{"version":"src"}', encoding="utf-8")
    (dst / "scene_image.json").write_text('{"version":"dst"}', encoding="utf-8")

    pathing._copy_tree_missing(src, dst)

    assert (dst / "scene_image.json").read_text(encoding="utf-8") == '{"version":"dst"}'


def test_copy_tree_missing_handles_directory_entries_and_file_destination_conflicts(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "workflows" / "portraits").mkdir(parents=True)
    (src / "workflows" / "portraits" / "character_portrait.json").write_text("{}", encoding="utf-8")
    dst.mkdir()
    # Simulate a conflicting file where a directory would normally be created.
    (dst / "workflows").write_text("not-a-dir", encoding="utf-8")

    pathing._copy_tree_missing(src, dst)

    assert (dst / "workflows").is_file()
    assert not (dst / "workflows" / "portraits" / "character_portrait.json").exists()
