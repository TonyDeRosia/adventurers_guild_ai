import sqlite3
from pathlib import Path

from engine.combat_runtime import CombatActionRequest
from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Tester")["character_id"]
    ch = rt.state_store.load_character(cid)
    ch.room_id = "emberwood_hunting_trail"
    rt.state_store.save_character(ch, "shattered_realms")
    return rt, rt.state_store.load_character(cid)


def wolf(rt, ch):
    return rt.resolve_entity_keywords("forest wolf", rt.find_visible_entities(ch.room_id, ch).get("mobs", []))["entity"]


def test_lifecycle_creates_real_corpse_transfers_items_and_truthful_statuses(tmp_path):
    rt, ch = make_runtime(tmp_path)
    ent = wolf(rt, ch)
    item_template = next(iter(rt.item_templates))
    drop = rt.spawn_item(item_template, "entity", owner_id=ent["entity_id"], stack_count=3)
    keep = rt.spawn_item(item_template, "entity", owner_id=ent["entity_id"], custom_flags={"keep_on_death": True})
    equip = rt.spawn_item(item_template, "equipment", owner_id=ent["entity_id"], equipped_slot="main_hand")
    destroy = rt.spawn_item(item_template, "entity", owner_id=ent["entity_id"], custom_flags={"destroy_on_death": True})

    enc = rt.combat_runtime.start_encounter(ch.room_id)
    attacker = rt.combat_runtime._load_actor("character:" + ch.id)
    defender = rt.combat_runtime.actor_from_entity(ent)
    rt.combat_runtime.join_encounter(enc, attacker, "side_1")
    rt.combat_runtime.join_encounter(enc, defender, "side_2")
    result = rt.combat_runtime.lifecycle.process_defeat_or_death(encounter_id=enc, attacker=attacker, defender=defender, trigger_action_id="a3h_kill")

    assert result.corpse_status == "completed"
    assert result.corpse_processed is True
    assert result.respawn_status == "pending"
    assert result.respawn_processed is False
    assert result.quest_credit_status == "unsupported"
    corpse_items = {i["instance_id"]: i for i in rt.find_container_items(result.corpse_id)}
    assert drop["instance_id"] in corpse_items
    assert corpse_items[drop["instance_id"]]["stack_count"] == 3
    assert equip["instance_id"] in corpse_items
    assert corpse_items[equip["instance_id"]]["equipped_slot"] == ""
    assert rt.find_item(keep["instance_id"])["owner_type"] == "entity"
    assert rt.find_item(destroy["instance_id"]) is None

    again = rt.combat_runtime.lifecycle.process_defeat_or_death(encounter_id=enc, attacker=attacker, defender=defender, trigger_action_id="a3h_kill")
    assert again.corpse_id == result.corpse_id
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM actor_respawn_schedules WHERE transition_id=?", (result.transition_id,)).fetchone()[0] == 1


def test_reward_idempotency_and_environmental_skip(tmp_path):
    rt, ch = make_runtime(tmp_path)
    ent = wolf(rt, ch)
    enc = rt.combat_runtime.start_encounter(ch.room_id)
    attacker = rt.combat_runtime._load_actor("character:" + ch.id)
    defender = rt.combat_runtime.actor_from_entity(ent)
    first = rt.combat_runtime.lifecycle.process_defeat_or_death(encounter_id=enc, attacker=attacker, defender=defender, trigger_action_id="reward_once")
    xp1 = rt.state_store.load_character(ch.id).xp
    second = rt.combat_runtime.lifecycle.process_defeat_or_death(encounter_id=enc, attacker=attacker, defender=defender, trigger_action_id="reward_once")
    assert rt.state_store.load_character(ch.id).xp == xp1
    assert second.reward_claim_id == first.reward_claim_id
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM actor_kill_credits WHERE transition_id=?", (first.transition_id,)).fetchone()[0] <= 1

    ent2 = rt.respawn_entity(ent["template_id"], ch.room_id, source_system="test")
    env = rt.combat_runtime.actor_from_entity(ent2)
    env.actor_id = "environment:room"
    skipped = rt.combat_runtime.lifecycle.award_kill_rewards("env_transition", enc, env, rt.combat_runtime.actor_from_entity(ent2), "env_action")
    assert skipped.status == "skipped_by_policy"
    assert skipped.eligible_actor_ids == ()


def test_process_due_respawn_completes_once(tmp_path):
    rt, ch = make_runtime(tmp_path)
    ent = wolf(rt, ch)
    enc = rt.combat_runtime.start_encounter(ch.room_id)
    attacker = rt.combat_runtime._load_actor("character:" + ch.id)
    defender = rt.combat_runtime.actor_from_entity(ent)
    life = rt.combat_runtime.lifecycle.process_defeat_or_death(encounter_id=enc, attacker=attacker, defender=defender, trigger_action_id="respawn_due")
    out = rt.combat_runtime.process_due_respawns(world_time=10**9)
    assert len([r for r in out if r.respawn_id == life.respawn_id]) == 1
    assert rt.combat_runtime.process_due_respawns(world_time=10**9) == []
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT status FROM actor_respawn_schedules WHERE respawn_id=?", (life.respawn_id,)).fetchone()[0] == "completed"


def test_static_no_direct_health_subtraction_in_runtime_gameplay():
    import subprocess
    cmd = ["rg", "-n", r"(health|hp)\s*-=", "engine", "-g", "*.py"]
    found = subprocess.run(cmd, text=True, capture_output=True, check=False)
    offenders = [line for line in found.stdout.splitlines() if "runtime_resources.py" not in line]
    assert offenders == []
