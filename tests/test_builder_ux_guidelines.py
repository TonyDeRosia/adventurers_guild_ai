from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor():
    return SimpleNamespace(id="ux_builder", name="UX", role="admin", account_role="admin", account_id="acct", session_id="sess", world_id="shattered_realms")


def svc(tmp_path):
    return BuilderService(BuilderWorkspace(tmp_path / "worlds"))


def open_medit(s):
    a = actor()
    res = s.start_editor(a, "medit", "entities", "ux_guard")
    assert res.ok
    return a, s.sessions.active[s.sessions.actor_key(a)]


def test_medit_contextual_help_values_and_search(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    out = s.handle_session_input(a, sess, "?").message
    assert "Builder Help" in out and "quickbuild guard" in out
    out = s.handle_session_input(a, sess, "help dragon").message
    assert "Guided Authoring: Dragon" in out and "Recommended classification" in out
    s.handle_session_input(a, sess, "1")
    prompt = s.handle_session_input(a, sess, "4").message
    assert "Creature Classification" in prompt and "Runtime Usage" in prompt
    values = s.handle_session_input(a, sess, "list").message
    assert "Legal Values" in values and "guard" in values


def test_guided_quickbuild_save_validation_and_undo_redo(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    menu = s.handle_session_input(a, sess, "quickbuild list").message
    assert "What are you creating?" in menu and "Merchant" in menu
    applied = s.handle_session_input(a, sess, "quickbuild guard").message
    assert "Guided defaults applied for guard" in applied
    assert sess.working_record["resources"]["health"] == 75
    undo = s.handle_session_input(a, sess, "undo").message
    assert "undo applied" in undo.lower()
    redo = s.handle_session_input(a, sess, "redo").message
    assert "redo applied" in redo.lower()
    save = s.handle_session_input(a, sess, "save").message
    assert "Saved successfully" in save and "You are still inside the editor" in save


def test_invalid_input_is_educational(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    bad = s.handle_session_input(a, sess, "mageboss").message
    assert '"mageboss" was not accepted' in bad
    assert "Type ? for help" in bad
