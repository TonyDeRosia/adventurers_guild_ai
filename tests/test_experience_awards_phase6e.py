import pytest
from engine.mud_state_store import MUDStateStore
from engine.progression import ProgressionService

def test_xp_award_history_and_negative_rejected(tmp_path):
    s=MUDStateStore('c','shattered_realms',db_path=tmp_path/'s.sqlite'); s.initialize(); s.save_character({'character_id':'hero'})
    p=ProgressionService(s); p.award_experience('hero',150,'admin',reason='test')
    assert p.get_actor_progression('hero')['experience'] >= 150
    assert p.get_experience_history('hero')[0]['reason']=='test'
    with pytest.raises(ValueError): p.award_experience('hero',-1)
