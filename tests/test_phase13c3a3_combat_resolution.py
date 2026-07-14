from engine.actors import Actor, ActorResources
from engine.character_stats import CharacterAttributeService, CombatStatService, StatModifier
from engine.combat import CombatEngine, CombatResolutionContext, AttackKind


def make_actor(actor_id, attrs=None, hp=100):
    a=Actor.create(actor_id, actor_id.title())
    a.attributes.update(attrs or {})
    a.resources=ActorResources(health=hp, maximum_health=hp)
    return a


def service():
    attr=CharacterAttributeService(state_store=None)
    return CombatStatService(attr)


def test_canonical_hit_damage_armor_resistance_and_critical_are_snapshot_driven():
    stats=service()
    engine=CombatEngine(combat_stats=stats, seed='phase13c3a3')
    attacker=make_actor('attacker', {'strength':20, 'dexterity':20, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    defender=make_actor('defender', {'strength':10, 'dexterity':1, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    defender.resistance_profile={'physical': 25}
    result=engine.resolution.resolve(attacker, defender, CombatResolutionContext(attacker_id='attacker', defender_id='defender', action_id='sure_hit'))
    assert result.ok and result.hit
    assert result.raw_amount > result.final_amount
    assert result.resource_changes[0].after == 100 - result.final_amount
    assert result.diagnostics['trace'][1]['step'] == 'attack_roll_resolved'


def test_deterministic_miss_returns_structured_result_and_messages():
    stats=service()
    engine=CombatEngine(combat_stats=stats, seed='phase13c3a3')
    engine.resolution.rng=lambda *parts: 100
    attacker=make_actor('attacker', {'strength':1, 'dexterity':1, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    defender=make_actor('defender', {'strength':10, 'dexterity':30, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    result=engine.resolution.resolve(attacker, defender, CombatResolutionContext(attacker_id='attacker', defender_id='defender'))
    assert result.ok and not result.hit
    assert result.reason_code == 'miss'
    assert 'miss' in result.messages['attacker'].lower()


def test_healing_kind_clamps_to_maximum_and_uses_healing_result():
    stats=service()
    engine=CombatEngine(combat_stats=stats, seed='phase13c3a3')
    engine.resolution.rng=lambda *parts: 1
    healer=make_actor('healer', {'strength':10, 'dexterity':20, 'constitution':10, 'intelligence':10, 'wisdom':20, 'charisma':10})
    target=make_actor('target', {'strength':10, 'dexterity':1, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10}, hp=100)
    target.resources.health=95
    result=engine.resolution.resolve(healer, target, CombatResolutionContext(attacker_id='healer', defender_id='target', attack_kind=AttackKind.HEALING.value))
    assert result.ok and result.hit
    assert target.resources.health == 100
    assert result.resource_changes[0].operation == 'healing'


def test_damage_bonus_applies_once_and_weapon_roll_is_not_average():
    stats=service(); engine=CombatEngine(combat_stats=stats, seed='damage-contract')
    seq=iter([1, 1, 1, 1])
    engine.resolution.rng=lambda *parts: next(seq)
    attacker=make_actor('attacker', {'strength':10, 'dexterity':10, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    attacker.equipment_profile={'equipped': {'main_hand': {'instance_id':'w1','template_id':'w1','id':'w1','name':'Test Axe','damage_min':2,'damage_max':6,'damage_type':'slash'}}}
    attacker.effect_container={'modifiers':[{'id':'dam','target_stat':'derived.damage_bonus','operation':'add','value':5,'source_type':'effect'}]}
    defender=make_actor('defender', {'strength':10, 'dexterity':1, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    res=engine.resolution.resolve(attacker, defender, CombatResolutionContext(attacker_id='attacker', defender_id='defender', action_id='a'))
    trace=res.diagnostics['trace'][-1]
    assert trace['weapon_roll'] == 1
    assert res.raw_amount == trace['base_damage']
    assert res.raw_amount < trace['weapon_roll'] + int(res.diagnostics['trace'][0].get('impossible', 0)) + 60  # regression guard against runaway double-counting
    assert res.raw_amount == trace['weapon_roll'] + 21 + 3


def test_armor_scaling_flags_resistance_flags_true_damage_and_partial_save_semantics():
    stats=service(); engine=CombatEngine(combat_stats=stats, seed='flags')
    engine.resolution.rng=lambda *parts: 1
    attacker=make_actor('attacker', {'strength':10, 'dexterity':10, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    defender=make_actor('defender', {'strength':10, 'dexterity':1, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    defender.actor_type='npc'
    defender.combat_profile={'modifiers':[{'modifier_id':'arm','source_type':'combat_profile','source_id':'test','target_stat':'derived.armor','operation':'add','value':100}]}
    defender.resistance_profile={'slash':50, 'true':95}
    base_ctx=dict(attacker_id='attacker', defender_id='defender', action_id='a', metadata={'base_amount':100, 'requires_hit_roll':False, 'can_critical':False, 'minimum_damage':1}, damage_kind='slash')
    mitigated=engine.resolution.resolve(attacker, defender, CombatResolutionContext(**base_ctx))
    assert engine.resolution._formula('armor_mitigation','max(minimum_damage, raw_damage * 100 / (100 + max(0, armor - armor_penetration)))', {'raw_damage':100,'armor':100,'armor_penetration':0,'minimum_damage':1}) == 50
    defender.resources.health=100
    defender.resources.health=100
    noresist=engine.resolution.resolve(attacker, defender, CombatResolutionContext(**{**base_ctx, 'action_id':'c', 'metadata':{**base_ctx['metadata'], 'resistance_applies':False}}))
    assert noresist.final_amount > mitigated.final_amount
    defender.resources.health=100
    true=engine.resolution.resolve(attacker, defender, CombatResolutionContext(**{**base_ctx, 'action_id':'d', 'damage_kind':'true'}))
    assert true.final_amount == true.raw_amount
    defender.resources.health=100
    saved=engine.resolution.resolve(attacker, defender, CombatResolutionContext(**{**base_ctx, 'action_id':'e', 'metadata':{**base_ctx['metadata'], 'save_type':'magic_save', 'damage_reduction_percent':25}}))
    assert saved.final_amount == round(mitigated.final_amount * .75)


def test_saving_throw_direction_stronger_attacker_lowers_defender_success():
    stats=service(); engine=CombatEngine(combat_stats=stats, seed='save-direction')
    attacker=make_actor('attacker', {'strength':10, 'dexterity':10, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    defender=make_actor('defender', {'strength':10, 'dexterity':10, 'constitution':10, 'intelligence':10, 'wisdom':10, 'charisma':10})
    a=engine.resolution._snapshot(attacker, CombatResolutionContext(attacker_id='attacker', defender_id='defender'))
    d=engine.resolution._snapshot(defender, CombatResolutionContext(attacker_id='attacker', defender_id='defender'))
    low=engine.resolution.resolve_saving_throw(a,d,CombatResolutionContext(attacker_id='attacker', defender_id='defender', action_id='low'), {'save_type':'magic_save','difficulty':1,'save_attacker_stat':'spell_power'})
    attacker.attributes['intelligence']=30
    a2=engine.resolution._snapshot(attacker, CombatResolutionContext(attacker_id='attacker', defender_id='defender'))
    high=engine.resolution.resolve_saving_throw(a2,d,CombatResolutionContext(attacker_id='attacker', defender_id='defender', action_id='high'), {'save_type':'magic_save','difficulty':1,'save_attacker_stat':'spell_power'})
    assert high.chance < low.chance
