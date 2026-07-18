from types import SimpleNamespace

from smart_mud.builder import BuilderService, BuilderWorkspace


def actor():
    return SimpleNamespace(id="phase16b", name="Phase", role="admin", account_role="admin", account_id="acct", session_id="sess", world_id="shattered_realms")


def open_session(tmp_path):
    s = BuilderService(BuilderWorkspace(tmp_path / "worlds")); a = actor()
    res = s.start_editor(a, "medit", "entities", "apprentice_mage_lina")
    assert res.ok
    return s, a, s.sessions.active[s.sessions.actor_key(a)]


def test_identity_menu_visible_guidance_and_field_bindings(tmp_path):
    s, a, sess = open_session(tmp_path)
    main = s.render_session(sess)
    assert "1. Identity" in main and "Name, species, classification, size, role, and Builder state." in main
    identity = s.handle_session_input(a, sess, "1").message
    assert "BIOLOGICAL / PHYSICAL IDENTITY" in identity
    assert "Species / Race" in identity and "Biological or lore race" in identity
    assert "Size" in identity and "Physical scale" in identity
    assert "Creature Classification" in identity and "Broad biological category" in identity
    assert "NPC Role" in identity and "Gameplay role/function" in identity
    assert "Enabled" in identity and "Yes means" in identity
    assert "True" not in identity and "False" not in identity


def test_identity_pickers_and_boolean_inputs(tmp_path):
    s, a, sess = open_session(tmp_path)
    s.handle_session_input(a, sess, "1")
    species = s.handle_session_input(a, sess, "4").message
    assert "Species / Race" in species and "Existing/common choices" in species and "custom <name>" in species
    s.handle_session_input(a, sess, "back")
    classification = s.handle_session_input(a, sess, "7").message
    assert "1. Humanoid" in classification and "People-shaped living creatures" in classification
    bad = s.handle_session_input(a, sess, "notaclass").message
    assert "not a known value for Creature Classification" in bad and "Choose a displayed number/name" in bad
    s.handle_session_input(a, sess, "back")
    size = s.handle_session_input(a, sess, "6").message
    assert "1. Tiny" in size and "Physical scale" in size and "Current:" in size
    assert s.handle_session_input(a, sess, "2").ok
    enabled = s.handle_session_input(a, sess, "9").message
    assert "Enabled Status" in enabled and "1. Yes" in enabled and "2. No" in enabled
    assert s.handle_session_input(a, sess, "off").ok
    assert sess.working_record["enabled"] is False


def test_wrong_context_and_save_confirmation(tmp_path):
    s, a, sess = open_session(tmp_path)
    s.handle_session_input(a, sess, "1")
    medit = s.handle_session_input(a, sess, "medit 1500").message
    assert "edit session is already active" in medit and "switch <mobile id>" in medit
    mlist = s.handle_session_input(a, sess, "mlist all").message
    assert "read-only mobile-list world command" in mlist and "keeps your draft open" in mlist
    s.handle_session_input(a, sess, "1")
    s.handle_session_input(a, sess, "Apprentice Mage Lina")
    save = s.handle_session_input(a, sess, "save").message
    assert "Saved successfully." in save and "Draft revision:" in save and "Unsaved changes:\nNo" in save
    assert "You remain in:\nMEDIT > Identity" in save
