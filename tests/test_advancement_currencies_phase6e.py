import pytest
from engine.mud_state_store import MUDStateStore
from engine.progression import ProgressionService

def test_currency_grant_spend_no_negative(tmp_path):
    s=MUDStateStore('c','shattered_realms',db_path=tmp_path/'s.sqlite'); s.initialize(); s.save_character({'character_id':'hero'})
    p=ProgressionService(s); p.grant_currency('hero','practice_sessions',2,'admin',None,'test')
    p.spend_currency('hero','practice_sessions',1)
    assert p.get_actor_progression('hero')['practice_sessions']==1
    with pytest.raises(ValueError): p.spend_currency('hero','practice_sessions',5)
