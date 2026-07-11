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

### Semantic rendering settings pipeline

The web runtime resolves MUD colors through `selected_preset`, `custom_roles`, and `effective_roles`. Web clients consume `effective_roles`, apply `--mud-color-*` CSS variables, and render backend `<span role="...">` semantic output. Telnet clients remain isolated from this CSS contract and receive plain or ANSI output only. See `docs/SEMANTIC_RENDERING.md`.

## Phase 2F display pipeline

Room output is now treated as a single classic-MUD render block. Runtime state is still authoritative in `MudRuntime`; command execution returns command text separately from the current room view, and transports render that shared logical layout for their target format.

Canonical room display order is: room title, blank line, description paragraphs, blank line, players, NPCs, mobs, objects, blank line, then exactly one exits line. Exits are always last. Player-facing output hides runtime room ids; ids are reserved for future debug or Builder contexts only.

The web client preserves backend-authored line breaks and keeps the pinned prompt in `#mud-player-prompt`, separate from scrollback room output in `#mud-world-output`. Telnet receives the same logical layout as plain/ANSI text and never receives HTML.

## Phase 2G canonical room renderer

Smart MUD now has one canonical room rendering path: `engine.mud_displays.render_room()`. `MudRuntime.play_view()`, `look`, movement, login/world entry, and transport adapters consume that one render block rather than assembling room strings independently. Web output keeps the renderer's semantic spans and line breaks; telnet/plain output is derived from the same block with HTML stripped or converted to ANSI.

Any command or future subsystem that changes rooms must call the canonical renderer after changing authoritative runtime state. This includes recall, goto, summon, portal travel, Builder Mode goto, teleportation, future AI scene transitions, future combat fleeing, and future death/respawn. Those systems provide data; the renderer decides presentation.

Combat, NPC AI, Builder Mode, crafting, and world expansion remain intentionally unimplemented here. Their future integrations must not concatenate room text manually.

## Phase 3A Runtime Entity System

Smart MUD now includes a canonical runtime entity foundation documented in `docs/ENTITY_SYSTEM.md`. World package templates remain immutable, while SQLite `entity_instances` hold mutable room location, ownership, state, flags, timestamps, and plugin data. `MudRuntime` is the sole authority for spawning, moving, despawning, destroying, state updates, keyword resolution, and visibility queries.

Room rendering uses the entity visibility API so players, NPCs, mobs, and objects/items are displayed in the canonical order without exposing internal entity IDs to normal players. NPCs and mobs can be seeded idempotently from world package data and persist across restart. Corpse and container concepts are reserved for later combat and inventory/container work without replacing the Phase 2E item system. Combat, AI behavior, Builder Mode, shops, doors, pets, summons, and world expansion remain out of scope for Phase 3A.

## Phase 3B Living Entity Runtime

`MudRuntime` is the single authority for living entity lifecycle, spawning, movement, state, visibility, dialogue, behavior flags, and corpse foundation. Web and telnet transports continue to call runtime APIs and render returned semantic output only. World package records remain immutable data; SQLite entity instances hold runtime state and survive world reloads without duplicating room populations.


## Runtime Interaction Command Layer

All non-combat interaction commands execute through `MudRuntime`: transport input is parsed, aliases and filler words are normalized, targets are resolved with deterministic priority, runtime APIs publish EventBus events, renderers produce semantic HTML or plain/ANSI text, and transports return the response. Web and telnet transports must not implement gameplay command logic. See `docs/INTERACTION_COMMANDS.md`.

## Runtime interaction targets

The runtime owns core non-combat command behavior before any AI narration is considered. Targeted interactions resolve against equipped items, inventory, portable room items, room features, visible NPCs, visible mobs, and exits. Room features are data-driven fixed scenery with optional interaction metadata; they default to nonportable for common scenery such as fountains, gates, doors, altars, statues, campfires, stairs, and portals. Semantic web output and plain-text telnet output continue to flow through the existing render pipeline.

## Phase 3D command registry note

Smart MUD now tracks player, placeholder, future builder/admin, future combat, future magic, future economy, and future quest commands through a canonical command registry. The `commands` and `help` commands use registry metadata so classic MUD command coverage is deliberate without adding combat, AI, Builder Mode, shops, quests, spellcasting, or world expansion.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.

## Phase 4A Builder Foundation

Smart MUD supports an in-game Builder foundation for authorized `builder`, `admin`, and `owner` roles. Builder commands are registered in the command registry and are hidden from normal players. Draft edits are persisted under `worlds/<world_id>/builder/` rather than being written directly to live world package files.

