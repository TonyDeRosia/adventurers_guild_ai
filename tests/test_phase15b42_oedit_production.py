from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor(name="Builder", role="admin"):
    return SimpleNamespace(id=name.lower(), name=name, account_id="acct", role=role, world_id="test_world", room_id="start")


def svc(tmp_path):
    return BuilderService(BuilderWorkspace(worlds_dir=tmp_path))


def seed(s, a, oid="training_sword", **extra):
    assert s.acquire_lock(a, "items", oid).ok
    rec = {
        "id": oid,
        "vnum": 9 if oid == "training_sword" else 10,
        "name": oid.replace("_", " ").title(),
        "keywords": oid.split("_"),
        "short_description": "a training sword" if oid == "training_sword" else "a source mace",
        "long_description": "A weapon rests here.",
        "look_description": "It is ready for testing.",
        "item_type": "weapon",
        "wear_flags": ["take", "wield"],
        "extra_flags": ["magic"],
        "weight": 3,
        "cost": 15,
        "damage_dice": "1d6",
    }
    rec.update(extra)
    assert s.mutate(a, "items", oid, rec).ok
    s.release_lock(a, "items", oid)


def test_oedit_type_values_are_meaningful_persistent_and_use_same_session(tmp_path):
    s = svc(tmp_path); a = actor(); seed(s, a)
    opened = s.object_menu(a, "training_sword")
    assert opened.ok
    sess = s.sessions.active[s.sessions.actor_key(a)]
    sid = sess.session_id
    values = s.sessions.handle(a, "c")
    assert values.ok
    assert "OEDIT Values: weapon" in values.message
    assert "Damage dice" in values.message and "Weapon type" in values.message
    assert s.sessions.active[s.sessions.actor_key(a)].session_id == sid
    assert "Current damage dice" in s.sessions.handle(a, "2").message
    changed = s.sessions.handle(a, "2d4")
    assert changed.ok and "Damage dice changed" in changed.message
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["damage_dice"] == "2d4"
    assert s.sessions.handle(a, "q").ok
    assert s.sessions.handle(a, "save").ok
    s.sessions.end(a)
    assert s.object_menu(a, "training_sword").ok
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["damage_dice"] == "2d4"


def test_oedit_validation_preview_undo_redo_and_quit_choices(tmp_path):
    s = svc(tmp_path); a = actor(); seed(s, a)
    assert s.object_menu(a, "training_sword").ok
    assert "Current weight" in s.sessions.handle(a, "8").message
    assert not s.sessions.handle(a, "-1").ok
    assert s.sessions.handle(a, "7").ok
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["weight"] == 7
    assert "Validation for training_sword" in s.sessions.handle(a, "validate").message
    assert s.sessions.handle(a, "preview").ok
    assert s.sessions.handle(a, "undo").ok
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["weight"] == 3
    assert s.sessions.handle(a, "redo").ok
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["weight"] == 7
    prompt = s.sessions.handle(a, "quit")
    assert prompt.ok and "Unsaved changes" in prompt.message and s.sessions.has(a)
    cancel = s.sessions.handle(a, "cancel")
    assert cancel.ok and "Quit cancelled" in cancel.message and s.sessions.has(a)
    assert s.sessions.handle(a, "quit").ok
    discard = s.sessions.handle(a, "discard")
    assert discard.ok and not s.sessions.has(a)
    assert s.object_menu(a, "training_sword").ok
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["weight"] == 3


def test_oedit_copy_modes_and_dependency_safe_delete(tmp_path):
    s = svc(tmp_path); a = actor(); seed(s, a); seed(s, a, "source_mace", damage_dice="3d5")
    assert s.object_menu(a, "training_sword").ok
    assert "Copy object" in s.sessions.handle(a, "w").message
    assert "COPY DESTINATION" in s.sessions.handle(a, "to cloned_sword").message
    assert s.sessions.handle(a, "COPY DESTINATION").ok
    assert "cloned_sword" in s.workspace.load(a.world_id)["items"]
    assert "Copy object" in s.sessions.handle(a, "w").message
    assert "COPY SOURCE" in s.sessions.handle(a, "from source_mace").message
    assert s.sessions.handle(a, "COPY SOURCE").ok
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["damage_dice"] == "3d5"
    # Deletion warns on references and does not remove the object.
    assert s.acquire_lock(a, "rooms", "test_room").ok
    assert s.mutate(a, "rooms", "test_room", {"id": "test_room", "objects": ["training_sword"]}).ok
    s.release_lock(a, "rooms", "test_room")
    blocked = s.sessions.handle(a, "x")
    assert not blocked.ok and "Delete protected" in blocked.message
    assert "training_sword" in s.workspace.load(a.world_id)["items"]
    s.sessions.end(a)
    assert s.object_menu(a, "cloned_sword").ok
    assert "type DELETE" in s.sessions.handle(a, "x").message
    assert "Delete cancelled" in s.sessions.handle(a, "q").message
    assert "type DELETE" in s.sessions.handle(a, "x").message
    deleted = s.sessions.handle(a, "DELETE")
    assert deleted.ok and "deleted" in deleted.message
    assert "cloned_sword" not in s.workspace.load(a.world_id)["items"]
