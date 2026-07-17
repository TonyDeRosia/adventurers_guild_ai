def _make_builder(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Phase Builder", role="owner")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid, session_id="phase15b43-redit")
    rt.handle_input(cid, "builder on")
    return rt, cid


def _out(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def test_redit_adventurers_lair_style_menu_and_routes(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    menu = _out(rt, cid, "redit guildhall_crossing_square")
    assert "-- Room number:" in menu
    assert "Room zone:" in menu
    assert "1) Name" in menu
    assert "2) Description" in menu
    assert "3) Room flags" in menu
    assert "4) Sector type" in menu
    for text in ["5) Exit north", "6) Exit east", "7) Exit south", "8) Exit west", "9) Exit up", "A) Exit down"]:
        assert text in menu
    assert "F) Extra descriptions menu" in menu
    assert "R) Room Resets" in menu
    assert "S) Script" in menu
    assert "W) Copy Room" in menu
    assert "X) Delete Room" in menu
    assert "Q) Quit" in menu

    assert "new room name" in _out(rt, cid, "1").lower()
    changed = _out(rt, cid, "Edited Crossing Square")
    assert "Room name changed" in changed
    assert "Draft status : modified" in changed
    assert "Room reset editing is not yet available" in _out(rt, cid, "r")
    assert "-- Exit down for room guildhall_crossing_square" in _out(rt, cid, "a")
    assert "4) Sector type" in _out(rt, cid, "q")
    assert "You have unsaved room changes" in _out(rt, cid, "q")
    assert "Continue editing" in _out(rt, cid, "c")
    assert rt.command_engine.builder_service.sessions.has(rt.active_characters[cid])


def test_redit_description_flags_sector_copy_delete_and_save(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "-- Room number:" in _out(rt, cid, "redit guildhall_crossing_square")
    assert "Multiline text editor" in _out(rt, cid, "2")
    assert "Line 1 added" in _out(rt, cid, "Line one")
    assert "Line 2 added" in _out(rt, cid, "Line two")
    assert "Text saved." in _out(rt, cid, ".save")
    flags = _out(rt, cid, "3")
    assert "Room flags" in flags and "INDOORS" in flags
    assert "Flag selection updated" in _out(rt, cid, "3")
    assert "4) Sector type" in _out(rt, cid, "q")
    assert "sector/terrain" in _out(rt, cid, "4")
    assert "Sector/terrain changed" in _out(rt, cid, "forest")
    assert "Copy room" in _out(rt, cid, "w")
    dest = "phase15b43_copy_room"
    assert "Type COPY ROOM" in _out(rt, cid, dest)
    copied = _out(rt, cid, "COPY ROOM")
    assert f"Copied room draft {dest}" in copied
    assert "Delete room safety check" in _out(rt, cid, "x")
    assert "Delete room cancelled" in _out(rt, cid, "q")
    assert "You have unsaved room changes" in _out(rt, cid, "q")
    saved = _out(rt, cid, "s")
    assert "Draft rooms guildhall_crossing_square updated" in saved
    assert not rt.command_engine.builder_service.sessions.has(rt.active_characters[cid])
    reopened = _out(rt, cid, "redit guildhall_crossing_square")
    assert "Line one" in reopened and "FOREST" not in reopened
    assert "Forest" in reopened
