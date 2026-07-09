from pathlib import Path

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path: Path):
    rt = MudRuntime(Path.cwd(), tmp_path / "user_data")
    acct = rt.create_account("Builder", role="builder")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    return rt, cid


def out(rt: MudRuntime, cid: str, cmd: str) -> str:
    return rt.handle_input(cid, cmd)["output"]


def test_builder_draft_room_goto_and_look_use_runtime_overlay(tmp_path):
    rt, cid = make_runtime(tmp_path)
    assert "Builder mode is now ON" in out(rt, cid, "builder on")
    assert "Draft room test_room" in out(rt, cid, "rcreate test_room")
    out(rt, cid, "rname Test Room")
    out(rt, cid, "rdesc This is a test.")
    moved = out(rt, cid, "goto test_room")
    assert "You have been transferred to test_room" in moved
    assert "Test Room" in moved
    looked = out(rt, cid, "look")
    assert "Test Room" in looked
    assert "Guildhall Crossing Square" not in looked


def test_builder_dig_link_map_and_last(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "builder on")
    out(rt, cid, "rcreate test_room")
    out(rt, cid, "rname Test Room")
    dug = out(rt, cid, 'dig north north_road "North Road"')
    assert "North Road" in dug
    assert "south" in dug
    back = out(rt, cid, "goto last")
    assert "Test Room" in back
    out(rt, cid, "link north north_road")
    mapped = out(rt, cid, "map")
    assert "Current: test_room Test Room" in mapped
    assert "North: north_road North Road" in mapped


def test_normal_player_cannot_goto_draft_room(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "builder on")
    out(rt, cid, "rcreate hidden_draft")
    out(rt, cid, "rname Hidden Draft")
    acct = rt.create_account("Player", role="player")
    pcid = rt.create_character(world_id="shattered_realms", name="Player", account_id=acct["account_id"])["character_id"]
    rt.enter_world(pcid)
    denied = out(rt, pcid, "goto hidden_draft")
    assert "permission" in denied.lower()


def test_btarget_tracks_current_edit_room_and_rname_rdesc_report_target(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "builder on")
    out(rt, cid, "rcreate room_one")
    out(rt, cid, "rcreate room_two")
    target = out(rt, cid, "btarget room room_one")
    assert "Editing room: room_one" in target
    assert "Dirty: yes" in target
    renamed = out(rt, cid, "rname Room One")
    assert "Room room_one name changed" in renamed
    assert "Editing room: room_one Room One" in renamed
    described = out(rt, cid, "rdesc First room description.")
    assert "Room room_one description changed." in described
    assert "Editing room: room_one Room One" in out(rt, cid, "rstat")
    out(rt, cid, "btarget clear")
    assert "Editing room: room_two" in out(rt, cid, "rwhere")


def test_dig_ambiguous_syntax_rejected_and_quoted_name_works(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "builder on")
    out(rt, cid, "rcreate source_room")
    bad = out(rt, cid, "dig north test room three")
    assert "Usage: dig <direction> <room_id>" in bad
    good = out(rt, cid, 'dig north quoted_room "Quoted Room"')
    assert "Dug north to quoted_room." in good
    assert "Quoted Room" in good


def test_self_loop_exit_blocked_allowed_with_flag_and_validate_catches(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "builder on")
    out(rt, cid, "rcreate loop_room")
    out(rt, cid, "rname Loop Room")
    out(rt, cid, "rdesc Loop desc")
    blocked = out(rt, cid, "dig north loop_room")
    assert "Self-loop exits are blocked" in blocked
    allowed = out(rt, cid, "dig north loop_room --allow-self-loop")
    assert "Dug north to loop_room." in allowed
    validation = out(rt, cid, "builder validate")
    assert "self-loop" in validation
