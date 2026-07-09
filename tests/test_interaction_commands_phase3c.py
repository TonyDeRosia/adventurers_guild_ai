from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus


def make_runtime(tmp_path):
    bus = EventBus()
    events = []
    for name in [
        "interaction_attempted", "interaction_succeeded", "interaction_failed",
        "environment_inspected", "entity_interaction", "object_interaction",
        "container_interaction", "command_alias_resolved",
    ]:
        bus.subscribe(name, lambda event, _events=events: _events.append(event.event_name), source=f"test_{name}")
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=bus)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Threec")['character_id']
    return rt, cid, events


def out(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def test_unknown_interactions_return_clean_text_and_events(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    assert "You cannot enter that." in out(rt, cid, "enter gate")
    assert "You cannot drink from that." in out(rt, cid, "drink from fountain")
    assert "You cannot eat that." in out(rt, cid, "eat gate")
    assert "You cannot pick that." in out(rt, cid, "pick lock")
    assert "interaction_attempted" in events
    assert "interaction_failed" in events
    assert "object_interaction" in events


def test_pickup_aliases_route_to_get_but_pick_lock_does_not(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    assert "pick up Fountain" in out(rt, cid, "pickup fountain")
    out(rt, cid, "drop fountain")
    assert "pick up Fountain" in out(rt, cid, "pick up fountain")
    assert "command_alias_resolved" in events
    assert "pick up" not in out(rt, cid, "pick lock")


def test_glance_scan_search_listen_smell_are_safe(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    assert "Crossing Square" in out(rt, cid, "glance")
    assert "Crossing Square" in out(rt, cid, "scan")
    assert "You see nothing unusual." in out(rt, cid, "search room")
    assert "You do not hear anything unusual." in out(rt, cid, "listen")
    assert "You smell nothing unusual." in out(rt, cid, "smell")
    assert "environment_inspected" in events


def test_run_and_walk_move_like_directions(tmp_path):
    rt, cid, _ = make_runtime(tmp_path)
    moved = out(rt, cid, "run north")
    assert "You head north." in moved
    assert "Old Gate Road" in moved
    moved = out(rt, cid, "walk south")
    assert "You head south." in moved
    assert "Crossing Square" in moved


def test_dialogue_aliases_and_container_placeholders(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    # Move to a room with an NPC if necessary; Phase 3B population is runtime-owned.
    npcs = rt.find_entities(entity_type="npc")
    assert npcs
    char = rt.state_store.load_character(cid)
    rt.move_entity(npcs[0]["entity_id"], char.room_id)
    target = str(npcs[0]["name"]).split()[0].lower()
    for command in [f"talk {target}", f"greet {target}", f"hello {target}"]:
        assert "says" in out(rt, cid, command)
    assert "entity_interaction" in events
    assert "cannot open" in out(rt, cid, "open chest").lower()
    assert "cannot close" in out(rt, cid, "close chest").lower()
    assert "nothing unusual" in out(rt, cid, "look in chest").lower()
    assert "cannot put" in out(rt, cid, "put sword chest").lower()
    assert "container_interaction" in events
