from types import SimpleNamespace
from pathlib import Path

from engine.mud_displays import build_abilities_document, render_display_plain


def test_ability_column_headers_and_widths():
    rows=[{"name":"Build Campfire","rank":1},{"name":"Set Camp","rank":1}]
    for width in (79,60,48,36):
        theme=SimpleNamespace(width=width, labels={})
        out=render_display_plain(build_abilities_document(rows, title="SKILLS", theme=theme))
        lines=out.splitlines()
        assert any("SKILLS" in line and "PROFICIENCY" in line for line in lines)
        assert not any(line.strip() == "SKILLS" for line in lines[1:])
        assert "Build Campfire" in out and "Set Camp" in out
        assert max(len(line) for line in lines) <= width


def test_spell_and_ability_headers_theme_override():
    theme=SimpleNamespace(width=60, labels={
        "spells.name_header":"MAGICS", "spells.proficiency_header":"POWER",
        "abilities.name_header":"KNOWN", "abilities.proficiency_header":"MASTERY",
    })
    spells=render_display_plain(build_abilities_document([{"name":"Recall","rank":1}], title="SPELLS", theme=theme))
    abilities=render_display_plain(build_abilities_document([{"name":"Recall","rank":1}], title="ABILITIES", theme=theme))
    assert "MAGICS" in spells and "POWER" in spells and "SPELLS" not in spells
    assert "KNOWN" in abilities and "MASTERY" in abilities and "ABILITIES" not in abilities


def test_runtime_set_camp_and_set_campfire_public_path(tmp_path):
    from engine.mud_runtime import MudRuntime
    rt = MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Phase Route')['character_id']
    rt.enter_world(cid)
    assert rt.actor_registry.require(cid).actor_id == cid
    assert rt.abilities._get_actor(cid).actor_id == cid
    first = rt.handle_input(cid, 'set camp')['semantic_output']
    assert 'You establish a modest campsite here.' in first
    assert 'Something went wrong' not in first
    second = rt.handle_input(cid, 'set camp')['semantic_output']
    assert 'A campsite is already established here.' in second
    assert 'Something went wrong' not in second
    typo = rt.handle_input(cid, 'set campfire')['semantic_output']
    assert 'BUILD CAMPFIRE' in typo
    assert 'permission' not in typo.lower()
    fire = rt.handle_input(cid, 'build campfire')['semantic_output']
    assert 'You build a small campfire.' in fire


def test_future_multiword_ability_alias_resolves(tmp_path):
    from engine.mud_runtime import MudRuntime
    rt = MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    ab = rt.abilities.registry.abilities['set_camp']
    ab.plugin_data = {**(ab.plugin_data or {}), 'aliases': ['establish camp']}
    assert rt._match_player_ability_command(['establish','camp'])['args'] == ['establish','camp']


def test_compact_ability_headers_use_dedicated_bright_yellow_roles():
    from engine.mud_displays import render_display_mud
    rows=[{"name":"Build Campfire","rank":1},{"name":"Set Camp","rank":1}]
    mud=render_display_mud(build_abilities_document(rows, title="SKILLS"), color_enabled=True)
    assert "{ability_list_header}SKILLS{/ability_list_header}" in mud
    assert "{ability_list_header}PROFICIENCY{/ability_list_header}" in mud
    assert "{character_value}Build Campfire{/character_value}" in mud
    assert "{character_value}1%{/character_value}" in mud
    from engine.mud_displays import render_display_ansi, render_display_html
    ansi=render_display_ansi(build_abilities_document(rows, title="SKILLS"), color_enabled=True)
    assert "\x1b[33mSKILLS" in ansi and "Build Campfire\x1b[0m" not in ansi
    html=render_display_html(build_abilities_document(rows, title="SKILLS"), color_enabled=True)
    assert 'role="ability_list_header"' in html and 'role="character_value">Build Campfire' in html
    plain=render_display_mud(build_abilities_document(rows, title="SKILLS"), color_enabled=False)
    assert "{ability_list_header}" not in plain and "SKILLS" in plain and "PROFICIENCY" in plain
    override=SimpleNamespace(width=70, labels={}, semantic_roles={"skills.name_header_role":"warning", "skills.proficiency_header_role":"quest"})
    themed=render_display_mud(build_abilities_document(rows, title="SKILLS", theme=override), color_enabled=True)
    assert "{warning}SKILLS{/warning}" in themed
    assert "{quest}PROFICIENCY{/quest}" in themed


def test_legacy_character_schema_set_camp_persists_and_reloads(tmp_path):
    from engine.mud_runtime import MudRuntime
    import json, sqlite3
    rt = MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    cid = 'char_shattered_realms_kraevok'
    data = {"id": cid, "name": "Kraevok", "role": "player", "room_id": rt.active_world.default_starting_room_id, "hp": 100, "max_hp": 100, "mana": 50, "max_mana": 50, "stamina": 100, "max_stamina": 100, "abilities": []}
    with sqlite3.connect(rt.state_store.db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS actor_ability_progression(actor_id TEXT,ability_id TEXT,rank INTEGER,maximum_rank INTEGER,proficiency INTEGER,learned_at_level INTEGER,source_class_id TEXT,source_race_id TEXT,source_profession_id TEXT,source_track_id TEXT,practice_cost INTEGER,training_cost INTEGER,skill_point_cost INTEGER,requirements_json TEXT,active INTEGER,learned_at TEXT,metadata_json TEXT,PRIMARY KEY(actor_id,ability_id))""")
        con.execute("INSERT OR REPLACE INTO characters(id,account_id,world_id,name,slug,role,immortal_level,builder_enabled,data) VALUES(?,?,?,?,?,?,?,?,?)", (cid,'','shattered_realms','Kraevok','kraevok','player',0,0,json.dumps(data)))
        con.execute("INSERT OR REPLACE INTO actor_ability_progression(actor_id,ability_id,rank,maximum_rank,proficiency,learned_at_level,source_class_id,source_race_id,source_profession_id,source_track_id,practice_cost,training_cost,skill_point_cost,requirements_json,active,learned_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid,'set_camp',1,1,None,1,None,None,None,None,0,0,0,'[]',1,'legacy','{}'))
        con.execute("INSERT OR REPLACE INTO actor_ability_progression(actor_id,ability_id,rank,maximum_rank,proficiency,learned_at_level,source_class_id,source_race_id,source_profession_id,source_track_id,practice_cost,training_cost,skill_point_cost,requirements_json,active,learned_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid,'build_campfire',1,1,None,1,None,None,None,None,0,0,0,'[]',1,'legacy','{}'))
    rt.enter_world(cid)
    assert rt.actor_registry.require(cid).actor_id == cid
    assert rt.abilities._get_actor(cid).actor_id == cid
    first = rt.handle_input(cid, 'set camp')['semantic_output']
    assert 'You establish a modest campsite here.' in first
    assert 'Something went wrong' not in first
    assert rt.actor_registry.require(cid).actor_id == cid
    rt2 = MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt2.load_world('shattered_realms')
    rt2.enter_world(cid)
    second = rt2.handle_input(cid, 'set camp')['semantic_output']
    assert 'A campsite is already established here.' in second
    assert 'Something went wrong' not in second
