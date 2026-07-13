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
