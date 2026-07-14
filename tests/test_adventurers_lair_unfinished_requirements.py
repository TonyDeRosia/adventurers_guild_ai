import json
from types import SimpleNamespace

from engine.economy import EconomyService
from engine.mud_commands import MudCommandEngine
from engine.mud_state_store import MUDStateStore
from engine.progression import GLORY_PRACTICE_COST, GLORY_TRAIN_COST, ProgressionService


def _store(tmp_path):
    s = MUDStateStore('c', 'shattered_realms', db_path=tmp_path/'s.sqlite')
    s.initialize()
    return s


def _char(**kw):
    data = dict(id='hero', character_id='hero', name='Hero', room_id='training_yard', world_id='shattered_realms', role='admin', immortal_level=100, inventory=[], actor_data={})
    data.update(kw)
    return SimpleNamespace(**data)


def test_buypractice_and_buytrain_spend_glory_atomically(tmp_path):
    s = _store(tmp_path); p = ProgressionService(s); p.initialize_actor_progression('hero')
    econ = EconomyService(s.db_path, world_id='shattered_realms', world_root='worlds/shattered_realms')
    econ.credit_currency('actor', 'hero', 'glory', GLORY_PRACTICE_COST + GLORY_TRAIN_COST, reason='test')
    engine = MudCommandEngine(s); ch = _char()
    r1 = engine.handle_command(ch, 'buypractice')
    r2 = engine.handle_command(ch, 'buytrain')
    state = p.get_actor_progression('hero')
    assert r1.ok and r2.ok
    assert state['practice_sessions'] == 1
    assert state['training_sessions'] == 1
    assert econ.get_currency_balance('actor', 'hero', 'glory') == 0


def test_insufficient_glory_grants_nothing(tmp_path):
    s = _store(tmp_path); p = ProgressionService(s); p.initialize_actor_progression('hero')
    result = MudCommandEngine(s).handle_command(_char(), 'buypractice')
    assert not result.ok
    assert 'currently have 0 Glory' in result.narrative
    assert p.get_actor_progression('hero')['practice_sessions'] == 0


def test_train_strength_persists_as_permanent_modifier(tmp_path):
    s = _store(tmp_path); p = ProgressionService(s); p.grant_currency('hero', 'training_sessions', 1, 'test', '', 'test')
    engine = MudCommandEngine(s); ch = _char()
    result = engine.handle_command(ch, 'train str')
    assert result.ok
    with s.connect() as con:
        row = con.execute("SELECT base_value, permanent_modifier FROM character_attributes WHERE character_id='hero' AND attribute_id='strength'").fetchone()
    assert row['permanent_modifier'] == 1
    restarted = ProgressionService(s)
    assert restarted.get_actor_progression('hero')['training_sessions'] == 0


def test_practice_projection_and_atomic_mutation(tmp_path):
    s = _store(tmp_path); p = ProgressionService(s); p.grant_currency('hero', 'practice_sessions', 1, 'test', '', 'test')
    p.learn_ability('hero', 'basic_attack', {'name':'Basic Attack', 'maximum_rank': 3, 'maximum_proficiency': 60, 'default_proficiency': 20})
    engine = MudCommandEngine(s); ch = _char(intelligence=14)
    listing = engine.handle_command(ch, 'practice')
    assert 'Basic Attack' in listing.narrative
    result = engine.handle_command(ch, 'practice basic attack')
    assert result.ok
    projections = p.list_known_practice_abilities('hero', intelligence=14)
    assert projections[0]['current_rank'] == 1
    assert projections[0]['maximum_rank'] == 3
    assert projections[0]['practice_proficiency_cap'] == 60
    assert projections[0]['current_proficiency'] > 20
    assert p.get_actor_progression('hero')['practice_sessions'] == 0


def test_advancement_repair_dry_run_and_apply_are_idempotent(tmp_path):
    s = _store(tmp_path); p = ProgressionService(s); p.grant_currency('hero', 'attribute_points', 30, 'demonstration', 'demo', 'demonstration grant')
    engine = MudCommandEngine(s); ch = _char()
    dry = engine.handle_command(ch, 'advancementrepair hero --dry-run')
    assert not json.loads(dry.narrative)['applied']
    assert p.get_actor_progression('hero')['attribute_points'] == 30
    applied = engine.handle_command(ch, 'advancementrepair hero --apply')
    assert json.loads(applied.narrative)['applied']
    assert p.get_actor_progression('hero')['attribute_points'] == 0
    engine.handle_command(ch, 'advancementrepair hero --apply')
    assert p.get_actor_progression('hero')['attribute_points'] == 0
