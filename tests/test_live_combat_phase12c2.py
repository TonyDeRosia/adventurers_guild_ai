from pathlib import Path
import time

from engine.mud_runtime import MudRuntime


def _runtime(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Pulse Tester')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.room_id = 'emberwood_hunting_trail'
    rt.state_store.save_character(ch, 'shattered_realms')
    rt.enter_world(cid, session_id='session_pulse')
    visible = rt.find_visible_entities(ch.room_id, ch)
    for wolf in visible.get('npcs', []) + visible.get('mobs', []):
        if 'wolf' in str(wolf.get('name', '')).lower():
            rt.update_entity_state(str(wolf.get('entity_id') or wolf.get('instance_id')), {'current_health': 500, 'maximum_health': 500, 'is_alive': True, 'current_state': 'standing'})
            break
    return rt, cid


def test_runtime_pulse_delivers_delayed_combat_output_once(tmp_path):
    rt, cid = _runtime(tmp_path)
    first = rt.handle_input(cid, 'attack forest wolf')
    assert first['ok']
    rt.process_runtime_pulse(time.monotonic() + 2.1)
    view = rt.play_view(cid)
    assert view['async_messages']
    assert any(any(word in m.lower() for word in ('hit', 'miss', 'strike', 'attack', 'graz', 'slash', 'bite')) for m in view['async_messages'])
    assert rt.play_view(cid)['async_messages'] == []


def test_world_time_advancement_does_not_trigger_combat_round(tmp_path):
    rt, cid = _runtime(tmp_path)
    assert rt.handle_input(cid, 'attack forest wolf')['ok']
    rt.play_view(cid)
    rt.advance_world_time('shattered_realms', 120)
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
