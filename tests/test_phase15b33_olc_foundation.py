import sqlite3


def _make_builder(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Phase Builder", role="owner")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid, session_id="phase15b33")
    rt.handle_input(cid, "builder on")
    return rt, cid


def _out(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def _history(rt, cid):
    with sqlite3.connect(rt.state_store.db_path) as con:
        return [r[0] for r in con.execute("SELECT command FROM command_history WHERE character_id=? ORDER BY id", (cid,))]


def test_medit_numbered_level_prompt_dirty_undo_redo_and_local_routing(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "Mobile Editor" in _out(rt, cid, "medit 1501")
    assert "Attributes" in _out(rt, cid, "5")
    prompt = _out(rt, cid, "1")
    assert "Current level" in prompt and "Enter new level" in prompt
    changed = _out(rt, cid, "3")
    assert "Level changed" in changed
    assert "1. Level" in changed and ": 3" in changed
    assert "Draft status: modified" in changed
    undone = _out(rt, cid, "u")
    assert "Session undo applied" in undone and "Draft status: clean" in undone
    redone = _out(rt, cid, "r")
    assert "Session redo applied" in redone and ": 3" in redone
    assert "Which command did you mean" not in _out(rt, cid, "not_a_game_command")
    assert all(cmd not in _history(rt, cid) for cmd in ["5", "1", "3", "u", "r", "not_a_game_command"])


def test_medit_multiline_cancel_save_and_flag_toggle(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "Mobile Editor" in _out(rt, cid, "medit 1501")
    assert "Descriptions" in _out(rt, cid, "3")
    assert "Multiline text editor" in _out(rt, cid, "1")
    assert "Line 1 added" in _out(rt, cid, "Temporary description line")
    assert "1: Temporary description line" in _out(rt, cid, ".show")
    cancelled = _out(rt, cid, "cancel")
    assert "Text edit cancelled" in cancelled and "Temporary description line" not in cancelled
    assert "Multiline text editor" in _out(rt, cid, "1")
    _out(rt, cid, "Saved description line")
    saved = _out(rt, cid, ".save")
    assert "Text saved" in saved and "Draft status: modified" in saved
    root = _out(rt, cid, "q")
    assert "Mobile Editor" in root
    flags = _out(rt, cid, "10")
    assert "Mobile Flags" in flags
    assert "SENTINEL" in _out(rt, cid, "1")
    toggled = _out(rt, cid, "1")
    assert "Flag selection updated" in toggled and "[X]" in toggled
    undone = _out(rt, cid, "u")
    assert "Session undo applied" in undone


def test_medit_reference_selector_and_keyword_list_duplicate_cancel(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "Mobile Editor" in _out(rt, cid, "medit 1501")
    assert "Keywords" in _out(rt, cid, "2")
    assert "list editor" in _out(rt, cid, "1")
    added = _out(rt, cid, "add phase15b33")
    assert "List updated" in added and "phase15b33" in added
    assert "Duplicate list value rejected" in _out(rt, cid, "add phase15b33")
    assert "Keywords" in _out(rt, cid, "back")
    assert "Mobile Editor" in _out(rt, cid, "q")
    assert "Body profile" in _out(rt, cid, "8")
    selector = _out(rt, cid, "1")
    assert "Body profile selector" in selector and "wolf" in selector
    assert "does not exist" in _out(rt, cid, "no_such_profile")
    selected = _out(rt, cid, "wolf")
    assert "Reference updated" in selected or "unchanged" in selected


def test_oedit_and_redit_share_numbered_foundation(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "Object Editor" in _out(rt, cid, "oedit 1300")
    fields = _out(rt, cid, "1")
    assert "Keywords list editor" in fields
    name_result = _out(rt, cid, "add training")
    assert "List updated" in name_result or "Duplicate list value rejected" in name_result
    _out(rt, cid, "q")
    _out(rt, cid, "q")
    _out(rt, cid, "d")
    redit_out = _out(rt, cid, "redit 1000")
    assert "Room Editor" in redit_out or "Currently editing:" in redit_out
    rfields = _out(rt, cid, "1")
    assert "Current room name" in rfields and "Enter new room name" in rfields
    invalid = _out(rt, cid, "   ")
    assert "blank input is not accepted" in invalid or invalid == ""
