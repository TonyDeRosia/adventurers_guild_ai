from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus


def make_runtime(tmp_path, bus=None):
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=bus or EventBus())
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Twelve A Four")["character_id"]
    return rt, cid


def text(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def test_inspection_aliases_and_visible_campfire_lifecycle_persist(tmp_path):
    rt, cid = make_runtime(tmp_path)

    assert "You establish a modest campsite here." in text(rt, cid, "set camp")
    assert "a small campsite" in text(rt, cid, "look")
    assert "You build a small campfire." in text(rt, cid, "build campfire")
    assert "an unlit campfire" in text(rt, cid, "look")
    assert "Kindling" in text(rt, cid, "look at campfire")
    assert "Kindling" in text(rt, cid, "inspect campfire")

    assert "You light the campfire." in text(rt, cid, "light campfire")
    assert "a lit campfire" in text(rt, cid, "look")
    assert "Warm flames" in text(rt, cid, "examine campfire")
    assert "You extinguish the campfire." in text(rt, cid, "extinguish campfire")
    assert "a bed of cold ashes" in text(rt, cid, "look")

    reloaded = MudRuntime(Path.cwd(), tmp_path, event_bus=EventBus())
    reloaded.load_world("shattered_realms")
    assert "a bed of cold ashes" in text(reloaded, cid, "look")


def test_expanded_socials_publish_events(tmp_path):
    events = []
    bus = EventBus()
    bus.subscribe("social_emote_performed", lambda event: events.append(event.payload["social_id"]), source="test_socials")
    rt, cid = make_runtime(tmp_path, bus)

    for command in ["wave", "bow", "nod", "salute", "point", "laugh", "smile", "cry", "cheer", "applaud", "hug", "highfive", "dance", "spit", "sit", "stand", "rest", "yawn", "stretch"]:
        output = text(rt, cid, command)
        assert "Phase Twelve A Four" in output
        assert 'say,' not in output.lower()

    assert set(events) >= {"wave", "bow", "nod", "salute", "point", "laugh", "smile", "cry", "cheer", "applaud", "hug", "highfive", "dance", "spit", "sit", "stand", "rest", "yawn", "stretch"}
