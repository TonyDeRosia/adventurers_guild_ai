# Smart MUD Master Roadmap

## Phase 1: Runtime foundation
- Goal: Establish one Smart MUD startup lifecycle, registry, plugin scan, SQLite runtime, and project identity.
- Completed work: Smart MUD web/terminal startup exists; SQLite runtime schema initializes; canonical world registry selected; Builder workspace is auto-created; docs identify ownership.
- Remaining work: Continue retiring legacy campaign UI references outside normal startup.
- Dependencies: None.
- Acceptance criteria: Startup reaches Ready using Smart MUD systems only and loads `shattered_realms`.
- Suggested version target: `0.1.0`.

## Phase 2: SQLite persistent world foundation
- Goal: Persist authoritative mutable world/runtime state in SQLite.
- Completed work: Character, command history, scrollback, room/NPC runtime, quests, death log, and builder audit tables initialize.
- Remaining work: Normalize migrations, add world state mutation APIs, backup/export flows.
- Dependencies: Phase 1.
- Acceptance criteria: Runtime state survives restart without mutating package source files.
- Suggested version target: `0.2.0`.

## Phase 3: Account and character system
- Goal: Add accounts, authentication boundaries, character slots, and character lifecycle.
- Completed work: Basic character creation exists without accounts.
- Remaining work: Accounts, permissions, character selection, deletion, recovery, admin controls.
- Dependencies: Phase 2.
- Acceptance criteria: Multiple accounts can own isolated character sets safely.
- Suggested version target: `0.3.0`.

## Phase 4: Builder framework
- Goal: Provide safe Builder infrastructure and audited editing workflows.
- Completed work: Builder workspace folders and audit table exist.
- Remaining work: Builder permissions, editors, validation previews, import/export, snapshots.
- Dependencies: Phases 2-3.
- Acceptance criteria: Builders can edit draft content without corrupting runtime packages.
- Suggested version target: `0.4.0`.

## Phase 5: tbaMUD command and display parity
- Goal: Match expected MUD command surfaces and display conventions.
- Completed work: Initial command catalog and room/score rendering exist.
- Remaining work: Complete command parity audit, prompts, help, socials, admin displays.
- Dependencies: Phases 1-3.
- Acceptance criteria: Core navigation, communication, inventory, stats, help, and admin surfaces behave predictably.
- Suggested version target: `0.5.0`.

## Phase 3B: Living entity runtime
- Goal: Replace passive entities with runtime-owned living instances.
- Completed work: Templates normalize living metadata; SQLite instances persist state/location; runtime spawning, idempotent population, movement, state changes, dialogue, visibility, corpse creation, respawn, and lifecycle events exist.
- Remaining work: Combat, Builder Mode, AI decision making, quests, shops, spellcasting, and pathfinding are intentionally deferred.
- Dependencies: Phase 3A entity foundation.
- Acceptance criteria: Rooms populate from runtime state, visible entities render through `MudRuntime`, and web/telnet remain presentation-only.
- Suggested version target: `0.3.5`.

## Phase 6: Deterministic gameplay systems
- Goal: Implement deterministic combat, skills, spells, quests, shops, trainers, factions, and economy.
- Completed work: Package directories and some data structures exist.
- Remaining work: Actual gameplay mechanics and test coverage.
- Dependencies: Phases 2, 3, and 5.
- Acceptance criteria: Gameplay can run without AI and produces reproducible state transitions.
- Suggested version target: `0.6.0`.

## Phase 7: AI layer
- Goal: Add AI as an extension layer over deterministic state, not as source of truth.
- Completed work: Plugin registration has AI context provider slots.
- Remaining work: Context policies, safety boundaries, NPC narration hooks, deterministic fallbacks.
- Dependencies: Phase 6.
- Acceptance criteria: Disabling AI leaves gameplay fully playable.
- Suggested version target: `0.7.0`.

## Phase 8: Shattered Realms reference world
- Goal: Ship a complete reference world package.
- Completed work: `worlds/shattered_realms` package exists and loads.
- Remaining work: Expand content depth after deterministic systems are ready.
- Dependencies: Phases 5-7.
- Acceptance criteria: Reference world demonstrates major runtime features.
- Suggested version target: `0.8.0`.

## Phase 9: Multiplayer server maturity
- Goal: Harden concurrent sessions, networking, permissions, and operational behavior.
- Completed work: Session model exists in-process.
- Remaining work: Multi-user concurrency, locks, websockets/telnet strategy, observability, moderation.
- Dependencies: Phases 2-6.
- Acceptance criteria: Multiple players can connect and interact safely.
- Suggested version target: `0.9.0`.

