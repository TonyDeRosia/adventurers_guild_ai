from engine.mud_state_store import MUDStateStore
from engine.progression import ProgressionService

def test_learn_ability_no_duplicate(tmp_path):
    s=MUDStateStore('c','shattered_realms',db_path=tmp_path/'s.sqlite'); s.initialize(); s.save_character({'character_id':'hero'})
    p=ProgressionService(s); p.learn_ability('hero','kick'); p.learn_ability('hero','kick')
    assert p.get_ability_rank('hero','kick') == 1
    assert s.load_abilities('hero').count('kick') == 1
