# Smart MUD Event System (Phase 2C)

Smart MUD owns one in-process `EventBus` for runtime messaging. The web shell creates the bus during startup and passes it to `MudRuntime`; transports then read the same instance from the runtime. Future systems can subscribe to events without coupling directly to command execution, rendering, transport adapters, persistence, or plugin discovery.

## Core Types

`smart_mud/event_bus.py` defines:

- `EventBus` — deterministic pub/sub bus.
- `MudEvent` — immutable event envelope passed to subscribers.
- `EventSubscription` — registered handler metadata.
- `EventCategory` — stable category enum inferred from event-name prefixes.

Each `MudEvent` includes an id, UTC ISO timestamp, event name, category, source system, copied payload, standard runtime identifiers, command, transport metadata, and free-form metadata.

## Lifecycle

1. A runtime component calls `publish()` with an event name and small payload.
2. The bus creates a `MudEvent` and stores it in bounded history.
3. Subscribers run in deterministic order.
4. Each subscriber receives a deep-copied event payload so one handler cannot mutate the payload seen by later handlers.
5. `publish()` returns a summary containing subscriber count, successful handlers, failed handlers, and errors.

## Subscriber Ordering

Handlers run by:

1. Lower numeric priority first.
2. Source name alphabetically.
3. Subscription creation order.

Duplicate `(event_name, handler)` subscriptions are ignored.

## Error Handling and Strict Mode

By default, one failing subscriber does not crash the bus. Failures are recorded in the publish result, the event metadata, and internal error history.

`EventBus(strict=True)` records the failure and then raises the subscriber exception.

## After-Commit Queue

`publish_after_commit()` currently queues events only. `flush_after_commit()` publishes queued events in order. `clear_after_commit()` drops them. SQLite transaction helpers are not yet wired to this queue; future persistence work should publish reserved transaction events such as `transaction_committed` and `transaction_failed` when real transaction boundaries exist.

## Categories

Categories are inferred from event-name prefixes. Supported prefixes are:

`runtime`, `startup`, `shutdown`, `database`, `plugin`, `world`, `transport`, `session`, `account`, `character`, `command`, `room`, `movement`, `builder`, `render`, and `system`.

Unknown prefixes map to `system`.

## Runtime and Transport Integration

Current integration publishes startup, database, plugin discovery/resolution, world scan/load, runtime readiness, character lifecycle, command, movement, room render, prompt render, and web/telnet transport message events where those actions already exist.

Transports do not own separate buses. `RuntimeTransportAdapter` uses `mud_runtime.event_bus`, so web and telnet paths observe the same runtime stream.

## Plugin Relationship

The existing `PluginRegistry` and `HookRegistry` remain the compatibility and plugin-facing API. Phase 2C bridges important runtime moments into EventBus visibility without replacing plugin hooks or invoking plugin handlers twice. Future plugin APIs may subscribe directly to EventBus events, but existing hook names such as `world_loaded`, `character_creation`, and `player_login` remain legacy-compatible integration points.

## Future Use

The bus is intended to support future AI listeners, builder listeners, multiplayer replication, auditing, analytics, and persistence reactions. Those systems should subscribe to focused event names and avoid mutating authoritative runtime state unless they explicitly own that side effect.

## Phase 2D Account and Session Foundation

Smart MUD now includes a local account/session foundation. See `docs/ACCOUNT_AND_SESSION_MODEL.md` for the SQLite account model, shared web/telnet session lifecycle, account-owned character creation/select/entry rules, role hierarchy, permission helper philosophy, orphan character migration behavior, and account/session/character EventBus events.

## Phase 2E Item Events

The item system publishes deterministic EventBus events from the runtime item pipeline. Core events include `item_spawned`, `item_destroyed`, `item_picked_up`, `item_dropped`, `item_equipped`, `item_removed`, `inventory_changed`, `equipment_changed`, and `room_inventory_changed`.

Item event payloads should include account, session, character, room, template, instance, and transport identifiers when they are available. Future plugins may observe predictable before/after stages, but they may not replace runtime ownership, write item ownership directly to SQLite, duplicate inventory logic, or bypass `transfer_item()`.

A pickup flow should publish in deterministic order: `before_item_pickup`, `item_picked_up`, `inventory_changed`, `room_inventory_changed`, `after_item_pickup`, `room_rendered`, `prompt_rendered`, and `transport_response_sent`.

### Phase 2E implementation note

Item events are emitted by `MudRuntime` from the canonical item pipeline. Pickup order is `before_item_pickup`, `item_picked_up`, `inventory_changed`, `room_inventory_changed`, and `after_item_pickup`; drop/equip/remove use analogous before/core/change/after ordering.
