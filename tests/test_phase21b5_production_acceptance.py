"""Phase 21B.5 production-boundary acceptance.

This intentionally starts at MudRuntime and the production transport adapters;
it never constructs an ability or death service itself.
"""
from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _runtime_with_terminal_target(tmp_path):
    runtime = MudRuntime(Path.cwd(), tmp_path)
    runtime.load_world("shattered_realms")
    character_id = runtime.create_character(
        world_id="shattered_realms", name="Phase Mage", class_id="mage"
    )["character_id"]
    runtime.enter_world(character_id, session_id="phase21b5")
    character = runtime.active_characters[character_id]
    # Use a production-materialized, durable NPC rather than a test-only
    # actor.  Moving it uses the same authoritative occupancy path as play.
    target = next(entity for entity in runtime.find_entities() if entity.get("entity_type") in {"npc", "mob"})
    runtime.move_entity(target["entity_id"], character.room_id)
    runtime.update_entity_state(target["entity_id"], {
        "current_health": 1, "maximum_health": 1, "is_alive": True, "current_state": "standing"
    })
    target = runtime.find_entity(target["entity_id"])
    # The combat actor is the authority consumed by the damage gateway.
    runtime.actor_registry.get(runtime.actor_id_for_entity_instance(target)).resources.health = 1
    return runtime, character_id, target, target["name"]


def test_browser_terminal_magic_missile_returns_authoritative_receipts(tmp_path):
    runtime, character_id, target, target_name = _runtime_with_terminal_target(tmp_path)
    assert runtime.abilities.death_runtime is runtime.death_runtime

    browser = WebTransportAdapter(runtime)
    session = browser.create_session(character_id=character_id, world_id="shattered_realms")
    response = browser.handle_message(TransportMessage(session, f"cast magic missile {target_name}"))

    receipt = response.metadata["result"]["ability_result"]
    assert receipt.ok and receipt.ability_id == "magic_missile"
    assert len(receipt.damage_results) == len(receipt.death_results) == 1
    damage, death = receipt.damage_results[0], receipt.death_results[0]
    assert damage["ability_request_id"] == receipt.request_id
    assert damage["target_actor_id"] == runtime.actor_id_for_entity_instance(target)
    assert damage["hp_before"] == 1 and damage["hp_after"] == 0 and damage["terminal"]
    assert death["damage_result_id"] == damage["damage_result_id"]
    assert death["ability_id"] == "magic_missile"
    assert death["credited_killer_actor_id"] == character_id
    assert death["corpse_id"]
    assert death["victim_removed"] is True
    assert runtime.find_entity(target["entity_id"]) is None
    corpses = [e for e in runtime.find_room_entities(runtime.active_characters[character_id].room_id) if e.get("entity_type") == "corpse"]
    matching = [e for e in corpses if e["entity_id"] == death["corpse_id"]]
    assert len(matching) == 1
    assert matching[0]["state"]["death_id"] == death["death_id"]
    assert response.metadata["used_mud_runtime"] is True


def test_telnet_adapter_uses_same_authority_and_never_emits_html(tmp_path):
    runtime, character_id, _target, target_name = _runtime_with_terminal_target(tmp_path)
    telnet = TelnetTransportAdapter(runtime)
    session = telnet.create_session(character_id=character_id, world_id="shattered_realms")
    response = telnet.handle_message(TransportMessage(session, f"cast magic missile {target_name}"))

    receipt = response.metadata["result"]["ability_result"]
    assert receipt.ok and receipt.death_results
    assert response.metadata["used_mud_runtime"] is True
    assert "<" not in response.output and "<" not in response.prompt
