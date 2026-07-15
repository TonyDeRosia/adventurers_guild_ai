import sqlite3
from pathlib import Path

from engine.mud_runtime import MudRuntime


def runtime_with_wolf(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Combat Tester')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.room_id = 'emberwood_hunting_trail'
    rt.state_store.save_character(ch, 'shattered_realms')
    visible = rt.find_visible_entities(ch.room_id, ch)
    for wolf in visible.get('npcs', []) + visible.get('mobs', []):
        if 'wolf' in str(wolf.get('name', '')).lower():
            rt.update_entity_state(str(wolf.get('entity_id') or wolf.get('instance_id')), {'current_health': 500, 'maximum_health': 500, 'is_alive': True, 'current_state': 'standing'})
            break
    return rt, rt.state_store.load_character(cid)


def test_attack_creates_persistent_encounter_and_wolf_retaliates(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    out = rt.command_engine.handle_command(ch, 'attack forest wolf')
    assert out.ok
    assert any(word in out.narrative.lower() for word in ('damage', 'miss', 'glance', 'hit', 'strike', 'pulverize'))
    assert 'clash begins' not in out.narrative.lower()
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM combat_encounters WHERE status='active'").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM combat_participants").fetchone()[0] == 2
    before = rt.state_store.load_character(ch.id).hp
    rt.process_runtime_pulse(__import__("time").monotonic() + 2.1)
    after = rt.state_store.load_character(ch.id).hp
    assert after < before


def test_combat_status_diagnose_consider_and_flee_use_runtime_path(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    assert 'look' in rt.command_engine.handle_command(ch, 'consider forest wolf').narrative.lower()
    assert 'unharmed' in rt.command_engine.handle_command(ch, 'diagnose forest wolf').narrative.lower()
    rt.command_engine.handle_command(ch, 'kill forest wolf')
    status = rt.command_engine.handle_command(ch, 'combat').narrative
    assert 'Combat Status' in status and 'Opponent: Forest Wolf' in status
    fled = rt.command_engine.handle_command(ch, 'flee').narrative
    assert 'flee' in fled.lower()
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute("SELECT end_reason FROM combat_encounters ORDER BY created_at DESC LIMIT 1").fetchone()[0] in {'victory','fled'}


def test_protected_borik_and_legacy_rules_boundary(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Borik Tester')['character_id']
    ch = rt.state_store.load_character(cid); ch.room_id = 'training_yard'; rt.state_store.save_character(ch, 'shattered_realms')
    out = rt.command_engine.handle_command(ch, 'attack borik')
    assert not out.ok
    assert 'protected' in out.narrative.lower()
    import engine.combat_runtime as cr
    assert 'from rules.combat' not in Path(cr.__file__).read_text()
    assert 'import rules.combat' not in Path(cr.__file__).read_text()


def test_restart_cancels_active_encounters_without_replaying_opening_attack(tmp_path):
    rt, ch = runtime_with_wolf(tmp_path)
    rt.command_engine.handle_command(ch, 'attack forest wolf')
    hp = rt.state_store.load_character(ch.id).hp
    rt2 = MudRuntime(Path('.'), tmp_path); rt2.load_world('shattered_realms')
    assert rt2.state_store.load_character(ch.id).hp == hp
    with sqlite3.connect(rt2.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM combat_encounters WHERE status='active'").fetchone()[0] == 0
        assert con.execute("SELECT end_reason FROM combat_encounters LIMIT 1").fetchone()[0] == 'cancelled_on_restart'
