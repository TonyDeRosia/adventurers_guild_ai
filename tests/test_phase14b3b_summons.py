import sqlite3
from engine.abilities import AbilityExecutionService, init_ability_schema
from engine.actors import Actor
from smart_mud.event_bus import EventBus

class pkg:
    id='w'; abilities=[]

def test_summon_presence_follow_cleanup_and_restart_hooks(tmp_path):
    db=tmp_path/'mud.db'; init_ability_schema(db); bus=EventBus(); s=AbilityExecutionService(db,pkg(),bus,'w')
    owner=Actor.create('hero','Hero','player'); owner.identity.current_location='r1'; s.register_actor(owner)
    out=s.summon_runtime.create_summons('hero','summon_guardian',{'parameters':{'name':'Guardian','follow_policy':'same_room','duration':5}},'act1')[0]
    sid=out['summon_instance_id']; assert sid in s.actors and s.actors[sid].identity.current_location == 'r1'
    bus.publish('movement_succeeded', {'actor_id':'hero','new_room_id':'r2'}, source_system='test')
    assert s.actors[sid].identity.current_location == 'r2'
    s.summon_runtime.cleanup_summon(sid, 'dismissed', 'act2')
    assert sid not in s.actors
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT state FROM summon_relationships WHERE actor_id=?", (sid,)).fetchone()[0] == 'dismissed'
