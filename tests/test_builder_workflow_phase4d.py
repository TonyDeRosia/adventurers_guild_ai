from pathlib import Path
from engine.mud_runtime import MudRuntime


def make_runtime(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Builder Four", role="builder")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Builder Four", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    rt.handle_input(cid, "builder on")
    return rt, cid


def out(rt, cid, cmd):
    return rt.handle_input(cid, cmd)["output"]


def test_builder_status_rooms_rfind_and_exits(isolated_builder_world):
    rt, cid = make_runtime(isolated_builder_world)
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


def test_multiline_rdesc_end_cancel_and_redit_cycle(isolated_builder_world):
    rt, cid = make_runtime(isolated_builder_world)
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


def test_phase4d_hotfix_builder_usability(isolated_builder_world):
    rt, cid = make_runtime(isolated_builder_world)
    out(rt, cid, "rcreate testies_two")
    out(rt, cid, "rname testies")
    one = out(rt, cid, "rdesc testies room")
    assert "Description updated for currently selected room:" in one
    assert "Room: testies_two" in one
    assert "Name: testies" in one
    assert "Description: testies room" in one

    assert "Description editor" in out(rt, cid, "rdesc")
    out(rt, cid, "pending line")
    assert "cancelled" in out(rt, cid, ".cancel").lower()
    assert "No active editor session." in out(rt, cid, ".end")

    out(rt, cid, "rcreate third_room")
    direct = out(rt, cid, "rdesc room testies_two This is the second test room.")
    assert "Room: testies_two" in direct and "Description: This is the second test room." in direct
    assert "Builder Status" in direct

    suggested = out(rt, cid, "rname suggest")
    assert "Testies Two" in suggested

    typo = out(rt, cid, "builder statys")
    assert "Unknown builder command: statys." in typo
    assert "Did you mean builder status?" in typo

    mlist = out(rt, cid, "mlist")
    assert "Mob List - Mobiles" in mlist
    assert "mobiles found" in mlist
    olist = out(rt, cid, "olist")
    assert "Object List - Objects" in olist
    assert "objects found" in olist

    out(rt, cid, 'dig south south_room "South Room"')
    removed = out(rt, cid, "del dir north")
    assert "Unlinked north." in removed
    out(rt, cid, "link north testies_two")
    removed = out(rt, cid, "delete direction north")
    assert "Unlinked north." in removed

    assert "Usage: rfind <query>" in out(rt, cid, "rfind")
    rooms = out(rt, cid, "rooms draft")
    assert "ID | Name | Exits | Markers" in rooms
    assert "current location" in rooms
    assert "current edit target" in rooms

    out(rt, cid, "redit testies_two")
    assert "Editor closed" in out(rt, cid, "quit")
    out(rt, cid, "rname testies")
    validate = out(rt, cid, "builder validate")
    assert "Builder validation failed." in validate
    assert "assigned to missing area emberwood_edge" in validate
