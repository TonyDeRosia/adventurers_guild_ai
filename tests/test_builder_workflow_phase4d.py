from pathlib import Path
from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path: Path):
    rt = MudRuntime(Path.cwd(), tmp_path / "user_data")
    acct = rt.create_account("Builder Four", role="builder")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Builder Four", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    rt.handle_input(cid, "builder on")
    return rt, cid


def out(rt, cid, cmd):
    return rt.handle_input(cid, cmd)["output"]


def test_builder_status_rooms_rfind_and_exits(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "rcreate alpha_room")
    out(rt, cid, "rname Alpha Room")
    out(rt, cid, 'dig north beta_room "Beta Room"')
    status = out(rt, cid, "bstatus")
    assert "Builder Mode" in status and "Editing room: beta_room" in status
    rooms = out(rt, cid, "rooms draft")
    assert "Draft Rooms" in rooms and "alpha_room" in rooms and "Current location:" in rooms
    found = out(rt, cid, "rfind beta")
    assert "beta_room" in found and "Beta Room" in found
    exits = out(rt, cid, "exits")
    assert "South -> alpha_room" in exits and "North -> none" in exits
    inspected = out(rt, cid, "x exit south")
    assert "Direction:\nSouth" in inspected and "Destination:\nalpha_room" in inspected and "Status:\nValid" in inspected


def test_multiline_rdesc_end_cancel_and_redit_cycle(tmp_path):
    rt, cid = make_runtime(tmp_path)
    out(rt, cid, "rcreate first_phase4d")
    out(rt, cid, "rcreate second_phase4d")
    assert "Description editor" in out(rt, cid, "rdesc")
    out(rt, cid, "The room is warm.")
    out(rt, cid, "A fireplace burns brightly.")
    done = out(rt, cid, ".end")
    assert "Updated room:" in done and "second_phase4d" in done
    assert "Description editor" in out(rt, cid, "rdesc")
    cancelled = out(rt, cid, ".cancel")
    assert "cancelled" in cancelled.lower()
    prev = out(rt, cid, "redit first_phase4d")
    assert "Room: first_phase4d" in prev
