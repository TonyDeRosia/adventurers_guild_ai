import sqlite3
from types import SimpleNamespace
from engine.crafting import CraftingService, init_crafting_schema
from engine.survival_needs import SurvivalNeedsService, init_survival_schema

class Runtime(SimpleNamespace):
    pass

def make_services(tmp_path):
    db=tmp_path/'mud.db'
    init_survival_schema(db); init_crafting_schema(db)
    surv=SurvivalNeedsService(db, 'worlds/shattered_realms', 'shattered_realms')
    rt=Runtime(survival_needs=surv)
    craft=CraftingService(db, runtime=rt, world_root='worlds/shattered_realms')
    rt.survival_needs=surv; surv.runtime=rt
    return db, craft, surv

def give(db, actor, iid, tid):
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,stack_count,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(iid,'shattered_realms',tid,'actor',actor,'guildhall_crossing_square',1,'now','now','{}','{}'))
    return iid

def cook_fish_flow(tmp_path):
    db, craft, surv = make_services(tmp_path); actor='cook_actor'
    craft.grant_profession(actor, 'cooking')
    give(db, actor, 'fish1', 'river_fish')
    prev=craft.preview_cooking(actor,'roasted_river_fish')
    assert prev.eligible, prev.details
    job=craft.start_cooking(actor,'roasted_river_fish')
    jid=job['crafting_job_id']
    job2=craft.complete_cooking(jid)
    assert job2['status']=='completed'
    again=craft.complete_cooking(jid)
    assert again['result_reward_packet_id']==job2['result_reward_packet_id']
    trace=craft.trace_cooking_job(jid)
    assert trace['outputs'] and trace['outputs'][0]['servings'] == 1
    out=trace['outputs'][0]['item_instance_id']
    assert surv.can_consume(actor,out).ok
    before=surv.get_actor_need(actor,'hunger')['current_value']
    res=surv.consume_item(actor,out)
    after=surv.get_actor_need(actor,'hunger')['current_value']
    assert res['ok'] and res['servings_remaining']==0 and after != before
    return trace
