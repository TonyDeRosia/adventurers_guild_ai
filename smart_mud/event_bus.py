"""Deterministic runtime event bus for Smart MUD."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from itertools import count
from copy import deepcopy
from typing import Any, Callable
import uuid


class EventCategory(StrEnum):
    RUNTIME = "runtime"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    DATABASE = "database"
    PLUGIN = "plugin"
    WORLD = "world"
    TRANSPORT = "transport"
    SESSION = "session"
    ACCOUNT = "account"
    CHARACTER = "character"
    COMMAND = "command"
    ROOM = "room"
    MOVEMENT = "movement"
    BUILDER = "builder"
    RENDER = "render"
    SYSTEM = "system"


_PREFIX_CATEGORIES = {category.value: category for category in EventCategory}


@dataclass(frozen=True)
class MudEvent:
    event_id: str
    timestamp: str
    event_name: str
    category: EventCategory
    source_system: str = "unknown"
    payload: Any = field(default_factory=dict)
    world_id: str = ""
    account_id: str = ""
    character_id: str = ""
    player_id: str = ""
    session_id: str = ""
    transport_type: str = ""
    command: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventSubscription:
    event_name: str
    handler: Callable[[MudEvent], Any]
    priority: int = 100
    source: str = "unknown"
    order: int = 0


@dataclass
class EventPublishResult:
    event: MudEvent
    subscriber_count: int
    successful_handlers: list[str] = field(default_factory=list)
    failed_handlers: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class EventBus:
    """Small deterministic in-process event bus.

    PluginRegistry hooks remain the compatibility/plugin-facing API. This bus is
    the runtime messaging spine used by the engine, transports, persistence, and
    future systems that need to observe events without owning side effects.
    """

    def __init__(self, *, strict: bool = False, history_limit: int = 1000) -> None:
        self.strict = strict
        self.history_limit = history_limit
        self._subscriptions: dict[str, list[EventSubscription]] = {}
        self._order = count()
        self._history: list[MudEvent] = []
        self._errors: list[dict[str, str]] = []
        self._after_commit: list[tuple[str, Any, str, dict[str, Any]]] = []

    def subscribe(self, event_name: str, handler: Callable[[MudEvent], Any], priority: int = 100, source: str = "unknown") -> EventSubscription:
        subs = self._subscriptions.setdefault(event_name, [])
        for sub in subs:
            if sub.handler is handler:
                return sub
        sub = EventSubscription(event_name=event_name, handler=handler, priority=priority, source=source, order=next(self._order))
        subs.append(sub)
        subs.sort(key=lambda item: (item.priority, item.source, item.order))
        return sub

    def unsubscribe(self, event_name: str, handler: Callable[[MudEvent], Any]) -> bool:
        subs = self._subscriptions.get(event_name, [])
        kept = [sub for sub in subs if sub.handler is not handler]
        self._subscriptions[event_name] = kept
        return len(kept) != len(subs)

    def publish(self, event_name: str, payload: Any = None, source_system: str = "unknown", **context: Any) -> EventPublishResult:
        event = self._make_event(event_name, payload, source_system, context)
        self._history.append(event)
        if len(self._history) > self.history_limit:
            self._history = self._history[-self.history_limit:]
        subs = list(self._subscriptions.get(event_name, []))
        result = EventPublishResult(event=event, subscriber_count=len(subs))
        first_error: BaseException | None = None
        for sub in subs:
            handler_name = getattr(sub.handler, "__name__", repr(sub.handler))
            handler_event = self._copy_event_for_handler(event)
            try:
                sub.handler(handler_event)
                result.successful_handlers.append(handler_name)
            except Exception as exc:  # noqa: BLE001 - bus must isolate subscribers by default.
                error = {"event_name": event_name, "handler": handler_name, "source": sub.source, "error": str(exc)}
                self._errors.append(error)
                result.failed_handlers.append(handler_name)
                result.errors.append(error)
                event.metadata.setdefault("subscriber_errors", []).append(error)
                if first_error is None:
                    first_error = exc
                if self.strict:
                    break
        if self.strict and first_error is not None:
            raise first_error
        return result

    def publish_after_commit(self, event_name: str, payload: Any = None, source_system: str = "unknown", **context: Any) -> None:
        self._after_commit.append((event_name, deepcopy(payload) if payload is not None else {}, source_system, deepcopy(context)))

    def flush_after_commit(self) -> list[EventPublishResult]:
        queued = list(self._after_commit)
        self._after_commit.clear()
        return [self.publish(name, payload, source, **context) for name, payload, source, context in queued]

    def clear_after_commit(self) -> None:
        self._after_commit.clear()

    def list_registered_events(self) -> list[str]:
        return sorted(self._subscriptions.keys())

    def list_subscribers(self, event_name: str | None = None) -> dict[str, list[EventSubscription]] | list[EventSubscription]:
        if event_name is not None:
            return list(self._subscriptions.get(event_name, []))
        return {name: list(subs) for name, subs in sorted(self._subscriptions.items())}

    def event_history(self, limit: int = 100) -> list[MudEvent]:
        return list(self._history[-limit:])

    def error_history(self) -> list[dict[str, str]]:
        return list(self._errors)

    def _make_event(self, event_name: str, payload: Any, source_system: str, context: dict[str, Any]) -> MudEvent:
        metadata = deepcopy(context.pop("metadata", {}) or {})
        return MudEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_name=event_name,
            category=self._category_for(event_name),
            source_system=source_system,
            payload=deepcopy(payload) if payload is not None else {},
            world_id=str(context.pop("world_id", "") or ""),
            account_id=str(context.pop("account_id", "") or ""),
            character_id=str(context.pop("character_id", "") or ""),
            player_id=str(context.pop("player_id", "") or ""),
            session_id=str(context.pop("session_id", "") or ""),
            transport_type=str(context.pop("transport_type", "") or ""),
            command=str(context.pop("command", "") or ""),
            metadata={**metadata, **deepcopy(context)},
        )

    def _copy_event_for_handler(self, event: MudEvent) -> MudEvent:
        return MudEvent(**{**event.__dict__, "payload": deepcopy(event.payload), "metadata": deepcopy(event.metadata)})

    def _category_for(self, event_name: str) -> EventCategory:
        prefix = str(event_name).split("_", 1)[0].lower()
        return _PREFIX_CATEGORIES.get(prefix, EventCategory.SYSTEM)
