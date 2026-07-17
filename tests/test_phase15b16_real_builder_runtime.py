from pathlib import Path
import sqlite3

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Kraevok')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.role = 'admin'; ch.builder_enabled = True
    rt.state_store.save_character(ch, 'shattered_realms')
    rt.active_characters[cid] = ch
    return rt, cid


def test_builder_testspawn_is_real_resident_runtime_actor(tmp_path):
    rt, cid = make_runtime(tmp_path)
    for cmd in ['medit ashback_bear', 'body bear', 'save', 'builder testroom', 'builder testspawn ashback_bear']:
        assert rt.handle_input(cid, cmd)['ok']
    ch = rt.active_characters[cid]
    visible = rt.find_visible_entities(ch.room_id, ch)['mobs']
    bear = rt.resolve_entity_keywords('bear', visible)['entity']
    actor_id = rt.entity_instance_to_actor_id[bear['entity_id']]
    assert actor_id in rt.combat_runtime.resident_actors
    assert actor_id in rt.resident_occupants_by_room[ch.room_id]
    assert 'Ashback Bear' in rt.handle_input(cid, 'look')['output']
    assert 'Ashback Bear' in rt.handle_input(cid, 'examine bear')['output']
    assert 'You consider Ashback Bear' in rt.handle_input(cid, 'consider bear')['output']
    weapons = rt.combat_runtime.resident_actors[actor_id].combat_profile['natural_weapons']
    assert {w['mechanical_family'] for w in weapons} == {'claw', 'maul', 'bite'}
    assert not ({'fist', 'punch'} & {w['mechanical_family'] for w in weapons})
    assert rt.handle_input(cid, 'kill bear')['ok']
    assert rt.combat_runtime.find_actor_encounter(f'character:{cid}')
    assert rt.builder_test_rooms
    assert rt.handle_input(cid, 'builder testclear')['ok']
    assert actor_id not in rt.combat_runtime.resident_actors
    assert ch.room_id not in rt.resident_occupants_by_room
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("select count(*) from entity_instances where entity_id=?", (bear['entity_id'],)).fetchone()[0] == 0


def test_runtime_generation_activation_and_new_spawn_policy(tmp_path):
    rt, cid = make_runtime(tmp_path)
    actor = rt.active_characters[cid]
    svc = rt.command_engine.builder_service
    assert svc.publish(actor).ok
    gen_a = svc.publish(actor).data['generation']
    assert svc.activate_generation(actor, gen_a).ok
    old = rt.materialize_entity_template(dict(rt.entity_templates['forest_wolf']), actor.room_id, generation_id=rt.active_content_generation_id)
    old_actor = rt.combat_runtime.resident_actors[rt.actor_id_for_entity_instance(old)]
    assert old_actor.generation_id == gen_a
    assert svc.start_editor(actor, 'medit', 'entities', 'forest_wolf').ok
    assert svc.sessions.handle(actor, 'name Forest Wolf B').ok
    assert svc.sessions.handle(actor, 'save').ok
    gen_b = svc.publish(actor).data['generation']
    assert svc.activate_generation(actor, gen_b).ok
    assert rt.active_content_generation_id == gen_b
    new = rt.materialize_entity_template(dict(rt.entity_templates['forest_wolf']), actor.room_id, generation_id=rt.active_content_generation_id)
    assert rt.combat_runtime.resident_actors[rt.actor_id_for_entity_instance(new)].generation_id == gen_b
    assert old_actor.generation_id == gen_a
    assert svc.rollback_generation(actor).ok
    assert rt.active_content_generation_id == gen_a
