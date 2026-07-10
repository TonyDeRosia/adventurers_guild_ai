from pathlib import Path
from engine.abilities import AbilityExecutionService, AbilityRegistry, init_ability_schema
from engine.actors import Actor
from smart_mud.world_registry import WorldRegistry


def pkg():
    return WorldRegistry().load_world('shattered_realms')


def service(tmp_path):
    db=tmp_path/'mud.db'; init_ability_schema(db)
    svc=AbilityExecutionService(db, pkg(), world_id='shattered_realms')
    a=Actor.create('hero','Hero','player'); b=Actor.create('rat_1','Rat','mob')
    svc.register_actor(a); svc.register_actor(b)
    for aid in ['power_strike','minor_heal','bless','poison_bite','basic_attack']:
        if aid in svc.registry.abilities: svc.grant_ability('hero', aid, 'test', aid)
    return svc,a,b


def test_phase6c_registry_loads_and_validates():
    reg=AbilityRegistry(pkg())
    assert 'power_strike' in reg.abilities
    assert 'minor_heal' in reg.abilities
    assert 'rat_basic' in reg.loadouts
    assert reg.validate() == []


def test_phase6c_grant_target_cost_cooldown_cast_damage_heal_effect(tmp_path):
    svc,a,b=service(tmp_path)
    assert any(x['ability_id']=='power_strike' for x in svc._grants('hero'))
    tr=svc.trace_ability('hero','power_strike','rat')
    assert tr['ok']
    before=a.resources.stamina
    res=svc.execute_instant_ability('hero','power_strike','rat')
    assert res['ok']
    assert a.resources.stamina < before
    assert svc.get_ability_status('hero','power_strike')['remaining'] >= 0
    a.resources.health=50
    heal=svc.execute_instant_ability('hero','minor_heal','self')
    assert heal['ok'] and a.resources.health > 50
    bless=svc.execute_instant_ability('hero','bless','self')
    assert bless['ok'] and a.effect_container.get('affects')


def test_phase6c_cast_records_and_cancel(tmp_path):
    svc,a,b=service(tmp_path)
    svc.registry.abilities['minor_heal'].timing={'activation_type':'cast','cast_time':2,'completes_immediately':False}
    res=svc.start_ability('hero','minor_heal','self')
    assert res['ok'] and res['cast_id'].startswith('cast_')
    assert svc.cancel_ability(res['cast_id'])['state']=='cancelled'
