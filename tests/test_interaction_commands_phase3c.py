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
        "target_looked", "feature_interaction_attempted", "feature_interaction_succeeded",
        "feature_interaction_failed", "bulk_get", "bulk_drop", "identify_attempted",
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


def test_room_features_are_inspectable_but_not_pickupable(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    assert "fountain for beginner Smart MUD play" in out(rt, cid, "look fountain")
    assert "old gate for beginner Smart MUD play" in out(rt, cid, "look gate")
    assert "fountain for beginner Smart MUD play" in out(rt, cid, "look at fountain")
    assert "fountain for beginner Smart MUD play" in out(rt, cid, "examine fountain")
    assert "You cannot take that." in out(rt, cid, "get fountain")
    assert "You aren't carrying that." in out(rt, cid, "drop fountain")
    assert "You cannot eat that." in out(rt, cid, "eat fountain")
    assert "You cannot drink from that." in out(rt, cid, "drink fountain")
    assert "target_looked" in events
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


def test_bulk_and_clean_fallback_commands(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    assert "There is nothing here you can take." in out(rt, cid, "get all")
    assert "You identify" in out(rt, cid, "identify fountain")
    assert "nothing readable" in out(rt, cid, "read fountain")
    assert "no obvious way" in out(rt, cid, "use fountain")
    for verb in ["push", "pull", "touch", "pray", "climb"]:
        assert "Unknown command" not in out(rt, cid, f"{verb} fountain")
    assert "identify_attempted" in events


def test_drop_all_drops_inventory_not_equipment(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    inv_before = rt.find_inventory_items(cid)
    eq_before = rt.find_equipped_items(cid)
    assert inv_before
    assert "You drop:" in out(rt, cid, "drop all")
    assert not rt.find_inventory_items(cid)
    assert len(rt.find_equipped_items(cid)) == len(eq_before)
    assert "bulk_drop" in events


def test_nonportable_feature_pickup_stops_after_failure(tmp_path):
    rt, cid, _ = make_runtime(tmp_path)
    msg = out(rt, cid, "get fountain")
    assert msg.strip() == "You cannot take that."
    assert "pick up" not in msg.lower()
    assert "Fountain" not in rt.handle_input(cid, "inventory")["output"]
