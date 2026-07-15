import json, shutil
from pathlib import Path
from types import SimpleNamespace

from engine.character_stats import CharacterAttributeService, CombatStatService
from engine.mud_commands import MudCommandEngine
from engine.builder_stat_content import StatCombatPublisher, StatCombatPublishValidator


def temp_world(tmp_path: Path) -> Path:
    root=tmp_path/'world'; shutil.copytree(Path('worlds/shattered_realms'), root)
    (root/'builder'/'attributes').mkdir(parents=True, exist_ok=True)
    (root/'builder'/'formulas').mkdir(parents=True, exist_ok=True)
    shutil.copy(root/'attributes'/'attributes.json', root/'builder'/'attributes'/'attributes.json')
    shutil.copy(root/'formulas'/'stat_formulas.json', root/'builder'/'formulas'/'stat_formulas.json')
    shutil.copy(root/'formulas'/'derived_stats.json', root/'builder'/'formulas'/'derived_stats.json')
    (root/'builder'/'combat').mkdir(parents=True, exist_ok=True)
    if not (root/'combat'/'combat_messages.json').exists(): (root/'combat'/'combat_messages.json').write_text('{"messages":[]}', encoding='utf-8')
    shutil.copy(root/'combat'/'postures.json', root/'builder'/'combat'/'postures.json')
    shutil.copy(root/'combat'/'range_rules.json', root/'builder'/'combat'/'range_rules.json')
    shutil.copy(root/'combat'/'combat_messages.json', root/'builder'/'combat'/'combat_messages.json')
    return root


def engine_for(root):
    e=MudCommandEngine(); c=SimpleNamespace(id='builder', name='Builder', role='builder')
    attr=CharacterAttributeService(None, world_id='test', world_root=root)
    e._stat_services=lambda character: (attr, CombatStatService(attr))
    return e,c


def run(e,c,cmd):
    r=e.handle_command(c,cmd); assert r.ok, r.narrative; return r.narrative

def fail(e,c,cmd):
    r=e.handle_command(c,cmd); assert not r.ok; return r.narrative


def test_attribute_formula_statdef_commands_and_reference_deletion(tmp_path):
    root=temp_world(tmp_path); e,c=engine_for(root)
    run(e,c,'attributeedit create test_attribute')
    for cmd in ['attributeedit name test_attribute Test Attribute','attributeedit short test_attribute TAT','attributeedit description test_attribute Desc','attributeedit minimum test_attribute 1','attributeedit default test_attribute 10','attributeedit maximum test_attribute 20','attributeedit creationmin test_attribute 1','attributeedit creationmax test_attribute 20','attributeedit order test_attribute 90','attributeedit group test_attribute custom','attributeedit role test_attribute custom','attributeedit visible test_attribute on','attributeedit enable test_attribute on','attributeedit tag test_attribute add phase_test']:
        run(e,c,cmd)
    assert 'test_attribute' in run(e,c,'attributeedit preview test_attribute')
    run(e,c,'formula create test_formula')
    run(e,c,'formula variable test_formula add strength')
    run(e,c,'formula expression test_formula strength + 5')
    assert 'final_result' in run(e,c,'formula test test_formula strength=10')
    run(e,c,'statdef create test_stat')
    run(e,c,'statdef formula test_stat test_formula')
    run(e,c,'statdef enable test_stat on')
    assert 'referenced' in fail(e,c,'formula delete test_formula')
    assert 'Builder stats validation: OK' in run(e,c,'builder validate stats')


def test_invalid_formula_and_range_validation(tmp_path):
    root=temp_world(tmp_path); e,c=engine_for(root)
    run(e,c,'formula create bad_formula')
    assert 'unsupported formula function' in fail(e,c,'formula expression bad_formula __import__("os")') or 'invalid_expression' in fail(e,c,'formula validate bad_formula')
    assert 'Unknown range field' in fail(e,c,'rangeedit set nope 3')
    run(e,c,'rangeedit set ranged_minimum_range 1')
    run(e,c,'rangeedit set ranged_maximum_range 5')
    assert 'range_rules' in run(e,c,'rangeedit preview')


def test_resistance_encumbrance_posture_combatmessage_commands(tmp_path):
    root=temp_world(tmp_path); e,c=engine_for(root)
    run(e,c,'resistanceedit create test_resistance')
    for cmd in ['resistanceedit unit test_resistance percentage','resistanceedit minimum test_resistance 0','resistanceedit maximum test_resistance 100','resistanceedit order test_resistance 99','resistanceedit enable test_resistance on']:
        run(e,c,cmd)
    run(e,c,'encumbranceedit set testing 125')
    run(e,c,'encumbranceedit rename testing Testing')
    run(e,c,'encumbranceedit penalty testing movement_speed -5')
    assert 'records' in run(e,c,'encumbranceedit preview')
    run(e,c,'postureedit create kneeling_test')
    run(e,c,'postureedit modifier kneeling_test attack_accuracy_modifier -2')
    run(e,c,'postureedit allow kneeling_test attack on')
    assert 'Required posture' in fail(e,c,'postureedit delete standing')
    run(e,c,'combatmessage create hit_test')
    run(e,c,'combatmessage field hit_test attacker You hit {defender} for {damage}.')
    run(e,c,'combatmessage condition hit_test result hit')
    assert 'unsupported placeholder' in fail(e,c,'combatmessage field hit_test observer {evil} happens')


def test_publish_transaction_success_preview_failure_rollback_and_reload_policy(tmp_path):
    root=temp_world(tmp_path); e,c=engine_for(root)
    run(e,c,'attributeedit create temp_publish_attr')
    before=(root/'attributes'/'attributes.json').read_bytes()
    assert 'temp_publish_attr' not in before.decode()
    assert 'Changed documents' in run(e,c,'builder preview stats')
    e._stats_publish_failure_injection='before_replacement'
    assert 'failed' in fail(e,c,'builder publish stats')
    assert (root/'attributes'/'attributes.json').read_bytes()==before
    e._stats_publish_failure_injection='after_replacement_0'
    assert 'failed' in fail(e,c,'builder publish stats')
    assert (root/'attributes'/'attributes.json').read_bytes()==before
    e._stats_publish_failure_injection=None
    out=run(e,c,'builder publish stats')
    assert 'published=true' in out and 'restart_required=True' in out
    assert 'temp_publish_attr' in (root/'attributes'/'attributes.json').read_text()
    assert (root/'builder'/'audit'/'stats_publish_manifests.jsonl').exists()
    assert 'clean' in run(e,c,'builder status stats')


def test_publish_validation_failure_writes_nothing(tmp_path):
    root=temp_world(tmp_path); e,c=engine_for(root)
    before={p: p.read_bytes() for p in [root/'formulas'/'derived_stats.json', root/'formulas'/'stat_formulas.json']}
    run(e,c,'statdef create invalid_ref_stat')
    assert 'missing_reference' in fail(e,c,'statdef formula invalid_ref_stat no_such_formula')
    assert before[root/'formulas'/'derived_stats.json'] == (root/'formulas'/'derived_stats.json').read_bytes()
