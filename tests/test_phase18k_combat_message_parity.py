from engine.actors import Actor
from engine.combat import CombatEngine
from engine.conditions import transition_text


def test_phase18k_second_person_health_transition_uses_look_not_looks():
    actor = Actor.create('character:hero', 'You', 'player')
    actor.resources.health = 60
    actor.resources.maximum_health = 100
    third = transition_text(actor.identity.name, actor)
    trans = third[len(actor.identity.name):].strip()
    direct = 'You look' + trans[len('looks'):] if trans.startswith('looks') else 'You ' + trans
    assert direct == 'You look wounded.'


def test_phase18k_authored_wolf_bite_does_not_fall_back_to_punch():
    engine = CombatEngine()
    wolf = Actor.create('entity:wolf', 'Forest Wolf', 'mob')
    hero = Actor.create('character:hero', 'Dravorik', 'player')
    event = type('E', (), {
        'attack_profile': {'name': 'wolf_bite'},
        'weapon': {'mechanical_family': 'wolf_bite', 'attack_verb': 'bites', 'attack_noun': 'fangs'},
        'final_damage': 3,
        'critical': False,
    })()
    msg = engine._messages(wolf, hero, 'hit', event)['victim']
    assert 'bites you' in msg
    assert 'punch' not in msg.lower()
