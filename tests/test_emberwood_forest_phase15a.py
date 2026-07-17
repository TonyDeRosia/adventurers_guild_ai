import json
from collections import deque
from pathlib import Path
from engine.character_stats import CharacterAttributeService, CombatStatService
from engine.zone_resets import ZoneResetService

ROOT=Path('worlds/shattered_realms')
FOREST=['emberwood_hunting_trail','emberwood_edge','emberwood_game_trail','forest_trail','fern_hollow','mossy_creek','fallen_oak','briar_thicket','fox_burrow','wolf_trail','woodland_camp','old_hunters_blind','deep_emberwood','spider_glade','wolf_den','ancient_ember_grove']
CREATURES=['forest_wolf','emberwood_fox','wild_boar','giant_wood_spider','dire_forest_wolf','emberwood_stag','ashback_bear']

def load(rel): return json.load(open(ROOT/rel))
def exits(room): return {e['direction']: e['destination_room_id'] for e in room.get('exits',[])}

def test_emberwood_rooms_topology_area_zone_and_vnums():
    rooms={r['id']:r for r in load('rooms/rooms.json')}
    assert len(set(rooms))==len(rooms)
    assert all(r in rooms for r in FOREST)
    old_gate_dirs=[e['direction'] for e in rooms['old_gate_road']['exits']]
    assert len(old_gate_dirs)==len(set(old_gate_dirs))
    assert sum(1 for e in rooms['old_gate_road']['exits'] if e['direction']=='north')==1
    assert exits(rooms['old_gate_road'])['north']=='emberwood_hunting_trail'
    for rid in FOREST:
        assert rooms[rid]['area_id']=='emberwood_edge'
        assert rooms[rid]['zone_id']=='emberwood_forest'
        assert not rooms[rid].get('npcs')
        dirs=[e['direction'] for e in rooms[rid]['exits']]
        assert len(dirs)==len(set(dirs))
        for d,t in exits(rooms[rid]).items():
            assert t in rooms
    opposite={'north':'south','south':'north','east':'west','west':'east','in':'out','out':'in'}
    for rid in FOREST+['old_gate_road']:
        for d,t in exits(rooms[rid]).items():
            if t in rooms and d in opposite and rid in FOREST and t in FOREST+['old_gate_road']:
                assert exits(rooms[t]).get(opposite[d])==rid
    seen={'old_gate_road'}; q=deque(['old_gate_road'])
    while q:
        r=q.popleft()
        for t in exits(rooms[r]).values():
            if t not in seen and t in rooms: seen.add(t); q.append(t)
    assert set(FOREST).issubset(seen)
    back={rid:[] for rid in rooms}
    for rid,r in rooms.items():
        for t in exits(r).values(): back.setdefault(t,[]).append(rid)
    for rid in FOREST: assert rid in seen and back[rid]
    br=load('builder/rooms.json')
    vnums=[r['vnum'] for r in br.values() if 'vnum' in r]
    assert len(vnums)==len(set(vnums))
    assert [br[r]['vnum'] for r in ['forest_trail','wolf_trail','wolf_den','woodland_camp']]==[1212,1213,1214,1215]

def test_emberwood_creature_snapshots_and_relationships():
    npcs={n['id']:n for n in load('npcs/npcs.json')}
    svc=CombatStatService(CharacterAttributeService(world_root=ROOT))
    snap={tid:svc.get_combat_snapshot(svc.build_actor_stat_input(npcs[tid])) for tid in CREATURES}
    assert all(s.resource_maxima['max_health'].value>0 and s.weapon_profile for s in snap.values())
    assert snap['emberwood_fox'].defense['evasion'] > snap['forest_wolf'].defense['evasion']
    assert snap['forest_wolf'].weapon_profile.maximum_damage > snap['emberwood_fox'].weapon_profile.maximum_damage
    assert snap['wild_boar'].defense['armor'] > snap['forest_wolf'].defense['armor']
    assert snap['wild_boar'].resource_maxima['max_health'] > snap['forest_wolf'].resource_maxima['max_health']
    assert snap['giant_wood_spider'].defense['evasion'] >= snap['forest_wolf'].defense['evasion']
    assert snap['dire_forest_wolf'].offense['hit_bonus'] > snap['forest_wolf'].offense['hit_bonus']
    assert snap['dire_forest_wolf'].weapon_profile.maximum_damage > snap['forest_wolf'].weapon_profile.maximum_damage
    assert snap['ashback_bear'].defense['armor'] > snap['wild_boar'].defense['armor']
    assert snap['ashback_bear'].resource_maxima['max_health'] > snap['dire_forest_wolf'].resource_maxima['max_health']
    assert snap['ashback_bear'].defense['evasion'] < snap['dire_forest_wolf'].defense['evasion']
    for tid in CREATURES:
        assert npcs[tid]['ability_loadout_id']
        assert npcs[tid]['combat_behavior_profile_id']
        assert npcs[tid]['body_profile_id']
        assert npcs[tid]['death_loot_profile_id']

