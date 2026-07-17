from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor(name="Builder", role="admin"):
    return SimpleNamespace(id=name.lower(), name=name, account_id="acct", role=role, world_id="test_world", room_id="start")


def svc(tmp_path):
    return BuilderService(BuilderWorkspace(worlds_dir=tmp_path))


def _seed_object(s, a):
    assert s.acquire_lock(a, "items", "training_sword").ok
    assert s.mutate(a, "items", "training_sword", {
        "id": "training_sword",
        "vnum": 9,
        "name": "Training Sword",
        "keywords": ["training", "sword"],
        "short_description": "a training sword",
        "long_description": "A training sword rests here.",
        "look_description": "The practice blade is nicked but serviceable.",
        "item_type": "weapon",
        "wear_flags": ["take", "wield"],
        "extra_flags": ["magic"],
        "weight": 3,
        "cost": 15,
        "destroy_timer": 0,
        "damage_dice": "1d6",
    }).ok
    s.release_lock(a, "items", "training_sword")


def test_oedit_opens_tba_style_current_value_menu_not_dashboard(tmp_path):
    s = svc(tmp_path); a = actor(); _seed_object(s, a)
    opened = s.object_menu(a, "9")
    assert opened.ok
    out = opened.message
    assert "-- Item number : [9]" in out
    assert "1) Keywords" in out and "2) S-Desc" in out and "C) Values" in out
    assert "training, sword" in out and "a training sword" in out
    assert "Grouped sections" not in out
    assert s.sessions.has(a)


def test_oedit_routes_fields_flags_lists_save_discard_and_invalid_input(tmp_path):
    s = svc(tmp_path); a = actor(); _seed_object(s, a)
    assert s.object_menu(a, "training_sword").ok
    assert "Keywords list editor" in s.sessions.handle(a, "1").message
    assert "List updated" in s.sessions.handle(a, "add practice").message
    assert "practice" in s.sessions.handle(a, "q").message
    assert "Current short description" in s.sessions.handle(a, "2").message
    assert "changed" in s.sessions.handle(a, "a sharper practice sword").message
    assert "Extra flags" in s.sessions.handle(a, "6").message
    assert "Flag selection updated" in s.sessions.handle(a, "1").message
    assert "-- Item number" in s.sessions.handle(a, "q").message
    assert "item type" in s.sessions.handle(a, "5").message
    bad = s.sessions.handle(a, "notatype")
    assert not bad.ok and "must be one of" in bad.message
    assert "Item type" in bad.message
    assert "-- Item number" in s.sessions.handle(a, "q").message
    # cancel prompt from field leaves us in menu through q, then save through root command
    while s.sessions.active[s.sessions.actor_key(a)].mode != "main_menu":
        s.sessions.handle(a, "q")
    saved = s.sessions.handle(a, "save")
    assert saved.ok
    s.sessions.end(a)
    assert s.object_menu(a, "training_sword").ok
    assert "practice" in s.sessions.active[s.sessions.actor_key(a)].working_record["keywords"]


def test_medit_primary_menu_is_numbered_current_value_menu(tmp_path):
    s = svc(tmp_path); a = actor()
    assert s.acquire_lock(a, "entities", "training_master").ok
    assert s.mutate(a, "entities", "training_master", {"id":"training_master", "name":"Training Master", "keywords":["master"], "level": 12, "entity_type":"npc"}).ok
    s.release_lock(a, "entities", "training_master")
    opened = s.start_editor(a, "medit", "entities", "training_master")
    assert opened.ok
    out = opened.message
    assert "Mobile Editor" in out
    assert "1. Identity - Training Master" in out
    assert "5. Level and attributes - level 12" in out
    assert "Grouped sections" not in out
    assert "Attributes" in s.sessions.handle(a, "5").message
