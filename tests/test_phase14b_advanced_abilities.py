from types import SimpleNamespace
import sqlite3
from engine.abilities import AbilityExecutionService, init_ability_schema
from engine.actors import Actor


def pkg():
    return SimpleNamespace(id='w', abilities=[
        {'id':'battle_aura','name':'Battle Aura','ability_type':'spell','targeting':{'mode':'self'},'plugin_data':{'canonical_effects':[{'effect_id':'battle_aura','operation':'aura','parameters':{'granted_effect_id':'battle_blessing'}}]}},
        {'id':'guard_stance','name':'Guard Stance','ability_type':'technique','targeting':{'mode':'self'},'plugin_data':{'canonical_effects':[{'effect_id':'guard_stance','operation':'stance','parameters':{'exclusive_group':'combat','modifiers':[{'stat_id':'defense','operation':'add','value':2}]}}]}},
        {'id':'wolf_form','name':'Wolf Form','ability_type':'spell','targeting':{'mode':'self'},'plugin_data':{'canonical_effects':[{'effect_id':'wolf_form','operation':'transform','parameters':{'body_profile_id':'wolf','natural_weapon_profiles':[{'id':'bite','minimum_damage':2,'maximum_damage':5}]}}]}},
        {'id':'summon_guardian','name':'Summon Guardian','ability_type':'spell','targeting':{'mode':'self'},'plugin_data':{'canonical_effects':[{'effect_id':'guardian','operation':'summon','parameters':{'summon_template_id':'guardian','name':'Guardian','duration':2,'natural_weapon_profiles':[{'id':'claw'}],'ability_grants':['guard_stance']}}]}},
        {'id':'make_spark','name':'Make Spark','ability_type':'spell','targeting':{'mode':'self'},'plugin_data':{'canonical_effects':[{'effect_id':'spark','operation':'create_item','parameters':{'template_id':'spark','quantity':1}}]}},
        {'id':'camp_field','name':'Camp Field','ability_type':'spell','targeting':{'mode':'self'},'plugin_data':{'canonical_effects':[{'effect_id':'camp_field','operation':'create_room_effect','parameters':{'room_id':'r1','duration':2,'tick_interval':1}}]}},
    ], ability_loadouts=[], ability_schools=[], ability_categories=[], cooldown_groups=[], effect_templates=[], resource_profiles=[], damage_profiles=[], combat_formulas=[])


def svc(tmp_path):
    db=tmp_path/'mud.db'; init_ability_schema(db); s=AbilityExecutionService(db,pkg(),world_id='w')
    hero=Actor.create('hero','Hero','player'); ally=Actor.create('ally','Ally','mob'); hero.identity.current_location='r1'; ally.identity.current_location='r1'
    s.register_actor(hero); s.register_actor(ally)
    for aid in s.registry.abilities: s.grant_ability('hero',aid)
    return s, db


def test_aura_membership_and_cleanup(tmp_path):
    s, db=svc(tmp_path)
    res=s.execute_instant_ability('hero','battle_aura','self')
    aura=res['effect_events'][0]['results'][0]['aura_instance_id']
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM aura_membership WHERE aura_instance_id=? AND active=1',(aura,)).fetchone()[0] == 1
    s.remove_aura(aura,'source_logout')
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM aura_membership WHERE aura_instance_id=? AND active=1',(aura,)).fetchone()[0] == 0


def test_stance_transform_summon_item_and_room_effect(tmp_path):
    s, db=svc(tmp_path)
    assert s.execute_instant_ability('hero','guard_stance','self')['ok']
    assert s.execute_instant_ability('hero','wolf_form','self')['effect_events'][0]['results'][0]['body_profile_id']=='wolf'
    sr=s.execute_instant_ability('hero','summon_guardian','self')['effect_events'][0]['results'][0]
    assert sr['summon_instance_id'] in s.actors
    assert s.process_summon_expirations(2)
    assert sr['summon_instance_id'] not in s.actors
    item=s.execute_instant_ability('hero','make_spark','self')['effect_events'][0]['results'][0]
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT template_id FROM item_instances WHERE instance_id=?',(item['item_instance_id'],)).fetchone()[0]=='spark'
    room=s.execute_instant_ability('hero','camp_field','self')['effect_events'][0]['results'][0]
    assert s.process_room_effect_ticks(1)[0]['room_effect_instance_id']==room['room_effect_instance_id']


def test_summon_profile_save_restore_and_repair(tmp_path):
    s, db=svc(tmp_path)
    sid=s.execute_instant_ability('hero','summon_guardian','self')['effect_events'][0]['results'][0]['summon_instance_id']
    profile=s.save_summon_profile('hero',sid,'guardian')
    s.dismiss_summon('hero',sid)
    restored=s.restore_summon_profile('hero', profile['profile_id'])
    assert restored['ok'] and restored['summon_instance_id'] in s.actors
    assert s.repair_summon_profile({'profile_id':'bad'})['repair_strategy']=='deterministic_fallback'
