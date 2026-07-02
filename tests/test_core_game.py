from pathlib import Path
import pytest

from engine.core_game import CoreGameError, calculate_derived_stats, load_collection, load_core_game, validate_records, SPECS, validate_point_allocation
from engine.gm_orchestrator import GMOrchestrator
from engine.game_state_manager import GameStateManager


def test_core_game_collections_load():
    core = load_core_game()
    assert {c['id'] for c in core['classes']} >= {'warrior', 'mage', 'battle_mage'}
    assert {r['id'] for r in core['races']} >= {'human', 'custom'}
    assert {s['id'] for s in core['spells']} >= {'arcane_bolt', 'raise_skeleton'}
    assert any(i['id'] == 'training_sword' for i in core['items'])
    assert any(z['id'] == 'guildhall_crossing' for z in core['zones'])


def test_invalid_content_fails_clearly():
    with pytest.raises(CoreGameError, match='missing required'):
        validate_records([{'id': 'broken'}], SPECS['classes'])


def test_derived_stats_and_allocation_validation():
    stats = {'Strength': 5, 'Dexterity': 5, 'Constitution': 5, 'Intelligence': 5, 'Wisdom': 5, 'Charisma': 5}
    assert calculate_derived_stats(stats)['HP'] == 45
    assert calculate_derived_stats(stats)['Mana'] == 45
    assert calculate_derived_stats(stats)['Stamina'] == 45
    with pytest.raises(CoreGameError, match='total 30'):
        validate_point_allocation({**stats, 'Strength': 6})


def _state(tmp_path, cls='Mage'):
    return GameStateManager(Path('data'), tmp_path / 'saves').create_new_campaign('Mira', cls, 'classic_fantasy', False, world_name='The Shattered Realms', starting_location_name='Guildhall Crossing')


def test_gm_orchestrator_context_and_fallback_known_spell(tmp_path):
    state = _state(tmp_path)
    rt = state.structured_state.runtime
    rt.scene_state['scene_v1'] = {'entities': [{'kind': 'npc', 'name': 'Guild Registrar'}]}
    rt.inventory_state = {'entries': [{'name': 'spellbook'}]}
    rt.abilities = [{'id': 'arcane_bolt', 'name': 'Arcane Bolt', 'type': 'spell'}]
    gm = GMOrchestrator(provider=None)
    decision = gm.decide('cast Arcane Bolt at the sign', state, [{'text': 'guild law'}])
    ctx = gm.build_context('cast Arcane Bolt', state, [{'text': 'guild law'}])
    assert ctx.scene_v1 and ctx.inventory and ctx.known_abilities and ctx.relevant_rules
    assert decision['skill_or_ability_used'] == 'Arcane Bolt'
    assert 'Arcane Bolt' in decision['narration']


def test_gm_orchestrator_provider_path(tmp_path):
    class Provider:
        def gm_decision(self, payload):
            return {'outcome': 'success', 'narration': 'The GM decides.'}
    result = GMOrchestrator(Provider()).decide('search', _state(tmp_path, 'Warrior'))
    assert result['outcome'] == 'success'
    assert result['action_interpretation'] == 'search'

from app.web import WebRuntime


def test_core_character_creation_mage_known_spells_inventory_and_no_journal(tmp_path, monkeypatch):
    monkeypatch.setenv('ADVENTURERS_GUILD_USER_DATA', str(tmp_path / 'user_data'))
    runtime = WebRuntime(Path.cwd())
    created = runtime.create_campaign({'slot': 'core_mage', 'character_name': 'Mira', 'character_role': 'Mage', 'species': '', 'background': 'Guild Recruit', 'starting_ability_mode': 'suggest', 'starting_item_mode': 'suggest', 'rules_style': 'Hybrid', 'play_style': 'Storybook Mode'})
    state = created['state']
    assert state['player']['class'] == 'Mage'
    assert [a['name'] for a in state['abilities'][:3]] == ['Arcane Bolt', 'Mage Ward', 'Detect Magic']
    assert 'spellbook' in [i['name'] for i in state['inventory_state']['entries']]
    assert not [e for e in state['campaign_events'] if e.get('type') == 'ability_suggested']


