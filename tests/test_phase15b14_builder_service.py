from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor(name="Tony", role="admin"):
    return SimpleNamespace(id=name.lower(), name=name, account_id="acct", role=role, world_id="test_world", room_id="start")


def svc(tmp_path):
    return BuilderService(BuilderWorkspace(worlds_dir=tmp_path))


def test_create_clone_edit_undo_redo_validate_preview_publish_generation(tmp_path):
    s=svc(tmp_path); a=actor()
    assert s.acquire_lock(a,"entities","forest_wolf").ok
    assert s.mutate(a,"entities","forest_wolf",{"name":"Forest Wolf","description":"A lean wolf.","entity_type":"mob"}).ok
    assert s.apply_body_profile(a,"forest_wolf","wolf").ok
    assert s.clone(a,"entities","forest_wolf","dire_wolf").ok
    assert s.workspace.load("test_world")["entities"]["dire_wolf"]["name"] == "Dire Wolf"
    assert "Forest Wolf" in s.preview(a,"entities","forest_wolf").message
    assert "natural weapons" in s.preview(a,"entities","forest_wolf").message
    assert s.validate_object(a,"entities","forest_wolf").message.startswith("Validation")
    assert s.undo(a).ok and s.redo(a).ok
    pub=s.publish(a)
    assert pub.ok
    assert s.activate_generation(a, pub.data["generation"]).ok
    assert (tmp_path/"test_world"/"builder"/"generations"/"active.json").exists()


def test_edit_locks_draft_recovery_testspawn_body_attack_and_autocomplete(tmp_path):
    s=svc(tmp_path); a=actor("Tony"); b=actor("Alice")
    assert s.acquire_lock(a,"items","sword_steel_long").ok
    assert s.mutate(a,"items","sword_steel_long",{"name":"Steel Longsword"}).ok
    assert s.acquire_lock(a,"entities","forest_wolf").ok
    busy=s.acquire_lock(b,"entities","forest_wolf")
    assert not busy.ok and "Tony" in busy.message
    bypass=s.mutate(b,"entities","forest_wolf",{"name":"Stolen"})
    assert not bypass.ok and "lock" in bypass.message
    assert s.admin_unlock(a,"entities","forest_wolf").ok
    assert s.acquire_lock(a,"entities","forest_wolf").ok
    assert s.mutate(a,"entities","forest_wolf",{"name":"Forest Wolf"}).ok
    assert s.apply_body_profile(a,"forest_wolf","bear").ok
    rec=s.workspace.load("test_world")["entities"]["forest_wolf"]
    assert "natural_attacks" not in rec
    assert len(rec["combat_profile"]["natural_weapons"]) == 3
    assert "Steel Longsword" in s.autocomplete(a,"items","sword").message
    ts=s.testspawn(a,"forest_wolf")
    assert ts.ok and ts.data["mob"]["ephemeral"]
    assert len(ts.data["mob"]["combat_profile"]["natural_weapons"]) == 3
    s2=svc(tmp_path)
    assert "forest_wolf" in s2.workspace.load("test_world")["entities"]


def test_interactive_medit_session_routes_natural_weapon_edits(tmp_path):
    s=svc(tmp_path); a=actor()
    assert s.acquire_lock(a,"entities","ashback_bear").ok
    assert s.mutate(a,"entities","ashback_bear",{"name":"Ashback Bear","description":"A scarred bear."}).ok
    s.release_lock(a,"entities","ashback_bear")
    opened=s.start_editor(a,"medit","entities","ashback_bear")
    assert opened.ok and "Mobile Editor" in opened.message
    assert "Natural Weapons" in s.sessions.handle(a,"7").message
    res=s.sessions.handle(a,"add bear_claw")
    assert res.ok and "bear_claw" in res.message
    assert s.sessions.handle(a,"set bear_claw weight 60").ok
    assert s.sessions.handle(a,"set bear_claw noun claws").ok
    assert "claws" in s.preview(a,"entities","ashback_bear").message
    assert s.sessions.handle(a,"quit").ok


def test_natural_attacks_migration_is_idempotent(tmp_path):
    s=svc(tmp_path); a=actor()
    root=s.workspace.ensure("test_world")
    (root/"entity_templates.json").write_text('{"wolf":{"id":"wolf","name":"Wolf","natural_attacks":[{"family":"bite","noun":"fangs","verb":"bites","weight":100,"damage_dice":"1d6"}]}}')
    first=s.workspace.load("test_world")["entities"]["wolf"]
    second=s.workspace.load("test_world")["entities"]["wolf"]
    assert "natural_attacks" not in first and "natural_attacks" not in second
    assert first["combat_profile"]["natural_weapons"][0]["noun_plural"] == "fangs"


def test_interactive_editor_menus_for_room_object_zone_area(tmp_path):
    s=svc(tmp_path)
    assert "Mobile Editor" in s.menu("medit","Forest Wolf") and "Natural Attacks" in s.menu("medit","Forest Wolf")
    assert "Room Editor" in s.menu("redit","Clearing") and "Ambient Effects" in s.menu("redit","Clearing")
    assert "Object Editor" in s.menu("oedit","Sword") and "Weapon Data" in s.menu("oedit","Sword")
    assert "Area Editor" in s.menu("aedit","Forest") and "Templates" in s.menu("aedit","Forest")
    assert "Zone Editor" in s.menu("zedit","Forest Zone") and "Resets" in s.menu("zedit","Forest Zone")