The Builder workspace uses `audit`, `history`, `snapshots`, `exports`, `imports`, and `templates` folders. Room, exit, feature, item template, entity template, and spawn edits go through Builder services so runtime validation and permission checks remain authoritative. `builder validate` checks draft consistency; `builder save` creates a safe export; `builder reload` reloads drafts where safe; `builder snapshot` captures the current draft state; and `builder history` reads audit records.

Future work may add a richer semantic web Builder UI and AI-assisted Builder tools, but Phase 4A intentionally does not add AI Builder, combat, quests, shops, or spellcasting.

## Phase 4A owner bootstrap and role authority

Local development owner access is explicit and SQLite-backed. No startup path silently promotes all accounts or characters. Project owners can grant themselves persisted access with `python tools/bootstrap_owner.py --account local_dev --role owner` or `python tools/bootstrap_owner.py --character Kraevok --role owner`; both target `user_data/mud_state.db` unless `--db` is provided.

Runtime roles are `player`, `helper`, `builder`, `admin`, and `owner`. Account and character roles are stored separately; command execution uses the higher effective role, so an owner account can use Builder commands after restart even if the selected character was originally a player. Builder commands allow `builder`, `admin`, and `owner`; owner-only role management uses `grantrole` and records every change in the `role_grant_log` SQLite table with account, character, role, timestamp, source, and grantor metadata.

## Phase 4B Builder runtime navigation note

Builder-created draft rooms now participate in a runtime world graph overlay for builder/admin/owner users with Builder Mode enabled. Runtime lookup merges live world package rooms with BuilderWorkspace drafts, with drafts overriding live rooms for builders only. `goto`, `look`, `rooms`/`rlist`, `rfind`/`rsearch`, `dig`, `link`, `unlink`, and `map`/`rmap` use this merged lookup and the canonical room renderer. Normal players do not see builder-only metadata or draft-only rooms. Draft saves export BuilderWorkspace content; promotion to live packages is not implemented yet. See `docs/BUILDER_NAVIGATION.md`.

## Smart MUD Phase 4C Builder Workflow 2.0

Phase 4C standardizes Builder Mode around a canonical room graph: live world rooms are merged with draft rooms for authorized builders, while normal players continue to see only live package content. Room rendering, look/exits, movement, goto, dig, link/unlink, map/rmap, and builder validation are required to use that shared graph so displayed exits match traversable exits.

Builder commands maintain an explicit editing context and print a `Currently editing:` block for room-editing workflows. `rname` and `rdesc` edit only the selected room target. Room ids must be safe lowercase underscore ids; room names may contain spaces. The primary workflow is `dig <direction> <room_id> ["Room Name"] [--one-way]`, with self-loops blocked unless explicitly allowed. Known limits: visual Builder UI, AI Builder, combat, shops, quests, and spellcasting remain future work and are not introduced by this phase.

## Phase 4C Hotfix 2 Builder integrity architecture

BuilderWorkspace normalizes draft room records as workspace data is loaded and before drafts are saved or exported. Normalization is scoped to `worlds/<world_id>/builder/` and does not mutate live package room files. The command layer renders a single canonical Builder Status block and publishes builder status, edit-target, alias, normalization, validation warning, and validation error events for audit-friendly workflows.


## Builder Workflow 3.0 Architecture

The Builder workspace remains draft-first and runtime-safe. Builder context tracks current location plus active room/object/feature/exit targets, with a canonical HUD renderer used by edit, save, validate, export, reload, and target-changing flows. Room ID rename is intentionally not implemented in this phase, but validation and documentation now treat exits, builder references, history, draft references, and reload target restoration as the future migration surface.

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


## Phase 4G World Data Architecture

`WORLD_DATA_SPECIFICATION.md` is the canonical world data reference. The engine owns rules and validation, world packages own content, Builder drafts are editable overlays, imports apply to drafts first, and Builder does not mutate live package files. The architecture keeps area/zone/vnum organization while reserving optional future collections and a generic location hierarchy.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.


## Runtime entity source architecture

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B deterministic simulation

The living-world service advances world time, evaluates schedules, decays needs, selects deterministic goals, moves entities through bounded pathfinding, and exposes context without AI calls or daemon threads.

## Phase 6C ability integration

The canonical AbilityExecutionService extends this system without replacing it. Ability damage is handed to CombatEngine, healing uses Actor resource APIs and HealingEvent records, effects are stored as canonical actor effect instances, costs use Actor resources, definitions and loadouts are world/Builder data, and future AI must select abilities through runtime authority.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7A canonical rewards

