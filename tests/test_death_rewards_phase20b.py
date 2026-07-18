from engine.death_rewards import *

def test_npc_xp_table_and_bonus_clamp():
    assert [npc_base_xp(x) for x in (-15,-14,-9,-7,-4,-2,-1,0,1,2,3,4,5,6)] == [1,3,5,15,40,60,90,120,150,180,220,260,300,350]
    assert npc_normal_xp(10,10,9,125) == 125

def test_pvp_alignment_glory_and_penalty_rules():
    assert pvp_group_xp(300,2,900) == (101,50)
    assert alignment_after(100, -100) == 100
    assert alignment_after(100, 100) == 88 # -200 / 16 truncates toward zero
    assert pve_glory(25,8) == 0 and pvp_glory(1000,10) == 0
    assert death_penalty(900,1,1000,100)["loss"] == 1
    assert death_penalty(900,100,1000,100)["percentage"] == 10

def test_rare_boundaries():
    assert rare_kill_bonus(3,1) == 1
    assert rare_kill_bonus(120,10) == 30
    assert rare_kill_bonus(120,11) == 0

def test_reward_transaction_is_idempotent(tmp_path):
    from engine.death_runtime import DeathRequest, DeathRuntimeService
    actors={"entity:mob":{"kind":"npc","level":10,"authored_bonus_xp":4,"alignment":-100}, "character:k":{"kind":"player","level":10,"current_exp":0,"alignment":100,"glory":0}}
    service=DeathRuntimeService(tmp_path / "rewards.sqlite", actor_lookup=actors.get, rng=type("R",(),{"randint":lambda *_:20})())
    request=DeathRequest("d", "w", "r", "entity:mob", "character:k", terminal_damage_event_id="terminal", source_metadata={"life_generation":"1","group_snapshot":[{"actor_id":"character:k","room_id":"r","zone_id":"z"}],"rare_live_count":1,"zone_id":"z"})
    service.process_death(request)
    assert service.process_rewards(request).status == "REWARDS_COMPLETED"
    assert actors["character:k"]["current_exp"] == 155 # 124 normal + 31 rare
    assert actors["character:k"]["glory"] == 20
    service.process_rewards(request)
    assert actors["character:k"]["current_exp"] == 155
