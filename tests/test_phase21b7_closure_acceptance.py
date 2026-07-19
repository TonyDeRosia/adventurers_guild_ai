"""Phase 21B.7 closure evidence at the real Browser and Telnet boundaries."""
from pathlib import Path

import pytest

from engine.mud_runtime import MudRuntime
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _runtime(tmp_path, *, npc_hp=100):
    runtime = MudRuntime(Path.cwd(), tmp_path)
    runtime.load_world("shattered_realms")
    character_id = runtime.create_character(world_id="shattered_realms", name="Closure Mage", class_id="mage")["character_id"]
    runtime.enter_world(character_id, session_id="phase21b7")
    character = runtime.active_characters[character_id]
    target = next(entity for entity in runtime.find_entities() if entity.get("entity_type") in {"npc", "mob"})
    runtime.move_entity(target["entity_id"], character.room_id)
    runtime.update_entity_state(target["entity_id"], {"current_health": npc_hp, "maximum_health": npc_hp, "is_alive": True, "current_state": "standing"})
    runtime.actor_registry.get(runtime.actor_id_for_entity_instance(target)).resources.health = npc_hp
    return runtime, character_id, target


def _adapter(runtime, kind, character_id):
    adapter = kind(runtime)
    return adapter, adapter.create_session(character_id=character_id, world_id="shattered_realms")


def _send(adapter, session, command, identity):
    return adapter.handle_message(TransportMessage(session, command, request_id=identity, idempotency_key=identity))


def _normalized(result):
    return {"ability_id": result.ability_id, "status": result.status, "failure_code": result.failure_code,
            "stage": result.stage_reached, "costs": result.calculated_costs, "paid": result.paid_costs,
            "roll": result.success_roll, "wait": result.wait_state_applied,
            "cooldown": result.cooldown_applied, "effects": result.effect_results,
            "damage_count": len(result.damage_results), "death_count": len(result.death_results)}


@pytest.mark.parametrize("kind", [WebTransportAdapter, TelnetTransportAdapter])
def test_transport_insufficient_mana_is_structured_and_non_mutating(tmp_path, kind):
    runtime, character_id, target = _runtime(tmp_path / kind.__name__)
    character = runtime.active_characters[character_id]
    actor = runtime.actor_registry.get(character_id)
    character.mana = actor.resources.mana = 0
    adapter, session = _adapter(runtime, kind, character_id)
    response = _send(adapter, session, f"cast magic missile {target['name']}", f"mana-{kind.__name__}")
    result = response.metadata["result"]["ability_result"]
    cost = result.calculated_costs[0]
    assert result.status == "FAILED_VALIDATION" and result.failure_code == "blocked_resource"
    assert cost["resource_id"] == "mana" and cost["amount"] > cost["current"] == 0
    assert not result.paid_costs and result.success_roll is None and not result.damage_results and not result.death_results
    assert runtime.find_entity(target["entity_id"])["state"]["current_health"] == 100
    assert "need" in response.output.lower() and "0" in response.output
    if kind is TelnetTransportAdapter:
        assert "<" not in response.output and "<" not in response.prompt


def test_insufficient_mana_transport_parity(tmp_path):
    outcomes = []
    for kind in (WebTransportAdapter, TelnetTransportAdapter):
        runtime, character_id, target = _runtime(tmp_path / kind.__name__)
        runtime.active_characters[character_id].mana = runtime.actor_registry.get(character_id).resources.mana = 0
        adapter, session = _adapter(runtime, kind, character_id)
        outcomes.append(_normalized(_send(adapter, session, f"cast magic missile {target['name']}", "mana-parity").metadata["result"]["ability_result"]))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", [WebTransportAdapter, TelnetTransportAdapter])
def test_transport_wait_rejection_precedes_payment(tmp_path, kind):
    runtime, character_id, target = _runtime(tmp_path / kind.__name__)
    actor = runtime.actor_registry.get(character_id)
    actor.wait_state = 3
    before_mana = actor.resources.mana
    adapter, session = _adapter(runtime, kind, character_id)
    response = _send(adapter, session, f"cast magic missile {target['name']}", f"wait-{kind.__name__}")
    result = response.metadata["result"]["ability_result"]
    assert result.failure_code == "WAIT_STATE" and result.failure_details["remaining_wait"] == 3
    assert actor.resources.mana == before_mana and not result.paid_costs and result.success_roll is None
    assert "wait 3" in response.output.lower()
    if kind is TelnetTransportAdapter:
        assert "<" not in response.output and "<" not in response.prompt


def test_set_camp_transport_parity_and_duplicate_is_non_consequential(tmp_path):
    outcomes = []
    for kind in (WebTransportAdapter, TelnetTransportAdapter):
        runtime, character_id, _target = _runtime(tmp_path / kind.__name__)
        adapter, session = _adapter(runtime, kind, character_id)
        first = _send(adapter, session, "set camp", "camp-parity").metadata["result"]["ability_result"]
        duplicate = _send(adapter, session, "set camp", "camp-parity").metadata["result"]["ability_result"]
        assert first.ok and first.ability_id == "set_camp" and len(first.effect_results) == 1
        assert not first.damage_results and not first.death_results and duplicate.status == "DUPLICATE_IGNORED"
        outcomes.append(_normalized(first))
    assert outcomes[0] == outcomes[1]


def test_terminal_event_chain_links_death_and_suppresses_duplicate_consequences(tmp_path):
    runtime, character_id, target = _runtime(tmp_path, npc_hp=1)
    adapter, session = _adapter(runtime, WebTransportAdapter, character_id)
    response = _send(adapter, session, f"cast magic missile {target['name']}", "terminal-events")
    result = response.metadata["result"]["ability_result"]
    assert result.ok and result.death_results
    events = runtime.event_bus.event_history(1000)
    names = [event.event_name for event in events]
    required = {"ability.requested", "ability.definition.resolved", "ability.target.resolved", "ability.cost.calculated", "ability.resource.paid", "ability.effect.started", "ability_damage_applied", "ability.damage.completed", "ability.death.completed", "death.requested", "death.corpse.created", "death.npc.extracted", "death.rewards.completed"}
    assert required <= set(names)
    death_events = [event.payload for event in events if event.event_name == "death.corpse.created"]
    assert death_events[-1]["ability_request_id"] == result.request_id
    consequence_count = sum(name in required for name in names)
    replay = _send(adapter, session, f"cast magic missile {target['name']}", "terminal-events").metadata["result"]["ability_result"]
    assert replay.status == "DUPLICATE_IGNORED" and replay.death_results == result.death_results
    assert consequence_count == sum(event.event_name in required for event in runtime.event_bus.event_history(1000))
    # Exercise the canonical combat heartbeat after extraction; no stale victim can act.
    runtime.combat_runtime.process_due_rounds(runtime.combat_runtime.world_time() + 1, violence_pulse=999)
    assert runtime.find_entity(target["entity_id"]) is None
