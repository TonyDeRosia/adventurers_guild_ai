from engine.rewards import RewardContent, RewardService


def test_treasure_group_combines_tables_and_guaranteed_rewards(tmp_path):
    svc = RewardService(db_path=tmp_path/"r.db", content=RewardContent("worlds/shattered_realms"))
    pkt = svc.resolve_treasure_group("starter_training_reward", {"source_type":"admin","source_id":"manual"}, {"recipient_type":"actor","recipient_id":"a"}, seed="s")
    assert pkt["metadata"]["treasure_group_id"] == "starter_training_reward"
    assert pkt["resolved_entries"][0]["reward_type"] == "practice_sessions"
