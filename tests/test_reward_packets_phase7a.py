from engine.rewards import RewardContent, RewardService, init_reward_schema


def test_reward_packet_is_stable_persistent_and_idempotent(tmp_path):
    db = tmp_path / "r.db"
    init_reward_schema(db)
    svc = RewardService(db_path=db, content=RewardContent("worlds/shattered_realms"))
    src = {"source_type":"admin","source_id":"test","source_instance_id":"one","world_id":"shattered_realms","world_time":10}
    rec = {"recipient_type":"actor","recipient_id":"actor1"}
    p1 = svc.resolve_reward_definition("starter_training_reward", src, rec, seed="same")
    p2 = svc.resolve_reward_definition("starter_training_reward", src, rec, seed="same")
    assert p1["reward_packet_id"] == p2["reward_packet_id"]
    assert p1["status"] == "resolved"
    assert p1["resolved_entries"][0]["source_rule_id"] == "practice"
