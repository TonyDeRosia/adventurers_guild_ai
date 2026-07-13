from types import SimpleNamespace

from engine.help_service import HelpEntry, HelpService
from engine.mud_commands import MudCommandEngine
from engine.mud_displays import build_abilities_document, build_score_document, build_worth_document, render_display_plain, render_display_html


def actor(**kw):
    base=dict(id='p1', name='Player', role='player', account_role='player', preferences={})
    base.update(kw)
    return SimpleNamespace(**base)


def test_help_service_matching_and_visibility():
    svc=HelpService('worlds/shattered_realms')
    assert svc.get_entry('RACE', actor()).title == 'Race'
    assert svc.get_entry('align', actor()).title == 'Alignment'
    assert svc.get_entry('build campfire', actor()).title == 'Build Campfire'
    assert 'character' in svc.categories(actor())
    assert any(e.title == 'Class' for e in svc.related('race', actor()))


def test_unknown_topic_guidance_and_title_no_json():
    eng=MudCommandEngine(); ch=actor()
    assert 'Type HELP RACE' in eng.handle_command(ch, 'race').narrative
    assert 'Type HELP ALIGNMENT' in eng.handle_command(ch, 'algin').narrative
    out=eng.handle_command(ch, 'title the Admin').narrative
    assert 'definition' not in out and 'progress_history' not in out
    assert 'Your title is now' in out


def test_compact_abilities_score_worth_and_no_color():
    rows=[{'name':'Build Campfire','rank':1,'maximum_rank':100,'description':'long text','costs':[{'resource_id':'mana','amount':5}]},{'name':'Set Camp','rank':1,'maximum_rank':1}]
    skills=render_display_plain(build_abilities_document(rows, title='SKILLS'))
    assert 'Build Campfire' in skills and 'Set Camp' in skills and 'Rank 1' in skills
    assert 'long text' not in skills and '/100' not in skills and 'Type HELP' not in skills and '─' not in skills
    spells=render_display_plain(build_abilities_document([{'name':'Recall','rank':1,'maximum_rank':100}], title='SPELLS'))
    assert 'Recall' in spells and 'Rank 1' in spells and '/100' not in spells and 'Type HELP' not in spells
    abilities=render_display_plain(build_abilities_document(rows + [{'name':'Recall','rank':1,'maximum_rank':100}], title='ABILITIES'))
    assert all(x in abilities for x in ('Build Campfire','Set Camp','Recall')) and 'Type HELP' not in abilities and '/100' not in abilities
    score=render_display_plain(build_score_document(actor(title='', level=1, hp=5, max_hp=10, xp=0, xp_to_next_level=100)))
    assert 'Race:' not in score and 'Class:' not in score and 'Carry Capacity' not in score
    worth=render_display_plain(build_worth_document(actor()))
    assert 'CURRENCIES' in worth and 'CHARACTER STATUS' not in worth
    html=render_display_html(build_score_document(actor()), color_enabled=False)
    assert '<span role=' not in html


def test_set_camp_specific_results_and_validation_consistency(tmp_path):
    from pathlib import Path
    from engine.mud_runtime import MudRuntime

    rt = MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    cid = rt.create_character(world_id='shattered_realms', name='Phase Thirteen Camp')['character_id']
    rt.enter_world(cid)
    char = rt.state_store.load_character(cid)
    svc = rt.abilities

    denial = svc.validate_ability_use(cid, 'set_camp', context={'camping_allowed': False})
    assert denial['reason_code'] == 'blocked_room'
    assert denial['message'] == 'You cannot establish a camp here.'

    combat = svc.validate_ability_use(cid, 'set_camp', context={'in_combat': True})
    assert combat['reason_code'] == 'blocked_combat'
    assert combat['message'] == 'You cannot establish a camp while fighting.'

    first = rt.handle_input(cid, 'set camp')['semantic_output']
    assert 'You establish a modest campsite here.' in first
    assert 'Something went wrong' not in first

    existing = svc.validate_ability_use(cid, 'set_camp')
    assert existing['reason_code'] == 'blocked_prerequisite'
    assert existing['message'] == 'A campsite is already established here.'
    second = rt.handle_input(cid, 'set camp')['semantic_output']
    assert existing['message'] in second
    assert 'Something went wrong' not in second
