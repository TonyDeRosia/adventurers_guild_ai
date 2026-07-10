# Smart MUD Command Registry

Smart MUD owns command metadata in `engine.command_registry.CommandRegistry`. The registry is the canonical source for command names, aliases, categories, access constraints, implementation status, help text, and transport safety.

## Philosophy

Smart MUD is not a tbaMUD or CircleMUD clone. It is a modern runtime with web and telnet-safe command handling. Classic MUD coverage is still tracked deliberately so players can try familiar commands without receiving accidental `Unknown command` responses for planned systems.

## Metadata

Each command records: `command`, `aliases`, `category`, `minimum_position`, `minimum_role`, `status`, `handler`, `short_help`, `long_help`, `implemented`, `placeholder`, `future_phase`, `transport_safe`, `admin_only`, and `builder_only`.

## Categories and statuses

Categories include movement, informational, interaction, object, equipment, communication, social, character, magic, combat, group, economy, quest, clan, toggle, builder, admin, and system.

Statuses include implemented, placeholder, planned, intentionally_omitted, future_builder, future_admin, future_combat, future_magic, future_economy, and future_quest.

## Placeholders

A placeholder command is intentionally recognized and returns useful text without activating a future system. For example, mount commands explain mounts are not implemented yet, while combat commands remain tracked as future combat rather than implemented behavior.

## Commands and help

`commands` groups visible commands by registry category and hides admin/builder/future commands from normal players. `commands all` and `commands planned` may expose planned registry entries that are still safe to display. `help <command>` falls back to registry metadata when no full helpfile exists.

## Future upgrades

Future systems should upgrade a placeholder by changing its registry status and wiring its handler, preserving aliases and help text wherever possible.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.

## Phase 4A Builder Foundation

Smart MUD supports an in-game Builder foundation for authorized `builder`, `admin`, and `owner` roles. Builder commands are registered in the command registry and are hidden from normal players. Draft edits are persisted under `worlds/<world_id>/builder/` rather than being written directly to live world package files.

The Builder workspace uses `audit`, `history`, `snapshots`, `exports`, `imports`, and `templates` folders. Room, exit, feature, item template, entity template, and spawn edits go through Builder services so runtime validation and permission checks remain authoritative. `builder validate` checks draft consistency; `builder save` creates a safe export; `builder reload` reloads drafts where safe; `builder snapshot` captures the current draft state; and `builder history` reads audit records.

Future work may add a richer semantic web Builder UI and AI-assisted Builder tools, but Phase 4A intentionally does not add AI Builder, combat, quests, shops, or spellcasting.

## Phase 4B Builder runtime navigation note

Builder-created draft rooms now participate in a runtime world graph overlay for builder/admin/owner users with Builder Mode enabled. Runtime lookup merges live world package rooms with BuilderWorkspace drafts, with drafts overriding live rooms for builders only. `goto`, `look`, `rooms`/`rlist`, `rfind`/`rsearch`, `dig`, `link`, `unlink`, and `map`/`rmap` use this merged lookup and the canonical room renderer. Normal players do not see builder-only metadata or draft-only rooms. Draft saves export BuilderWorkspace content; promotion to live packages is not implemented yet. See `docs/BUILDER_NAVIGATION.md`.

## Smart MUD Phase 4C Builder Workflow 2.0

Phase 4C standardizes Builder Mode around a canonical room graph: live world rooms are merged with draft rooms for authorized builders, while normal players continue to see only live package content. Room rendering, look/exits, movement, goto, dig, link/unlink, map/rmap, and builder validation are required to use that shared graph so displayed exits match traversable exits.

Builder commands maintain an explicit editing context and print a `Currently editing:` block for room-editing workflows. `rname` and `rdesc` edit only the selected room target. Room ids must be safe lowercase underscore ids; room names may contain spaces. The primary workflow is `dig <direction> <room_id> ["Room Name"] [--one-way]`, with self-loops blocked unless explicitly allowed. Known limits: visual Builder UI, AI Builder, combat, shops, quests, and spellcasting remain future work and are not introduced by this phase.

## Phase 4C Hotfix 2 command registry notes

The text Builder polish pass keeps builder commands hidden from normal command lists while ensuring common aliases are not unknown. Registered/handled commands include `redit`, `rstat`, `rcreate`, `rname`, `rdesc`, `desc`, `btarget`, `rtarget`, `target`, `save`, `rsave`, `asave`, `bsave`, and `wsave`.

`desc` is intentionally a Builder Mode alias for `rdesc`, not a player look/examine command. Save aliases route to builder export only when Builder Mode is enabled; otherwise normal players receive autosave or Builder Mode-required messages.


## Phase 4D Builder Commands

Builder Workflow 3.0 registers `builder status`, `bstatus`, Builder-only `status`, `rooms [draft|live|all]`, `rfind <query>`, `redit next`, `redit previous`, `exits`, `examine exit <dir>`, `x exit <dir>`, `back`, and `forward`. `rdesc` without arguments enters the multiline description editor and uses `.end` / `.cancel` sentinel commands.

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

## Phase 4H localized Builder lists

Builder list commands are local by default: `alist` shows the current area, `zlist` shows the current area's zones, and `rlist`/`rooms` shows the current zone's rooms. Use explicit `all`, `area <area_id>`, `zone <zone_id>`, or VNUM ranges such as `1000-1029` to broaden or focus results. See `docs/BUILDER_LIST_COMMANDS.md`.

## Phase 4H Bulk Item Routing

`get all`, `take all`, `get everything`, and `take everything` share one bulk pickup implementation. `drop all` and `drop everything` share one bulk drop implementation. Bulk commands use runtime-owned item movement APIs and publish the normal per-item transfer events for each moved instance; bulk pickup also emits aggregate start/completed metadata for audit consumers.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.


## Living entity command resolution

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B commands

Added: `worldtime`, `simulation`, `etime`, `eprofile`, `estate`, `eactivity`, `eneeds`, `egoals`, `eschedule`, `erelationships`, `ememories`, `econtext`, `schedulelist`, `needlist`, `goallist`, `relationshiplist`, and `memorylist`.

## Phase 6C canonical ability commands

Phase 6C registers the canonical ability command surface: `abilities`, `skills`, `spells`, `ability <name>`, `use <ability> [target]`, `cast <ability> [target]`, `invoke`, `perform`, `cancel`, `cooldowns`, and safe `spellup cast`. Builder/Admin diagnostics and authoring include `abilitylist`, `abilitystat`, `abilitytrace`, `loadoutlist`, `loadoutstat`, `abilitygrant`, `abilityrevoke`, `actorabilities`, `abilitycooldowns`, and `abilitycasts`. Skills and spells intentionally share the same ability execution service.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7A reward command surface

Phase 7A reserves and documents reward, loot, treasure, corpse-loot, claim, and resource-node commands for the Smart MUD client: `rewardlist`, `rewardstat`, `rewardcreate`, `rewardentry`, `loottablelist`, `loottablepreview`, `treasurelist`, `deathlootlist`, `corpsedecaylist`, `nodelist`, `rewardresolve`, `rewarddeliver`, `rewardretry`, `rewardcancel`, `rewardpacket`, `rewardtrace`, `loottrace`, `corpsecontents`, `corpseloottrace`, `grantreward`, `claimlist`, `rewards`, and `claim`.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.
