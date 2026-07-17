from tests.test_phase15b43_redit_menu import _make_builder, _out


def test_redit_all_exit_editors_and_destination_keywords_description(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "-- Room number:" in _out(rt, cid, "redit guildhall_crossing_square")
    for choice, direction in [("5","north"),("q",""),("6","east"),("q",""),("7","south"),("q",""),("8","west"),("q",""),("9","up"),("q",""),("A","down")]:
        out = _out(rt, cid, choice)
        if direction:
            assert f"-- Exit {direction} for room guildhall_crossing_square" in out
            assert "1) Destination" in out and "R) Repair Reverse Exit" in out
    assert "4) Sector type" in _out(rt, cid, "q")
    assert "-- Exit north" in _out(rt, cid, "5")
    assert "Enter destination" in _out(rt, cid, "1")
    changed = _out(rt, cid, "emberwood_hunting_trail")
    assert "Exit destination changed" in changed
    assert "Reverse status" in changed
    assert "Multiline text editor" in _out(rt, cid, "2")
    assert "Line 1 added" in _out(rt, cid, "A narrow trail leads onward.")
    assert "Text saved." in _out(rt, cid, ".save")
    assert "Enter space-separated" in _out(rt, cid, "3")
    assert "Exit keywords changed" in _out(rt, cid, "door gate archway")


def test_room_link_commands_drafts_only(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    out = _out(rt, cid, 'rdig north phase15b45_north "Phase North"')
    assert "Dug north" in out and "phase15b45_north south ->" in out
    links = _out(rt, cid, "rlinks phase15b45_north")
    assert "Outbound exits" in links and "south" in links
    rt.handle_input(cid, "goto guildhall_crossing_square")
    assert "Relinked existing exit destination" in _out(rt, cid, "relink north emberwood_hunting_trail")
    undug = _out(rt, cid, "undig north")
    assert "Removed exit" in undug
    assert "No north exit" in _out(rt, cid, "dig north -1")
