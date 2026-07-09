# Smart MUD Architecture

## Runtime lifecycle

Normal startup is `run.bat` -> `run.py` -> `app/web.py` -> `engine/mud_runtime.py`. Terminal mode enters through `app/main.py`, which constructs the same `WebRuntime` used by the web shell.

Startup reports these phases: loading configuration, opening SQLite, running migrations, discovering plugins, resolving plugin dependencies, scanning worlds, preparing Builder workspace, validating runtime packages, loading world assets, initializing runtime, and ready.

## Module ownership

- `run.py`: launcher, backend process readiness, desktop/web mode selection, terminal dispatch.
- `app/web.py`: single web startup lifecycle and API facade.
- `app/main.py`: terminal UI over the same runtime.
- `engine/mud_runtime.py`: live sessions, SQLite-backed character state, command execution, and active world loading.
- `smart_mud/world_registry.py`: canonical world package discovery, validation, Builder workspace preparation, and package loading.
- `engine/world_registry.py`: compatibility reexports only; do not add validation logic here.
- `engine/plugin_system.py`: plugin manifests, dependency resolution, registration metadata, and hooks.

## World registry ownership

`smart_mud/world_registry.py` owns validation logic. Runtime code must import `WorldRegistry` from `smart_mud.world_registry`. Legacy imports from `engine.world_registry` are allowed only because that module reexports the canonical implementation.

## SQLite ownership

`engine/mud_runtime.py` owns runtime SQLite schema creation and MUD state persistence. SQLite stores runtime state; world packages remain read-only content templates.

## Plugin ownership

`engine/plugin_system.py` discovers plugins from `plugins/`, validates plugin manifests, records registrations, and resolves required dependencies before a world is loaded.

## World package ownership

World packages under `worlds/` own gameplay content and reference data. Required runtime directories are documented in `docs/WORLD_PACKAGE_SPEC.md`. Missing runtime content is fatal.

## Builder workspace ownership

Builder workspace folders under `worlds/<world_id>/builder/` are infrastructure for future Builder tools. They are automatically created by the canonical world registry and must never block startup.

## Legacy systems excluded from startup

Normal Smart MUD startup must not initialize the Adventure Guild AI campaign runtime, legacy campaign save flow, image generation runtime, ComfyUI process ownership, campaign browser ownership, or old character-sheet campaign editor ownership. Legacy files may remain for history or compatibility tests, but they are not part of the startup path.

## Where future Codex prompts should modify systems

- World validation or Builder workspace behavior: `smart_mud/world_registry.py`.
- Runtime persistence or command session state: `engine/mud_runtime.py`.
- Startup logging or HTTP API: `app/web.py`.
- Launcher behavior: `run.py`.
- Plugin metadata or dependency behavior: `engine/plugin_system.py`.
- Package layout rules: `docs/WORLD_PACKAGE_SPEC.md`.

## Phase 2A transport architecture

Smart MUD separates engine concerns from client transports. `MudRuntime` remains the owner of command execution, SQLite-backed state, loaded world packages, plugin hooks, and rendering helpers. The transport layer sits between clients and the runtime.

```text
Engine Core: MudRuntime, command parser, SQLite, worlds, plugins, renderer
Transport Layer: web transport, telnet transport, future websocket transport
Clients: Smart MUD web desktop, browser, Mudlet/telnet clients
```

Transport adapters must not own game rules, world state, character state, inventory, combat, or AI behavior. They only own connection handling, input/output, session metadata, and format negotiation.

The built-in web desktop remains supported and continues to receive web-safe rendering. Telnet clients receive ANSI or plain text rather than HTML.

## Phase 2B playability boundary

Phase 2B keeps game logic centralized in `MudRuntime` and `MudCommandEngine`. Command aliases resolve to canonical deterministic handlers, while transport adapters continue to format runtime results for web HTML or ANSI/plain text without duplicating gameplay logic.

Room rendering now uses loaded package room data plus runtime character location state. Visible NPCs and objects are resolved from world package records when available, with safe ID fallbacks for incomplete data. Movement commands validate current-room exits, persist character location changes in SQLite, and render the new room through the same shared display builder.

Phase 2B is intentionally a playability bridge before world expansion: no combat loop, AI behavior, Builder Mode, or account system is introduced here.

## Phase 2C Event Bus

Smart MUD now includes a canonical deterministic EventBus in `smart_mud/event_bus.py`. `WebRuntime` creates the process runtime bus, passes it into `MudRuntime`, and web/telnet transport adapters use `mud_runtime.event_bus` rather than creating separate buses. Command, movement, render, transport, startup, database, world, and character lifecycle events are published as small structured payloads. The existing plugin registry remains the plugin-facing compatibility API; EventBus exposes the same runtime milestones to future listeners without replacing plugin discovery or hook behavior. See `docs/EVENT_SYSTEM.md` for lifecycle, ordering, strict mode, categories, and after-commit queue details.

## Phase 2D Account and Session Foundation

Smart MUD now includes a local account/session foundation. See `docs/ACCOUNT_AND_SESSION_MODEL.md` for the SQLite account model, shared web/telnet session lifecycle, account-owned character creation/select/entry rules, role hierarchy, permission helper philosophy, orphan character migration behavior, and account/session/character EventBus events.

## Phase 2E Item Runtime Authority

Phase 2E item ownership is centralized in `MudRuntime`. Runtime item templates are immutable world-package records, while item instances are mutable SQLite-backed runtime records with exactly one owner at a time. Web UI code, telnet transport code, plugins, Builder Mode, world packages, and SQLite helpers must not directly manipulate inventory or equipment state.

All object interactions must use the canonical runtime item API documented in `docs/ITEM_SYSTEM.md`. Ownership transfers flow through `transfer_item()`, whether initiated by `get`, `take`, `drop`, `wear`, `remove`, `wield`, future shops, future trading, future Builder Mode tools, or plugins. Equipment is an ownership state of the same item instance, not a duplicate inventory copy.

Room rendering must use runtime room inventory and render sections in this order: room title, room description, exits, visible NPCs, visible players, visible objects, and prompt. Equipped items and carried inventory items must never appear as room objects.

### Phase 2E runtime implementation note

`MudRuntime` now exposes the canonical item API and owns template normalization, SQLite-backed item instances, starter spawning, room seeding, inventory/equipment commands, keyword resolution, equipment conflict handling, and item EventBus publishing. Transports continue to call runtime command handling only.

## Phase 2E semantic rendering hotfix

Web MUD output uses semantic HTML spans as the presentation boundary. Runtime and display builders should emit roles such as `room_name`, `room_description`, `exit`, `object`, `player`, `command_echo`, `score_label`, `score_value`, `equipment_slot`, `equipment_item`, `gold`, `hp`, `mp`, and prompt-specific roles instead of embedding fixed color values in command text. The browser maps those roles through the active MUD color settings and CSS variables so changing the preset affects newly rendered output without changing game logic.

Telnet and plain transports remain HTML-safe by converting the same runtime output to ANSI/plain text. Web-only spans must not leak into telnet output, and telnet formatting must not become a separate gameplay rendering path.
