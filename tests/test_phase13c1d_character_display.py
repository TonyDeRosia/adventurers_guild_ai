from types import SimpleNamespace

from engine.mud_displays import build_score_document, build_worth_document, build_abilities_document, build_prompt_document, render_display_plain, render_display_html, render_display_mud
from engine.mud_rendering import render_semantic_plain
from engine.display_themes import validate_display_theme, preview_display_theme


def _char(**kw):
    base=dict(name='Kraevok', title='Adventurer', race='Human', character_class='Adventurer', level=1, hp=46, max_hp=100, mana=50, max_mana=50, stamina=100, max_stamina=100, xp=0, xp_to_next_level=100, gold=0, posture='standing', attributes={'strength': {'final': 10}, 'dexterity': {'final': 10}, 'constitution': {'final': 10}}, calculated_stats={'armor': 0})
    base.update(kw)
    return SimpleNamespace(**base)


def test_score_and_worth_use_classic_frame_without_placeholders():
    score=render_display_plain(build_score_document(_char()))
    assert '╔' in score and 'CHARACTER STATUS' in score and '╚' in score
    assert 'Name: Kraevok' in score and 'HP: 46/100' in score and 'TNL: 100' in score
    assert 'Str: 10' in score and 'Gold: 0' in score and 'Posture: standing' in score
    assert 'Premium' not in score and 'future' not in score
    worth=render_display_plain(build_worth_document(_char()))
    assert 'CURRENCIES' in worth and 'Gold: 0' in worth
    assert 'You have 0 gold coins' not in worth and 'Premium' not in worth


def test_skills_and_spells_are_distinct_structured_displays():
    skill={'id':'build_campfire','name':'Build Campfire','ability_type':'skill','category':'starter','rank':1,'maximum_rank':100,'status_text':'Requires an established campsite.','costs':[],'description':'Build a simple campfire at an established campsite.','progression_metadata':{'source_type':'starter_character'}}
    spell={'id':'recall','name':'Recall','ability_type':'spell','rank':1,'maximum_rank':100,'status_text':'Ready','cooldown_remaining':'—','costs':[{'resource_id':'mana','amount':5}], 'targeting': {'mode':'self'}, 'description':'Return safely to your configured recall point.'}
    skills=render_display_plain(build_abilities_document([skill], title='SKILLS'))
    spells=render_display_plain(build_abilities_document([spell], title='SPELLS'))
    assert 'SKILLS' in skills and 'SPELLS' in spells and 'Your abilities:' not in skills + spells
    assert 'Source:' not in skills and 'starter_character' not in skills
    assert 'Requires an established campsite.' not in skills
    assert 'Mana: 5' not in spells and 'Target: Self' not in spells
    assert 'Type HELP Build Campfire' not in skills
    assert '1%' in skills and 'Rank' not in skills
    html=render_display_html(build_abilities_document([skill], title='SKILLS'))
    assert 'role="character_title"' in html and 'warning' not in html


def test_prompt_presets_custom_unknown_and_parity():
    compact=render_display_plain(build_prompt_document(_char()))
    classic=render_display_plain(build_prompt_document(_char(preferences={'prompt_preset':'classic'})))
    custom=render_display_plain(build_prompt_document(_char(prompt_template='[%h/%H HP %Z]')))
    assert compact == '[46/100 HP 50/50 MP 100/100 ST]'
    assert '100 TNL' in classic and '0 Gold' in classic
    assert '%Z' in custom
    assert render_semantic_plain(render_display_mud(build_prompt_document(_char(preferences={'prompt_preset':'classic'})))) == classic


def test_builder_theme_validation_and_preview():
    good={'labels': {'score.title':'&YCHARACTER STATUS&n'}, 'semantic_roles': {'frame':'character_frame'}}
    assert validate_display_theme(good) == []
    assert validate_display_theme({'templates': {'score': {'title':'{name}'}}})
    assert preview_display_theme(good)['ok'] == 'true'
    bad={'templates': {'score': {'title':'{player.secret}'}, 'mail': {'title':'x'}}, 'labels': {'x':'<script>alert(1)</script>'}}
    errors='\n'.join(validate_display_theme(bad))
    assert 'unsupported display family' in errors and 'arbitrary expressions' in errors and 'HTML' in errors


def test_cell_roles_are_rendered_independently_and_unknown_ability_is_not_ready():
    doc = build_score_document(_char(title='Long Title', xp_to_next_level=42, attributes={'strength': {'base': 10, 'modifier': 2, 'final': 12}, 'dexterity': {'base': 10, 'modifier': -1, 'final': 9}}, calculated_stats={'armor': 5}))
    mud = render_display_mud(doc)
    assert '{character_label}Name: {/character_label}{character_value}Kraevok{/character_value}' in mud
    assert '{character_label}Title: {/character_label}{character_value}Long Title{/character_value}' in mud
    assert 'TNL: 42' in render_display_plain(doc)
    abilities = render_display_plain(build_abilities_document([{'name': 'Mystery'}]))
    assert 'Mystery' in abilities and '1%' in abilities and 'Rank' not in abilities
    assert 'Status: Ready' not in abilities


def test_builder_preview_uses_real_runtime_builder_for_multiple_families():
    raw = {'width': 60}
    score = preview_display_theme(raw, 'score')
    skills = preview_display_theme(raw, 'skills')
    assert score['ok'] == 'true' and 'CHARACTER STATUS' in score['plain']
    assert skills['ok'] == 'true' and 'Build Campfire' in skills['plain']
