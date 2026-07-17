from types import SimpleNamespace

from smart_mud.builder import BuilderService, BuilderWorkspace


def actor():
    return SimpleNamespace(id="builder", name="Builder", role="admin", account_role="admin", world_id="shattered_realms", current_area_id="starter_guildlands", current_zone_id="guildhall_crossing", room_id="guildhall_crossing_square")


def test_builder_content_query_lists_drafts_without_json_ids(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    svc = BuilderService(ws)
    a = actor()
    drafts = ws.load("shattered_realms")
    drafts.setdefault("entities", {})["dire_forest_wolf"] = {"id": "dire_forest_wolf", "name": "Dire Forest Wolf", "vnum": 1501, "level": 8, "race": "wolf", "area_id": "starter_guildlands", "zone_id": "guildhall_crossing", "keywords": ["wolf", "dire"]}
    drafts.setdefault("items", {})["iron_sword"] = {"id": "iron_sword", "name": "Iron Sword", "vnum": 1301, "item_type": "weapon", "wear_slots": ["main_hand"], "area_id": "starter_guildlands", "zone_id": "guildhall_crossing"}
    drafts.setdefault("rooms", {})["wolf_den"] = {"id": "wolf_den", "name": "Wolf Den", "vnum": 1002, "area_id": "starter_guildlands", "zone_id": "guildhall_crossing", "exits": {"south": {"target_room_id": "guildhall_crossing_square"}}}
    ws.save_drafts("shattered_realms", drafts)

    mlist = svc.list_content(a, "mob", ["all"])
    assert mlist.ok
    assert mlist.message.count("Index VNum") == 1
    assert "   1) [1501] Dire Forest Wolf" in mlist.message
    assert "dire_forest_wolf" not in mlist.message.split("Index VNum", 1)[1]
    assert " | " not in mlist.message

    olist = svc.list_content(a, "object", ["vnum", "1301"])
    assert "1301" in olist.message and "iron_sword" in olist.message and "Iron Sword" in olist.message
    assert "1301 | iron_sword" not in olist.message

    rlist = svc.list_content(a, "room", ["vnum", "1002"])
    assert "1002" in rlist.message and "wolf_den" in rlist.message and "Wolf Den" in rlist.message
    assert "1002 | wolf_den" not in rlist.message


def test_builder_editor_discovery_resolves_vnum_to_same_session(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    svc = BuilderService(ws)
    a = actor()
    drafts = ws.load("shattered_realms")
    drafts.setdefault("entities", {})["dire_forest_wolf"] = {"id": "dire_forest_wolf", "name": "Dire Forest Wolf", "vnum": 1501, "area_id": "starter_guildlands", "zone_id": "guildhall_crossing"}
    ws.save_drafts("shattered_realms", drafts)

    opened = svc.discover_editor_target(a, "medit", ["1501"])
    assert opened.ok
    assert svc.sessions.active["builder"].object_id == "dire_forest_wolf"
    svc.sessions.end(a)

    opened = svc.discover_editor_target(a, "medit", ["id", "dire_forest_wolf"])
    assert opened.ok
    assert svc.sessions.active["builder"].object_id == "dire_forest_wolf"


def test_vnum_report_finds_free_and_cross_type_conflict(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    svc = BuilderService(ws)
    a = actor()
    drafts = ws.load("shattered_realms")
    drafts.setdefault("entities", {})["mob_a"] = {"id": "mob_a", "name": "Mob A", "vnum": 1500}
    drafts.setdefault("items", {})["item_a"] = {"id": "item_a", "name": "Item A", "vnum": 1500}
    ws.save_drafts("shattered_realms", drafts)

    free = svc.vnum_report(a, ["free", "mob"])
    assert "first free mob: 1501" in free.message
    report = svc.vnum_report(a, [])
    assert "1500(mob,object)" in report.message
