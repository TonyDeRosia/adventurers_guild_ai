from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus


def make_runtime(tmp_path):
    bus = EventBus(); events = []
    for name in ["entity_spawned", "entity_despawned", "entity_destroyed", "entity_reset", "entity_moved", "entity_state_changed", "entity_dialogue", "room_entities_changed", "corpse_spawned"]:
        bus.subscribe(name, lambda event: events.append((event.event_name, event.payload)), source=f"phase3b_{name}")
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=bus)
    rt.load_world("shattered_realms")
    return rt, events


def test_living_template_fields_and_runtime_instance_creation(tmp_path):
    rt, events = make_runtime(tmp_path)
    tmpl = rt.entity_templates["guild_registrar_maren"]
    for key in ["id", "race", "class", "gender", "level", "size", "alignment", "spawn_group", "spawn_rules", "wander_rules", "dialogue_package", "behavior_flags", "visibility_flags", "script_hooks", "plugin_data"]:
        assert key in tmpl
    ent = rt.spawn_entity("guild_registrar_maren", room_id="guildhall_crossing_square", state={"current_state": "standing", "current_health": 42})
    assert ent["instance_id"] == ent["entity_id"]
    assert ent["current_state"] == "standing"
    assert ent["current_health"] == 42
    assert ent["is_alive"] is True and ent["is_visible"] is True
    assert any(name == "entity_spawned" for name, _ in events)


def test_population_idempotent_visibility_movement_state_dialogue_and_corpse(tmp_path):
    rt, events = make_runtime(tmp_path)
    before = len(rt.find_room_entities("guildhall_registrar_office"))
    rt.populate_world(); rt.populate_world()
    assert len(rt.find_room_entities("guildhall_registrar_office")) == before

    cid = rt.create_character(world_id="shattered_realms", name="Living Tester")["character_id"]
    char = rt.state_store.load_character(cid); char.room_id = "guildhall_registrar_office"; rt.state_store.save_character(char, "shattered_realms")
    npc = rt.resolve_entity_keywords("maren", rt.find_room_entities(char.room_id))["entity"]
    assert "Guild Registrar Maren" in rt.handle_input(cid, "hello maren")["output"]

    rt.update_entity_state(npc["entity_id"], {**npc["state"], "visibility_flags": ["hidden"]})
    assert all(e["entity_id"] != npc["entity_id"] for e in rt.find_visible_entities(char.room_id, char)["npcs"])
    rt.change_entity_state(npc["entity_id"], "wandering")
    moved = rt.teleport_entity(npc["entity_id"], "guildhall_crossing_square")
    assert moved["room_id"] == "guildhall_crossing_square"
    reset = rt.reset_entity(npc["entity_id"])
    assert reset["room_id"] == "guildhall_registrar_office"
    corpse = rt.create_corpse(npc["entity_id"])
    assert corpse["entity_type"] == "corpse" and corpse["current_state"] == "corpse"
    names = [name for name, _payload in events]
    assert {"entity_dialogue", "entity_state_changed", "entity_moved", "entity_reset", "corpse_spawned"}.issubset(set(names))


def test_respawn_and_sqlite_persistence_across_reload(tmp_path):
    rt, _ = make_runtime(tmp_path)
    ent = rt.respawn_entity("cellar_rats", room_id="guildhall_cellar")
    rt.change_entity_state(ent["entity_id"], "resting")
    rt2 = MudRuntime(Path.cwd(), tmp_path); rt2.load_world("shattered_realms")
    loaded = rt2.find_entity(ent["entity_id"])
    assert loaded["room_id"] == "guildhall_cellar"
    assert loaded["current_state"] == "resting"
