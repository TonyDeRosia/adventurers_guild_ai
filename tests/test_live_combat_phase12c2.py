from pathlib import Path

from engine.mud_runtime import MudRuntime


def _runtime(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Pulse Tester')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.room_id = 'emberwood_hunting_trail'
    rt.state_store.save_character(ch, 'shattered_realms')
    rt.enter_world(cid, session_id='session_pulse')
    return rt, cid


def test_runtime_pulse_delivers_delayed_combat_output_once(tmp_path):
    rt, cid = _runtime(tmp_path)
    first = rt.handle_input(cid, 'attack forest wolf')
    assert first['ok']
    rt.runtime_pulse(2)
    view = rt.play_view(cid)
    assert view['async_messages']
    assert any(any(word in m.lower() for word in ('hit', 'miss', 'strike', 'attack', 'graz', 'slash', 'bite')) for m in view['async_messages'])
    assert rt.play_view(cid)['async_messages'] == []


def test_movement_block_defend_and_flee_use_combat_runtime(tmp_path):
    rt, cid = _runtime(tmp_path)
    rt.handle_input(cid, 'attack forest wolf')
    blocked = rt.handle_input(cid, 'west')
    assert 'Use FLEE' in blocked['output']
    defended = rt.handle_input(cid, 'defend')
    assert 'defend' in defended['output'].lower() or 'guard' in defended['output'].lower()
    fled = rt.handle_input(cid, 'flee')
    assert fled['ok']
    assert 'break away' in fled['output'].lower()
