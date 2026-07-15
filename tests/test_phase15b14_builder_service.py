from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor(name="Tony"):
    return SimpleNamespace(id=name.lower(), name=name, account_id="acct", role="builder", world_id="test_world", room_id="start")


def svc(tmp_path):
    return BuilderService(BuilderWorkspace(worlds_dir=tmp_path))


def test_create_clone_edit_undo_redo_validate_preview_publish_generation(tmp_path):
    s=svc(tmp_path); a=actor()
    assert s.mutate(a,"entities","forest_wolf",{"name":"Forest Wolf","description":"A lean wolf.","entity_type":"mob"}).ok
    assert s.apply_body_profile(a,"forest_wolf","wolf").ok
    assert s.clone(a,"entities","forest_wolf","dire_wolf").ok
    assert "Forest Wolf" in s.preview(a,"entities","forest_wolf").message
    assert s.validate_object(a,"entities","forest_wolf").message.startswith("Validation")
    assert s.undo(a).ok and s.redo(a).ok
    pub=s.publish(a)
    assert pub.ok and (tmp_path/"test_world"/"builder"/"generations"/"active.json").exists()


def test_edit_locks_draft_recovery_testspawn_body_attack_and_autocomplete(tmp_path):
    s=svc(tmp_path); a=actor("Tony"); b=actor("Alice")
    assert s.mutate(a,"items","sword_steel_long",{"name":"Steel Longsword"}).ok
    assert s.acquire_lock(a,"entities","forest_wolf").ok
    busy=s.acquire_lock(b,"entities","forest_wolf")
    assert not busy.ok and "Tony" in busy.message
    assert s.admin_unlock(a,"entities","forest_wolf").ok
    assert s.apply_body_profile(a,"forest_wolf","bear").ok
    rec=s.workspace.load("test_world")["entities"]["forest_wolf"]
    assert len(rec["natural_attacks"]) == 3
    assert "Steel Longsword" in s.autocomplete(a,"items","sword").message
    assert s.testspawn(a,"forest_wolf").ok
    # recovery: a new service sees the saved draft
    s2=svc(tmp_path)
    assert "forest_wolf" in s2.workspace.load("test_world")["entities"]


def test_interactive_editor_menus_for_room_object_zone_area(tmp_path):
    s=svc(tmp_path)
    assert "Mobile Editor" in s.menu("medit","Forest Wolf") and "Natural Attacks" in s.menu("medit","Forest Wolf")
    assert "Room Editor" in s.menu("redit","Clearing") and "Ambient Effects" in s.menu("redit","Clearing")
    assert "Object Editor" in s.menu("oedit","Sword") and "Weapon Data" in s.menu("oedit","Sword")
    assert "Area Editor" in s.menu("aedit","Forest") and "Templates" in s.menu("aedit","Forest")
    assert "Zone Editor" in s.menu("zedit","Forest Zone") and "Resets" in s.menu("zedit","Forest Zone")
