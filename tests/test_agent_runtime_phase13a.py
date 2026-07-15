from pathlib import Path

from engine.agent_runtime import AgentActionRequest, AgentTestControllerAdapter, REASON_CONTROLLER_LEASE_REQUIRED, REASON_STALE_LIFECYCLE, RESULT_SUCCESS
from engine.mud_runtime import MudRuntime


def _rt(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    account = rt.ensure_dev_account()
    payload = rt.create_character(world_id="shattered_realms", name="Agent Tester", account_id=account["account_id"])
    ch = rt.state_store.load_character(payload["character_id"])
    actor_id = "character:" + ch.id
    adapter = AgentTestControllerAdapter(rt.agent_gateway, "ctrl_test")
    lease = adapter.acquire(actor_id)
    assert lease["ok"]
    return rt, adapter, actor_id, lease["lifecycle_id"]


def test_observation_contract_and_lease(tmp_path):
    rt, adapter, actor_id, lifecycle_id = _rt(tmp_path)
    obs = adapter.observe(actor_id)
    assert obs.actor_id == actor_id
    assert obs.lifecycle_id == lifecycle_id
    assert obs.self_state["health"] == obs.self_state["maximum_health"]
    assert "available_actions" in obs.to_dict()
    assert all("target_ref" in e for e in obs.visible_exits)
    assert "wait" in {a["action_type"] for a in obs.available_actions}
    no_lease = rt.agent_gateway.submit_action(AgentActionRequest("r0", actor_id, lifecycle_id, obs.observation_id, "wait", controller_id="other"))
    assert no_lease.reason_code == REASON_CONTROLLER_LEASE_REQUIRED


def test_wait_idempotency_persists(tmp_path):
    rt, adapter, actor_id, lifecycle_id = _rt(tmp_path)
    obs = adapter.observe(actor_id)
    req = dict(request_id="same-wait", actor_id=actor_id, lifecycle_id=lifecycle_id, observation_id=obs.observation_id, action_type="wait", parameters={"minutes": 1})
    first = adapter.submit(**req)
    second = adapter.submit(**req)
    assert first.to_dict() == second.to_dict()
    assert first.result_code == RESULT_SUCCESS
    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    third = rt2.agent_gateway.submit_action(AgentActionRequest(**{**req, "controller_id": "ctrl_test"}))
    assert third.to_dict() == first.to_dict()


def test_move_and_stale_lifecycle_rejection(tmp_path):
    rt, adapter, actor_id, lifecycle_id = _rt(tmp_path)
    obs = adapter.observe(actor_id)
    if obs.visible_exits:
        res = adapter.submit(request_id="move-1", actor_id=actor_id, lifecycle_id=lifecycle_id, observation_id=obs.observation_id, action_type="move", target_ref=obs.visible_exits[0]["target_ref"])
        assert res.accepted or res.reason_code in {"MOVEMENT_BLOCKED", "EXIT_CLOSED", "EXIT_LOCKED"}
    stale = adapter.submit(request_id="stale-1", actor_id=actor_id, lifecycle_id="old-life", observation_id=obs.observation_id, action_type="wait")
    assert stale.reason_code == REASON_STALE_LIFECYCLE
