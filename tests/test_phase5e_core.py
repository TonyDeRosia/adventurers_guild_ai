import sqlite3
from pathlib import Path

from engine.actors import Actor
from engine.mud_runtime import MudRuntime, MudCharacter
from engine.phase5e import EquipmentModifierBridge, RuntimeEffectService, SafeExpression, actor_modifiers, resolve_actor_value, ensure_effect_schema


def runtime(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    return rt


def test_equipped_item_modifiers_only_when_equipped(tmp_path):
    rt=runtime(tmp_path); rt.state_store.save_character(MudCharacter(id='c', name='C', role='player'), rt.active_world_id)
    item=rt.spawn_item('iron_sword','character','c')
    assert EquipmentModifierBridge(rt).get_equipment_modifiers('c') == []
    rt.move_item(item['instance_id'],'equipment','c',equipped_slot='primary_weapon')
    mods=EquipmentModifierBridge(rt).get_equipment_modifiers('c')
    assert mods[0].source_instance_id == item['instance_id']
    assert mods[0].source_template_id == 'iron_sword'
    assert mods[0].target_key == 'attack_power'
    assert resolve_actor_value(rt, Actor.create('c','C'), 'attack_power').final_value == 24
    rt.move_item(item['instance_id'],'character','c')
    assert EquipmentModifierBridge(rt).get_equipment_modifiers('c') == []


def test_effect_instances_persist_and_emit_modifiers(tmp_path):
    rt=runtime(tmp_path)
    svc=RuntimeEffectService(rt)
    e=svc.apply_effect('c','blessed_example', duration=100)
    assert e['effect_template_id']=='blessed_example'
    mods=svc.get_effect_modifiers('c')
    assert any(m.source_type=='effect' and m.target_key=='wisdom' for m in mods)
    # restart equivalent: new service over same sqlite sees the same active row, no duplicate.
    svc2=RuntimeEffectService(rt)
    assert len(svc2.get_active_effects('c', viewer='admin')) == 1


def test_safe_expression_rejects_unsafe_and_division_by_zero():
    assert SafeExpression('clamp(base + strength * 2, 0, 100)').eval({'base':1,'strength':3}) == 7
    for expr in ['__import__("os")', '(1).__class__', '[x for x in y]', '1/0']:
        try:
            SafeExpression(expr).eval({})
        except Exception:
            pass
        else:
            raise AssertionError(expr)


def test_effect_schema_idempotent(tmp_path):
    db=tmp_path/'x.sqlite'
    ensure_effect_schema(db); ensure_effect_schema(db)
    with sqlite3.connect(db) as con:
        cols=[r[1] for r in con.execute('PRAGMA table_info(actor_effect_instances)')]
    assert 'effect_instance_id' in cols and 'metadata_json' in cols
