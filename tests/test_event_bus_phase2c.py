from __future__ import annotations

from pathlib import Path

import pytest

from app.web import WebRuntime
from smart_mud.event_bus import EventBus
from smart_mud.transport import TransportMessage, WebTransportAdapter


def test_event_bus_subscribe_publish_and_introspection() -> None:
    bus = EventBus()
    calls: list[tuple[str, dict]] = []

    def handler(event):
        event.payload["mutated"] = True
        calls.append((event.event_name, event.payload))

    sub = bus.subscribe("command_received", handler, source="test")
    bus.subscribe("command_received", handler, source="test")
    result = bus.publish("command_received", {"raw_input": "look"}, source_system="test")
    assert result.subscriber_count == 1
    assert result.successful_handlers == ["handler"]
    assert not result.failed_handlers
    assert calls == [("command_received", {"raw_input": "look", "mutated": True})]
    assert result.event.payload == {"raw_input": "look"}
    assert result.event.event_id
    assert result.event.timestamp
    assert bus.list_registered_events() == ["command_received"]
    assert bus.list_subscribers("command_received") == [sub]
    assert bus.event_history(1)[0].event_id == result.event.event_id
    assert bus.unsubscribe("command_received", handler) is True
    assert bus.publish("command_received").subscriber_count == 0


def test_event_bus_deterministic_order_priority_source_creation() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe("runtime_ready", lambda event: calls.append("z"), priority=20, source="z")
    bus.subscribe("runtime_ready", lambda event: calls.append("b2"), priority=10, source="b")
    bus.subscribe("runtime_ready", lambda event: calls.append("a"), priority=10, source="a")
    bus.subscribe("runtime_ready", lambda event: calls.append("b1"), priority=10, source="b")
    bus.publish("runtime_ready")
    assert calls == ["a", "b2", "b1", "z"]


def test_event_bus_failures_strict_and_after_commit() -> None:
    bus = EventBus()
    seen: list[str] = []

    def fail(event):
        raise RuntimeError("boom")

    bus.subscribe("room_rendered", fail)
    bus.subscribe("room_rendered", lambda event: seen.append("after"))
    result = bus.publish("room_rendered")
    assert result.failed_handlers == ["fail"]
    assert seen == ["after"]
    assert bus.error_history()

    strict = EventBus(strict=True)
    strict.subscribe("room_rendered", fail)
    with pytest.raises(RuntimeError):
        strict.publish("room_rendered")
    assert strict.error_history()

    queued: list[str] = []
    bus.subscribe("a_event", lambda event: queued.append("a"))
    bus.subscribe("b_event", lambda event: queued.append("b"))
    bus.publish_after_commit("a_event")
    bus.publish_after_commit("b_event")
    assert queued == []
    bus.flush_after_commit()
    assert queued == ["a", "b"]
    bus.publish_after_commit("a_event")
    bus.clear_after_commit()
    bus.flush_after_commit()
    assert queued == ["a", "b"]


def _entered_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    runtime.select_world("shattered_realms")
    created = runtime.create_character({"name": "Phase Tester", "race_id": "human", "class_id": "mage"})
    character_id = created["character"]["character_id"]
    runtime.enter_world(character_id)
    return runtime, character_id


def test_runtime_and_transport_share_event_bus_and_publish_command_events(tmp_path: Path, monkeypatch) -> None:
    runtime, character_id = _entered_runtime(tmp_path, monkeypatch)
    assert runtime.event_bus is runtime.mud_runtime.event_bus
    web = WebTransportAdapter(runtime.mud_runtime)
    assert web.event_bus is runtime.event_bus
    session = web.create_session("web-test")
    session.character_id = character_id

    seen: list[str] = []
    for name in [
        "transport_message_received",
        "command_received",
        "command_resolved",
        "command_executed",
        "room_rendered",
        "prompt_rendered",
        "transport_response_sent",
    ]:
        runtime.event_bus.subscribe(name, lambda event, name=name: seen.append(name))

    web.handle_message(TransportMessage(session, "l"))
    assert "transport_message_received" in seen
    assert "command_received" in seen
    assert "command_resolved" in seen
    assert "command_executed" in seen
    assert "room_rendered" in seen
    assert "prompt_rendered" in seen
    assert "transport_response_sent" in seen

    seen.clear()
    runtime.event_bus.subscribe("command_unknown", lambda event: seen.append("command_unknown"))
    web.handle_message(TransportMessage(session, "frobnicate"))
    assert "command_unknown" in seen


def test_runtime_movement_events_and_aff_alias(tmp_path: Path, monkeypatch) -> None:
    runtime, character_id = _entered_runtime(tmp_path, monkeypatch)
    seen: list[str] = []
    for name in ["movement_succeeded", "movement_failed"]:
        runtime.event_bus.subscribe(name, lambda event, name=name: seen.append(name))
    assert "You have no active affects." in runtime.handle_input("aff", command_echo=False)["output_text"]
    runtime.handle_input("n", command_echo=False)
    runtime.handle_input("u", command_echo=False)
    assert "movement_succeeded" in seen
    assert "movement_failed" in seen
