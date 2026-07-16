from types import SimpleNamespace

from engine.mud_commands import MudCommandEngine


def actor():
    return SimpleNamespace(id="builder", account_id="acct", role="builder", account_role="builder", world_id="shattered_realms", room_id="start", edit_room_id="start", current_area_id="", current_zone_id="", name="Builder", builder_zone_ids=["emberwood_edge"])


def setup_engine(isolated_builder_world):
    e = MudCommandEngine(); e.builder = isolated_builder_world.workspace
    a = actor()
    drafts = e.builder.load("shattered_realms")
    drafts["areas"] = {"emberwood": {"id":"emberwood", "name":"Emberwood", "vnum_start":1000, "vnum_end":1999, "room_vnum_start":1000, "room_vnum_end":1299}}
    drafts["zones"] = {"emberwood_edge": {"id":"emberwood_edge", "name":"Emberwood Edge", "area_id":"emberwood", "vnum_start":1000, "vnum_end":1099}}
    drafts["rooms"] = {"start": {"id":"start", "name":"Trail", "area_id":"emberwood", "zone_id":"emberwood_edge", "vnum":1000, "description":"Trail", "exits":{"north":{"target_room_id":"far"}}, "flags":[]}, "far": {"id":"far", "name":"Far Trail", "area_id":"emberwood", "zone_id":"emberwood_edge", "vnum":1001, "description":"Far", "exits":{}, "flags":["outdoors"]}}
    drafts["entities"] = {"dire_forest_wolf": {"id":"dire_forest_wolf", "name":"Dire Forest Wolf", "vnum":1501, "level":4, "area_id":"emberwood", "zone_id":"emberwood_edge", "keywords":["wolf"], "description":"A wolf.", "body_profile_id":"wolf", "combat_profile":{"natural_weapons":[{"id":"bite"}]}, "ai_profile_id":"wolf_ai"}, "young_forest_wolf": {"id":"young_forest_wolf", "name":"Young Forest Wolf", "vnum":1505, "level":2, "area_id":"emberwood", "zone_id":"emberwood_edge"}}
    drafts["items"] = {"ash_sword": {"id":"ash_sword", "name":"Ash Sword", "vnum":1301, "item_type":"weapon", "wear_slots":["wield"], "area_id":"emberwood", "zone_id":"emberwood_edge", "keywords":["sword"], "description":"A sword."}}
    e.builder.save_drafts("shattered_realms", drafts)
    return e, a


def out(e, a, cmd):
    res = e.handle_command(a, cmd)
    assert res.ok, res.narrative
    return res.narrative


def test_phase15b22_mlist_olist_aligned_and_location_from_room(isolated_builder_world):
    e, a = setup_engine(isolated_builder_world)
    text = out(e, a, "mlist")
    assert "Mob List" in text
    assert "Area : Emberwood" in text
    assert "Zone : Emberwood Edge" in text
    assert "VNUM" in text and "ID" in text and "Lvl" in text
    assert "1501" in text and "dire_forest_wolf" in text
    assert "Missing keywords" in out(e, a, "mlist incomplete")
    otext = out(e, a, "olist")
    assert "Object List" in otext and "ash_sword" in otext and "weapon" in otext and "wield" in otext


def test_phase15b22_alist_zlist_service_format(isolated_builder_world):
    e, a = setup_engine(isolated_builder_world)
    alist = out(e, a, "alist")
    assert "Area List" in alist and "Area name" in alist and "Emberwood" in alist
    zlist = out(e, a, "zlist")
    assert "Zone List" in zlist and "VNUM range" in zlist and "Emberwood Edge" in zlist


def test_phase15b22_editor_picker_and_open_by_vnum_id_search(isolated_builder_world):
    e, a = setup_engine(isolated_builder_world)
    picker = e.handle_command(a, "medit wolf").narrative
    assert "MEDIT choices" in picker and "Choose one; do not guess" in picker
    assert e.handle_command(a, "medit dire_forest_wolf").ok
    assert "Mobile Editor" in e.handle_command(a, "medit 1501").narrative