## Phase 10: Packaging, releases, and polish
- Goal: Produce reliable releases with docs, installers, migration tools, and UX polish.
- Completed work: Launcher and packaging artifacts exist from earlier app history.
- Remaining work: Rebrand packaging, release automation, migration docs, final UI polish.
- Dependencies: Phases 1-9.
- Acceptance criteria: Users can install, run, update, and diagnose Smart MUD confidently.
- Suggested version target: `1.0.0`.

## Phase 2A: Transport abstraction and telnet foundation

Phase 2A introduces a shared transport abstraction so the web desktop client and telnet-style clients can communicate with the same `MudRuntime` command engine. The phase includes:

- shared transport session/message/response concepts;
- a web adapter preserving the existing Smart MUD desktop UI;
- a disabled-by-default telnet server foundation on configurable host/port, default port `4000`;
- output format separation for `web_html`, `ansi_text`, and `plain_text`;
- documentation for future websocket support.

This phase explicitly does not add full multiplayer, gameplay systems, account authentication, or AI behavior.

## Phase 2B: Basic MUD playability and room display parity

Phase 2B establishes basic playability before any Shattered Realms content expansion. It adds deterministic command alias parity for core information commands, movement directions, help surfaces, communication placeholders, and clean unknown-command responses.

The phase also replaces room-display stub text with classic MUD room output sourced from loaded world package data and SQLite-backed character location state. Movement checks package-defined exits, persists the new character room to SQLite, and renders the destination through the shared display pipeline used by web and telnet transports.

This phase explicitly does not add combat, AI behavior, Builder Mode, full accounts, or a complete Shattered Realms world build-out.

### Phase 2C Complete: Event Bus Architecture

Phase 2C adds the Smart MUD Event Bus as architecture-only infrastructure. Runtime, commands, movement, rendering, transports, persistence startup, plugin discovery/resolution, and world loading now publish deterministic runtime messages. This prepares future AI listeners, builder listeners, auditing, multiplayer replication, and persistence transaction integration without adding combat, AI behavior, full accounts, Builder Mode commands, or Shattered Realms expansion.

## Phase 2D Account and Session Foundation

Smart MUD now includes a local account/session foundation. See `docs/ACCOUNT_AND_SESSION_MODEL.md` for the SQLite account model, shared web/telnet session lifecycle, account-owned character creation/select/entry rules, role hierarchy, permission helper philosophy, orphan character migration behavior, and account/session/character EventBus events.

### Phase 2D hotfix: explicit account and character flow

Account and character endpoints now return predictable JSON. Successful responses include `ok: true` with account/session/character data where applicable. Expected user errors return `ok: false`, a human-readable `error`, a machine-readable `code`, and a suggested `state` without bubbling validation exceptions into HTTP 500 responses. Missing accounts use `account_not_found`, wrong passwords use `wrong_password`, duplicate accounts use `duplicate_account`, duplicate character names use `duplicate_character_name`, invalid character names use `invalid_character_name`, and ownership/session failures use clean 401/403/409-style responses.

The web client must use explicit character selection. Creating an account or character does not silently enter `Player` / `player_player`; after account login/create and world selection the client lists account-owned characters for that world and offers a Create Character action plus explicit Enter Character buttons. Legacy orphan characters may still be attached to the first local development account by migration for dev convenience, but they are presented in character select instead of auto-entered.

Developer fallback remains limited to account convenience: an empty login can create or reuse the local development account when no account exists. It must not auto-create or auto-enter a gameplay character unless a future explicit dev fallback setting is added.

## Phase 2E: Inventory, Equipment, Items, and Object Interaction

Phase 2E builds the canonical item foundation documented in `docs/ITEM_SYSTEM.md`. The phase replaces placeholder inventory and equipment output with persistent runtime item instances, room-owned objects, character-owned inventory, and durable equipment state.

The runtime remains the sole authority over item ownership. World packages define immutable item templates and optional starter item configuration; SQLite persists mutable item instances only; transports and plugins must request item operations through `MudRuntime` instead of updating ownership themselves.

Required work includes the canonical `MudRuntime` item API (`spawn_item()`, `transfer_item()`, `pickup_item()`, `drop_item()`, `equip_item()`, `unequip_item()`, keyword resolution, visible-room-item lookup, and equipment validation), deterministic EventBus item events, room rendering of real runtime objects, aliases for inventory/equipment/object commands, and focused tests for persistence, starter items, keyword matching, transfer behavior, web output, and telnet output.