def test_emberwood_reset_profile_and_no_static_population():
    assert load('population_definitions/population_definitions.json') == []
    profiles=ZoneResetService(worlds_dir='worlds').load_profiles('shattered_realms')
    prof=next(p for p in profiles if p['reset_profile_id']=='emberwood_forest_population')
    v=ZoneResetService(worlds_dir='worlds').validate_profile(prof)
    assert v.ok, v.errors
    assert prof['zone_id']=='emberwood_forest'
    assert prof['reset_mode']=='when_empty'
    assert prof['reset_interval_seconds']==600
    rooms={c['room_id']:[] for c in prof['commands']}
    for c in prof['commands']:
        assert c['command_type']=='SPAWN_ENTITY'
        rooms[c['room_id']].append(c)
        assert c['maximum_count'] >= c['spawn_count']
    assert 'woodland_camp' not in rooms
    assert 'old_hunters_blind' not in rooms
    bear=[c for c in prof['commands'] if c['entity_template_id']=='ashback_bear']
    assert len(bear)==1 and bear[0]['maximum_scope']=='zone' and bear[0]['maximum_count']==1

def test_phase15b31_canonical_spawns_loaded_and_match_reset_profile():
    from smart_mud.world_registry import WorldRegistry
    world = WorldRegistry().load_world('shattered_realms')
    spawns = {s['id']: s for s in world.spawns}
    assert len(spawns) >= 15
    profiles = ZoneResetService(worlds_dir='worlds').load_profiles('shattered_realms')
    prof = next(p for p in profiles if p['reset_profile_id'] == 'emberwood_forest_population')
    command_ids = {c['reset_command_id'] for c in prof['commands'] if c['command_type'] == 'SPAWN_ENTITY'}
    assert command_ids.issubset(spawns)
    for cid in command_ids:
        spawn = spawns[cid]
        command = next(c for c in prof['commands'] if c['reset_command_id'] == cid)
        assert spawn['entity_template_id'] == command['entity_template_id']
        assert spawn['room_id'] == command['room_id']
        assert spawn['reset_profile_id'] == prof['reset_profile_id']


def test_phase15b31_zone_reset_living_count_ignores_dead_and_corpses(tmp_path):
    import sqlite3, json
    from engine.mud_runtime import MudRuntime
    db = tmp_path / 'mud_state.db'
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world('shattered_realms')
    svc = ZoneResetService(runtime=rt, db_path=db, worlds_dir='worlds')
    assert svc._count('entity', 'forest_wolf', 'room', 'emberwood_hunting_trail', 'emberwood_forest', 'shattered_realms') == 1
    wolf = rt.find_room_entities('emberwood_hunting_trail')[0]
    rt.update_entity_state(wolf['entity_id'], {'current_state': 'dead', 'is_alive': False}, source_system='test')
    assert svc._count('entity', 'forest_wolf', 'room', 'emberwood_hunting_trail', 'emberwood_forest', 'shattered_realms') == 0
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ('corpse_test','shattered_realms','corpse','forest_wolf','corpse','[]','corpse','corpse','emberwood_hunting_trail','room','','',1,json.dumps({'current_state':'corpse','is_alive':False}),'[]','now','now','{}'))
    assert svc._count('entity', 'forest_wolf', 'room', 'emberwood_hunting_trail', 'emberwood_forest', 'shattered_realms') == 0
    result = svc.execute('emberwood_forest_population', trigger='manual', force=True)
    assert result['entities'] == 1
    assert svc._count('entity', 'forest_wolf', 'room', 'emberwood_hunting_trail', 'emberwood_forest', 'shattered_realms') == 1
    again = svc.execute('emberwood_forest_population', trigger='manual', force=True)
    assert again['entities'] == 0

def test_phase15b31_spawn_validation_rejects_bad_refs_and_duplicate_ids(tmp_path):
    import json, shutil
    from smart_mud.world_registry import WorldRegistry, WorldValidationError
    src = Path('worlds/shattered_realms')
    dst_root = tmp_path / 'worlds'
    dst = dst_root / 'shattered_realms'
    ignore = shutil.ignore_patterns('builder', '__pycache__')
    shutil.copytree(src, dst, ignore=ignore)
    spawn_path = dst / 'spawns' / 'spawns.json'
    data = json.loads(spawn_path.read_text())
    data['spawns'].append(dict(data['spawns'][0]))
    data['spawns'].append({**data['spawns'][0], 'id': 'bad_template_ref', 'entity_template_id': 'missing_template'})
    data['spawns'].append({**data['spawns'][0], 'id': 'bad_room_ref', 'room_id': 'missing_room'})
    spawn_path.write_text(json.dumps(data))
    try:
        WorldRegistry(dst_root).load_world('shattered_realms')
    except WorldValidationError as exc:
        text = '\n'.join(exc.errors)
    else:
        raise AssertionError('invalid canonical spawn data should fail validation')
    assert 'Duplicate spawn ID' in text
    assert 'missing entity template' in text
    assert 'missing room' in text
