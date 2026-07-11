import json, sqlite3
from pathlib import Path

from engine.survival_needs import SurvivalNeedsService, init_survival_schema

WORLD = Path('worlds/shattered_realms')

def test_phase11d1_definitions_profiles_and_schema(tmp_path):
    db=tmp_path/'mud.db'; init_survival_schema(db)
    svc=SurvivalNeedsService(db,WORLD,'shattered_realms')
    assert not svc.content.validate()
    with sqlite3.connect(db) as con:
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'actor_need_state','actor_need_history','need_progression_events','consumption_sessions','consumption_results','survival_event_consumption','survival_audit_events'} <= tables
    assert {'hunger','thirst','fatigue','nutrition','hydration','satiation'} <= {r['id'] for r in svc.content.list('actor_need_definitions')}

def test_phase11d1_initialization_persistence_and_deterministic_progression(tmp_path):
    db=tmp_path/'mud.db'; init_survival_schema(db)
    svc=SurvivalNeedsService(db,WORLD,'shattered_realms')
    rows=svc.initialize_actor_needs('char_survivor')
    assert len(rows) == 6
    again=svc.initialize_actor_needs('char_survivor')
    assert len(again) == 6
    svc.process_actor_needs('char_survivor', 60)
    h=svc.get_actor_need('char_survivor','hunger')
    assert round(h['current_value'], 2) == 83.8
    svc2=SurvivalNeedsService(db,WORLD,'shattered_realms')
    assert round(svc2.get_actor_need('char_survivor','hunger')['current_value'], 2) == 83.8
    assert svc2.preview_need_progression('char_survivor', 60)[0]['target_world_time'] == 60

def test_phase11d1_exact_item_consumption_portions_idempotency(tmp_path):
    db=tmp_path/'mud.db'; init_survival_schema(db)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data,destroyed_at,destroy_reason,servings_remaining) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('item_water','shattered_realms','waterskin','actor','char_survivor','','',1,'normal',100,'0','0',json.dumps({'servings_remaining':2}),json.dumps({}),None,'',2))
    svc=SurvivalNeedsService(db,WORLD,'shattered_realms')
    svc.initialize_actor_needs('char_survivor')
    before=svc.get_actor_need('char_survivor','thirst')['current_value']
    r1=svc.consume_item('char_survivor','item_water')
    r2=svc.consume_item('char_survivor','item_water')
    r3=svc.consume_item('char_survivor','item_water')
    assert r1['ok'] and r2['ok'] and not r3['ok']
    assert r2['servings_remaining'] == 0
    assert svc.get_actor_need('char_survivor','thirst')['current_value'] > before
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT servings_remaining FROM item_instances WHERE instance_id='item_water'").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM consumption_sessions WHERE item_instance_id='item_water' AND status='completed'").fetchone()[0] == 2

def test_phase11d1_legacy_living_world_needs_migrate(tmp_path):
    db=tmp_path/'mud.db'; init_survival_schema(db)
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE entity_needs(id TEXT PRIMARY KEY,world_id TEXT,entity_instance_id TEXT,need_type TEXT,current_value REAL,minimum REAL,maximum REAL,decay_rate REAL,recovery_rate REAL,threshold_low REAL,threshold_critical REAL,disabled INTEGER,last_updated_at TEXT,created_at TEXT,updated_at TEXT,plugin_data JSON)")
        con.execute("INSERT INTO entity_needs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('old','shattered_realms','char_legacy','hunger',42,0,100,0,0,30,10,0,'0','0','0','{}'))
    svc=SurvivalNeedsService(db,WORLD,'shattered_realms')
    assert svc.get_actor_need('char_legacy','hunger')['current_value'] == 42
