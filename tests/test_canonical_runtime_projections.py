"""Production regression coverage for canonical runtime resource projections."""
from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _runtime(tmp_path):
    runtime = MudRuntime(Path.cwd(), tmp_path)
    runtime.load_world("shattered_realms")
    cid = runtime.create_character(world_id="shattered_realms", name="Projection Mage", class_id="mage")["character_id"]
    runtime.enter_world(cid, session_id="canonical-projections")
    return runtime, cid


def test_resident_actor_is_the_shared_ability_combat_and_prompt_authority(tmp_path):
    runtime, cid = _runtime(tmp_path)
    character = runtime.active_characters[cid]
    ability_actor = runtime.actor_registry.get(cid)
    combat_actor = runtime.combat_runtime.resident_actors[cid]
    assert ability_actor is combat_actor

    ability_actor.resources.mana = 0
    prompt = runtime.prompt_snapshot(cid)["prompt_text"]
    assert "0/50 MP" in prompt
    result = runtime.handle_input(cid, "cast magic missile nobody")
    assert not result["ok"]
    assert "0/50 MP" in result["view"]["prompt"]


def test_report_uses_resident_resources_and_has_transport_parity(tmp_path):
    values = []
    for adapter_type in (WebTransportAdapter, TelnetTransportAdapter):
        runtime, cid = _runtime(tmp_path / adapter_type.__name__)
        actor = runtime.actor_registry.get(cid)
        actor.resources.mana = 0
        adapter = adapter_type(runtime)
        session = adapter.create_session(character_id=cid, world_id="shattered_realms")
        response = adapter.handle_message(TransportMessage(session, "report", request_id="report"))
        assert "0/50 mana" in response.output
        assert "0/50" in response.prompt
        values.append("0/50 mana" in response.output)
    assert values == [True, True]
