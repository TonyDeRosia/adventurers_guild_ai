import time
from pathlib import Path

from engine.mud_runtime import MudRuntime, MudCharacter


def _runtime(tmp_path: Path):
    rt = MudRuntime(Path.cwd(), user_data_dir=tmp_path)
    rt.load_world("shattered_realms")
    cid = "char_shattered_realms_hbtester"
    ch = MudCharacter(id=cid, name="HB Tester", role="admin", room_id="emberwood_hunting_trail", hp=30, max_hp=30, mana=10, max_mana=10, stamina=10, max_stamina=10)
    rt.state_store.save_character(ch, "shattered_realms")
    rt.enter_world(cid, session_id="sess")
    return rt, cid


def test_heartbeat_config_and_admin_commands(tmp_path):
    rt, cid = _runtime(tmp_path)
    assert rt.pulse_config["base_pulse_ms"] == 100
    out = rt.handle_input(cid, "pulseinfo")["output"]
    assert "violence_pulse_count" in out
    assert "base_pulse_ms" in out
    assert "Residents" in rt.handle_input(cid, "residentlist")["output"]
    assert "regeneration_active" in rt.handle_input(cid, f"residentstat {cid}")["output"]


def test_combat_and_movement_do_not_synchronously_save(tmp_path):
    rt, cid = _runtime(tmp_path)
    before = rt.performance_counters.get("character_sql_saves", 0)
    res = rt.handle_input(cid, "attack forest wolf")
    assert res["ok"]
    assert res["save_status"]["status"] == "dirty_awaiting_autosave"
    assert rt.performance_counters.get("character_sql_saves", 0) == before
    blocked = rt.handle_input(cid, "west")
    assert "FLEE" in blocked["output"]
    assert rt.performance_counters.get("character_sql_saves", 0) == before


def test_violence_pulse_delivers_without_command_and_logout_evicts(tmp_path):
    rt, cid = _runtime(tmp_path)
    rt.handle_input(cid, "attack forest wolf")
    rt.process_runtime_pulse(time.monotonic() + 2.2)
    view = rt.play_view(cid)
    assert view["async_messages"]
    rt.handle_input(cid, "quit")
    assert cid not in rt.active_characters
    assert f"character:{cid}" not in rt.combat_runtime.resident_actors


def test_restore_self_and_latency_stats(tmp_path):
    rt, cid = _runtime(tmp_path)
    ch = rt.active_characters[cid]
    ch.hp = 0; ch.mana = 0; ch.stamina = 0
    rt.mark_character_dirty(cid, "test")
    out = rt.handle_input(cid, "restore self")["output"]
    assert "Restored" in out
    assert ch.hp == ch.max_hp and ch.mana == ch.max_mana and ch.stamina == ch.max_stamina
    assert "Latency statistics" in rt.handle_input(cid, "latencystat")["output"]


def test_corpse_keyword_resolution_shared_for_get(tmp_path):
    rt, cid = _runtime(tmp_path)
    ch = rt.active_characters[cid]
    corpse = rt.spawn_entity("forest_wolf", entity_type="corpse", room_id=ch.room_id, state={"current_state":"corpse","container_open":True,"created_monotonic":time.monotonic(),"decay_seconds":999}, flags=["corpse"])
    cid_corpse = corpse["entity_id"]
    item = rt.spawn_item("wolf_pelt", owner_type="corpse", owner_id=cid_corpse)
    out = rt.handle_input(cid, "get all cor")["output"]
    assert "Wolf Pelt" in out or item["name"] in out
    assert rt.find_inventory_items(cid)
