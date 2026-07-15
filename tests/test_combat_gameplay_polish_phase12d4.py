import sqlite3
from pathlib import Path

from engine.mud_runtime import MudRuntime


def runtime_with_wolves(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Kraevok')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.room_id = 'emberwood_hunting_trail'
    rt.state_store.save_character(ch, 'shattered_realms')
    return rt, rt.state_store.load_character(cid)


def test_look_reflects_combat_and_clears_after_death(tmp_path):
    rt, ch = runtime_with_wolves(tmp_path)
    wolf = rt.resolve_entity_keywords('forest wolf', rt.find_visible_entities(ch.room_id, ch)['mobs'])['entity']
    rt.command_engine.handle_command(ch, 'kill forest wolf')
    look = rt._handle_runtime_command(ch, 'look').narrative.lower()
    assert 'forest wolf is here, fighting kraevok.' in look

    current = rt.find_entity(wolf['entity_id'])
    st = dict(current['state']); st.update({'current_health': 1, 'maximum_health': 8, 'is_alive': True})
    rt.update_entity_state(wolf['entity_id'], st)
    for _ in range(6):
        rt.command_engine.handle_command(ch, 'kill forest wolf')
        rt.advance_world_time('shattered_realms', 2)
        if rt.find_visible_entities(ch.room_id, ch).get('corpses'):
            break
    after = rt._handle_runtime_command(ch, 'look').narrative.lower()
    assert 'fighting kraevok' not in after
    assert 'corpse of forest wolf' in after


def test_numbered_target_command_replaces_queued_action_without_duplicates(tmp_path):
    rt, ch = runtime_with_wolves(tmp_path)
    first = rt.command_engine.handle_command(ch, 'kill wolf')
    assert first.ok
    target = rt.command_engine.handle_command(ch, 'target 1.wolf')
    assert target.ok
    assert 'turn your attention' in target.narrative.lower()
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM combat_action_queue WHERE status='queued'").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM combat_action_queue WHERE status='replaced'").fetchone()[0] >= 1
