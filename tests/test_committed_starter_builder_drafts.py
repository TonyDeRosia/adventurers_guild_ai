import json
from pathlib import Path
from types import SimpleNamespace

from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace

ROOT = Path("worlds/shattered_realms/builder")
REQUIRED_FILES = {
    "areas": "areas.json",
    "zones": "zones.json",
    "rooms": "rooms.json",
    "features": "features.json",
    "items": "item_templates.json",
    "entities": "entity_templates.json",
    "spawns": "spawns.json",
}
REQUIRED_ZONES = {
    "guildhall_crossing": (1000, 1029),
    "registrar_hall": (1030, 1049),
    "training_grounds": (1050, 1079),
    "market_lane": (1080, 1119),
    "wayfarers_mug": (1120, 1149),
    "old_gate_road": (1150, 1179),
    "east_farmland": (1180, 1209),
    "emberwood_edge": (1210, 1239),
    "abandoned_watchpost": (1240, 1269),
    "rat_cellar": (1270, 1299),
}


def load(name):
    return json.loads((ROOT / REQUIRED_FILES[name]).read_text(encoding="utf-8"))


def actor():
    return SimpleNamespace(role="builder", account_role="builder", world_id="shattered_realms", id="c1", account_id="a1", room_id="guildhall_crossing_square", edit_room_id="guildhall_crossing_square", name="Tester")


def test_repo_contains_required_builder_draft_files_as_json_objects():
    for filename in REQUIRED_FILES.values():
        path = ROOT / filename
        assert path.exists(), filename
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)


def test_committed_starter_area_zones_rooms_are_organized_and_consistent():
    areas = load("areas")
    zones = load("zones")
    rooms = load("rooms")
    assert areas["starter_guildlands"]["world_id"] == "shattered_realms"
    assert "starter" in areas["starter_guildlands"]["tags"]
    for zone_id, (start, end) in REQUIRED_ZONES.items():
        zone = zones[zone_id]
        assert zone["area_id"] == "starter_guildlands"
        assert (zone["vnum_start"], zone["vnum_end"]) == (start, end)
        for room_id in zone["room_ids"]:
            assert room_id in rooms
    start = rooms["guildhall_crossing_square"]
    assert start["area_id"] == "starter_guildlands"
    assert start["zone_id"] == "guildhall_crossing"
    assert start["vnum"] == 1000
    starter_vnums = []
    for room_id, room in rooms.items():
        assert room["area_id"]
        assert room["zone_id"]
        assert room["vnum"] is not None
        if room["area_id"] == "starter_guildlands":
            starter_vnums.append(room["vnum"])
        for exit_data in room.get("exits", {}).values():
            assert exit_data["target_room_id"] in rooms
    assert len(starter_vnums) == len(set(starter_vnums))


def test_builder_validate_rstat_and_export_import_use_isolated_starter_drafts(isolated_builder_world):
    bw = isolated_builder_world.workspace
    a = actor()
    validation = bw.validate(a)
    assert validation.ok, validation.message
    assert not [w for w in validation.data["warnings"] if "legacy" in w.lower() and "guildhall" in w.lower()]

    engine = MudCommandEngine()
    engine.builder = bw
    rstat = engine.handle_command(a, "rstat").narrative
    assert "Area: starter_guildlands, Starter Guildlands" in rstat
    assert "Zone: guildhall_crossing, Guildhall Crossing" in rstat
    assert "VNUM: 1000" in rstat
    assert "Status: organized" in rstat

    exported = bw.export(a)
    assert exported.ok
    export_path = Path(exported.message.rsplit(" ", 1)[-1].rstrip("."))
    bundle = json.loads(export_path.read_text(encoding="utf-8"))
    for key in REQUIRED_FILES:
        assert key in bundle
    import_path = isolated_builder_world.builder_path / "imports" / "committed_round_trip.json"
    import_path.write_text(export_path.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        assert bw.import_validate(a, import_path.name).ok
    finally:
        import_path.unlink(missing_ok=True)
        export_path.unlink(missing_ok=True)


def test_mutating_builder_operations_do_not_change_repository_drafts(isolated_builder_world):
    protected = [ROOT / filename for filename in REQUIRED_FILES.values()]
    before = {path: path.read_bytes() for path in protected}
    noise_dirs = [ROOT / name for name in ("imports", "exports", "history", "audit", "snapshots")]
    noise_before = {path: sorted(p.relative_to(path).as_posix() for p in path.rglob("*")) if path.exists() else [] for path in noise_dirs}

    bw = isolated_builder_world.workspace
    a = actor()
    engine = MudCommandEngine()
    engine.builder = bw
    assert engine.handle_command(a, "rcreate repo_integrity_room").ok
    assert engine.handle_command(a, "rname Repository Integrity Room").ok
    assert bw.export(a).ok
    assert bw.template_copy(a, "area_zone_room_template.json", "integrity_import.json", force=True).ok
    assert bw.import_validate(a, "integrity_import.json").ok

    assert {path: path.read_bytes() for path in protected} == before
    noise_after = {path: sorted(p.relative_to(path).as_posix() for p in path.rglob("*")) if path.exists() else [] for path in noise_dirs}
    assert noise_after == noise_before
