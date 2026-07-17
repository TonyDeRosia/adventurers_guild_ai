from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace, MobileTemplate


def actor(name="Tony", role="admin"):
    return SimpleNamespace(id=name.lower(), name=name, account_id="acct", session_id="sess", role=role, world_id="test_world")


def service(tmp_path):
    s = BuilderService(BuilderWorkspace(tmp_path))
    a = actor()
    s.workspace.ensure("test_world")
    drafts = s.workspace.load("test_world")
    drafts["body_profiles"]["bear"] = {"id":"bear","capabilities":["claw","bite","maul"],"size":"large","limbs":["foreleg","jaw"],"natural_armor":2,"movement_modes":["walk"],"suggested_natural_weapon_ids":["bear_claw","bear_bite","bear_maul"]}
    drafts["natural_weapon_profiles"]["bear_claw"] = {"id":"bear_claw","family":"claw","noun":"claws","verb":"claws","weight":60,"damage_dice":"1d8","damage_type":"slashing"}
    drafts["natural_weapon_profiles"]["bear_bite"] = {"id":"bear_bite","family":"bite","noun":"bite","verb":"bites","weight":25,"damage_dice":"1d8","damage_type":"piercing"}
    drafts["natural_weapon_profiles"]["bear_maul"] = {"id":"bear_maul","family":"maul","noun":"maul","verb":"mauls","weight":15,"damage_dice":"2d6","damage_type":"bludgeoning"}
    drafts["entities"]["ashback_bear"] = {"id":"ashback_bear","name":"Ashback Bear","description":"A bear waits.","_builder_revision":0}
    s.workspace.save_drafts("test_world", drafts)
    return s, a


def test_scratch_save_discard_quit_and_resident_testspawn(tmp_path):
    s, a = service(tmp_path)
    assert s.start_editor(a, "medit", "entities", "ashback_bear").ok
    assert s.sessions.handle(a, "name Ashback Bear Draft").ok
    assert s.workspace.load("test_world")["entities"]["ashback_bear"]["name"] == "Ashback Bear"
    assert s.sessions.handle(a, "body bear").ok
    preview = s.sessions.handle(a, "preview")
    assert preview.ok
    mob = preview.data["runtime_projection"]
    families = {w["mechanical_family"] for w in mob["combat_profile"]["natural_weapons"]}
    assert {"claw", "bite", "maul"} <= families
    assert "fist" not in families and "punch" not in families
    assert s.sessions.handle(a, "save").ok
    assert s.workspace.load("test_world")["entities"]["ashback_bear"]["name"] == "Ashback Bear Draft"
    assert s.sessions.handle(a, "quit").message.startswith("Editor closed")


def test_session_natural_weapon_edits_are_scratch_until_save_and_quit_prompts(tmp_path):
    s, a = service(tmp_path)
    assert s.start_editor(a, "medit", "entities", "ashback_bear").ok
    assert s.sessions.handle(a, "7").ok
    assert s.sessions.handle(a, "add bear_claw").ok
    stored = s.workspace.load("test_world")["entities"]["ashback_bear"]
    assert not (stored.get("combat_profile") or {}).get("natural_weapons")
    quit_msg = s.sessions.handle(a, "quit").message
    assert "Save, Discard, or Cancel" in quit_msg
    assert s.sessions.handle(a, "cancel").ok
    assert s.sessions.handle(a, "undo").ok
    assert not (s.sessions.active[s.sessions.actor_key(a)].working_record.get("combat_profile") or {}).get("natural_weapons")
    assert s.sessions.handle(a, "redo").ok
    assert s.sessions.handle(a, "save").ok
    stored = s.workspace.load("test_world")["entities"]["ashback_bear"]
    assert (stored.get("combat_profile") or {}).get("natural_weapons")


def test_canonical_adapter_and_generation_activation_rollback(tmp_path):
    s, a = service(tmp_path)
    legacy = {"id":"wolf","name":"Wolf","natural_attacks":[{"id":"fangs","family":"bite","noun":"fangs","verb":"bites","selection_weight":100}]}
    canon = MobileTemplate.from_legacy(legacy).to_canonical_dict()
    assert "natural_attacks" not in canon
    assert canon["combat_profile"]["natural_weapons"][0]["mechanical_family"] == "bite"
    assert s.acquire_lock(a, "entities", "ashback_bear").ok
    assert s.mutate(a, "entities", "ashback_bear", {"combat_profile":{"natural_weapons":[{"id":"bear_claw","family":"claw","noun":"claws","verb":"claws","selection_weight":100,"damage_type":"slashing","damage_dice":"1d8"}]}}).ok
    pub = s.publish(a)
    assert pub.ok
    act = s.activate_generation(a, pub.data["generation"])
    assert act.ok and s.active_content_generation_id == pub.data["generation"]
    assert s.rollback_generation(a).ok or "No previous" in s.rollback_generation(a).message
