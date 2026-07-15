from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus


def runtime(tmp_path):
    bus = EventBus(); events = []
    for name in ["entity_spawned", "entity_moved", "entity_state_changed", "entity_despawned", "entity_destroyed", "room_entities_changed", "npc_spawned", "mob_spawned", "corpse_spawned"]:
        bus.subscribe(name, lambda event: events.append((event.event_name, event.payload)), source=f"test_{name}")
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=bus)
    rt.load_world("shattered_realms")
    return rt, events


def test_entity_templates_load_immutable_and_seed_idempotently(tmp_path):
    rt, _ = runtime(tmp_path)
    assert rt.entity_templates["guild_registrar_maren"]["entity_type"] == "npc"
    assert rt.entity_templates["cellar_rats"]["entity_type"] == "mob"
    try:
        rt.entity_templates["guild_registrar_maren"]["name"] = "Changed"
    except TypeError:
        pass
    assert rt.entity_templates["guild_registrar_maren"]["name"] == "Guild Registrar Maren"
    before = len(rt.find_room_entities("guildhall_registrar_office"))
    rt._seed_room_entities()
    assert len(rt.find_room_entities("guildhall_registrar_office")) == before


def test_npc_mob_rendering_lookup_movement_persistence_and_ids_hidden(tmp_path):
    rt, _ = runtime(tmp_path)
    cid = rt.create_character(world_id="shattered_realms", name="Entity Tester")["character_id"]
    char = rt.state_store.load_character(cid)
    char.room_id = "guildhall_registrar_office"; rt.state_store.save_character(char, "shattered_realms")
    out = rt.handle_input(cid, "look")["output"]
    assert "Guild Registrar Maren" in out and "ent_" not in out
    assert "Guild Registrar Maren is a memorable resident" in rt.handle_input(cid, "look maren")["output"]
    npc = rt.resolve_entity_keywords("registrar", rt.find_room_entities(char.room_id))["entity"]
    moved = rt.move_entity(npc["entity_id"], "guildhall_crossing_square")
    assert moved["current_room_id"] == "guildhall_crossing_square"
    rt2 = MudRuntime(Path.cwd(), tmp_path); rt2.load_world("shattered_realms")
    assert rt2.find_entity(npc["entity_id"])["current_room_id"] == "guildhall_crossing_square"
    mob = rt.spawn_entity("cellar_rats", room_id="guildhall_registrar_office")
    assert "Cellar Rats" in rt.handle_input(cid, "look")["output"]
    assert "yellow teeth" in rt.handle_input(cid, "examine rats")["output"]
    assert rt.despawn_entity(mob["entity_id"])


def test_corpse_spawn_state_and_entity_events(tmp_path):
    rt, events = runtime(tmp_path)
    corpse = rt.spawn_entity("fallen_test_subject", entity_type="corpse", room_id="guildhall_crossing_square", state={"source_entity_id": "mob_test", "decay_at": "2099-01-01T00:00:00+00:00"}, flags=["corpse"], source_system="test", character_id="char_test", session_id="sess_test")
    assert corpse["entity_type"] == "corpse"
    assert corpse["state"]["source_entity_id"] == "mob_test"
    changed = rt.update_entity_state(corpse["entity_id"], {"decay_at": "2099-01-02T00:00:00+00:00"})
    assert changed["state"]["decay_at"].startswith("2099-01-02")
    assert rt.destroy_entity(corpse["entity_id"], reason="test cleanup")
    names = [name for name, _payload in events]
    assert "entity_spawned" in names and "corpse_spawned" in names
    assert "entity_state_changed" in names and "entity_destroyed" in names
    assert "room_entities_changed" in names


def test_items_still_render_with_entity_visibility(tmp_path):
    rt, _ = runtime(tmp_path)
    cid = rt.create_character(world_id="shattered_realms", name="Item Entity Tester")["character_id"]
    assert "Fountain" in rt.handle_input(cid, "look")["output"]
