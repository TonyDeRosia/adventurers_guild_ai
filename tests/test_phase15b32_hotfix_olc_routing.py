import sqlite3


def _make_builder(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Phase Hotfix Builder", role="owner")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Hotfix Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid, session_id="phase15b32-hotfix")
    rt.handle_input(cid, "builder on")
    return rt, cid


def _out(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def _history(rt, cid):
    with sqlite3.connect(rt.state_store.db_path) as con:
        return [r[0] for r in con.execute("SELECT command FROM command_history WHERE character_id=? ORDER BY id", (cid,))]


def test_root_q_routes_through_production_input_path_and_closes_clean_editor(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    opened = _out(rt, cid, "medit 1501")
    assert "Mobile Editor" in opened
    char = rt.active_characters[cid]
    assert rt.command_engine.builder_service.sessions.has(char)

    closed = _out(rt, cid, "q")

    assert "Which command did you mean?" not in closed
    assert "Goodbye" not in closed
    assert "Editor closed and lock released" in closed
    assert cid in rt.active_characters
    assert not rt.command_engine.builder_service.sessions.has(char)
    assert "q" not in _history(rt, cid)
    assert "Guildhall" in _out(rt, cid, "look")


def test_uppercase_q_and_full_quit_are_local_while_editor_active(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "Mobile Editor" in _out(rt, cid, "medit 1501")
    closed = _out(rt, cid, "Q")
    assert "Which command did you mean?" not in closed
    assert "Editor closed and lock released" in closed
    assert cid in rt.active_characters

    assert "Mobile Editor" in _out(rt, cid, "medit 1501")
    closed = _out(rt, cid, "quit")
    assert "Which command did you mean?" not in closed
    assert "Editor closed and lock released" in closed
    assert cid in rt.active_characters
    hist = _history(rt, cid)
    assert "Q" not in hist
    assert "quit" not in hist


def test_submenu_q_returns_to_root_and_unknown_alpha_is_local(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    assert "Mobile Editor" in _out(rt, cid, "medit 1501")
    submenu = _out(rt, cid, "5")
    assert "MEDIT" in submenu and "Attributes" in submenu
    root = _out(rt, cid, "q")
    assert "Which command did you mean?" not in root
    assert "Mobile Editor" in root
    assert "Commands: level <n>" not in root

    unknown = _out(rt, cid, "quest")
    assert "Which command did you mean?" not in unknown
    assert "Invalid editor input" in unknown
    assert rt.command_engine.builder_service.sessions.has(rt.active_characters[cid])
    hist = _history(rt, cid)
    assert "5" not in hist
    assert "q" not in hist
    assert "quest" not in hist


def test_global_q_unchanged_without_active_editor(isolated_builder_world):
    rt, cid = _make_builder(isolated_builder_world)
    output = _out(rt, cid, "q")
    assert "Which command did you mean? quaff, quest, questlog, quests, quit" in output
    assert "q" in _history(rt, cid)
