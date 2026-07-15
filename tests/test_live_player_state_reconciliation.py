from engine.actors import Actor, ActorResources
from engine.character_state import derive_position_from_health, reconcile_actor_position, build_action_state, state_message


def actor(hp=10, pos="standing", life="alive"):
    a = Actor.create("character:test", "Tester")
    a.resources = ActorResources(health=hp, maximum_health=20)
    a.lifecycle_state = life
    a.combat_profile["combat_state"] = pos
    a.combat_profile["position"] = pos
    return a


def test_positive_hp_stale_incapacitated_reconciles_to_standing():
    a = actor(10, "incapacitated")
    stored, derived, changed = reconcile_actor_position(a)
    assert (stored, derived, changed) == ("incapacitated", "standing", True)
    assert build_action_state(a).can_attack is True


def test_legitimately_dead_character_not_resurrected():
    a = actor(-11, "standing", "dead")
    reconcile_actor_position(a)
    st = build_action_state(a)
    assert st.derived_position == "dead"
    assert st.can_attack is False
    assert state_message(st.derived_position) == "You are dead and cannot attack."


def test_attack_rejection_messages_by_position():
    cases = {
        "sleeping": "You are asleep. WAKE before trying to fight.",
        "resting": "You need to stand before you can attack.",
        "sitting": "You need to stand before you can attack.",
        "stunned": "You are too stunned to attack.",
        "incapacitated": "You are incapacitated and cannot fight.",
        "mortally_wounded": "You are mortally wounded and cannot fight.",
        "dead": "You are dead and cannot attack.",
    }
    hp = {"stunned": 0, "incapacitated": -4, "mortally_wounded": -8, "dead": -11}
    for pos, msg in cases.items():
        a = actor(hp.get(pos, 10), pos, "dead" if pos == "dead" else "alive")
        reconcile_actor_position(a)
        st = build_action_state(a)
        assert st.can_attack is False
        assert state_message(st.derived_position) == msg


def test_hp_threshold_contract():
    assert derive_position_from_health(1, "incapacitated") == "standing"
    assert derive_position_from_health(0, "standing") == "stunned"
    assert derive_position_from_health(-2, "standing") == "stunned"
    assert derive_position_from_health(-3, "standing") == "incapacitated"
    assert derive_position_from_health(-5, "standing") == "incapacitated"
    assert derive_position_from_health(-6, "standing") == "mortally_wounded"
    assert derive_position_from_health(-10, "standing") == "mortally_wounded"
    assert derive_position_from_health(-11, "standing") == "dead"
