from pathlib import Path

from engine.actors import Actor
from engine.mud_runtime import MudRuntime


def _runtime(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    return rt


def test_phase18i_runtime_cast_parser_separates_spell_and_target_and_executes_by_id(tmp_path):
    rt = _runtime(tmp_path)
    payload = rt.create_character(world_id='shattered_realms', name='Phase I Mage', race_id='human', class_id='mage')
    char_id = payload['character_id']
    char = rt.state_store.load_character(char_id)
    rt.register_live_character(char)
    wolf = Actor.create('wolf', 'Wolf', 'mob')
    wolf.identity.current_location = getattr(char, 'room_id', '') or 'start'
    rt.abilities.register_actor(wolf)

    spells = rt.handle_input(char_id, 'spells')['output']
    for name in ('Armor', 'Detect Magic', 'Magic Missile', 'Strength'):
        assert name in spells

    cases = {
        'c magic wolf': ('magic_missile', 'wolf'),
        'c magic missile wolf': ('magic_missile', 'wolf'),
        'c mag mis wolf': ('magic_missile', 'wolf'),
        "c 'magic missile' wolf": ('magic_missile', 'wolf'),
        'c "magic missile" wolf': ('magic_missile', 'wolf'),
        'cast magic missile wolf': ('magic_missile', 'wolf'),
        'c armor self': ('armor', 'self'),
        'c detect magic self': ('detect_magic', 'self'),
        'c strength self': ('strength', 'self'),
    }
    gateway = rt.abilities.gateway()
    for raw, (ability_id, target) in cases.items():
        parsed = gateway.resolve_spell_tokens(char_id, raw.split(' ', 1)[1])
        assert parsed['status'] == 'RESOLVED', raw
        assert parsed['ability_id'] == ability_id
        assert parsed['target_text'] == target
        assert target not in parsed['canonical_name'].lower().split(), raw
        result = rt.command_engine.handle_command(char, raw).narrative
        assert 'You do not recognize an ability called' not in result
        assert 'You do not know' not in result
        rt.abilities._world_time = rt.abilities.world_time() + 2

    before = rt.abilities.actor_registry.get(char_id).resources.mana
    bad = rt.command_engine.handle_command(char, "c 'magic missile wolf").narrative
    after = rt.abilities.actor_registry.get(char_id).resources.mana
    assert 'missing a closing quote' in bad
    assert after == before


def test_phase18i_displayed_known_rows_execute_by_id_without_unknown_or_not_known(tmp_path):
    rt = _runtime(tmp_path)
    payload = rt.create_character(world_id='shattered_realms', name='Phase I Display', race_id='human', class_id='mage')
    char = rt.state_store.load_character(payload['character_id'])
    rt.register_live_character(char)
    svc = rt.abilities
    for row in svc.list_known_spells(char.id) + svc.list_known_skills(char.id):
        assert svc.knows(char.id, row['id']) is True
        target = 'self' if row['id'] != 'magic_missile' else ''
        res = svc.gateway().execute_by_id(char.id, row['id'], target, {'command': f"phase18i {row['id']}", 'source': 'test'})
        assert res.reason_code not in {'unknown_ability', 'not_known'}


def test_phase18i_spellup_considers_known_buffs(tmp_path):
    rt = _runtime(tmp_path)
    payload = rt.create_character(world_id='shattered_realms', name='Phase I Spellup', race_id='human', class_id='mage')
    char = rt.state_store.load_character(payload['character_id'])
    rt.register_live_character(char)
    out = rt.command_engine._cmd_spellup(char, [], 'spellup').narrative
    assert 'Magic Missile:' not in out
    assert any(name in out for name in ('Armor:', 'Detect Magic:', 'Strength:', 'low mana', 'already active', 'cast'))
    assert '0 cast, 0 already active, 0 low mana, 0 blocked' not in out
