from engine.mud_state_store import MUDStateStore
from engine.progression import ProgressionService

def test_progression_initialization_migrates_level_xp(tmp_path):
    store=MUDStateStore('c','shattered_realms',db_path=tmp_path/'s.sqlite'); store.initialize(); store.save_character({'character_id':'hero','level':3,'xp':250,'race_id':'human','class_id':'adventurer'})
    service=ProgressionService(store); a=service.initialize_actor_progression('hero'); b=service.initialize_actor_progression('hero')
    assert a['progression_state_id']==b['progression_state_id']; assert b['level']==3; assert b['experience']==250
