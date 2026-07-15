from types import SimpleNamespace
from pathlib import Path
from engine.mud_state_store import MUDStateStore
from engine.character_stats import CharacterAttributeService, CombatStatService, StatModifier
from engine.mud_commands import MudCommandEngine


def char(**kw):
    base=dict(id='kraevok', name='Kraevok', level=1, hp=40, mana=10, stamina=15, inventory=[])
    base.update(kw); return SimpleNamespace(**base)

def store(tmp_path):
    s=MUDStateStore('test', world_id='shattered_realms', db_path=tmp_path/'mud.sqlite'); s.initialize(); s.save_character({'character_id':'kraevok','name':'Kraevok','world_id':'shattered_realms','hp':40,'mana':10,'stamina':15}); return s

def test_starter_attribute_definitions_load_and_migrate_idempotently(tmp_path):
    s=store(tmp_path); svc=CharacterAttributeService(s)
    c=char(attributes={'strength':99,'dexterity':'bad'})
    changed=svc.migrate_character(c)
    assert set(changed)=={'strength','dexterity','constitution','intelligence','wisdom','charisma'}
    assert svc.migrate_character(c)==[]
    attrs=svc.get_all_attributes(c)
    assert attrs['strength'].base_value==30
    assert attrs['dexterity'].base_value==10


def test_modifiers_breakdown_stacking_and_clamping(tmp_path):
    s=store(tmp_path); svc=CharacterAttributeService(s); c=char()
    mods=[StatModifier('m1','equipment','ring','strength','add',2,stacking_group='gear'), StatModifier('m2','affect','poison','strength','subtract',1)]
    a=svc.get_attribute(c,'strength', {'modifiers': mods})
    assert a.final_value==11
    assert a.equipment_modifier==2 and a.affect_modifier==-1
    huge=svc.get_attribute(c,'strength', {'modifiers':[StatModifier('m3','temporary','test','strength','add',1000)]})
    assert huge.final_value==30


def test_derived_combat_resources_carrying_and_resistances(tmp_path):
    s=store(tmp_path); attr=CharacterAttributeService(s); combat=CombatStatService(attr); c=char(inventory=[{'item_id':'stone','quantity':3,'weight':2}])
    snap=combat.get_combat_snapshot(c, {'modifiers':[StatModifier('fire','equipment','cloak','resistance.fire','add',5)]})
    assert snap.resources['max_health']==105
    assert snap.resources['health']==40
    assert snap.offense['attack_power']>=21
    assert snap.carrying['current_carry_weight']==6
    assert snap.resistances['fire']==5


def test_player_commands_attributes_combatstats_and_breakdown(tmp_path):
    s=store(tmp_path); e=MudCommandEngine(state_store=s)
    c=char(role='builder')
    assert 'Strength:' in e.handle_command(c,'attributes').narrative
    assert 'Base: 10' in e.handle_command(c,'attributes strength').narrative
    assert 'OFFENSE' in e.handle_command(c,'combatstats').narrative
    assert 'formula' in e.handle_command(c,'statbreakdown attack_power').narrative
    assert 'Attribute drafts' in e.handle_command(c,'attributeedit list').narrative
