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

## Phase 4A Builder Foundation

Smart MUD supports an in-game Builder foundation for authorized `builder`, `admin`, and `owner` roles. Builder commands are registered in the command registry and are hidden from normal players. Draft edits are persisted under `worlds/<world_id>/builder/` rather than being written directly to live world package files.

The Builder workspace uses `audit`, `history`, `snapshots`, `exports`, `imports`, and `templates` folders. Room, exit, feature, item template, entity template, and spawn edits go through Builder services so runtime validation and permission checks remain authoritative. `builder validate` checks draft consistency; `builder save` creates a safe export; `builder reload` reloads drafts where safe; `builder snapshot` captures the current draft state; and `builder history` reads audit records.

Future work may add a richer semantic web Builder UI and AI-assisted Builder tools, but Phase 4A intentionally does not add AI Builder, combat, quests, shops, or spellcasting.

### Phase 4A hotfix: Owner bootstrap and Builder access setup

Completed: added an explicit local owner bootstrap helper, persisted account/character roles, in-game `whoami` role inspection, owner-only `grantrole`, and SQLite role grant logging. To make yourself owner locally, run one of:

```bash
python tools/bootstrap_owner.py --account local_dev --role owner
python tools/bootstrap_owner.py --character Kraevok --role owner
```

Normal players remain denied Builder access; `builder`, `admin`, and `owner` can use `builder on`; no account or character is silently promoted. AI Builder, combat, and UI redesign remain out of scope.

## Phase 4B Builder runtime navigation note

Builder-created draft rooms now participate in a runtime world graph overlay for builder/admin/owner users with Builder Mode enabled. Runtime lookup merges live world package rooms with BuilderWorkspace drafts, with drafts overriding live rooms for builders only. `goto`, `look`, `rooms`/`rlist`, `rfind`/`rsearch`, `dig`, `link`, `unlink`, and `map`/`rmap` use this merged lookup and the canonical room renderer. Normal players do not see builder-only metadata or draft-only rooms. Draft saves export BuilderWorkspace content; promotion to live packages is not implemented yet. See `docs/BUILDER_NAVIGATION.md`.

## Smart MUD Phase 4C Builder Workflow 2.0

Phase 4C standardizes Builder Mode around a canonical room graph: live world rooms are merged with draft rooms for authorized builders, while normal players continue to see only live package content. Room rendering, look/exits, movement, goto, dig, link/unlink, map/rmap, and builder validation are required to use that shared graph so displayed exits match traversable exits.

Builder commands maintain an explicit editing context and print a `Currently editing:` block for room-editing workflows. `rname` and `rdesc` edit only the selected room target. Room ids must be safe lowercase underscore ids; room names may contain spaces. The primary workflow is `dig <direction> <room_id> ["Room Name"] [--one-way]`, with self-loops blocked unless explicitly allowed. Known limits: visual Builder UI, AI Builder, combat, shops, quests, and spellcasting remain future work and are not introduced by this phase.

## Phase 4C Hotfix 2: Builder polish, aliases, and normalization

Completed: canonical Builder Status output, clearer location-versus-editing state, `redit` detail output, safe room-id and room-name checks, `desc` and save aliases, draft room normalization, and expanded validation categories. Known limits remain unchanged: full visual Builder UI, AI Builder, combat, quests, shops, and spellcasting are future phases.


## Phase 4D — Builder Workflow 3.0

Phase 4D polishes Builder Mode into a cohesive professional MUD-building workflow: canonical Builder HUD, status aliases, draft/live/all room listings, partial room search, multiline `rdesc`, safer `rname`, cleaner edit confirmations, exit inspection, standardized dig/save/reload language, stronger validation categories, and Builder-only history commands. It explicitly does not add gameplay, AI, combat, spells, quests, classes, economy, NPC behavior, web editors, or room ID rename execution.

## Phase 4E Area, Zone, and VNUM Organization

Builder Mode now supports draft areas and zones before room creation. Builders can use `acreate`/`aset current`, `zcreate`/`zset current`, `rcreate <vnum>`, and `dig <direction> <vnum>` to create rooms with canonical `<area_id>_<vnum>` IDs while preserving explicit `custom` legacy room IDs. Builder status shows world, area, zone, location, edit target, and dirty state. Builder export includes `areas`, `zones`, `rooms`, `items`, `entities`, and `spawns`; validation warns on legacy loose rooms and checks area/zone/vnum consistency. See `docs/AREA_ZONE_VNUM_SYSTEM.md`.

## Phase 4E organized room workflow hotfix

Builders can now finish the practical area/zone/vnum workflow without mutating live world package files. Draft exports remain under the builder workspace.

Canonical workflow:

```text
builder on
acreate test_area 100 110 "Test Area"
zcreate test_zone 100 110 "Test Zone"
rcreate 101
rname Test Room 101
rdesc This room belongs to the test zone.
rooms area test_area
rooms unassigned
rassign test_two area current zone current vnum 102
builder validate
builder save
builder export
```

Operational commands:

