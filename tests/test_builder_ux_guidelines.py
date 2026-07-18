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


def test_professional_field_prompts_include_full_inline_education(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    s.handle_session_input(a, sess, "4")
    prompt = s.handle_session_input(a, sess, "1").message
    assert "Species" in prompt
    assert "What It Is" in prompt
    assert "Why It Exists" in prompt
    assert "Runtime Usage" in prompt
    assert "Common Values" in prompt and "dragon" in prompt
    assert "Recommended" in prompt
    assert "Examples" in prompt and "Skeleton Warrior" in prompt
    assert "Related Fields" in prompt and "Body Profile" in prompt
    assert "Required" in prompt and "Affects Publishing" in prompt and "Inherited" in prompt
    assert "Safe Commands" in prompt and "inspect" in prompt


def test_enum_prompts_show_selectable_values_and_invalid_input_teaches(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    s.handle_session_input(a, sess, "1")
    prompt = s.handle_session_input(a, sess, "4").message
    assert "Creature Classification" in prompt
    assert "Legal Values" in prompt and "1." in prompt and "guard" in prompt
    bad = s.handle_session_input(a, sess, "dragonman").message
    assert '"dragonman" is not a known value for Creature Classification' in bad
    assert "Try list to view supported values" in bad


def test_inspector_search_and_world_command_recovery_are_contextual(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    s.handle_session_input(a, sess, "4")
    s.handle_session_input(a, sess, "1")
    inspect = s.handle_session_input(a, sess, "inspect").message
    assert "Inspector" in inspect
    assert "Current value" in inspect
    assert "Runtime effect" in inspect
    assert "Validation state" in inspect
    assert "Publish status" in inspect
    search = s.handle_session_input(a, sess, "back").message
    search = s.handle_session_input(a, sess, "search dragon").message
    assert 'Builder Search: "dragon"' in search and "Species" in search
    recovery = s.handle_session_input(a, sess, "look").message
    assert "world command" in recovery
    assert "currently editing" in recovery
    assert "save — save the draft" in recovery


def test_headers_footers_status_and_aligned_section_rows(tmp_path):
    s = svc(tmp_path); a, sess = open_medit(s)
    main = s.render_session(sess)
    assert "Builder Status" in main
    assert "Mode: MEDIT / main menu / main_menu" in main
    assert "Commands" in main and "preview Preview" in main and "save Save" in main
    section = s.handle_session_input(a, sess, "5").message
    assert "MEDIT ux_guard > Attributes" in section
    assert "Fields show purpose" in section
    assert " 1. Level" in section
    assert "Overall challenge and progression tier" in section
    assert "Commands" in section and "validate Validate" in section
