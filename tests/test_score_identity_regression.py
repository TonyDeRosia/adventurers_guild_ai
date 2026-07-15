from types import SimpleNamespace

import pytest

from engine.display_services import CharacterDisplaySnapshotService
from engine.mud_commands import MudCommandEngine
from engine.mud_displays import CharacterDisplaySnapshot
from engine.mud_runtime import MudCharacter
from app.web import WebRuntime
from pathlib import Path
import os


def test_progression_identity_snapshot_resolves_names_and_rejects_bad_track(tmp_path):
    os.environ["SMART_MUD_USER_DATA_DIR"] = str(tmp_path / "user_data1")
    rt = WebRuntime(Path.cwd()).mud_runtime
    rt.load_world("shattered_realms")
    created = rt.create_character(world_id="shattered_realms", name="Identity", race_id="human", class_id="warrior")
    rt.enter_world(created["character_id"])
    snap = rt.character_display_snapshots.build_snapshot(rt.active_characters[created["character_id"]])
    assert snap.race == {"id":"human", "name":"Human", "availability":"available", "source_version": snap.race["source_version"]}
    assert snap.character_class["id"] == "warrior"
    assert snap.character_class["name"] == "Warrior"
    svc = rt._progression_service()
    svc.update_actor_progression(created["character_id"], {"primary_class_track_id":"cleric_healer"})
    with pytest.raises(ValueError):
        svc.progression_identity_snapshot(created["character_id"])


def test_legacy_migration_is_idempotent_preserves_level_xp_and_score_read_only(tmp_path):
    os.environ["SMART_MUD_USER_DATA_DIR"] = str(tmp_path / "user_data2")
    rt = WebRuntime(Path.cwd()).mud_runtime
    rt.load_world("shattered_realms")
    char = MudCharacter(id="char_legacy", name="Legacy", role="player", level=4, xp=250, gold=77, actor_data={"race_id":"halfling","class_id":"rogue"})
    rt.state_store.save_character(char, "shattered_realms")
    svc = rt._progression_service()
    first = svc.repair_legacy_progression_identity(char, apply=True)
    second = svc.repair_legacy_progression_identity(char, apply=True)
    state = svc.get_actor_progression(char.id)
    assert first["proposed_race_id"] == second["proposed_race_id"] == "halfling"
    assert state["primary_class_id"] == "rogue"
    assert state["level"] == 4 and state["experience"] == 250
    before = state["updated_at"]
    snap = CharacterDisplaySnapshotService(rt).build_snapshot(char)
    assert snap.race["name"] == "Halfling"
    assert svc.get_actor_progression(char.id)["updated_at"] == before


def test_incomplete_score_boundary_is_safe_and_not_cached(caplog):
    engine = MudCommandEngine()
    char = SimpleNamespace(id="bad", name="Bad", role="player", entry_context=SimpleNamespace(entry_id="entry1"))
    engine.character_display_snapshots = SimpleNamespace(build_snapshot=lambda _c: CharacterDisplaySnapshot(character_id="bad", identity={"display_name":"Bad"}))
    result = engine._cmd_score(char, [], "score")
    assert not result.ok
    assert "could not be loaded" in result.narrative
    assert "score_projection_incomplete" not in result.narrative
    assert any("score_projection_incomplete" in r.message for r in caplog.records)
