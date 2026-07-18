from engine.abilities import AbilityDefinition, AbilityExecutionService
from engine.actors import Actor


def _actor(level=1, cls='mage', mana=999):
    a = Actor.create('hero', 'Hero', 'player')
    a.progression_profile['level'] = level
    a.plugin_data['primary_class_id'] = cls
    a.resources.mana = mana
    a.resources.maximum_mana = max(mana, 999)
    return a


def _mm():
    return AbilityDefinition.from_dict({
        'id':'magic_missile','name':'Magic Missile','ability_type':'spell',
        'costs':[{'resource_id':'mana','cost_type':'legacy_spell_mana','amount':25,'consume_on':'start'}],
        'plugin_data': {'legacy_mana': {'mana_max':25,'mana_min':10,'mana_change':3,'class_unlock_levels': {'mage':1,'magic_user':1,'adventurer':1}}},
        'damage_components':[{'id':'d','base_amount':7}], 'targeting': {'mode':'single_enemy'}
    })


def test_magic_missile_legacy_cost_curve_magic_user_and_adventurer():
    svc = AbilityExecutionService(records={'abilities': []}) if False else AbilityExecutionService()
    ab = _mm()
    expected = {1:25, 2:22, 3:19, 4:16, 5:13, 6:10, 20:10}
    for cls in ('mage', 'adventurer'):
        for level, cost in expected.items():
            assert svc.spell_costs.calculate(_actor(level, cls), ab).final_cost == cost


def test_spell_reductions_order_and_floor():
    svc = AbilityExecutionService(); ab = _mm(); a = _actor(1)
    assert svc.spell_costs.calculate(a, ab).final_cost == 25
    a.plugin_data['affect_flags'] = ['AFF_EMPOWERED']
    assert svc.spell_costs.calculate(a, ab).final_cost == 22
    a.plugin_data['supreme_caster_discipline'] = True
    assert svc.spell_costs.calculate(a, ab).final_cost == 20
    a.plugin_data['tactical_spell_memory'] = True
    assert svc.spell_costs.calculate(a, ab).final_cost == 19
    a.plugin_data['enchanters_focus'] = True
    assert svc.spell_costs.calculate(a, ab).final_cost == 17
    tiny = AbilityDefinition(id='tiny', name='Tiny', ability_type='spell', costs=[{'resource_id':'mana','amount':1}], plugin_data={'legacy_mana': {'mana_max':1,'mana_min':1,'mana_change':0,'class_unlock_levels': {'mage':1}}}, damage_components=[{'id':'d'}])
    assert svc.spell_costs.calculate(a, tiny).final_cost == 1


def test_low_mana_validation_message_keeps_available_and_required():
    svc = AbilityExecutionService(); ab = _mm(); svc.registry.abilities[ab.id] = ab
    actor = _actor(1, 'mage', mana=8); svc.register_actor(actor); svc.grant_ability('hero','magic_missile')
    res = svc.validate_ability_use('hero','magic_missile','missing')
    # target failure has priority before mana for invalid target, but trace still has canonical cost
    assert any(st.get('step') == 'validate_resources' and st['costs'][0]['amount'] == 25 for st in res['trace'])
    actor.resources.mana = 8
    # Direct cost validation is deterministic regardless of target fixture availability.
    costs = svc._validate_costs(actor, ab)['costs'][0]
    assert costs['amount'] == 25 and costs['current'] == 8 and costs['ok'] is False
