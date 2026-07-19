"""Production proof that generic NPC names use the canonical resident resolver."""
from pathlib import Path
import pytest
from engine.mud_runtime import MudRuntime


def _runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Wolf Mage", class_id="mage")["character_id"]
    rt.enter_world(cid, session_id="wolf-target")
    ch = rt.active_characters[cid]
    wolf = rt.spawn_entity("forest_wolf", room_id=ch.room_id)
    actor = rt.actor_registry.get(rt.actor_id_for_entity_instance(wolf)); actor.resources.health = 10000; actor.resources.maximum_health = 10000
    rt.update_entity_state(wolf["entity_id"], {**wolf["state"], "current_health": 10000, "maximum_health": 10000, "is_alive": True})
    return rt, cid, rt.find_entity(wolf["entity_id"])


@pytest.mark.parametrize("command", ["c magic wolf", "cast magic wolf", "c magic missile wolf", "cast magic missile wolf", "c 'magic missile' wolf", "cast 'magic missile' wolf", 'c "magic missile" wolf', 'cast "magic missile" wolf'])
def test_forest_wolf_spell_forms_resolve_exact_resident(tmp_path, command):
    rt, cid, wolf = _runtime(tmp_path)
    response = rt.handle_input(cid, command)
    result = response["ability_result"]
    assert result.ok, response["output"]
    assert result.ability_id == "magic_missile" and result.target_id == rt.actor_id_for_entity_instance(wolf)
    assert len(result.calculated_costs) == len(result.paid_costs) == len(result.damage_results) == 1
    assert result.damage_results[0]["target_actor_id"] == rt.actor_id_for_entity_instance(wolf)
    assert "invalid target" not in response["output"].lower()


def test_target_normalization_and_missing_target_are_canonical_and_safe(tmp_path):
    rt, cid, wolf = _runtime(tmp_path); ch = rt.active_characters[cid]; actor = rt.actor_registry.get(cid)
    for query in ("wolf", " Forest   Wolf ", "FOREST", "1.wolf"):
        assert rt.find_occupant(ch.room_id, query, {"living": True, "visible_to": ch})["entity"]["entity_id"] == wolf["entity_id"]
    mana, wait = actor.resources.mana, actor.wait_state
    result = rt.handle_input(cid, "c magic bear")["ability_result"]
    assert result.ability_id == "magic_missile" and not result.ok
    assert not result.paid_costs and result.success_roll is None and not result.damage_results
    assert actor.resources.mana == mana and actor.wait_state == wait
