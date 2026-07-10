from engine.quests import QuestContent, QuestValidator

def test_conversation_definitions_validate():
    c=QuestContent('worlds/shattered_realms')
    assert c.get('conversation_definitions','jory_rat_problem')
    assert QuestValidator(c).validate_conversation('jory_rat_problem').ok
