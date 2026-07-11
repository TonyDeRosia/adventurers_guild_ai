from pathlib import Path
import sqlite3

from engine.survival_needs import SurvivalNeedsService
from engine.mud_rendering import render_mud_color_html, render_mud_color_ansi, render_semantic_plain, validate_mud_color_markup
from engine.mud_displays import render_room
from smart_mud.transport import html_to_plain_text

WORLD = Path('worlds/shattered_realms')


def test_campsite_campfire_lifecycle_uniqueness_parent_cleanup(tmp_path):
    db = tmp_path / 's.db'
    svc = SurvivalNeedsService(db, WORLD, 'shattered_realms')
    cs1 = svc.create_campsite('char_a', 'basic_campsite', 'room_a')
    assert cs1['expires_world_time'] == 480
    cf1 = svc.create_campfire('char_a', 'basic_campfire', 'room_a')
    assert cf1['expires_world_time'] == 120
    cs2 = svc.create_campsite('char_a', 'basic_campsite', 'room_b')
    assert cs2['replaced_previous']
    with sqlite3.connect(db) as con:
        assert con.execute("select status from campsite_instances where campsite_instance_id=?", (cs1['campsite_instance_id'],)).fetchone()[0] == 'replaced'
        assert con.execute("select status from campfire_instances where campfire_instance_id=?", (cf1['campfire_instance_id'],)).fetchone()[0] == 'replaced'
    assert not svc.create_campfire('char_a', 'basic_campfire', 'room_a')['ok']
    cf2 = svc.create_campfire('char_a', 'basic_campfire', 'room_b')
    assert cf2['ok']
    expired = svc.process_due_runtime_objects(500)
    assert expired['expired_count'] >= 1
    with sqlite3.connect(db) as con:
        assert con.execute("select count(*) from campsite_instances where status in ('active','occupied','abandoned')").fetchone()[0] == 0
        assert con.execute("select count(*) from campfire_instances where status in ('unlit','lit','extinguished','low_fuel')").fetchone()[0] == 0


def test_different_players_may_have_separate_campsites(tmp_path):
    db = tmp_path / 's.db'
    svc = SurvivalNeedsService(db, WORLD, 'shattered_realms')
    assert svc.create_campsite('char_a', room_id='room_a')['ok']
    assert svc.create_campsite('char_b', room_id='room_a')['ok']
    with sqlite3.connect(db) as con:
        assert con.execute("select count(*) from campsite_instances where status='active'").fetchone()[0] == 2


def test_color_markup_safe_browser_terminal_plain_and_validation():
    text = 'A white room with &rred warning&n and &ccyan magic&n <script>x</script>'
    html = render_mud_color_html(text)
    assert 'mud-color-red' in html and '&lt;script&gt;' in html and '<script>' not in html
    ansi = render_mud_color_ansi('plain &rred&n')
    assert '\x1b[31m' in ansi and ansi.endswith('\x1b[0m')
    assert render_semantic_plain('{room_description}&rred&n{/room_description}') == 'red'
    assert validate_mud_color_markup('&z bad') and validate_mud_color_markup('\x1b[31m bad')


def test_unmarked_room_entities_objects_default_to_white_roles():
    class Room:
        title='Room'
        description='Unmarked description.'
        players=[]
        npcs=[{'name':'NPC Name'}]
        mobs=[{'name':'Mob Name'}]
        objects=[{'name':'Object Name'}]
        exits=[]
    html = render_room(Room(), {})
    assert 'role="room_description"' in html
    assert 'role="npc"' in html and 'role="mob"' in html and 'role="object"' in html
    assert html_to_plain_text(html).count('Unmarked description.') == 1
