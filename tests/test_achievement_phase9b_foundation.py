from pathlib import Path
from engine.achievements import AchievementContent, AchievementService, AchievementEventRouter
from smart_mud.event_bus import EventBus


def svc(tmp_path):
    return AchievementService(tmp_path/'ach.db', world_id='shattered_realms', world_root=Path('worlds/shattered_realms'))


def test_phase9b_content_validation_and_pilot_definitions():
    content=AchievementContent('worlds/shattered_realms')
    result=content.validate()
    assert result['errors']==[]
    assert content.get('achievement_definitions','first_blood')['criteria_group_ids']
    assert content.get('title_definitions','rat_hunter')['source_types']==['achievement']
    assert content.get('collection_definitions','starter_discoveries')['entry_ids']


def test_event_consumption_idempotent_completion_title_accolade(tmp_path):
    s=svc(tmp_path)
    ev={'event_type':'actor_killed','event_id':'kill-1','payload':{'actor_id':'hero','victim_template_id':'rat','target_tags':['rat'],'world_time':10}}
    r1=s.process_achievement_event(ev)
    r2=s.process_achievement_event(ev)
    assert s.get_actor_achievement('hero','first_blood')['status']=='completed'
    assert len(s.get_completion_history('hero','first_blood'))==1
    assert any(x.get('ignored') and x.get('reason')=='duplicate_event' for x in r2)
    assert any(a['accolade_id']=='first_victory' for a in s.list_accolades('hero'))


def test_unique_room_progress_persists_and_collection_completion(tmp_path):
    s=svc(tmp_path)
    for rid in ['town_square','town_square','training_yard','rat_cellar']:
        s.process_achievement_event({'event_type':'room_entered','event_id':'enter-'+rid,'payload':{'actor_id':'hero','room_id':rid}})
    progress=s.get_actor_achievement('hero','guildlands_explorer')
    assert progress['status']=='completed'
    coll=s.get_collection_progress('hero','starter_discoveries')
    assert coll['completed'] is True
    s2=AchievementService(tmp_path/'ach.db', world_id='shattered_realms', world_root=Path('worlds/shattered_realms'))
    assert s2.get_actor_achievement('hero','guildlands_explorer')['status']=='completed'


def test_title_select_survives_restart(tmp_path):
    s=svc(tmp_path)
    s.grant_title('hero','rat_hunter','achievement','rat_hunter_10')
    s.select_title('hero','rat_hunter')
    assert s.render_actor_title('hero')=='Rat Hunter'
    s2=AchievementService(tmp_path/'ach.db', world_id='shattered_realms', world_root=Path('worlds/shattered_realms'))
    assert s2.render_actor_title('hero')=='Rat Hunter'


def test_event_router_subscribes_to_eventbus(tmp_path):
    bus=EventBus()
    s=AchievementService(tmp_path/'ach.db', event_bus=bus, world_root=Path('worlds/shattered_realms'))
    AchievementEventRouter(s).subscribe()
    bus.publish('training_transaction_completed', {'actor_id':'hero','event_id':'train-1','offer_id':'basic'})
    assert s.get_actor_achievement('hero','first_lesson')['status']=='completed'
