import sqlite3
from engine.abilities import AbilityExecutionService, init_ability_schema
from engine.actors import Actor
from smart_mud.event_bus import EventBus

class pkg:
    id='w'; abilities=[]

def actor(aid, room):
    a=Actor.create(aid, aid, 'player'); a.identity.current_location=room; return a

def test_aura_reconciles_entry_exit_source_movement_and_restart(tmp_path):
    db=tmp_path/'mud.db'; init_ability_schema(db); bus=EventBus(); s=AbilityExecutionService(db,pkg(),bus,'w')
    s.register_actor(actor('hero','r1')); s.register_actor(actor('ally','r1')); s.register_actor(actor('far','r2'))
    aura=s.aura_runtime.activate_aura('hero','blessing',{'effect_id':'blessing','parameters':{'scope':'room','granted_effect_id':'blessed'}},'act1')
    assert [x['added'] for x in s.aura_runtime.reconcile_aura(aura['aura_instance_id'])] == []
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM aura_membership WHERE active=1").fetchone()[0] == 1
    bus.publish('movement_succeeded', {'actor_id':'far','new_room_id':'r1'}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM aura_membership WHERE active=1").fetchone()[0] == 2
    bus.publish('movement_succeeded', {'actor_id':'hero','new_room_id':'r2'}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM aura_membership WHERE active=1").fetchone()[0] == 0
        effects=c.execute("SELECT count(*) FROM actor_effect_instances WHERE active=1").fetchone()[0]
    bus.publish('runtime_ready', {}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM aura_membership WHERE active=1").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM actor_effect_instances WHERE active=1").fetchone()[0] == effects
    bus.publish('actor_died', {'actor_id':'hero'}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT active FROM aura_instances WHERE aura_instance_id=?", (aura['aura_instance_id'],)).fetchone()[0] == 0
