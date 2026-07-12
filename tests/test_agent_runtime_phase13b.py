from pathlib import Path

from engine.agent_runtime import AgentActionRequest, AgentTestControllerAdapter, DeterministicControllerEvaluator, REASON_ACTION_NOT_AVAILABLE, REASON_STALE_LIFECYCLE, RESULT_SUCCESS
from engine.mud_runtime import MudRuntime


def _runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    wolf = next(e for e in rt.find_room_entities("emberwood_hunting_trail") if e.get("entity_type") == "mob")
    actor_id = "entity:" + wolf["entity_id"]
    adapter = AgentTestControllerAdapter(rt.agent_gateway, "ctrl_wolf")
    lease = adapter.acquire(actor_id)
    assert lease["ok"]
    return rt, adapter, actor_id, lease["lifecycle_id"]


def test_entity_actor_resolution_observation_and_lease(tmp_path):
    rt, adapter, actor_id, lifecycle_id = _runtime(tmp_path)
    ctx = rt.agent_gateway.resolve_controlled_actor(actor_id)
    assert ctx.actor_type == "mob"
    assert ctx.lifecycle_id == lifecycle_id
    obs = adapter.observe(actor_id)
    assert obs.self_state["actor_type"] == "mob"
    assert obs.self_state["current_room_id"] == "emberwood_hunting_trail"
    assert obs.self_state["health"] == obs.self_state["maximum_health"]
    assert "move" in {a["action_type"] for a in obs.available_actions}
    assert next(a for a in obs.available_actions if a["action_type"] == "speak")["current_availability"] is False
    assert rt.agent_gateway.acquire_control(actor_id, "second")["reason_code"] == "DUPLICATE_CONTROLLER"


def test_entity_movement_and_stale_lifecycle(tmp_path):
    rt, adapter, actor_id, lifecycle_id = _runtime(tmp_path)
    obs = adapter.observe(actor_id)
    exit_ref = next(e["target_ref"] for e in obs.visible_exits if e["movement_allowed"])
    res = adapter.submit(request_id="wolf-move", actor_id=actor_id, lifecycle_id=lifecycle_id, observation_id=obs.observation_id, action_type="move", target_ref=exit_ref)
    assert res.result_code == RESULT_SUCCESS
    assert rt.agent_gateway.resolve_controlled_actor(actor_id).room_id != "emberwood_hunting_trail"
    stale = adapter.submit(request_id="wolf-stale", actor_id=actor_id, lifecycle_id="old-life", observation_id=obs.observation_id, action_type="wait")
    assert stale.reason_code == REASON_STALE_LIFECYCLE


def test_entity_speech_capability_and_deterministic_wait(tmp_path):
    rt, adapter, actor_id, lifecycle_id = _runtime(tmp_path)
    obs = adapter.observe(actor_id)
    speech = adapter.submit(request_id="wolf-say", actor_id=actor_id, lifecycle_id=lifecycle_id, observation_id=obs.observation_id, action_type="speak", parameters={"text": "<b>growl</b>"})
    assert speech.reason_code == REASON_ACTION_NOT_AVAILABLE
    evaluator = DeterministicControllerEvaluator(rt.agent_gateway)
    evaluator.upsert_profile("demo_wait", allowed_action_types=["wait"], interval=3, idle_action="wait")
    rt.agent_gateway.register_controller("ctrl_auto", "deterministic", actor_id, metadata={"controller_profile_id": "demo_wait"})
    assert rt.agent_gateway.acquire_control(actor_id, "ctrl_auto", controller_type="deterministic", override_reason="test")["ok"]
    result = evaluator.step(actor_id, "ctrl_auto")
    assert result is not None
    assert result.action_type == "wait"
    with rt.state_store.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM agent_decision_audit WHERE controller_id='ctrl_auto'").fetchone()[0] == 1
