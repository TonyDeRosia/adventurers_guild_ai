from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus


def _runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=EventBus())
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Latency Save Policy")["character_id"]
    return rt, cid


def test_read_only_commands_do_not_save_character(tmp_path):
    rt, cid = _runtime(tmp_path)
    calls = []
    original = rt.state_store.save_character

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    rt.state_store.save_character = spy
    for command in ["look", "score", "worth", "equipment", "inventory", "abilities"]:
        result = rt.handle_input(cid, command)
        assert result["ok"] is True
        assert result["mutation_state"] == "read_only"
    assert calls == []


def test_quit_final_save_is_coalesced_to_one_character_save(tmp_path):
    rt, cid = _runtime(tmp_path)
    calls = []
    original = rt.state_store.save_character

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    rt.state_store.save_character = spy
    first = rt.handle_input(cid, "quit")
    assert first["ok"] is True
    assert first["mutation_state"] == "session_transition"
    assert len(calls) == 1
    assert rt.performance_counters["quit_final_saves"] == 1
