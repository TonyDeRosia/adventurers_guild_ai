from engine.quests import QuestContent, QuestValidator

def test_phase8a_pilot_quests_validate():
    c = QuestContent('worlds/shattered_realms')
    assert c.get('quest_definitions','cellar_rat_problem')['start_stage_id'] == 'cellar_rat_problem_accept'
    assert QuestValidator(c).validate_all().ok
