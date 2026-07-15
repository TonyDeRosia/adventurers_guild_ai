from pathlib import Path

from engine.mud_runtime import MudRuntime


def _runtime(tmp_path):
    rt = MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    return rt


def test_entered_character_registered_reload_refreshed_and_logout_unregisters(tmp_path):
    rt = _runtime(tmp_path)
    cid = rt.create_character(world_id='shattered_realms', name='Registry One')['character_id']
    rt.enter_world(cid)
    first_actor = rt.actor_registry.require(cid)
    assert rt.abilities._get_actor(cid) is first_actor

    rt.handle_input(cid, 'look')
    refreshed_actor = rt.actor_registry.require(cid)
    assert rt.abilities._get_actor(cid) is refreshed_actor
    assert refreshed_actor.actor_id == cid

    out = rt.handle_input(cid, 'logout')['semantic_output']
    assert 'leave the game' in out
    assert rt.actor_registry.get(cid) is None


def test_two_entered_characters_keep_separate_registry_entries(tmp_path):
    rt = _runtime(tmp_path)
    cid1 = rt.create_character(world_id='shattered_realms', name='Registry Alpha')['character_id']
    cid2 = rt.create_character(world_id='shattered_realms', name='Registry Beta')['character_id']
    rt.enter_world(cid1)
    rt.enter_world(cid2)
    assert rt.actor_registry.require(cid1).actor_id == cid1
    assert rt.actor_registry.require(cid2).actor_id == cid2
    assert rt.actor_registry.require(cid1) is not rt.actor_registry.require(cid2)


def test_set_camp_public_path_no_keyerror_repeated_and_campfire(tmp_path):
    rt = _runtime(tmp_path)
    cid = rt.create_character(world_id='shattered_realms', name='Registry Camper')['character_id']
    rt.enter_world(cid)
    first = rt.handle_input(cid, 'set camp')['semantic_output']
    assert 'You establish a modest campsite here.' in first
    assert 'KeyError' not in first and 'Something went wrong' not in first
    second = rt.handle_input(cid, 'set camp')['semantic_output']
    assert 'A campsite is already established here.' in second
    fire = rt.handle_input(cid, 'build campfire')['semantic_output']
    assert 'campfire' in fire.lower() and 'Requires an established campsite' not in fire


def test_stale_actor_data_id_is_repaired_and_persisted(tmp_path):
    rt = _runtime(tmp_path)
    cid = rt.create_character(world_id='shattered_realms', name='Kraevok')['character_id']
    char = rt.state_store.load_character(cid)
    char.actor_data = {'actor_id': 'actor', 'actor_type': 'player', 'identity': {'name': 'Kraevok'}, 'resources': {'health': 77, 'maximum_health': 100}}
    rt.state_store.save_character(char, 'shattered_realms')

    rt.enter_world(cid)
    actor = rt.actor_registry.require(cid)
    assert actor.actor_id == cid
    assert rt.actor_registry.get('actor') is None
    repaired = rt.state_store.load_character(cid)
    assert repaired.actor_data['actor_id'] == cid
    assert repaired.actor_data['plugin_data']['actor_data_migration']['migrated_from_actor_id'] == 'actor'
    assert rt.handle_input(cid, 'set camp')['ok'] is True
