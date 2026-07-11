import sqlite3
from pathlib import Path
from types import SimpleNamespace

from engine.crafting import CraftingService, init_crafting_schema
from engine.economy import EconomyService, init_economy_schema
from engine.gathering import GatheringService, init_gathering_schema
from engine.property import PropertyService
from engine.survival_needs import SurvivalNeedsService, init_survival_schema

WORLD = Path('worlds/shattered_realms')

class Bus:
    def __init__(self): self.events=[]
    def publish(self, name, payload, **kw): self.events.append((name, payload, kw))

class Runtime(SimpleNamespace):
    def transfer_item(self, item_instance_id, to_owner, reason=''):
        owner_type, owner_id = to_owner
        with sqlite3.connect(self.db_path) as c:
            c.execute("UPDATE item_instances SET owner_type=?, owner_id=? WHERE instance_id=?", (owner_type, owner_id, item_instance_id))

def give(db, actor, iid, tid):
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,stack_count,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(iid,'shattered_realms',tid,'actor',actor,'emberwood_hunting_trail',1,'now','now','{}','{}'))
    return iid

def make_services(tmp_path):
    db=tmp_path/'loop.db'; init_gathering_schema(db); init_crafting_schema(db); init_survival_schema(db); init_economy_schema(db)
    bus=Bus(); rt=Runtime(db_path=db)
    surv=SurvivalNeedsService(db, WORLD, 'shattered_realms', event_bus=bus)
    econ=EconomyService(db, world_root=WORLD, event_bus=bus)
    prop=PropertyService(db, world_root=WORLD, event_bus=bus)
    object.__setattr__(prop, 'economy', econ)
    rt.survival_needs=surv; rt.property_service=prop; rt.transfer_item=rt.transfer_item
    craft=CraftingService(db, runtime=rt, world_root=WORLD, event_bus=bus)
    gather=GatheringService(db, WORLD, event_bus=bus)
    surv.runtime=rt; prop.economy=econ; econ.runtime=rt
    return db,bus,gather,craft,surv,econ,prop

def test_builder_authored_wolf_corpse_processing_is_deterministic_idempotent_and_persistent(tmp_path):
    db,bus,gather,_,_,_,_=make_services(tmp_path); actor='survivor'; corpse='corpse_wolf_loop'
    profile=gather.get_corpse_extraction_profile('starter_forest_wolf_corpse_processing')
    assert profile['actor_template_ids']==['forest_wolf']
    skin=gather.process_corpse(actor,corpse,'forest_wolf','skinning',world_time=20)
    meat=gather.process_corpse(actor,corpse,'forest_wolf','butchering',world_time=21)
    hide=gather.process_corpse(actor,corpse,'forest_wolf','harvesting',world_time=22)
    assert skin['yields']==[{'item_template_id':'wolf_pelt','quantity':1,'quality_id':'standard_quality'}]
    assert meat['yields']==[{'item_template_id':'small_meat','quantity':2,'quality_id':'standard_quality'}]
    assert hide['item_template_id']=='torn_hide'
    assert gather.process_corpse(actor,corpse,'forest_wolf','skinning',world_time=23)['reason']=='corpse_resource_already_extracted'
    assert any(e[0]=='corpse_processed' for e in bus.events)
    assert len(GatheringService(db,WORLD).trace_corpse_extraction(corpse)['extractions'])==3

def test_complete_survival_loop_cooking_consumption_sale_property_rest_and_restart_persist(tmp_path):
    db,bus,gather,craft,surv,econ,prop=make_services(tmp_path); actor='loop_actor'; corpse='corpse_wolf_loop2'
    craft.grant_profession(actor,'cooking')
    meat=gather.process_corpse(actor,corpse,'forest_wolf','butchering',world_time=30)
    give(db, actor, 'meat1', meat['item_template_id'])
    camp=surv.create_campfire(actor, room_id='guildhall_crossing_square'); surv.add_campfire_fuel(actor,camp['campfire_instance_id']); surv.light_campfire(actor,camp['campfire_instance_id'])
    job=craft.start_cooking(actor,'cooked_small_meat',['meat1'],'campfire')
    done=craft.complete_cooking(job['crafting_job_id']); trace=craft.trace_cooking_job(job['crafting_job_id'])
    cooked=trace['outputs'][0]['item_instance_id']
    assert done['status']=='completed' and trace['outputs'][0]['servings'] >= 1 and trace['outputs'][0]['freshness_profile_id']=='fresh_cooked_food'
    before=surv.get_actor_need(actor,'hunger')['current_value']; eaten=surv.consume_item(actor,cooked); after=surv.get_actor_need(actor,'hunger')['current_value']
    assert eaten['ok'] and eaten['servings_remaining'] >= 0 and after != before
    pelt=give(db, actor, 'pelt1', 'wolf_pelt'); quote=econ.quote_sale(actor,'blacksmith_shop',pelt); sale=econ.confirm_sale(actor,quote.quote_id)
    cooked_sale=give(db, actor, 'cooked_sale1', 'cooked_small_meat'); sale2=econ.confirm_sale(actor,econ.quote_sale(actor,'blacksmith_shop',cooked_sale).quote_id)
    assert sale['status']=='completed' and sale2['status']=='completed' and econ.get_currency_balance('actor',actor,'gold') >= 10
    prop.materialize_property('wayfarers_mug_room_1',world_time=40)
    room=prop.list_available_properties(actor, property_type='inn_room')[0]; rent_quote=prop.quote_rent(actor, room['property_instance_id'], duration=120)
    lease=prop.confirm_rent(actor,rent_quote.quote_id,duration_minutes=120,world_time=41)
    assert prop.evaluate_property_access(actor,room['property_instance_id'],'enter',world_time=42)['allowed']
    sleep=surv.start_sleep(actor,'inn_bed'); rest=surv.complete_rest(sleep['rest_session_id'])
    assert rest['status']=='completed'
    assert EconomyService(db, world_root=WORLD).get_currency_balance('actor',actor,'gold') == econ.get_currency_balance('actor',actor,'gold')
    assert PropertyService(db, world_root=WORLD).get_lease(lease['lease_id'])['status']=='active'
    assert SurvivalNeedsService(db,WORLD,'shattered_realms').get_actor_need(actor,'fatigue') is not None
    names={e[0] for e in bus.events}
    assert {'corpse_processed','cooking_completed','survival_event_consumption','shop_item_sold','property_rented','sleep_completed'} <= names

def test_builder_validation_loads_survival_loop_content(tmp_path):
    _,_,gather,craft,_,econ,prop=make_services(tmp_path)
    assert gather.validate_content()['ok']
    assert craft.get_cooking_recipe('cooked_small_meat')
    assert econ.content.get('shop_definitions','blacksmith_shop')
    assert prop.content.get('property_definitions','wayfarers_mug_room_1')