def test_core_character_creation_warrior_known_skills(tmp_path, monkeypatch):
    monkeypatch.setenv('ADVENTURERS_GUILD_USER_DATA', str(tmp_path / 'user_data'))
    runtime = WebRuntime(Path.cwd())
    state = runtime.create_campaign({'slot': 'core_warrior', 'character_name': 'Bran', 'character_role': 'Warrior', 'starting_ability_mode': 'suggest', 'starting_item_mode': 'suggest', 'rules_style': 'Hybrid', 'play_style': 'MUD Mode'})['state']
    names = [a['name'] for a in state['abilities']]
    assert 'Power Strike' in names and 'Guard Stance' in names
    assert 'training sword' in [i['name'] for i in state['inventory_state']['entries']]


def test_gm_decision_validation_unknown_spell_strict(tmp_path):
    state = _state(tmp_path, 'Warrior')
    state.settings.rules_style = 'Strict'
    gm = GMOrchestrator(provider=None)
    ctx = gm.build_context('cast Fireball at the scarecrow', state, [])
    decision, errors, repaired = gm.validate_decision({'narration': 'Flames gather.', 'outcome': 'success', 'state_changes': {}, 'skill_or_ability_used': 'Fireball'}, ctx, strict_rules=True)
    assert 'unknown_ability_used' in errors
    assert repaired is False


def test_gm_decision_applies_scene_npc_and_inventory(tmp_path):
    state = _state(tmp_path)
    scene = state.structured_state.runtime.scene_state['scene_v1'] = {'entities': [{'kind': 'npc', 'actor_id': 'npc_guard', 'name': 'Guard'}], 'recent_changes': []}
    state.structured_state.runtime.inventory_state = {'entries': [{'id': 'old_key', 'name': 'old key'}]}
    gm = GMOrchestrator(provider=None)
    applied = gm.apply_gm_decision({
        'narration': 'The guard opens the way.',
        'scene_updates': {'summary': 'The gate is open.'},
        'npc_state_updates': [{'actor_id': 'npc_guard', 'mood': 'relieved'}],
        'inventory_changes': [{'action': 'add', 'item': {'id': 'gate_token', 'name': 'gate token'}}, {'action': 'remove', 'item_id': 'old_key'}],
        'memory_notes': ['Guard helped at the gate.'],
    }, state)
    assert scene['summary'] == 'The gate is open.'
    assert scene['entities'][0]['mood'] == 'relieved'
    ids = [item.get('id') for item in state.structured_state.runtime.inventory_state['entries']]
    assert 'gate_token' in ids and 'old_key' not in ids
    assert applied['scene'] and applied['npc'] == ['npc_guard'] and applied['memory']


def test_campaign_engine_provider_gm_path_does_not_overwrite_narration(tmp_path):
    from engine.campaign_engine import CampaignEngine

    class Provider:
        provider_name = 'test'
        def gm_decision(self, payload):
            return {'outcome': 'success', 'narration': 'Provider GM narration wins.', 'state_changes': {}}

    state = _state(tmp_path, 'Warrior')
    state.structured_state.runtime.scene_state['scene_v1_enabled'] = True
    state.structured_state.runtime.scene_state['scene_v1'] = {'summary': 'A room.', 'entities': [], 'exits': []}
    engine = CampaignEngine(Provider())
    result = engine.run_turn(state, 'look around')
    assert result.narrative == 'Provider GM narration wins.'
    assert result.metadata['requested_mode'] == 'gm_orchestrator'
    assert result.metadata['debug_trace'][0]['provider_decision_used'] is True
    assert state.turn_count == 1


def test_campaign_engine_null_provider_uses_deterministic_fallback(tmp_path):
    from engine.campaign_engine import CampaignEngine
    from models.base import NullNarrationAdapter

    state = _state(tmp_path, 'Warrior')
    engine = CampaignEngine(NullNarrationAdapter())
    result = engine.run_turn(state, 'look')
    assert result.metadata['requested_mode'] != 'gm_orchestrator'
    assert state.structured_state.runtime.scene_state['last_gm_debug_trace']['provider_available'] is False
    assert state.structured_state.runtime.scene_state['last_gm_debug_trace']['deterministic_fallback_used'] is True
