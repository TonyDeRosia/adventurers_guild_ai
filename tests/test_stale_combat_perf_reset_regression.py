import sqlite3
from pathlib import Path

from engine.actors import Actor, ActorIdentity, ActorResources
from engine.mud_runtime import MudRuntime
from engine.performance_counters import validate_performance_counter_schema


def _runtime(tmp_path):
    rt = MudRuntime(Path("."), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Stale Combat Tester")["character_id"]
    ch = rt.state_store.load_character(cid)
    ch.room_id = "emberwood_hunting_trail"
    ch.role = "admin"
    rt.state_store.save_character(ch, "shattered_realms")
    rt.enter_world(cid, session_id="stale-combat")
    return rt, cid, rt._resident_character(cid)


def _durable_wolf(rt, ch):
    for wolf in rt.find_visible_entities(ch.room_id, ch).get("npcs", []) + rt.find_visible_entities(ch.room_id, ch).get("mobs", []):
        if "wolf" in str(wolf.get("name", "")).lower():
            rt.update_entity_state(str(wolf.get("entity_id") or wolf.get("instance_id")), {"current_health": 500, "maximum_health": 500, "is_alive": True, "current_state": "standing"})
            return


def test_perfstat_reset_keeps_typed_maps_and_rejected_kill_safe(tmp_path):
    rt, cid, ch = _runtime(tmp_path)
    before_scheduler = rt.performance_counters.get("scheduler_starts")
    out = rt.command_engine.handle_command(ch, "perfstat reset")
    assert out.ok, out.narrative
    assert isinstance(rt.performance_counters["combat_validation_rejection_by_reason"], dict)
    assert isinstance(rt.combat_runtime.violence_profiler.rows, dict)
    assert rt.performance_counters.get("scheduler_starts") == before_scheduler
    assert rt.performance_counters["combat_encounters_active"] == 0
    assert validate_performance_counter_schema(rt.performance_counters) == (True, "")

    before_saves = rt.performance_counters.get("character_saves", 0)
    ch.room_id = "training_yard"
    rejected = rt.handle_input(cid, "kill borik")
    assert "Trace ID" not in rejected["output"]
    assert not rejected["ok"]
    assert "protected" in rejected["output"].lower()
    assert rt.performance_counters["combat_validation_rejection_by_reason"].get("protected") == 1
    assert not rt.combat_runtime.find_actor_encounter(rt.combat_runtime.actor_id_for_character(ch))
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM combat_encounters WHERE status='active'").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM combat_action_queue WHERE status='queued'").fetchone()[0] == 0
    assert rt.performance_counters.get("character_saves", 0) == before_saves

    out2 = rt.command_engine.handle_command(ch, "perfstat reset")
    assert out2.ok
    assert isinstance(rt.performance_counters["combat_validation_rejection_by_reason"], dict)


def test_encounter_guard_prevents_old_cleanup_from_clearing_new_fight(tmp_path):
    rt, _cid, ch = _runtime(tmp_path)
    cr = rt.combat_runtime
    hero = cr._actor_from_source(ch)
    old_foe = Actor("entity:old", "npc", ActorIdentity(name="Old Foe", current_location=ch.room_id), ActorResources(health=100, maximum_health=100))
    new_foe = Actor("entity:new", "npc", ActorIdentity(name="New Foe", current_location=ch.room_id), ActorResources(health=100, maximum_health=100))

    encounter_a = cr.start_encounter(ch.room_id)
    cr.join_encounter(encounter_a, hero, "side_1")
    cr.join_encounter(encounter_a, old_foe, "side_2")
    cr.set_target(encounter_a, hero.actor_id, old_foe.actor_id)
    cr.clear_actor_combat_state(hero.actor_id, "flee_success", expected_encounter_id=encounter_a, status="fled")
    cr.end_encounter(encounter_a, "fled")

    encounter_b = cr.start_encounter(ch.room_id)
    hero = cr._actor_from_source(ch)
    cr.join_encounter(encounter_b, hero, "side_1")
    cr.join_encounter(encounter_b, new_foe, "side_2")
    cr.set_target(encounter_b, hero.actor_id, new_foe.actor_id)
    cr.set_target(encounter_b, new_foe.actor_id, hero.actor_id)

    assert cr.clear_actor_combat_state(hero.actor_id, "delayed_old_cleanup", expected_encounter_id=encounter_a, status="fled") is False
    assert cr.find_actor_encounter(hero.actor_id) == encounter_b
    with sqlite3.connect(rt.state_store.db_path) as con:
        row = con.execute("SELECT current_target_actor_id, participation_status FROM combat_participants WHERE encounter_id=? AND actor_id=?", (encounter_b, hero.actor_id)).fetchone()
    assert row == (new_foe.actor_id, "active")


def test_windows_flee_sequence_projection_and_second_flee(tmp_path):
    rt, cid, ch = _runtime(tmp_path)
    _durable_wolf(rt, ch)
    assert not rt.combat_runtime.is_actor_in_active_combat(rt.combat_runtime.actor_id_for_character(ch))
    assert rt.handle_input(cid, "attack forest wolf")["ok"]
    assert rt.combat_runtime.is_actor_in_active_combat(rt.combat_runtime.actor_id_for_character(ch))
    assert "Use FLEE" in rt.handle_input(cid, "west")["output"]
    start_room = ch.room_id
    start_stamina = ch.stamina
    fled = rt.handle_input(cid, "flee")
    assert fled["ok"]
    assert ch.room_id != start_room
    assert not rt.combat_runtime.is_actor_in_active_combat(rt.combat_runtime.actor_id_for_character(ch))
    assert "Standing" in rt.handle_input(cid, "score")["output"]
    assert "Fighting" not in rt.handle_input(cid, "score")["output"]
    assert rt.performance_counters.get("combat_encounters_active", 0) == 0 or not rt.combat_runtime.is_actor_in_active_combat(rt.combat_runtime.actor_id_for_character(ch))
    moved_from = ch.room_id
    assert rt.handle_input(cid, "east")["ok"] or rt.handle_input(cid, "west")["ok"]
    second_room = ch.room_id
    second = rt.handle_input(cid, "flee")
    assert "You are not fighting." in second["output"]
    assert ch.room_id == second_room
    assert ch.stamina == start_stamina
    assert not any("fled" in m.lower() for m in second.get("view", {}).get("async_messages", []))
    assert moved_from != ""
