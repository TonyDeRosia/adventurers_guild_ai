import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from smart_mud.builder import BuilderWorkspace

ROOT = Path('worlds/shattered_realms/builder')
PACK = 'starter_guildlands_content_pack_v1.json'
ZONE_RANGES = {
    'guildhall_crossing': (1000, 1029), 'registrar_hall': (1030, 1049),
    'training_grounds': (1050, 1079), 'market_lane': (1080, 1119),
    'wayfarers_mug': (1120, 1149), 'old_gate_road': (1150, 1179),
    'east_farmland': (1180, 1209), 'emberwood_edge': (1210, 1239),
    'abandoned_watchpost': (1240, 1269), 'rat_cellar': (1270, 1299),
}
REVERSE = {'north':'south','south':'north','east':'west','west':'east','up':'down','down':'up','in':'out','out':'in'}

def actor():
    return SimpleNamespace(id='builder', account_id='acct', role='builder', world_id='shattered_realms')

def load_pack():
    return json.loads((ROOT / 'templates' / PACK).read_text(encoding='utf-8'))

def test_phase4h_content_pack_files_and_shape():
    assert (ROOT / 'templates' / PACK).exists()
    assert (ROOT / 'examples' / PACK).exists()
    data = load_pack()
    for key in ['areas','zones','rooms','features','items','entities','spawns']:
        assert key in data and isinstance(data[key], dict)
    assert len(data['rooms']) >= 40
    assert sum(len(room.get('features', {})) for room in data['rooms'].values()) >= 30
    assert len(data['features']) >= 10
    assert len(data['items']) >= 10
    assert len(data['entities']) >= 12
    assert len(data['spawns']) >= 20

def test_phase4h_room_vnums_exits_zones_spawns_and_ai_profiles():
    data = load_pack()
    existing = set(json.loads((ROOT / 'rooms.json').read_text(encoding='utf-8')))
    room_ids = set(data['rooms']) | existing
    vnums = set()
    for rid, room in data['rooms'].items():
        assert rid.startswith('starter_guildlands_')
        assert room['area_id'] == 'starter_guildlands'
        assert room['vnum'] not in vnums
        vnums.add(room['vnum'])
        lo, hi = ZONE_RANGES[room['zone_id']]
        assert lo <= room['vnum'] <= hi
        for direction, exit_data in room.get('exits', {}).items():
            target = exit_data.get('target_room_id')
            assert target in room_ids
            if direction in REVERSE and 'one_way' not in room.get('flags', []):
                target_room = data['rooms'].get(target)
                if target_room:
                    reverse = target_room.get('exits', {}).get(REVERSE[direction], {})
                    assert reverse.get('target_room_id') == rid
    for zid, zone in data['zones'].items():
        for room_id in zone.get('room_ids', []):
            assert room_id in room_ids
    for spawn in data['spawns'].values():
        assert spawn['entity_template_id'] in data['entities']
        assert spawn['room_id'] in room_ids
        assert 1700 <= spawn['spawn_vnum'] <= 1799
    required = {'personality','speech_style','daily_role','goals','fears','relationships','memory_seed','behavior_notes'}
    for entity in data['entities'].values():
        assert required <= set(entity.get('plugin_data', {}).get('ai_profile', {}))

def test_phase4h_builder_import_pipeline_and_template_copy(tmp_path):
    worlds_dir = tmp_path / 'worlds'
    shutil.copytree(Path('worlds/shattered_realms'), worlds_dir / 'shattered_realms', ignore=shutil.ignore_patterns('audit','history','snapshots','exports'))
    bw = BuilderWorkspace(worlds_dir=worlds_dir)
    a = actor()
    assert PACK in bw.template_list(a).message
    copy = bw.template_copy(a, PACK, 'copied_pack.json')
    assert copy.ok
    assert (worlds_dir / 'shattered_realms/builder/imports/copied_pack.json').exists()
    assert bw.import_validate(a, 'copied_pack.json').ok
    preview = bw.import_preview(a, 'copied_pack.json')
    assert preview.ok and 'Rooms to add/update:' in preview.message
    assert bw.import_apply(a, 'copied_pack.json').ok
    validation = bw.validate(a)
    assert validation.ok
