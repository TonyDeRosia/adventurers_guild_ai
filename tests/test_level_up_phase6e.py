from engine.mud_state_store import MUDStateStore
from engine.progression import ProgressionService

def test_overflow_level_up_idempotent(tmp_path):
    s=MUDStateStore('c','shattered_realms',db_path=tmp_path/'s.sqlite'); s.initialize(); s.save_character({'character_id':'hero','class_id':'adventurer'})
    p=ProgressionService(s); p.award_experience('hero',1000)
    lvl=p.get_actor_progression('hero')['level']; assert lvl > 1
    assert p.process_all_pending_levels('hero') == 0
