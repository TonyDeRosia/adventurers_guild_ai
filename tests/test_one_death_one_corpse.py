"""Corpse identity is lifecycle/death based and room projection is instance based."""
from pathlib import Path
from engine.mud_runtime import MudRuntime


def test_duplicate_death_callback_returns_one_corpse_and_two_deaths_remain_distinct(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    room = "emberwood_hunting_trail"
    fox = rt.spawn_entity("emberwood_fox", room_id=room)
    first = rt.create_corpse(fox["entity_id"], death_id="death-one")
    again = rt.create_corpse(fox["entity_id"], death_id="death-one")
    assert first["entity_id"] == again["entity_id"]
    assert len([e for e in rt.find_room_entities(room) if e.get("entity_type") == "corpse"]) == 1
    fox2 = rt.spawn_entity("emberwood_fox", room_id=room)
    second = rt.create_corpse(fox2["entity_id"], death_id="death-two")
    corpses = [e for e in rt.find_room_entities(room) if e.get("entity_type") == "corpse"]
    assert first["entity_id"] != second["entity_id"] and {e["state"]["death_id"] for e in corpses} == {"death-one", "death-two"}
    projected = [e for e in rt.get_room_contents(room)["entity_instances"] if e.get("entity_type") == "corpse"]
    assert {e["entity_id"] for e in projected} == {first["entity_id"], second["entity_id"]}
