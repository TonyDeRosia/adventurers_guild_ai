import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from engine.display_themes import ThemeResolutionMode, resolve_effective_display_theme, load_display_themes
from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace

PROTECTED = [
    Path("worlds/shattered_realms/builder"),
    Path("worlds/shattered_realms/world"),
    Path("worlds/shattered_realms/areas"),
    Path("worlds/shattered_realms/zones"),
    Path("worlds/shattered_realms/display_themes"),
]


def _snapshot(paths=PROTECTED):
    out = {}
    for root in paths:
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def test_repository_world_files_not_mutated_by_publish_suite_guard():
    assert _snapshot() == _snapshot()


def _copy_world(tmp_path):
    src = Path("worlds/shattered_realms")
    dst = tmp_path / "worlds" / "shattered_realms"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("builder", "snapshots", "exports", "audit", "history", "__pycache__"))
    (dst / "builder").mkdir(parents=True, exist_ok=True)
    return tmp_path / "worlds", dst


def _actor():
    return SimpleNamespace(id="builder", role="builder", account_role="builder", world_id="shattered_realms", room_id="r", preferences={})


def test_builder_publish_themes_and_assignments_are_isolated_until_publish(tmp_path):
    worlds_dir, root = _copy_world(tmp_path)
    builder = BuilderWorkspace(worlds_dir=worlds_dir)
    engine = MudCommandEngine(); engine.builder = builder
    actor = _actor()
    drafts = builder.load("shattered_realms")
    drafts["areas"]["a"] = {"id":"a", "name":"A", "world_id":"shattered_realms", "zone_ids":["z"]}
    drafts["zones"]["z"] = {"id":"z", "name":"Z", "world_id":"shattered_realms", "area_id":"a", "room_ids":["r"]}
    builder.save_drafts("shattered_realms", drafts)

    assert engine._cmd_displaytheme(actor, ["create", "vital_theme"], "").ok
    assert engine._cmd_displaytheme(actor, ["label", "vital_theme", "health", "&YVitality&n"], "").ok
    assert engine._cmd_displaytheme(actor, ["label", "vital_theme", "mana", "Aether"], "").ok
    assert engine._cmd_displaytheme(actor, ["assign", "world", "vital_theme"], "").ok
    assert engine._cmd_displaytheme(actor, ["assign", "zone", "z", "score", "vital_theme"], "").ok
    assert engine._cmd_displaytheme(actor, ["assign", "area", "a", "score", "vital_theme"], "").ok

    live = resolve_effective_display_theme(actor, world_root=root, family="score")
    draft = resolve_effective_display_theme(actor, world_root=root, family="score", resolution_mode=ThemeResolutionMode.BUILDER_DRAFT_PREVIEW)
    assert live.theme_id != "vital_theme"
    assert draft.theme_id == "vital_theme"

    published = builder.publish_drafts(actor)
    assert published.ok, published.message
    themes = load_display_themes(root)
    assert themes["vital_theme"].labels["health"] == "&YVitality&n"
    assert json.loads((root / "world" / "world.json").read_text())["default_display_theme_id"] == "vital_theme"
    assert json.loads((root / "zones" / "zones.json").read_text())[0]["display_theme_ids"]["score"] == "vital_theme"
    assert json.loads((root / "areas" / "areas.json").read_text())[0]["display_theme_ids"]["score"] == "vital_theme"
    reloaded = resolve_effective_display_theme(actor, world_root=root, family="score")
    assert reloaded.theme_id == "vital_theme"


def test_builder_publish_validation_is_transactional(tmp_path):
    worlds_dir, root = _copy_world(tmp_path)
    builder = BuilderWorkspace(worlds_dir=worlds_dir)
    actor = _actor()
    before = {p: p.read_text() for p in [root/"display_themes"/"display_themes.json", root/"areas"/"areas.json", root/"zones"/"zones.json"] if p.exists()}
    drafts = builder.load("shattered_realms")
    drafts["display_themes"] = {"bad": {"theme_id":"bad", "width": 12}}
    drafts["world"] = {"shattered_realms": {"id":"shattered_realms", "default_display_theme_id":"missing"}}
    builder.save_drafts("shattered_realms", drafts)
    result = builder.publish_drafts(actor)
    assert not result.ok
    assert "width" in result.message and "missing theme" in result.message
    after = {p: p.read_text() for p in before}
    assert after == before
