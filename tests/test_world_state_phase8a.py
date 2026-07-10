from engine.quests import WorldStateService

def test_world_state_set_increment_history_restart(tmp_path):
    db=tmp_path/'q.db'; ws=WorldStateService(db)
    ws.set_state('world','shattered_realms','tutorial_complete', True)
    assert ws.compare_state('world','shattered_realms','tutorial_complete', True)
    ws.increment_state('world','shattered_realms','rat_count', 2)
    assert ws.get_state('world','shattered_realms','rat_count')['value'] == 2
    assert len(ws.get_state_history('world','shattered_realms','rat_count')) == 1
    assert WorldStateService(db).get_state('world','shattered_realms','rat_count')['value'] == 2
