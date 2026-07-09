from __future__ import annotations

from pathlib import Path


def test_readme_no_longer_presents_normal_startup_as_adventurers_guild_ai() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Smart MUD")
    assert "Smart MUD is a package-driven, SQLite-backed MUD engine" in readme
    assert "Normal startup does not initialize the legacy Adventure Guild AI" in readme
    assert "ComfyUI process ownership" in readme
    assert "# Adventurer's Guild AI" not in readme
    assert "auto-start ComfyUI" not in readme


def test_world_package_spec_separates_runtime_content_from_builder_workspace() -> None:
    spec = Path("docs/WORLD_PACKAGE_SPEC.md").read_text(encoding="utf-8")
    assert "## Required runtime package content" in spec
    assert "## Auto-created Builder workspace" in spec
    assert "Missing runtime gameplay/content folders are fatal" in spec
    assert "not fatal install requirements" in spec
    required_section = spec.split("## Auto-created Builder workspace", 1)[0]
    assert "- `rooms/`" in required_section
    assert "- `colors/`" in required_section
    assert "- `builder/`" not in required_section


def test_smart_mud_architecture_and_roadmap_exist() -> None:
    architecture = Path("docs/SMART_MUD_ARCHITECTURE.md").read_text(encoding="utf-8")
    roadmap = Path("docs/SMART_MUD_MASTER_ROADMAP.md").read_text(encoding="utf-8")
    assert "smart_mud/world_registry.py` owns validation logic" in architecture
    assert "Legacy systems excluded from startup" in architecture
    for phase in range(1, 11):
        assert f"Phase {phase}:" in roadmap
    assert "acceptance criteria" in roadmap.lower()