Phase 2E explicitly does not implement combat, AI behavior, Builder Mode gameplay, crafting, banking, shops, quests, spells, skills, NPC AI, or playable world expansion beyond existing Shattered Realms data.

### Phase 2E implementation status

Phase 2E has an initial runtime implementation: persistent item instances, starter item spawning, runtime room object seeding, inventory/equipment/get/drop/wear/remove/wield/unwield/hold/look-object/examine-object command handling, centralized keyword matching, and deterministic item events. Deferred systems remain out of scope.

### Phase 2E semantic color hotfix

The Phase 2E display path now treats semantic rendering as the standard for web output and ANSI/plain rendering as the standard for telnet. Room, score, worth, equipment, inventory, prompt, command echo, and common informational output are expected to carry semantic roles rather than collapsing into one terminal-green style. This hotfix does not add combat, AI behavior, Builder Mode, or world expansion.

#### Phase 2E hotfix acceptance update

Semantic MUD color rendering is wired end-to-end through settings `effective_roles`, frontend `--mud-color-*` variables, role-based CSS selectors, and backend semantic spans. Changing a role color in Settings updates future web output without adding combat, AI behavior, Builder Mode, or world expansion.

### Phase 2F: Classic MUD display formatting

Phase 2F standardizes presentation without adding combat, AI behavior, Builder Mode, world expansion, or runtime authority changes. Room rendering now follows a traditional MUD layout: title, blank line, description, blank line, players, NPCs, mobs, objects, blank line, and one final `[ Exits: ... ]` line. Room ids are hidden from normal players, room names and descriptions render once, movement messages are separated from destination room renders, and `look` produces one room display.

Command echo and command output remain line-separated, semantic color roles remain intact, telnet output stays HTML-free, and the pinned Smart MUD prompt remains separate from room rendering.

### Phase 2G: Canonical room renderer and final display polish

Phase 2G centralizes Smart MUD room output in `engine.mud_displays.render_room()`. Login/world entry, `look`, movement, web, and telnet all use that canonical render block, preserving semantic roles and matching line spacing across HTML and plain text. The optional `You see:` section appears only when visible entities exist, orders players before NPCs before mobs before objects, and keeps room object display compact. Object descriptions are handled by targeted `look` / `examine` output instead of normal room rendering.

Future room-changing commands and systems—recall, goto, summon, portal, Builder goto, teleport, AI scene transitions, combat fleeing, and death—must update runtime state and then invoke the canonical renderer. They must not assemble room text themselves. The pinned Smart MUD prompt remains separate, and combat, NPC AI, Builder Mode, crafting, and world expansion remain out of scope.

## Phase 3A Runtime Entity System

Smart MUD now includes a canonical runtime entity foundation documented in `docs/ENTITY_SYSTEM.md`. World package templates remain immutable, while SQLite `entity_instances` hold mutable room location, ownership, state, flags, timestamps, and plugin data. `MudRuntime` is the sole authority for spawning, moving, despawning, destroying, state updates, keyword resolution, and visibility queries.

Room rendering uses the entity visibility API so players, NPCs, mobs, and objects/items are displayed in the canonical order without exposing internal entity IDs to normal players. NPCs and mobs can be seeded idempotently from world package data and persist across restart. Corpse and container concepts are reserved for later combat and inventory/container work without replacing the Phase 2E item system. Combat, AI behavior, Builder Mode, shops, doors, pets, summons, and world expansion remain out of scope for Phase 3A.


## Phase 3C - Core Interaction Command Layer

Phase 3C adds runtime-owned non-combat interaction commands, pickup aliases, run/walk helpers, entity dialogue aliases, container-safe placeholders, canonical room features, and EventBus interaction events. Combat, AI decision making, Builder Mode, and expanded Shattered Realms content remain out of scope. See `docs/INTERACTION_COMMANDS.md`.

### Phase 3C Hotfix: core command completion

The interaction layer now includes usable non-combat command fallbacks, targeted look/examine behavior, safe bulk inventory commands, and nonportable room-feature handling. Room features are inspectable without becoming inventory items, and command handling publishes targeted-look, feature-interaction, bulk-get/drop, and identify events for downstream systems.

## Phase 3D command registry note

Smart MUD now tracks player, placeholder, future builder/admin, future combat, future magic, future economy, and future quest commands through a canonical command registry. The `commands` and `help` commands use registry metadata so classic MUD command coverage is deliberate without adding combat, AI, Builder Mode, shops, quests, spellcasting, or world expansion.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.
