import shutil
from pathlib import Path
from types import SimpleNamespace

from engine.mud_commands import MudCommandEngine
from engine.mud_runtime import MudRuntime
from smart_mud.builder import BuilderWorkspace
from smart_mud.world_registry import WorldRegistry

ROOT = Path(__file__).resolve().parents[1]
PACK = "starter_guildlands_content_pack_v1.json"


def actor(role="builder"):
    return SimpleNamespace(
        id="builder",
        account_id="acct",
        role=role,
        account_role=role,
        world_id="shattered_realms",
        room_id="guildhall_crossing_square",
        edit_room_id="guildhall_crossing_square",
        current_area_id="starter_guildlands",
        current_zone_id="guildhall_crossing",
        name="Builder",
    )


def engine_with_pack(isolated_builder_world):
    bw = isolated_builder_world.workspace
    a = actor()
    assert bw.template_copy(a, PACK, "pack.json").ok
    assert bw.import_apply(a, "pack.json").ok
    engine = MudCommandEngine()
    engine.builder = bw
    return engine, a


def text(engine, a, command):
    return engine.handle_command(a, command).narrative


def runtime_with_pack(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Runtime Builder", role="builder")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Runtime Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    rt.handle_input(cid, "builder on")
    char = rt.state_store.load_character(cid)
    assert char is not None
    assert rt.builder.template_copy(char, PACK, "pack.json").ok
    assert rt.builder.import_apply(char, "pack.json").ok
    return rt, cid


def runtime_text(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def test_alist_defaults_current_and_all_and_id(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    default = text(engine, a, "alist")
    assert "starter_guildlands" in default
    assert 'Use "alist all" to list all areas.' in default
    all_text = text(engine, a, "alist all")
    assert "ID | Name | Range | Rooms | Zones | Source | Current" in all_text
    detail = text(engine, a, "alist starter_guildlands")
    assert "Area detail:" in detail
    assert "room_vnum_start-room_vnum_end" in detail


def test_zlist_local_all_area_zone_and_range(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    default = text(engine, a, "zlist")
    assert "guildhall_crossing" in default
    assert "rat_cellar" not in default  # current shows current zone detail only
    all_text = text(engine, a, "zlist all")
    assert "guildhall_crossing" in all_text and "rat_cellar" in all_text
    area_text = text(engine, a, "zlist area starter_guildlands")
    assert "guildhall_crossing" in area_text and "rat_cellar" in area_text
    zone_detail = text(engine, a, "zlist guildhall_crossing")
    assert "Zone detail:" in zone_detail and "room_ids count:" in zone_detail
    rng = text(engine, a, "zlist 1000-1029")
    assert "guildhall_crossing" in rng and "registrar_hall" not in rng


def test_rlist_and_rooms_filters_and_errors(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    default = text(engine, a, "rlist")
    assert "Rooms in zone guildhall_crossing" in default
    assert "guildhall_crossing_square" in default
    assert "starter_guildlands_1031" not in default
    assert "starter_guildlands_1031" in text(engine, a, "rlist all")
    assert "starter_guildlands_1031" not in text(engine, a, "rlist zone guildhall_crossing")
    area = text(engine, a, "rlist area starter_guildlands")
    assert "guildhall_crossing_square" in area and "starter_guildlands_1031" in area
    rng = text(engine, a, "rooms 1000 1029")
    assert "guildhall_crossing_square" in rng and "starter_guildlands_1031" not in rng
    one = text(engine, a, "rlist 1000")
    assert "guildhall_crossing_square" in one
    assert "Invalid range: start must be less than or equal to end." in text(engine, a, "rlist 1099-1000")
    assert "Invalid range" in text(engine, a, "rlist 1000-east")
    assert text(engine, a, "rooms").splitlines()[0] == default.splitlines()[0]


def test_runtime_rlist_and_rooms_filters_use_active_drafts_after_import(isolated_builder_world):
    rt, cid = runtime_with_pack(isolated_builder_world)

    alist = runtime_text(rt, cid, "alist all")
    assert "starter_guildlands" in alist
    assert " | 70 | " in alist

    zlist = runtime_text(rt, cid, "zlist all")
    assert "guildhall_crossing" in zlist
    assert "rat_cellar" in zlist

    zone_rooms = runtime_text(rt, cid, "rlist zone guildhall_crossing")
    assert "Rooms in zone guildhall_crossing" in zone_rooms
    assert "guildhall_crossing_square" in zone_rooms
    assert "starter_guildlands_1031" not in zone_rooms

    area_rooms = runtime_text(rt, cid, "rooms area starter_guildlands")
    assert "guildhall_crossing_square" in area_rooms
    assert "starter_guildlands_1031" in area_rooms

    ranged = runtime_text(rt, cid, "rlist 1000-1029")
    assert "guildhall_crossing_square" in ranged
    assert "starter_guildlands_1031" not in ranged

    assert "Invalid range: start must be less than or equal to end." in runtime_text(rt, cid, "rlist 1099-1000")
    assert "Invalid range. Usage:" in runtime_text(rt, cid, "rlist 1000-east")


def test_rooms_legacy_large_warning_and_placeholders(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    drafts = engine.builder.load("shattered_realms")
    drafts["rooms"]["legacy_room"] = {"id": "legacy_room", "name": "Legacy", "exits": {}, "area_id": "", "zone_id": "", "vnum": None}
    engine.builder.save_drafts("shattered_realms", drafts)
    assert "legacy_room" in text(engine, a, "rooms unassigned")
    assert "Large listing:" in text(engine, a, "rlist all")
    mlist = text(engine, a, "mlist")
    assert "Current zone: guildhall_crossing" in mlist and "mlist 1500-1599" in mlist
    olist = text(engine, a, "olist")
    assert "Current zone: guildhall_crossing" in olist and "olist 1300-1399" in olist
