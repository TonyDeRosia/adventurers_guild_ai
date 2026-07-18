from pathlib import Path

import pytest

from engine.mud_runtime import MudRuntime, MudCharacter
from smart_mud.world_registry import WorldRegistry


def test_phase18a_resolver_quotes_and_spellup_affects(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    payload = rt.create_character(world_id='shattered_realms', name='Phase Admin', race_id='human', class_id='mage')
    char = rt.state_store.load_character(payload['character_id'])
    char.role = 'admin'; char.immortal_level = 100; char.mana = 999; char.max_mana = 999
    rt.state_store.save_character(char, 'shattered_realms')
    char = rt.state_store.load_character(char.id)
    spells = rt.command_engine._cmd_spells(char, [], 'spells').narrative
    assert 'Magic Missile' in spells
    gateway = rt.abilities.gateway()
    assert gateway.resolve_ability_prefix(char.id, 'magic missile fox') == ('magic_missile', 'fox')
    assert gateway.resolve_ability_prefix(char.id, "'magic missile' fox") == ('magic_missile', 'fox')
    assert gateway.resolve_ability_prefix(char.id, 'mm fox') == ('magic_missile', 'fox')
    out = rt.command_engine._cmd_spellup(char, [], 'spellup').narrative
    assert 'Spellup complete:' in out and 'Magic Missile' not in out
    assert 'cast' in out
    aff = rt.command_engine._cmd_affects(char, [], 'aff').narrative
    saff = rt.command_engine._cmd_saff(char, [], 'saff').narrative
    assert 'Armor' in aff or 'Bless' in aff or 'Strength' in aff
    assert 'Spell' in saff and 'None.' not in saff.split('Equipment effects:')[0]
    again = rt.command_engine._cmd_spellup(char, [], 'spellup').narrative
    assert 'already active' in again


def test_phase18a_race_class_registry_and_scholar_progression(tmp_path):
    world = WorldRegistry().load_world('shattered_realms')
    assert 'custom' not in {r['id'] for r in world.races}
    assert 'scholar' in {c['id'] for c in world.classes}
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    with pytest.raises(ValueError):
        rt.create_character(world_id='shattered_realms', name='Bad Race', race_id='custom', class_id='mage')
    payload = rt.create_character(world_id='shattered_realms', name='New Scholar', race_id='human', class_id='scholar')
    char = rt.state_store.load_character(payload['character_id'])
    rt._ensure_starter_progression(char)
    skills = rt.command_engine._cmd_skills(char, [], 'skills').narrative
    assert 'Study' in skills and 'Appraise' in skills
    known = {r['id'] for r in rt.abilities.get_actor_abilities(char.id)}
    assert 'teach' not in known
    char.level = 80; rt.state_store.save_character(char, 'shattered_realms'); rt._ensure_starter_progression(char)
    assert 'teach' in {r['id'] for r in rt.abilities.get_actor_abilities(char.id)}
    char.level = 100; rt.state_store.save_character(char, 'shattered_realms'); rt._ensure_starter_progression(char)
    assert 'master_instructor' in {r['id'] for r in rt.abilities.get_actor_abilities(char.id)}
    legacy = MudCharacter(id='legacy_custom', name='Legacy Custom', role='player', actor_data={'race_id':'custom','class_id':'mage'})
    rt.state_store.save_character(legacy, 'shattered_realms')
    assert rt.state_store.load_character('legacy_custom').actor_data.get('race_id') == 'custom'