- `aset current <area_id>` selects the current area and shows the Builder HUD. If the selected area does not contain the current zone, the current zone is cleared.
- `zset current <zone_id>` selects the zone and also selects that zone's parent area.
- `rcreate <vnum>` creates an organized draft room with `area_id`, `zone_id`, and `vnum` from the current area and zone. It rejects duplicate vnums and out-of-range vnums with guidance.
- `dig <direction> <vnum> "Name"` creates an organized linked draft room using the current area and zone and reports the created room plus both link directions.
- `rooms unassigned` and `rooms legacy` list loose draft rooms where `area_id` and `zone_id` are blank and `vnum` is null. Legacy rooms are warnings, not validation failures.
- `rassign <here|room_id> area <area_id|current> zone <zone_id|current> vnum <number>` explicitly assigns a loose or existing room to an area, zone, and vnum.
- `rmove <here|room_id> [area <area_id>] zone <zone_id> vnum <number>` moves an assigned room to another zone/vnum. If the room was unassigned, it uses the assignment workflow and says so.
- Assigned rooms keep their existing room IDs in Phase 4E. The generated convention is `<area_id>_<vnum>`, and Builder warns when the current ID does not match it.
- `rrenameid <room_id> <new_room_id>` is registered as a placeholder only. Safe room ID migration is deferred because exits, spawns, builder history, and other references must be rewritten atomically.
- `builder export`, `build export`, `builder save`, `build save`, `bsave`, `wsave`, and `asave changed` route to the safe builder export/save behavior.

`builder status`, `astat`, `zstat`, and `rstat` should be used as guidance screens: they show current area, current zone, current room, edit target, room organization status, vnum, and the next suggested `rassign` command for legacy rooms.

`builder validate` groups Errors, Warnings, and Info. Organization warnings include legacy loose rooms, assigned room ID convention mismatches, rooms missing vnums, empty areas/zones, and range overlaps. Organization errors include missing referenced areas/zones, duplicate vnums within an area, out-of-range room vnums, and zone/area mismatches.

## Phase 4F Starter Migration and Builder Import

`builder migrate starter` snapshots the Builder workspace, reads the live Shattered Realms starter package, and writes normalized Builder drafts with `starter_guildlands`, starter zones, preserved room IDs, area/zone assignments, and vnums. Live world package files are not modified.

Builder JSON imports are staged from `worlds/<world_id>/builder/imports/` with `builder import list`, `builder import validate <file>`, `builder import preview <file>`, and `builder import apply <file> [--merge|--replace-drafts]`. The import/export bundle contains `areas`, `zones`, `rooms`, `features`, `items`, `entities`, and `spawns` so draft data can round-trip through `builder export` and import validation.

## Phase 4F Hotfix: committed organized starter drafts

Fresh downloads now include the organized Shattered Realms starter Builder drafts under `worlds/shattered_realms/builder/`. The live package files remain unchanged; the committed Builder drafts are the default editable organized starter layer that Builder Mode overlays at runtime.

Use `builder validate` to verify the committed starter draft layer. The starting room `guildhall_crossing_square` is assigned to `starter_guildlands`, zone `guildhall_crossing`, vnum `1000`, and should report `Status: organized` in `rstat`.

`builder migrate starter` remains available to reset or regenerate the starter drafts from the live Shattered Realms package. Regeneration should update the draft JSON files only; do not commit runtime audit, history, snapshot, export, local database, or user-data artifacts.

To exchange the organized starter layer, run `builder export`, then place the exported bundle in the Builder import folder and run `builder import validate <file>` before applying it.


## Phase 4G: World Data Specification v1.0

Before large-scale Shattered Realms expansion, Smart MUD freezes the data contract for world packages and Builder imports in `docs/WORLD_DATA_SPECIFICATION.md`. Phase 4G documents current area/zone/vnum drafts, import/export bundles, optional generic location hierarchy, profile libraries, plugin_data conventions, inheritance, validation, migration, backward compatibility, and tbaMUD design parity without adding combat, AI behavior, quests, shops, classes, skills, spells, or a visual Builder UI.

### Phase 4G Hotfix: Builder import templates and duplicate scenery rendering

Completed hotfix scope:

- Builder workspace setup auto-creates `imports/`, `templates/`, and `examples/`.
- Shattered Realms ships built-in import templates in `worlds/shattered_realms/builder/templates/`.
- In-game commands `builder template list`, `builder template show`, and `builder template copy` help builders create import files without manual folder/file setup.
- Import validation covers a valid area/zone/room template, an intentional duplicate-vnum failure example, and future-key warning behavior.
- Builder room rendering prefers draft features over duplicate nonportable live scenery while preserving portable runtime item instances.

No combat, AI, quests, shops, skills, classes, spells, or visual Builder UI were added by this hotfix.


## Phase 4H - Starter Guildlands Content Pack v1

Added a Builder-importable Starter Guildlands content pack with 44 draft rooms, room features, reusable features, starter-safe item templates, entity templates with future AI metadata, and spawn placeholders. The phase proves external JSON worldbuilding through Builder import/export without implementing combat, quests, shops, skills, spells, classes, visual Builder UI, AI behavior, or live package changes.

## Phase 4H localized Builder lists

Builder list commands are local by default: `alist` shows the current area, `zlist` shows the current area's zones, and `rlist`/`rooms` shows the current zone's rooms. Use explicit `all`, `area <area_id>`, `zone <zone_id>`, or VNUM ranges such as `1000-1029` to broaden or focus results. See `docs/BUILDER_LIST_COMMANDS.md`.

### Phase 4H Stability Hotfix

Builder tests now isolate mutable workspace operations with a temporary copied Shattered Realms package and temporary SQLite database, protecting committed starter drafts from test-order pollution. Item bulk commands now treat duplicate names as distinct instances: `get all`/`take all` collect every portable room item, skip NPCs and nonportable scenery, and `drop all` returns every eligible unequipped carried item while preserving equipped state and instance identity. Seeded room items remain persistent until a future explicit reset system is designed.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.


## Phase 5A hotfix status

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B completed foundation

Persistent living entity identity, schedules, needs, goals, memories, relationships, deterministic world time, and non-AI context contracts are established as the substrate for future controlled AI influence.

## Phase 5E status

The equipment/effect/stat-resolution foundation is present: canonical modifiers, SQLite effect instances, pilot slot/effect/resource/resistance/formula data, safe expressions, and focused tests. Combat execution remains explicitly out of scope.
