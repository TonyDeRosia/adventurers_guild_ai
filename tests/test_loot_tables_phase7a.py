from engine.rewards import RewardContent, RewardService


def test_loot_table_seeded_trace_and_cycle_validation(tmp_path):
    svc = RewardService(db_path=tmp_path/"r.db", content=RewardContent("worlds/shattered_realms"))
    a = svc.trace_loot_table("rat_common_loot", seed="12345")
    b = svc.trace_loot_table("rat_common_loot", seed="12345")
    assert a == b
    assert "trace" in a and isinstance(a["trace"], list)
    result = svc.content.validate()
    assert not [e for e in result["errors"] if "rat_common_loot" in e]


def test_loot_resolution_creates_packet_and_record(tmp_path):
    svc = RewardService(db_path=tmp_path/"r.db", content=RewardContent("worlds/shattered_realms"))
    pkt = svc.resolve_loot_table("giant_rat_loot", {"source_type":"corpse","source_id":"rat","source_instance_id":"spawn1"}, {"recipient_type":"corpse","recipient_id":"corpse1"}, seed="abc")
    assert pkt["metadata"]["loot_table_id"] == "giant_rat_loot"
    assert pkt["resolved_entries"]
