import time
from pathlib import Path

from engine.mud_runtime import MudRuntime, MudCharacter
from engine.character_state import derive_position_from_health


def _rt(tmp_path):
    rt = MudRuntime(Path.cwd(), user_data_dir=tmp_path)
    rt.load_world("shattered_realms")
    admin = MudCharacter(id="char_admin_restore", name="Kraevok", role="admin", room_id="emberwood_hunting_trail", hp=0, max_hp=100, mana=0, max_mana=50, stamina=0, max_stamina=100, actor_data={"position":"stunned"})
    player = MudCharacter(id="char_player_restore", name="Player", role="player", room_id="emberwood_hunting_trail", hp=0, max_hp=100, mana=10, max_mana=50, stamina=20, max_stamina=100, actor_data={"position":"stunned"})
    rt.state_store.save_character(admin, "shattered_realms")
    rt.state_store.save_character(player, "shattered_realms")
    rt.enter_world(admin.id, session_id="admin")
    rt.enter_world(player.id, session_id="player")
    return rt, admin.id, player.id


def test_zero_hp_recovery_queues_message_and_prompt(tmp_path):
    rt, _aid, pid = _rt(tmp_path)
    actor = rt.combat_runtime.resident_actors[f"character:{pid}"]
    assert derive_position_from_health(0) == "stunned"
    before_saves = rt.performance_counters.get("character_saves", 0)
    rt.runtime_resources._next_regeneration_monotonic = 0
    assert rt.runtime_resources.process_due_regeneration(time.monotonic()) >= 1
    assert rt.active_characters[pid].hp == 1
    view = rt.async_messages(pid, after=0)
    assert any("regain consciousness" in m["output_text"] for m in view["messages"])
    assert view["prompt_changed"] and view["resource_changed"] and view["position_changed"]
    assert rt.performance_counters.get("character_saves", 0) == before_saves


def test_restore_self_online_target_all_and_diagnostics(tmp_path):
    rt, aid, pid = _rt(tmp_path)
    out = rt.handle_input(aid, "adminstatus")["output"]
    assert "RESTORE allowed: yes" in out
    out = rt.handle_input(aid, "restore self")["output"]
    assert "Restored Kraevok" in out
    assert rt.active_characters[aid].hp == 100
    out = rt.handle_input(aid, "restore Player")["output"]
    assert "Restored Player" in out
    assert rt.active_characters[pid].hp == 100
    assert list(rt.active_characters).count(pid) == 1
    rt.active_characters[pid].hp = 1
    out = rt.handle_input(aid, "restore all")["output"]
    assert "Restored Player" in out and "Kraevok" not in out
    assert "Restore stat" in rt.handle_input(aid, "restorestat Player")["output"]


def test_restore_offline_and_perf_schema(tmp_path):
    rt, aid, pid = _rt(tmp_path)
    rt.active_characters.pop(pid)
    rt.unregister_live_character(pid)
    out = rt.handle_input(aid, "restore Player")["output"]
    assert "offline" in out
    assert pid not in rt.active_characters
    assert rt.state_store.load_character(pid).hp == 100
    assert "schema valid" in rt.handle_input(aid, "perfstat validate")["output"].lower()
    assert "combat_sql_round_history_insert" in rt.handle_input(aid, "perfstat schema")["output"]
    assert "Performance counters reset." in rt.handle_input(aid, "perfstat reset")["output"]


def test_true_death_respawns_player(tmp_path):
    rt, _aid, pid = _rt(tmp_path)
    actor = rt.combat_runtime.resident_actors[f"character:{pid}"]
    actor.resources.health = -12
    actor.combat_profile["position"] = "mortally_wounded"
    rt.runtime_resources._respawn_player(actor, rt, reason="test_death")
    assert rt.active_characters[pid].hp == 100
    assert rt.active_characters[pid].actor_data["position"] == "standing"
    assert any("return you to life" in m["output_text"] for m in rt.async_messages(pid, 0)["messages"])
