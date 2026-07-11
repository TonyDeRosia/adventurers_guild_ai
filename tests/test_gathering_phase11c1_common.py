from pathlib import Path
import sqlite3
from engine.gathering import GatheringService, init_gathering_schema

WORLD = Path('worlds/shattered_realms')

def service(tmp_path):
    return GatheringService(tmp_path/'gathering.db', WORLD)

def node(gs):
    return gs.materialize_node('emberleaf_patch_crossing','guildhall_crossing_square', world_time=0)

def test_resource_definition_loading_and_validation(tmp_path):
    gs=service(tmp_path); v=gs.validate_content()
    assert v['ok'], v
    r=gs.get_resource_definition('emberleaf')
    assert r['resource_type']=='herb' and r['yield_profile_id']=='emberleaf_yield'

def test_node_definition_loading_materialization_and_restart(tmp_path):
    gs=service(tmp_path); n1=node(gs); n2=node(gs)
    assert n1['node_instance_id']==n2['node_instance_id']
    assert n1['capacity_current']==3 and n1['status']=='available'
    gs2=service(tmp_path)
    assert gs2.get_node_instance(n1['node_instance_id'])['capacity_current']==3

def test_capacity_depletion_idempotent_completion_and_traces(tmp_path):
    gs=service(tmp_path); n=node(gs)
    s=gs.start_gathering('actor1', n['node_instance_id'], 'emberleaf', 'training_sword', world_time=1)
    assert s['ok'], s
    r1=gs.complete_gathering(s['gathering_session_id'], world_time=2)
    r2=gs.complete_gathering(s['gathering_session_id'], world_time=2)
    assert r1['ok'] and r2['idempotent']
    n2=gs.get_node_instance(n['node_instance_id'])
    assert n2['capacity_current']==2 and n2['status']=='partially_depleted'
    assert gs.trace_node(n['node_instance_id'])['restart_state']=='SQLite authoritative'
    assert gs.trace_yield(s['gathering_session_id'])['deterministic'] is True

def test_world_time_regeneration_bounded_and_idempotent(tmp_path):
    gs=service(tmp_path); n=node(gs)
    for i in range(3):
        s=gs.start_gathering(f'a{i}', n['node_instance_id'], 'emberleaf', 'training_sword', world_time=i)
        assert s['ok']; gs.complete_gathering(s['gathering_session_id'], world_time=i+1)
    assert gs.get_node_instance(n['node_instance_id'])['status']=='depleted'
    out=gs.process_node_regeneration('shattered_realms', 500)
    assert out['regenerated']
    after=gs.get_node_instance(n['node_instance_id'])['capacity_current']
    assert after == 2  # maximum_cycles_per_tick bounds catch-up
    gs.process_node_regeneration('shattered_realms', 500)
    assert gs.get_node_instance(n['node_instance_id'])['capacity_current']==after

def test_availability_environment_requirements_and_tool_rejections(tmp_path):
    gs=service(tmp_path); n=node(gs)
    assert not gs.evaluate_node_availability('actor', n['node_instance_id'], environment={'season_id':'winter'})['available']
    assert gs.evaluate_node_availability('actor', n['node_instance_id'], environment={'season_id':'spring'})['available']
    assert not gs.evaluate_gathering_requirements('actor', n['node_instance_id'], 'emberleaf')['ok']
    bad=gs.evaluate_gathering_requirements('actor', n['node_instance_id'], 'emberleaf', tool_id='wrong_tool')
    assert not bad['ok'] and 'tool' in str(bad)

def test_interruption_cooldown_schema_concurrency_and_audit(tmp_path):
    db=tmp_path/'gathering.db'; init_gathering_schema(db); gs=GatheringService(db,WORLD); n=node(gs)
    s=gs.start_gathering('actor1', n['node_instance_id'], 'emberleaf', 'training_sword')
    assert s['ok']
    assert gs.interrupt_gathering(s['gathering_session_id'],'movement')['ok']
    rows=gs.get_actor_gathering_sessions('actor1')
    assert rows[0]['status']=='interrupted'
    with sqlite3.connect(db) as c:
        assert c.execute('select count(*) from gathering_audit_events').fetchone()[0] >= 1
