from tests.test_phase15b43_redit_menu import _make_builder, _out


def test_redit_extra_description_add_edit_copy_move_delete_save_and_runtime(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "-- Room number:" in _out(rt, cid, "redit guildhall_crossing_square")
    screen = _out(rt, cid, "f")
    assert "-- Room Extra Descriptions:" in screen
    assert "A) Add" in screen and "Q) Back" in screen
    assert "I do not understand" not in _out(rt, cid, "look")

    assert "Enter one or more keywords" in _out(rt, cid, "a")
    assert "Enter at least one" in _out(rt, cid, "!!!")
    assert "multiline description" in _out(rt, cid, "  Mural   Painting mural WALL ")
    assert "Line 1 added" in _out(rt, cid, "A faded mural depicts the city founding.")
    added = _out(rt, cid, ".save")
    assert "Extra description added" in added
    assert "Entry 1 of 1" in added
    assert "mural painting wall" in added

    assert "replacement keywords" in _out(rt, cid, "1")
    changed = _out(rt, cid, "Board bulletin NOTICE board")
    assert "Extra description keywords changed" in changed
    assert "board bulletin notice" in changed
    assert "Multiline text editor" in _out(rt, cid, "2")
    _out(rt, cid, "A large bulletin board is mounted here.")
    _out(rt, cid, "Fresh notices overlap older parchment.")
    desc = _out(rt, cid, ".save")
    assert "Fresh notices overlap older parchment." in desc

    copied = _out(rt, cid, "c")
    assert "Extra description copied" in copied and "Entry 2 of 2" in copied
    assert "Previous description: Available" in copied
    assert "Entry 1 of 2" in _out(rt, cid, "3")
    assert "Entry 2 of 2" in _out(rt, cid, "4")
    assert "Room Extra Descriptions" in _out(rt, cid, "q")
    assert "Extra descriptions reordered" in _out(rt, cid, "move 2 up")
    assert "Delete extra description" in _out(rt, cid, "delete 1")
    assert "Type DELETE DESCRIPTION" in _out(rt, cid, "delete")
    cancelled = _out(rt, cid, "q")
    assert "Delete cancelled" in cancelled
    assert "Delete extra description" in _out(rt, cid, "delete 1")
    deleted = _out(rt, cid, "DELETE DESCRIPTION")
    assert "Extra description deleted" in deleted
    assert "Room Extra Descriptions" in deleted
    assert "4) Sector type" in _out(rt, cid, "q")
    assert "You have unsaved room changes" in _out(rt, cid, "q")
    assert "Draft rooms guildhall_crossing_square updated" in _out(rt, cid, "s")

    reopened = _out(rt, cid, "redit guildhall_crossing_square")
    assert "Extra descriptions menu" in reopened
    assert "board bulletin notice" in _out(rt, cid, "f")
    _out(rt, cid, "q")
    _out(rt, cid, "q")
    _out(rt, cid, "discard")
    look = _out(rt, cid, "look board")
    assert "A large bulletin board is mounted here." in look
    assert "Fresh notices overlap older parchment." in look
    assert "A large bulletin board is mounted here." in _out(rt, cid, "examine NOTICE")


def test_redit_extra_description_cancel_and_validation(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    _out(rt, cid, "redit guildhall_crossing_square")
    _out(rt, cid, "f")
    assert "Enter one or more keywords" in _out(rt, cid, "add")
    assert "Keyword edit cancelled" in _out(rt, cid, "q")
    assert "Room Extra Descriptions" in _out(rt, cid, "f")
    assert "- none" in _out(rt, cid, "list")
