from engine.phase5e import BASELINE_FORMULAS, SafeExpression, validate_modifier_decl


def test_phase5e_baseline_smoke():
    assert 'attack_power_v1' in BASELINE_FORMULAS
    assert SafeExpression('base + modifier_total').eval({'base': 2, 'modifier_total': 3}) == 5
    assert validate_modifier_decl({'id':'m','target_domain':'derived_stat','target_key':'attack_power','operation':'add','value':1,'stacking_policy':'stack'}) == []
