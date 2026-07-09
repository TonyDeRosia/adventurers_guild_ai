from pathlib import Path
from engine.mud_runtime import MudRuntime
import shutil


def make_runtime(tmp_path: Path, role="builder"):
    shutil.rmtree(Path.cwd() / "worlds" / "shattered_realms" / "builder", ignore_errors=True)
    rt = MudRuntime(Path.cwd(), tmp_path / "user_data")
    acct = rt.create_account(f"Phase Four {role.title()}", role=role)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name=f"Phase Four {role.title()}", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    if role != "player":
        rt.handle_input(cid, "builder on")
    return rt, cid


def out(rt, cid, cmd):
    return rt.handle_input(cid, cmd)["output"]


def setup_area_zone(rt, cid):
    out(rt, cid, 'acreate test_area 100 110 "Test Area"')
    out(rt, cid, 'zcreate test_zone 100 110 "Test Zone"')


def test_builder_export_and_assignment_workflow(tmp_path):
    rt, cid = make_runtime(tmp_path)
    setup_area_zone(rt, cid)
    assert "Builder drafts exported safely" in out(rt, cid, "builder export")
    assert "Builder drafts exported safely" in out(rt, cid, "build export")
    out(rt, cid, "rcreate test_two")
    legacy = out(rt, cid, "rooms unassigned")
    assert "Legacy / Unassigned Rooms" in legacy and "test_two" in legacy
    assigned = out(rt, cid, "rassign test_two area current zone current vnum 101")
    assert "Room assigned:" in assigned
    assert "Current ID kept: test_two" in assigned
    assert "Room ID does not match generated convention" in assigned
    validate = out(rt, cid, "builder validate")
    assert "assigned room ID does not match generated convention" in validate


def test_rcreate_dig_duplicates_and_rmove_placeholder(tmp_path):
    rt, cid = make_runtime(tmp_path)
    setup_area_zone(rt, cid)
    created = out(rt, cid, "rcreate 101")
    assert "test_area_101" in created and "VNUM: 101" in created
    assert "VNUM 101 is already used by room test_area_101" in out(rt, cid, "rcreate 101")
    dug = out(rt, cid, 'dig north 102 "North Room"')
    assert "Area:\ntest_area" in dug and "Zone:\ntest_zone" in dug and "VNUM:\n102" in dug
    out(rt, cid, 'zcreate other_zone 103 110 "Other Zone"')
    moved = out(rt, cid, "rmove test_area_101 zone other_zone vnum 103")
    assert "Room moved:" in moved and "VNUM: 103" in moved
    assert "Room ID migration is not implemented yet" in out(rt, cid, "rrenameid test_area_101 test_area_103")


def test_normal_player_denied_builder_organization_commands(tmp_path):
    rt, cid = make_runtime(tmp_path, role="player")
    assert "permission" in out(rt, cid, "rassign here area current zone current vnum 1").lower()
