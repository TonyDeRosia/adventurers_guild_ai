from pathlib import Path

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path('.'), tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Kraevok')['character_id']
    ch = rt.state_store.load_character(cid)
    ch.room_id = 'ancient_ember_grove'
    rt.state_store.save_character(ch, 'shattered_realms')
    rt.active_characters[cid] = ch
    return rt, ch


def test_ashback_bear_look_and_kill_share_resident_actor(tmp_path, monkeypatch):
    rt, ch = make_runtime(tmp_path)
    called = {'refresh': 0, 'sql': 0}
    monkeypatch.setattr(rt.combat_runtime, 'refresh_content', lambda: called.__setitem__('refresh', called['refresh'] + 1))
    look = rt._handle_runtime_command(ch, 'look').narrative
    assert 'Ashback Bear is here among the trees.' in look
    bear = rt.resolve_entity_keywords('bear', rt.find_visible_entities(ch.room_id, ch)['mobs'])['entity']
    actor_id = rt.entity_instance_to_actor_id[bear['entity_id']]
    actor = rt.combat_runtime.resident_actors[actor_id]
    for query in ['bear', 'ashback', 'ashback bear', 'Ashback Bear', '1.bear']:
        rt2, ch2 = make_runtime(tmp_path / query.replace(' ', '_').replace('.', '_'))
        monkeypatch.setattr(rt2.combat_runtime, 'refresh_content', lambda: called.__setitem__('refresh', called['refresh'] + 1))
        result = rt2.command_engine.handle_command(ch2, f'kill {query}')
        assert result.ok, result.narrative
        assert 'They are not here.' not in result.narrative
        b2 = rt2.resolve_entity_keywords('bear', rt2.find_visible_entities(ch2.room_id, ch2)['mobs'])['entity']
        assert rt2.combat_runtime.resident_actors[rt2.entity_instance_to_actor_id[b2['entity_id']]] is rt2.combat_runtime.resident_actors[rt2.actor_id_for_entity_instance(b2)]
        assert rt2.combat_runtime.find_actor_encounter(f'character:{ch2.id}')
    assert called['refresh'] == 0
    assert rt.combat_runtime.resident_actors[actor_id] is actor


def test_emberwood_creatures_resolve_from_room_occupancy(tmp_path):
    rt, ch = make_runtime(tmp_path)
    names = ['Giant Wood Spider', 'Emberwood Fox', 'Forest Wolf', 'Dire Forest Wolf', 'Wild Boar', 'Ashback Bear', 'Emberwood Stag']
    found = {e['name']: e for room in list(rt.resident_occupants_by_room) for e in rt.find_visible_entities(room, ch).get('mobs', []) + rt.find_visible_entities(room, ch).get('npcs', [])}
    for name in names:
        ent = found[name]
        ch.room_id = ent['room_id']
        first_token = ('dire' if name == 'Dire Forest Wolf' else name.split()[-1].lower())
        assert rt.find_occupant(ch.room_id, first_token, {'living': True, 'visible_to': ch})['entity']['name'] == name
        assert rt.find_occupant(ch.room_id, name.lower(), {'living': True, 'visible_to': ch})['entity']['name'] == name


def test_duplicate_numbered_targets_are_stable_and_renumber_after_death(tmp_path):
    rt, ch = make_runtime(tmp_path)
    room = ch.room_id
    rt.spawn_entity('forest_wolf', room_id=room)
    rt.spawn_entity('dire_forest_wolf', room_id=room)
    rt.spawn_entity('forest_wolf', room_id=room)
    assert rt.find_occupant(room, 'wolf', {'living': True, 'visible_to': ch})['entity']['name'] in {'Forest Wolf', 'Dire Forest Wolf'}
    assert rt.find_occupant(room, '1.wolf', {'living': True, 'visible_to': ch})['entity']['name'] in {'Forest Wolf', 'Dire Forest Wolf'}
    second = rt.find_occupant(room, '2.wolf', {'living': True, 'visible_to': ch})['entity']
    third = rt.find_occupant(room, '3.wolf', {'living': True, 'visible_to': ch})['entity']
    assert second['entity_id'] != third['entity_id']
    rt.update_entity_state(second['entity_id'], {**second['state'], 'current_health': 0, 'is_alive': False, 'current_state': 'dead'})
    renumbered = rt.find_occupant(room, '2.wolf', {'living': True, 'visible_to': ch})['entity']
    assert renumbered['entity_id'] == third['entity_id']


def test_living_visible_entities_do_not_fall_back_to_sql_entity_scan(tmp_path, monkeypatch):
    rt, ch = make_runtime(tmp_path)
    calls = {"find_entity": 0, "fetch_entities": 0}
    original_find_entity = rt.find_entity
    original_fetch = rt._fetch_entities

    def counted_find_entity(entity_id):
        calls["find_entity"] += 1
        return original_find_entity(entity_id)

    def counted_fetch(where, params):
        if "entity_type='corpse'" not in where:
            calls["fetch_entities"] += 1
        return original_fetch(where, params)

    monkeypatch.setattr(rt, "find_entity", counted_find_entity)
    monkeypatch.setattr(rt, "_fetch_entities", counted_fetch)
    visible = rt.find_visible_entities(ch.room_id, ch)
    assert any(ent["name"] == "Ashback Bear" for ent in visible["mobs"])
    assert calls == {"find_entity": 0, "fetch_entities": 0}


def test_kill_target_resolution_sql_boundary_is_traced(tmp_path):
    rt, ch = make_runtime(tmp_path)
    result = rt.handle_input(ch.id, "kill bear")
    assert result["ok"], result["output"]
    assert result["trace"]["gameplay_sql_before_response"] == 0
    assert "gameplay_sql_response_render" in result["trace"]
