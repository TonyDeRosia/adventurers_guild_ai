from engine.actors import Actor
from engine.runtime_resources import RuntimeResourceService, ResourceMutationResult, LifecycleTransitionResult
from engine.mud_state_store import MUDStateStore
from engine.mud_runtime import MudCharacter, MudRuntime


def test_runtime_resource_service_persists_character_resources(tmp_path):
    store = MUDStateStore('camp', world_id='world', db_path=tmp_path/'mud.sqlite')
    store.initialize()
    store.save_character(character_id='c1', world_id='world', name='Hero', hp_current=50, mana_current=20, stamina_current=30)
    actor = Actor.create('character:c1', 'Hero')
    actor.resources.health = 50
    actor.resources.maximum_health = 100
    svc = RuntimeResourceService(db_path=store.db_path, world_id='world')

    result = svc.apply_damage(actor, 12, action_id='hit-1')

    assert isinstance(result, ResourceMutationResult)
    assert result.ok
    assert result.before == 50
    assert result.after == 38
    assert actor.resources.health == 38
    assert store.load_character('c1')['hp_current'] == 38
    assert store.load_character_stats('c1')['health'] == 38


def test_runtime_resource_service_clamps_and_lifecycle_once(tmp_path):
    store = MUDStateStore('camp', world_id='world', db_path=tmp_path/'mud.sqlite')
    store.initialize()
    actor = Actor.create('entity:rat1', 'Rat')
    actor.resources.health = 5
    actor.resources.maximum_health = 5
    svc = RuntimeResourceService(db_path=store.db_path, world_id='world')

    dmg = svc.apply_damage(actor, 99, action_id='kill-1')
    first = svc.evaluate_zero_health(actor, trigger_action_id='kill-1')
    second = svc.evaluate_zero_health(actor, trigger_action_id='kill-1')

    assert dmg.after == 0
    assert isinstance(first, LifecycleTransitionResult)
    assert first.ok and first.new_state == 'dead' and not first.already_processed
    assert second.ok and second.already_processed


def test_stale_character_save_cannot_restore_canonical_resources(tmp_path):
    rt = MudRuntime(root=__import__('pathlib').Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    ch = MudCharacter(id='c_stale', name='Stale', role='player', room_id='guildhall_registrar_office', hp=100, max_hp=100, mana=100, max_mana=100, stamina=100, max_stamina=100)
    rt.state_store.save_character(ch, 'shattered_realms')
    old = rt.state_store.load_character('c_stale')
    actor = Actor.create('character:c_stale', 'Stale', 'player')
    actor.resources.health = 100; actor.resources.maximum_health = 100
    actor.resources.mana = 100; actor.resources.maximum_mana = 100
    actor.resources.stamina = 100; actor.resources.maximum_stamina = 100

    rt.runtime_resources.apply_damage(actor, 60, action_id='combat-health-40')
    rt.runtime_resources.pay_cost(actor, 'mana', 60, action_id='combat-mana-40')
    rt.runtime_resources.pay_cost(actor, 'stamina', 60, action_id='combat-stamina-40')
    assert old.hp == old.mana == old.stamina == 100

    # Simulate a non-combat command path that retained and saved an old object.
    rt.state_store.save_character(old, 'shattered_realms')
    reloaded = rt.state_store.load_character('c_stale')
    assert (reloaded.hp, reloaded.mana, reloaded.stamina) == (40, 40, 40)

    rt2 = MudRuntime(root=__import__('pathlib').Path('.'), user_data_dir=tmp_path)
    rt2.load_world('shattered_realms')
    restarted = rt2.state_store.load_character('c_stale')
    assert (restarted.hp, restarted.mana, restarted.stamina) == (40, 40, 40)


def test_expected_resource_version_mismatch_denies_without_overwrite(tmp_path):
    store = MUDStateStore('camp', world_id='world', db_path=tmp_path/'mud.sqlite')
    store.initialize()
    actor = Actor.create('character:cver', 'Versioned')
    actor.resources.health = 100
    actor.resources.maximum_health = 100
    svc = RuntimeResourceService(db_path=store.db_path, world_id='world')
    first = svc.apply_damage(actor, 10, action_id='v1')

    stale = svc.apply_damage(actor, 10, action_id='stale', expected_version=max(0, first.persistence_version - 1))

    assert not stale.ok
    assert stale.reason_code == 'stale_resource_version'
    assert actor.resources.health == 90
