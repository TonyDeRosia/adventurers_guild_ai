from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, TransportSession, WebTransportAdapter


def make_runtime(tmp_path):
    bus = EventBus()
    events = []
    for name in [
        "object_examined", "entity_examined", "feature_examined", "self_examined",
        "command_usage", "command_placeholder", "identify_requested", "read_requested",
        "use_requested",
    ]:
        bus.subscribe(name, lambda event, _events=events: _events.append(event.event_name), source=f"phase3e_{name}")
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=bus)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Threee")["character_id"]
    return rt, cid, events


def out(rt, cid, command):
    return rt.handle_input(cid, command)


def test_self_room_feature_direction_and_usage_semantics(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    self_view = out(rt, cid, "look self")
    assert "Phase Threee" in self_view["output"]
    assert "Current Room:" in self_view["output"]
    assert "{entity_title}" in self_view["semantic_output"]

    assert "Crossing Square" in out(rt, cid, "look room")["view"]["text"]

    feature = out(rt, cid, "look fountain")
    assert "weathered stone fountain" in feature["output"]
    assert "{feature}" in feature["semantic_output"]

    direction = out(rt, cid, "look north")
    assert "north" in direction["output"].lower()
    assert "north to" in direction["output"].lower() or "nothing unusual" in direction["output"].lower()

    usage = out(rt, cid, "read")
    assert "Read what?" in usage["output"]
    assert "{usage}" in usage["semantic_output"]
    assert "self_examined" in events
    assert "feature_examined" in events
    assert "command_usage" in events


def test_identify_read_use_events_and_placeholders(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    identified = out(rt, cid, "identify fountain")
    assert "Weight:" in identified["output"]
    assert "Required Level:" in identified["output"]
    assert "{object_title}" in identified["semantic_output"]

    assert "nothing readable" in out(rt, cid, "read fountain")["output"]
    assert "no obvious way" in out(rt, cid, "use fountain")["output"]
    assert {"identify_requested", "read_requested", "use_requested", "command_placeholder"}.issubset(set(events))


def test_entity_player_look_and_shared_web_telnet_runtime(tmp_path):
    rt, cid, events = make_runtime(tmp_path)
    other = rt.create_character(world_id="shattered_realms", name="Other Player")["character_id"]
    other_char = rt.state_store.load_character(other)
    char = rt.state_store.load_character(cid)
    other_char.room_id = char.room_id
    rt.state_store.save_character(other_char, "shattered_realms")

    player = out(rt, cid, "look other")
    assert "Other Player" in player["output"]
    assert "entity_examined" in events

    npcs = rt.find_entities(entity_type="npc")
    assert npcs
    rt.move_entity(npcs[0]["entity_id"], char.room_id)
    npc = out(rt, cid, f"look {npcs[0]['name']}")
    assert npcs[0]["name"] in npc["output"]

    web = WebTransportAdapter(rt)
    telnet = TelnetTransportAdapter(rt)
    web_session = TransportSession("w", "web", "", character_id=cid, world_id="shattered_realms")
    telnet_session = TransportSession("t", "telnet", "", character_id=cid, world_id="shattered_realms")
    assert "Fountain" in web.handle_message(TransportMessage(web_session, "look fountain")).output
    telnet_output = telnet.handle_message(TransportMessage(telnet_session, "look fountain")).output
    assert "Fountain" in telnet_output
    assert "<span" not in telnet_output
