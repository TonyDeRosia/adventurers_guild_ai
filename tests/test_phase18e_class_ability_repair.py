from pathlib import Path

from engine.mud_runtime import MudRuntime


def _rt(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    return rt


def test_warrior_identity_and_class_ability_reconciliation(tmp_path):
    rt = _rt(tmp_path)
    payload = rt.create_character(world_id='shattered_realms', name='Phase Warrior', race_id='human', class_id='warrior')
    char = rt.state_store.load_character(payload['character_id'])
    rt._ensure_starter_progression(char)
    char = rt.state_store.load_character(payload['character_id'])
    rt._ensure_starter_progression(char)

    state = rt._progression_service().get_actor_progression(char.id)
    assert state['primary_class_id'] == 'warrior'
    assert getattr(char, 'primary_class_id') == 'warrior'
    score = rt.command_engine._cmd_score(char, [], 'score').narrative
    assert 'Class: Warrior' in score
    assert 'Name: Phase Warrior' in score
    assert 'Alignment: 0' in score
    assert '║                                                                               ║\n{character_frame}║ Name:' not in score
    assert '║                                                                               ║\n{character_frame}║ Alignment:' not in score

    known = {r['id'] for r in rt.abilities.get_actor_abilities(char.id)}
    assert {'kick', 'bandage', 'bash'} <= known
    assert 'magic_missile' not in known
    assert 'armor' not in known
    assert 'Magic Missile' not in rt.command_engine._cmd_spells(char, [], 'spells').narrative
    assert 'Kick' in rt.command_engine._cmd_skills(char, [], 'skills').narrative


def test_legacy_universal_starter_grants_are_retired_but_manual_survives(tmp_path):
    rt = _rt(tmp_path)
    payload = rt.create_character(world_id='shattered_realms', name='Legacy Warrior', race_id='human', class_id='warrior')
    char = rt.state_store.load_character(payload['character_id'])
    ps = rt._progression_service()
    ps.learn_ability(char.id, 'magic_missile', {'source_type': 'starter_character'})
    ps.learn_ability(char.id, 'armor', {'source_type': 'awarded'})
    rt._ensure_starter_progression(char)
    known = {r['id'] for r in rt.abilities.get_actor_abilities(char.id)}
    assert 'magic_missile' not in known
    assert 'armor' in known


def test_multiword_spell_resolution_and_category_failures(tmp_path):
    rt = _rt(tmp_path)
    payload = rt.create_character(world_id='shattered_realms', name='Phase Mage', race_id='human', class_id='mage')
    char = rt.state_store.load_character(payload['character_id'])
    rt._ensure_starter_progression(char)
    gateway = rt.abilities.gateway()
    assert gateway.resolve_ability_prefix(char.id, 'magic missile fox') == ('magic_missile', 'fox')
    assert gateway.resolve_ability_prefix(char.id, "'magic missile' fox") == ('magic_missile', 'fox')
    assert gateway.resolve_ability_prefix(char.id, '"magic missile" fox') == ('magic_missile', 'fox')
    assert gateway.resolve_ability_prefix(char.id, 'MAGIC    MISSILE fox') == ('magic_missile', 'fox')

    warrior_payload = rt.create_character(world_id='shattered_realms', name='No Spell', race_id='human', class_id='warrior')
    warrior = rt.state_store.load_character(warrior_payload['character_id'])
    rt._ensure_starter_progression(warrior)
    res = gateway.execute(warrior.id, 'magic missile', 'self', {'command': 'cast magic missile'})
    assert res.reason_code == 'not_known'
    res = gateway.execute(warrior.id, 'kick', 'self', {'command': 'cast kick'})
    assert res.reason_code == 'wrong_category'
