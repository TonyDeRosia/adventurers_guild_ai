import sqlite3
from pathlib import Path

from engine.zone_resets import ZoneResetService, init_zone_reset_schema

class FakeRuntime:
    active_world_id='shattered_realms'; world_generation=1
    def __init__(self, db):
        self.state_store=type('S',(),{'db_path':Path(db)})(); self.characters={}; self.spawned_entities=[]; self.spawned_items=[]
    def spawn_entity(self, template_id, room_id='', state=None, flags=None, source_system='runtime', **kw):
        eid=f'entity_{len(self.spawned_entities)+1}'
        self.spawned_entities.append(eid)
        with sqlite3.connect(self.state_store.db_path) as c:
            c.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'shattered_realms','npc',template_id,template_id,'[]','','',room_id,'room','','',1,'{}','[]','','','{}'))
        return {'entity_id':eid,'instance_id':eid}
    def spawn_item(self, template_id, owner_type, owner_id='', room_id='', stack_count=1, equipped_slot='', custom_flags=None, plugin_data=None):
        iid=f'item_{len(self.spawned_items)+1}'
        self.spawned_items.append(iid)
        with sqlite3.connect(self.state_store.db_path) as c:
            c.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,'shattered_realms',template_id,owner_type,owner_id or '',room_id or '',equipped_slot or '',stack_count,'normal',100,'','{}','{}','{}'))
        return {'instance_id':iid}

def init_runtime_tables(db):
    init_zone_reset_schema(db)
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE IF NOT EXISTS entity_instances(entity_id TEXT PRIMARY KEY,world_id TEXT,entity_type TEXT,template_id TEXT,name TEXT,keywords TEXT,short_description TEXT,long_description TEXT,current_room_id TEXT,owner_type TEXT,owner_id TEXT,faction_id TEXT,level INTEGER,state TEXT,flags TEXT,created_at TEXT,updated_at TEXT,plugin_data TEXT,destroyed_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS item_instances(instance_id TEXT PRIMARY KEY,world_id TEXT,template_id TEXT,owner_type TEXT,owner_id TEXT,room_id TEXT,equipped_slot TEXT,stack_count INTEGER,condition TEXT,durability INTEGER,created_at TEXT,updated_at TEXT,custom_flags TEXT,plugin_data TEXT,destroyed_at TEXT)")

def service(tmp_path):
    db=tmp_path/'mud.sqlite'; init_runtime_tables(db); rt=FakeRuntime(db); return ZoneResetService(runtime=rt, db_path=db), rt

def profile(**over):
    p={'reset_profile_id':'p','world_id':'shattered_realms','zone_id':'training_grounds','display_name':'P','enabled':True,'reset_mode':'manual_only','definition_version':'1','commands':[{'reset_command_id':'c1','command_type':'SPAWN_ENTITY','enabled':True,'order':1,'condition':{'type':'always'},'failure_policy':'continue','entity_template_id':'training_master_borik','room_id':'training_yard','spawn_count':2,'maximum_scope':'room','maximum_count':2,'result_reference':'guard'}]}
    p.update(over); return p

def test_profile_and_command_validation(tmp_path):
    svc,_=service(tmp_path)
    assert svc.validate_profile(profile()).ok
    bad=profile(reset_mode='sometimes'); assert 'invalid reset mode' in ';'.join(svc.validate_profile(bad).errors)
    bad=profile(commands=[dict(profile()['commands'][0], condition={'type':'python_eval'})]); assert 'invalid condition' in ';'.join(svc.validate_profile(bad).errors)
    bad=profile(commands=[dict(profile()['commands'][0], failure_policy='rollback')]); assert 'invalid failure policy' in ';'.join(svc.validate_profile(bad).errors)
    bad=profile(commands=[dict(profile()['commands'][0], maximum_scope='area')]); assert 'invalid maximum scope' in ';'.join(svc.validate_profile(bad).errors)

def test_reference_forward_validation_and_plan_cache(tmp_path):
    svc,_=service(tmp_path)
    p=profile(commands=[dict(profile()['commands'][0], reset_command_id='c2', target_reference='later')])
    assert 'invalid forward reference' in ';'.join(svc.validate_profile(p).errors)
    a=svc.compile_plan(profile()); b=svc.compile_plan(profile()); assert a is b
    svc.invalidate_plan_cache(); c=svc.compile_plan(profile()); assert c is not a

def test_manual_preview_non_mutating_and_count_limit(tmp_path):
    svc,rt=service(tmp_path); plan=svc.compile_plan(profile())
    res=svc.execute_plan(plan, preview=True, trigger='preview')
    assert res['status']=='succeeded' and rt.spawned_entities==[]
    res=svc.execute_plan(plan, trigger='manual')
    assert res['entities']==2
    res2=svc.execute_plan(plan, trigger='manual')
    assert res2['entities']==0

def test_modes_occupancy_and_duplicate_prevention(tmp_path):
    svc,rt=service(tmp_path)
    assert svc.execute_plan(svc.compile_plan(profile(reset_mode='never')), trigger='manual')['status']=='rejected'
    rt.characters={'char': {'room_id':'training_yard'}}
    assert svc.execute_plan(svc.compile_plan(profile(reset_mode='when_empty')), trigger='automatic')['status']=='skipped'
    rt.characters={}
    assert svc.execute_plan(svc.compile_plan(profile(reset_mode='always')), trigger='automatic')['status']=='succeeded'
    svc._active_profiles.add('p')
    assert svc.execute_plan(svc.compile_plan(profile()), trigger='manual')['reason']=='duplicate run prevented'
