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


def test_respawned_entity_gets_new_lifecycle_and_can_die_again(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    first = wolf(rt)
    first_life = (first['state'] or {})['lifecycle_id']
    st = dict(first['state']); st.update({'current_health': 1, 'maximum_health': 8, 'is_alive': True})
    rt.update_entity_state(first['entity_id'], st)
    rt.command_engine.handle_command(ch, 'kill forest wolf')
    second = rt.respawn_entity(first['template_id'], room_id=ch.room_id, source_system='test')
    second_life = (second['state'] or {})['lifecycle_id']
    assert second_life != first_life
    st = dict(second['state']); st.update({'current_health': 1, 'maximum_health': 8, 'is_alive': True})
    rt.update_entity_state(second['entity_id'], st)
    rt.command_engine.handle_command(ch, 'kill forest wolf')
    with sqlite3.connect(rt.state_store.db_path) as con:
        rows = con.execute("SELECT death_id,lifecycle_id,corpse_entity_id FROM combat_death_transactions ORDER BY created_at").fetchall()
        assert len(rows) == 2
        assert len({r[0] for r in rows}) == 2
        assert len({r[1] for r in rows}) == 2
        assert len({r[2] for r in rows}) == 2
    corpses = rt.find_visible_entities(ch.room_id, ch).get('corpses', [])
    assert len(corpses) == 2


def test_output_drain_claims_messages_once_and_preserves_order(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    cid2 = rt.create_character(world_id='shattered_realms', name='Other')['character_id']
    rt.combat_runtime.enqueue_output(ch.id, 'one')
    rt.combat_runtime.enqueue_output(ch.id, 'two')
    rt.combat_runtime.enqueue_output(cid2, 'other')
    assert rt.combat_runtime.drain_output(ch.id) == ['one', 'two']
    assert rt.combat_runtime.drain_output(ch.id) == []
    assert rt.combat_runtime.drain_output(cid2) == ['other']


def test_action_consume_is_atomic_and_replaced_action_cannot_execute(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    w = wolf(rt)
    enc = rt.combat_runtime.start_encounter(ch.room_id)
    actor = rt.combat_runtime.actor_id_for_character(ch)
    defender = rt.combat_runtime.actor_from_entity(w)
    attacker = rt.combat_runtime._load_actor(actor)
    rt.combat_runtime.join_encounter(enc, attacker, 'side_1')
    rt.combat_runtime.join_encounter(enc, defender, 'side_2')
    rt.combat_runtime.queue_action(enc, actor, 'defend')
    rt.combat_runtime.queue_action(enc, actor, 'basic_attack', defender.actor_id)
    first = rt.combat_runtime._consume_action(enc, actor)
    second = rt.combat_runtime._consume_action(enc, actor)
    assert first and first['action_type'] == 'basic_attack'
    assert second is None
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM combat_action_queue WHERE status='replaced'").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM combat_action_queue WHERE status='consumed'").fetchone()[0] == 1
