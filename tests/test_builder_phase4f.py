import json, shutil
from types import SimpleNamespace
from pathlib import Path

from smart_mud.builder import BuilderWorkspace
from engine.mud_commands import MudCommandEngine


def actor(role="builder"):
    return SimpleNamespace(role=role, account_role=role, world_id="shattered_realms", id="c1", account_id="a1", room_id="guildhall_crossing_square", edit_room_id="guildhall_crossing_square", name="Tester")


def workspace(tmp_path):
    root = tmp_path / "worlds"
    shutil.copytree(Path("worlds/shattered_realms"), root / "shattered_realms", ignore=shutil.ignore_patterns("builder"))
    return BuilderWorkspace(worlds_dir=root), root


def test_builder_migrate_starter_assigns_area_zone_vnums_and_preserves_live(tmp_path):
    bw, root = workspace(tmp_path)
    live_rooms_path = root / "shattered_realms/rooms/rooms.json"
    before = live_rooms_path.read_text()
    res = bw.migrate_starter(actor())
    assert res.ok
    assert "Starter migration complete" in res.message
    assert live_rooms_path.read_text() == before
    assert list((root / "shattered_realms/builder/snapshots").iterdir())
    drafts = bw.load("shattered_realms")
    assert "starter_guildlands" in drafts["areas"]
    for zid in ["guildhall_crossing", "registrar_hall", "training_grounds", "market_lane", "wayfarers_mug", "old_gate_road", "east_farmland", "emberwood_edge", "abandoned_watchpost", "rat_cellar"]:
        assert zid in drafts["zones"]
    live_ids = {r["id"] for r in json.loads(live_rooms_path.read_text())}
    assert live_ids <= set(drafts["rooms"])
    assert all(drafts["rooms"][rid]["area_id"] for rid in live_ids)
    assert all(drafts["rooms"][rid]["zone_id"] for rid in live_ids)
    assert all(drafts["rooms"][rid]["vnum"] is not None for rid in live_ids)
    assert drafts["rooms"]["guildhall_crossing_square"]["vnum"] == 1000


def test_builder_import_validate_preview_apply_round_trip(tmp_path):
    bw, root = workspace(tmp_path)
    a = actor()
    bw.ensure("shattered_realms")
    imp = root / "shattered_realms/builder/imports/my_area.json"
    bundle = {
        "areas": {"test_area": {"id":"test_area", "name":"Test Area", "world_id":"shattered_realms", "vnum_start":2000, "vnum_end":2099, "room_vnum_start":2000, "room_vnum_end":2099}},
        "zones": {"test_zone": {"id":"test_zone", "name":"Test Zone", "world_id":"shattered_realms", "area_id":"test_area", "vnum_start":2000, "vnum_end":2099}},
        "rooms": {"test_room": {"id":"test_room", "name":"Test Room", "description":"A test room.", "world_id":"shattered_realms", "area_id":"test_area", "zone_id":"test_zone", "vnum":2000, "exits":{}, "features":{}, "flags":[], "tags":[], "plugin_data":{}}},
        "features": {}, "items": {}, "entities": {}, "spawns": {},
    }
    imp.write_text(json.dumps(bundle))
    assert "my_area.json" in bw.import_list(a).message
    assert bw.import_validate(a, "my_area.json").ok
    preview = bw.import_preview(a, "my_area.json")
    assert preview.ok and "No files changed" in preview.message
    assert "test_room" not in bw.load("shattered_realms")["rooms"]
    assert bw.import_apply(a, "my_area.json").ok
    assert "test_room" in bw.load("shattered_realms")["rooms"]
    out = bw.export(a)
    exported = Path(out.message.rsplit(" ", 1)[-1].rstrip("."))
    target = root / "shattered_realms/builder/imports/round_trip.json"
    target.write_text(exported.read_text())
    assert bw.import_validate(a, "round_trip.json").ok


def test_builder_import_broken_bundle_fails_and_player_denied(tmp_path):
    bw, root = workspace(tmp_path)
    bw.ensure("shattered_realms")
    (root / "shattered_realms/builder/imports/bad.json").write_text(json.dumps({"rooms":{"bad_room":{"id":"bad_room"}}}))
    assert not bw.import_validate(actor(), "bad.json").ok
    engine = MudCommandEngine()
    engine.builder = bw
    player = actor("player")
    assert not engine.handle_command(player, "builder migrate starter").ok
