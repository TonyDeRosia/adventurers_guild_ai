from types import SimpleNamespace
from engine.character_stats import CharacterAttributeService, CombatStatService, StatModifier, ActorStatInput, NaturalWeaponProfile
from engine.mud_state_store import MUDStateStore


def svc(tmp_path):
    store=MUDStateStore(str(tmp_path/'state.db')); store.initialize()
    attr=CharacterAttributeService(store); return CombatStatService(attr)


def actor(**kw):
    d={'id':'hero','level':3,'hp':50,'mana':20,'stamina':20,'inventory':[]}
    d.update(kw); return SimpleNamespace(**d)


def test_actor_stat_input_consumes_all_modifier_buckets_and_traces(tmp_path):
    s=svc(tmp_path)
    ai=ActorStatInput('mob1','mob','shattered_realms','wolf','spawn1','inst1',None,3,{'strength':12,'dexterity':12,'constitution':12,'intelligence':10,'wisdom':10,'charisma':10},
        permanent_modifiers=[StatModifier('perm','permanent','p','derived.attack_power','add',1)],
        template_modifiers=[StatModifier('tmpl','template','t','derived.attack_power','add',2)],
        instance_modifiers=[StatModifier('inst','instance','i','derived.attack_power','add',3)],
        situational_modifiers=[StatModifier('sit','situational','s','derived.attack_power','add',4)],
        body_profile={'modifiers':[{'modifier_id':'body','source_type':'body_profile','source_id':'b','target_stat':'derived.attack_power','operation':'add','value':5}]},
        combat_profile={'modifiers':[{'modifier_id':'combat','source_type':'combat_profile','source_id':'c','target_stat':'derived.attack_power','operation':'add','value':6}]},
        source_versions={'template':'t1','instance':'i1'})
    bd=s.get_breakdown(ai,'attack_power')
    assert bd['components']['template']==2
    assert bd['components']['instance']==3
    assert bd['components']['situational']==4
    assert bd['components']['body_profile']==5
    assert bd['components']['combat_profile']==6
    assert {m['modifier_id'] for m in bd['modifiers']} >= {'perm','tmpl','inst','sit','body','combat'}
    snap=s.get_combat_snapshot(ai)
    assert snap.offense['attack_power'].template_component == 2
    assert snap.offense['attack_power'].operation_trace


def test_stacking_rules_are_shared_for_actor_inputs(tmp_path):
    s=svc(tmp_path)
    mods=[
        StatModifier('lo','effect','e1','derived.damage_bonus','add',2,stacking_group='g',stacking_rule='highest'),
        StatModifier('hi','equipment','e2','derived.damage_bonus','add',7,stacking_group='g',stacking_rule='highest'),
        StatModifier('uniq1','template','t','derived.damage_bonus','add',3,stacking_group='u',stacking_rule='unique_by_group'),
        StatModifier('uniq2','instance','i','derived.damage_bonus','add',4,stacking_group='u',stacking_rule='unique_by_group'),
    ]
    ai=ActorStatInput('a','npc','shattered_realms','t',None,'i',None,1,{},effect_snapshot=mods)
    applied=s.collect_actor_modifiers(ai)
    assert [m.modifier_id for m in applied] == ['hi','uniq2']


def test_semantic_role_projection_survives_attribute_ids(tmp_path):
    s=svc(tmp_path)
    vals=s.project_legacy_template_attributes('brute',9,'brute',{})
    assert s.semantic_roles['physical_power'] in vals
    assert s.semantic_roles['endurance'] in vals


def test_natural_weapon_is_snapshot_default_when_no_equipped_weapon(tmp_path):
    s=svc(tmp_path)
    bite=NaturalWeaponProfile('bite','Bite','melee',3,5,'pierce',100,1,0,0,'physical_power',0,True,'actor_stat',True,True)
    ai=ActorStatInput('wolf','mob','shattered_realms','wolf',None,'wolf1',None,2,{},natural_weapon_profiles=[bite])
    snap=s.get_combat_snapshot(ai)
    assert snap.weapon_profile.source == 'Bite'
    assert snap.natural_weapon_profiles[0].profile_id == 'bite'


def test_inventory_weight_snapshot_fallback_filters_destroyed_and_equipped(tmp_path):
    s=svc(tmp_path); ch=actor(inventory=[{'weight':2,'quantity':3},{'weight':10,'quantity':1,'destroyed':True},{'weight':4,'equipped_slot':'main_hand'}])
    snap=s.get_combat_snapshot(ch,{})
    assert snap.carrying['current_carry_weight'] == 6
