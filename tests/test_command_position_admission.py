from engine.actors import Actor, ActorIdentity, ActorResources
from engine.character_state import ActorPosition, command_position_admission, position_rank


def actor(position: str) -> Actor:
    return Actor("character:tester", "character", ActorIdentity("tester", "Tester", "room"), ActorResources(health=10, maximum_health=10), combat_profile={"position": position, "combat_state": position})


def test_sleeping_command_admission_is_central_and_ordered():
    asleep = actor("sleeping")
    assert position_rank("sleeping") < ActorPosition.RESTING < ActorPosition.STANDING
    for command in ("look", "north", "cast", "kill", "campfire"):
        ok, message = command_position_admission(asleep, command)
        assert not ok
        assert message == "In your dreams, or what?"
    assert command_position_admission(asleep, "wake")[0]


def test_position_admission_accepts_tba_thresholds():
    assert command_position_admission(actor("resting"), "look")[0]
    assert command_position_admission(actor("sitting"), "cast")[0]
    assert command_position_admission(actor("standing"), "north")[0]
    assert command_position_admission(actor("standing"), "kill")[0]
