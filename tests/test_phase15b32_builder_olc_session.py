from tests.test_phase15b22_builder_usability import setup_engine, actor


def test_medit_q_is_local_and_submenu_back_navigation(isolated_builder_world):
    e, a = setup_engine(isolated_builder_world)
    opened = e.handle_command(a, "medit 1501")
    assert opened.ok and "MEDIT 1501" in opened.narrative
    assert e.builder_service.sessions.has(a)
    sub = e.handle_command(a, "5")
    assert sub.ok and "MEDIT 1501 > Level and Attributes" in sub.narrative
    bad = e.handle_command(a, "nonsense")
    assert not bad.ok and "Unknown MEDIT option" in bad.narrative
    assert "Which command did you mean" not in bad.narrative
    root = e.handle_command(a, "q")
    assert root.ok and "MEDIT 1501" in root.narrative and "> Level" not in root.narrative
    closed = e.handle_command(a, "q")
    assert closed.ok and "Editor closed" in closed.narrative
    assert not e.builder_service.sessions.has(a)
    assert "Which command did you mean" not in closed.narrative


def test_dirty_exit_confirmation_cancel_discard_save_and_lock(isolated_builder_world):
    e, a = setup_engine(isolated_builder_world)
    assert e.handle_command(a, "medit 1501").ok
    assert e.handle_command(a, "5").ok
    assert e.handle_command(a, "level 6").ok
    assert e.handle_command(a, "back").ok
    confirm = e.handle_command(a, "q")
    assert confirm.ok and "Save changes before leaving" in confirm.narrative
    assert e.builder_service.sessions.has(a)
    cancel = e.handle_command(a, "cancel")
    assert cancel.ok and "Quit cancelled" in cancel.narrative
    sess = e.builder_service.sessions.active[e.builder_service.sessions.actor_key(a)]
    assert sess.dirty and sess.lock_key == "entities:dire_forest_wolf"
    assert e.handle_command(a, "q").ok
    discard = e.handle_command(a, "discard")
    assert discard.ok and "discarded" in discard.narrative
    assert not e.builder_service.sessions.has(a)

    assert e.handle_command(a, "medit 1501").ok
    assert e.handle_command(a, "5").ok
    assert e.handle_command(a, "level 7").ok
    assert e.handle_command(a, "back").ok
    assert "Save changes" in e.handle_command(a, "quit").narrative
    saved = e.handle_command(a, "save")
    assert saved.ok and "Editor saved, closed" in saved.narrative
    assert not e.builder_service.sessions.has(a)
    assert e.builder.load("shattered_realms")["entities"]["dire_forest_wolf"]["level"] == 7


def test_shared_root_quit_for_medit_oedit_redit(isolated_builder_world):
    e, a = setup_engine(isolated_builder_world)
    for cmd, label in [("medit 1501", "Mobile Editor"), ("oedit 1301", "Object Editor"), ("redit 1000", "Room Editor")]:
        opened = e.handle_command(a, cmd)
        assert opened.ok and label in opened.narrative
        assert e.builder_service.sessions.has(a)
        closed = e.handle_command(a, "q")
        assert closed.ok and "Editor closed" in closed.narrative
        assert not e.builder_service.sessions.has(a)
