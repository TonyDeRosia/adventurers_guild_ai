import sqlite3
from engine.abilities import AbilityExecutionService, init_ability_schema
from engine.actors import Actor
from smart_mud.event_bus import EventBus

class pkg:
    id='w'; abilities=[]

def make_actor(aid, room):
    a=Actor.create(aid,aid,'player'); a.identity.current_location=room; return a

def test_room_effect_resident_entry_exit_ticks_and_recovery(tmp_path):
    db=tmp_path/'mud.db'; init_ability_schema(db); bus=EventBus(); s=AbilityExecutionService(db,pkg(),bus,'w')
    s.register_actor(make_actor('caster','r1')); s.register_actor(make_actor('resident','r1')); s.register_actor(make_actor('visitor','r2'))
    fx=s.room_effect_runtime.create_room_effect('caster','campfire',{'effect_id':'warmth','parameters':{'room_id':'r1','tick_interval':1,'resident_operations':[{'effect_id':'warm','tags':['benefit']}]}},'act1')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM room_effect_membership WHERE state='active'").fetchone()[0] == 2
    bus.publish('movement_succeeded', {'actor_id':'visitor','new_room_id':'r1'}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM room_effect_membership WHERE state='active'").fetchone()[0] == 3
    ticks=s.room_effect_runtime.process_ticks(1); assert len(ticks) == 1
    assert s.room_effect_runtime.process_ticks(1) == []
    bus.publish('actor_left_room', {'actor_id':'visitor','room_id':'r1'}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT state FROM room_effect_membership WHERE actor_id='visitor'").fetchone()[0] == 'left_room'
    bus.publish('runtime_ready', {}, source_system='test')
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT count(*) FROM room_effect_membership WHERE room_effect_instance_id=? AND actor_id='resident'", (fx['room_effect_instance_id'],)).fetchone()[0] == 1
