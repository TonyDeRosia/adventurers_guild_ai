from engine.quests import QuestContent, QuestService, QuestValidator

def test_phase8a_foundation_smoke(tmp_path):
    svc = QuestService(tmp_path/'q.db', 'worlds/shattered_realms')
    assert svc.get_quest_definition('cellar_rat_problem')
    assert QuestValidator(QuestContent('worlds/shattered_realms')).validate_all().ok