All future reward sources should call `RewardService`: source validation, deterministic resolution, packet persistence, destination resolution, delivery, EventBus publication, and audit/history rows happen in one canonical pipeline. Combat, lifecycle, quests, harvesting, containers, and admin grants must not create separate reward implementations.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.

## Phase 7C crafting integration

Phase 7C adds `engine.crafting.CraftingService` as the single canonical crafting and production service. Recipes are Builder/world-package data; exact runtime item instances are selected and reserved; jobs persist in SQLite and advance by world time; costs use EconomyService; outputs use RewardService; profession rewards use canonical profession/progression state; and crafted item instances retain quality and provenance without mutating item templates. Salvaging and refining are normal recipe types, while quests, final trainers, autonomous AI production, random affixes, auction houses, and final enchantment remain outside this phase.


## Phase 8A Quest Integration

Phase 8A introduces `engine.quests.QuestService`, `QuestEventRouter`, `ConversationService`, and `WorldStateService` as the canonical quest and authored narrative-state foundation. Quests are Builder/world-package data, consume canonical EventBus-style events idempotently, branch deterministically, persist runtime state in SQLite, and hand rewards to RewardService instead of mutating items, XP, currencies, abilities, progression, Actor stats, or world records directly. Future AI may propose text or actions, but QuestService validates all outcomes; unrestricted scripts remain forbidden.

## Phase 8B Organization Integration

Phase 8B adds the canonical `OrganizationService` for parties, guilds, clans, NPC organizations, roles, permissions, invitations, applications, shared quest context, group combat attribution, and organization audit history. These systems provide context only and call existing canonical services for combat, quests, rewards, economy, progression, crafting, and world state.


## Phase 8C faction integration note

Phase 8C adds `FactionService` as the canonical owner of faction reputation, standing, diplomacy interpretation, access decisions, faction reward eligibility, and reputation history. Factions link to `OrganizationService` identities; organization membership, roles, permissions, group combat attribution, quests, rewards, economy, combat, and world state remain owned by their existing canonical services. Subsystems must call `FactionService` rather than mutating faction reputation directly. Faction warfare, laws, territory conquest, elections, autonomous politics, and PvP faction rules remain outside this foundation.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.

## Phase 9B Achievement Integration

Phase 9B routes canonical subsystem events into `engine.achievements.AchievementService`. The achievement service owns achievement/title/accolade/collection runtime state, consumes EventBus events idempotently, and delegates reward delivery to `RewardService` instead of mutating XP, currency, items, abilities, faction reputation, organization roles, quest state, or Actor statistics directly.


## Phase 10A Written Content Integration

Written communication and readable content now route through `engine.written_content.WrittenContentService`. The canonical model is document instance -> immutable content version -> owner/placement/access -> delivery or publication -> read state -> audit. Integrations should call the service instead of writing mail, board, book, note, journal, or sign rows directly. Postage and service fees are quoted/settled through `EconomyService`; organization and faction decisions remain delegated to their canonical services; quest and achievement progress consumes written-content events.

Builder/world packages may include written document, content, access, retention, render, sanitization, mail service, board, posting, moderation, readable item, book, and journal profile collections. External messaging, unrestricted markup, executable links, arbitrary file attachments, AI-generated authoritative mail, and cross-server messaging remain forbidden.

## Phase 10B Property Integration

Smart MUD now includes the canonical `PropertyService` (`engine.property`) for Builder-authored property definitions, SQLite property instances, leases, access grants, property storage containers, actor home locations, and immutable property audit events. Related systems should integrate by service boundary: EconomyService for money, OrganizationService/FactionService for membership and reputation checks, WrittenContentService for notices, Quest/Achievement systems via property events, and canonical item instances for storage.


## Phase 11B Perception Integration

Phase 11B adds `engine.perception.PerceptionService` as the single sensory boundary for stealth, concealment, search, tracking, scent, sound, trails, and observer knowledge. It queries canonical services, especially `EnvironmentService`, and stores restart-safe sensory state in SQLite.

## Phase 11C1 Gathering Foundation Integration

Phase 11C1 introduces `engine.gathering.GatheringService` as the single canonical foundation for resource definitions, node definitions, runtime node state, capacity/depletion, world-time regeneration, requirements, tools, sessions, deterministic yields, quality, rare-yield hooks, diagnostics, and Builder collections. It is intentionally a reusable foundation: Phase 11C2 will add the full gameplay rollout for harvesting, mining, lumberjacking, fishing, skinning, scavenging, excavation, profession XP presentation, quest/achievement integration, and pilot content.
