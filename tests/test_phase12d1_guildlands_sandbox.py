import json
from collections import deque
from pathlib import Path

ROOMS_PATH = Path('worlds/shattered_realms/builder/rooms.json')
ZONES_PATH = Path('worlds/shattered_realms/builder/zones.json')

REVERSE = {
    'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east',
    'northeast': 'southwest', 'southwest': 'northeast',
    'northwest': 'southeast', 'southeast': 'northwest',
    'in': 'out', 'out': 'in', 'up': 'down', 'down': 'up',
}

PHASE12D1_ROOMS = {
    'forest_trail', 'wolf_trail', 'wolf_den', 'woodland_camp',
    }


def load_rooms():
    return json.loads(ROOMS_PATH.read_text())


def test_guildlands_builder_sandbox_has_20_to_30_connected_rooms():
    rooms = load_rooms()
    assert 20 <= len(rooms) <= 30
    assert PHASE12D1_ROOMS <= set(rooms)

    seen = {'guildhall_crossing_square'}
    queue = deque(seen)
    while queue:
        rid = queue.popleft()
        for exit_data in rooms[rid].get('exits', {}).values():
            target = exit_data['target_room_id']
            assert target in rooms
            if target not in seen:
                seen.add(target)
                queue.append(target)
    assert seen == set(rooms)


def test_guildlands_builder_sandbox_exits_are_bidirectional():
    rooms = load_rooms()
    for room_id, room in rooms.items():
        for direction, exit_data in room.get('exits', {}).items():
            target_id = exit_data['target_room_id']
            reverse = REVERSE.get(direction)
            assert reverse, f'{room_id}.{direction} does not declare a known reverse direction'
            assert rooms[target_id]['exits'].get(reverse, {}).get('target_room_id') == room_id


def test_phase12d1_rooms_are_builder_authored_engine_validation_rooms():
    rooms = load_rooms()
    for room_id in PHASE12D1_ROOMS:
        room = rooms[room_id]
        assert room['world_id'] == 'shattered_realms'
        assert room['area_id'] == 'starter_guildlands'
        assert room['plugin_data']['purpose'] == 'engine_validation_sandbox'
        assert 'outdoor' in room['tags']


def test_zone_membership_references_existing_rooms():
    rooms = load_rooms()
    zones = json.loads(ZONES_PATH.read_text())
    for zone in zones.values():
        for room_id in zone.get('room_ids', []):
            assert room_id in rooms
