import sqlite3
from pathlib import Path

from engine.mud_runtime import MudRuntime


def runtime_with_wolf(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Kraevok')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.room_id = 'emberwood_hunting_trail'
    rt.state_store.save_character(ch, 'shattered_realms')
    return rt, rt.state_store.load_character(cid)


def wolf(rt):
    return rt.resolve_entity_keywords('forest wolf', rt.find_visible_entities('emberwood_hunting_trail').get('mobs', []))['entity']


def test_lethal_damage_retires_living_wolf_and_creates_lootable_corpse_once(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    w = wolf(rt)
    st = dict(w['state']); st.update({'current_health': 1, 'maximum_health': 8, 'is_alive': True})
    rt.update_entity_state(w['entity_id'], st)

    out = rt.command_engine.handle_command(ch, 'kill forest wolf')
    text = out.narrative.lower()
    assert 'killing blow' in text or 'collapses and dies' in text
    assert 'for 1 damage' not in text
    assert wolf(rt) is None

    corpses = rt.find_visible_entities('emberwood_hunting_trail', ch).get('corpses', [])
    assert len(corpses) == 1
    corpse = corpses[0]
    assert corpse['entity_type'] == 'corpse'
    assert (corpse.get('state') or {}).get('source_entity_id') == w['entity_id']

    look = rt._handle_runtime_command(ch, 'look corpse').narrative.lower()
    assert 'corpse of forest wolf' in look
    assert 'not been skinned' in look
    inside = rt._handle_runtime_command(ch, 'look in corpse').narrative.lower()
    assert 'inside the corpse' in inside or 'corpse is empty' in inside

    again = rt.combat_runtime._handle_lethal_damage(out.encounter_id if hasattr(out, 'encounter_id') else '', rt.combat_runtime.actor_from_entity(corpse), rt.combat_runtime.actor_from_entity(w)) if False else None
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM combat_death_transactions").fetchone()[0] == 1
    rt.create_corpse(w['entity_id'])
    assert len(rt.find_visible_entities('emberwood_hunting_trail', ch).get('corpses', [])) == 1


def test_room_look_and_actor_inspection_show_state_and_condition(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    w = wolf(rt)
    st = dict(w['state']); st.update({'current_health': 3, 'maximum_health': 8, 'current_state': 'sleeping'})
    rt.update_entity_state(w['entity_id'], st)
    room = rt._handle_runtime_command(ch, 'look').narrative.lower()
    assert 'forest wolf is sleeping here' in room
    look = rt._handle_runtime_command(ch, 'look forest wolf').narrative.lower()
    assert 'condition:' in look
    assert 'badly wounded' in look or 'seriously injured' in look
    assert 'equipment:' in look
