# Smart MUD Builder Mode

Builder Mode is the command-first foundation for safe in-game world editing.

## Permissions

Only accounts/characters with the `builder`, `admin`, or `owner` role can run Builder commands. Normal `player` and `helper` roles cannot see or use Builder internals.

## Workspace

Drafts are stored under `worlds/<world_id>/builder/` with these folders:

- `audit`
- `history`
- `snapshots`
- `exports`
- `imports`
- `templates`

Live world files are not overwritten by normal edit commands. `builder save` writes a safe export into `builder/exports` for manual promotion.

## Commands

Mode and lifecycle commands:

- `builder`, `build`, `builder on`, `builder off`
- `builder validate`
- `builder save`
- `builder reload`
- `builder snapshot`
- `builder history`

Room commands:

- `redit`, `rstat`, `rcreate`, `rset`, `rdesc`, `rname`, `rexits`, `rfeature`, `rdelete`

Exit commands:

- `exedit`, `excreate`, `exset`, `exdelete`

Feature commands:

- `fedit`, `fcreate`, `fset`, `fdesc`, `fdelete`

Item template commands:

- `oedit`, `ocreate`, `oset`, `odesc`, `odelete`, `ostat`

Entity template commands:

- `medit`, `mcreate`, `mset`, `mdesc`, `mdelete`, `mstat`

Spawn commands:

- `spawnedit`, `spawncreate`, `spawnset`, `spawndelete`, `spawnstat`

World inspection commands:

- `zstat`, `astat`, `wstat`

## Draft vs. Live Data

Builder edits create draft JSON records. Movement, interaction, rendering, and spawning remain runtime-owned and must continue to use runtime validation. Builder features can be discovered by draft-aware look/examine-style flows without hardcoding individual feature IDs.

## Validation

`builder validate` reports duplicate/missing IDs where represented in draft data, missing names, broken room exits, missing spawn entity templates, invalid wear slots, invalid entity types, invalid JSON/plugin data, and world-package compliance issues that can be checked safely from drafts.

## Audit, History, and Snapshots

Every Builder change records timestamp, account ID, character ID, world ID, action, target type, target ID, before/after snapshots where feasible, and reason when supplied. Audit JSONL files are written under `builder/audit` and mirrored to `builder/history`. Snapshots copy current draft files to a timestamped folder under `builder/snapshots`.

## Web and Telnet

Builder commands use normal command input. Web output remains semantic text/HTML through existing rendering paths, and telnet output remains plain/ANSI. A full web Builder UI is future work.

## Explicit Non-Goals

Phase 4A does not implement AI Builder, combat, quests, shops, spellcasting, or a redesigned UI.

## Local owner bootstrap

No account or character is silently promoted. For local development, grant yourself access explicitly with the CLI helper after the local SQLite database has an account or character:

```bash
python tools/bootstrap_owner.py --account local_dev --role owner
```

or, for a specific character:

```bash
python tools/bootstrap_owner.py --character Kraevok --role owner
```

The helper writes to `user_data/mud_state.db` by default. Use `--db /path/to/mud_state.db` when testing against another local database.

Supported persisted roles are `player`, `helper`, `builder`, `admin`, and `owner`. Builder commands allow `builder`, `admin`, and `owner`; `owner` is the top role and has all Builder/admin permissions. Restarting the app preserves the account and character roles in SQLite.

## Role inspection and grants

Use `whoami` in game to inspect account role, character role, and effective role. `score` also shows account and character roles.

Owners may grant roles in game with:

```text
grantrole <character/account> <player|helper|builder|admin|owner>
```

Non-owners are denied. Each CLI or in-game role grant is logged to SQLite with account, character when available, role, timestamp, and source.

## Phase 4B Builder runtime navigation note

Builder-created draft rooms now participate in a runtime world graph overlay for builder/admin/owner users with Builder Mode enabled. Runtime lookup merges live world package rooms with BuilderWorkspace drafts, with drafts overriding live rooms for builders only. `goto`, `look`, `rooms`/`rlist`, `rfind`/`rsearch`, `dig`, `link`, `unlink`, and `map`/`rmap` use this merged lookup and the canonical room renderer. Normal players do not see builder-only metadata or draft-only rooms. Draft saves export BuilderWorkspace content; promotion to live packages is not implemented yet. See `docs/BUILDER_NAVIGATION.md`.

## Smart MUD Phase 4C Builder Workflow 2.0

Phase 4C standardizes Builder Mode around a canonical room graph: live world rooms are merged with draft rooms for authorized builders, while normal players continue to see only live package content. Room rendering, look/exits, movement, goto, dig, link/unlink, map/rmap, and builder validation are required to use that shared graph so displayed exits match traversable exits.

Builder commands maintain an explicit editing context and print a `Currently editing:` block for room-editing workflows. `rname` and `rdesc` edit only the selected room target. Room ids must be safe lowercase underscore ids; room names may contain spaces. The primary workflow is `dig <direction> <room_id> ["Room Name"] [--one-way]`, with self-loops blocked unless explicitly allowed. Known limits: visual Builder UI, AI Builder, combat, shops, quests, and spellcasting remain future work and are not introduced by this phase.

## Phase 4C Hotfix 2: Builder polish and draft integrity

Builder output now uses one canonical `Builder Status:` block. The block separates the builder's current location from the current edit target so moving around and editing a room are visibly different:

```text
Builder Status:
Location:
  Room: testies_2
  Name: Testies 2
  Source: draft

Currently editing:
  Type: room
  Room: testies_2
  Name: Testies 2
  Source: draft
  Dirty: yes
```

If no edit room is selected, the edit section reads `Currently editing: none`. Builder-only status is never shown to normal players.

Room ids are machine identifiers and must be lowercase snake_case with no spaces, uppercase letters, or punctuation other than underscores. Room names are human display names and may contain spaces and capitalization. `rname` rejects ID-looking names such as `testies_two` unless the builder explicitly uses `rname --force testies_two`; room-id migration is reserved for a future command.

`desc <text>` is a Builder Mode alias for `rdesc <text>`. Outside Builder Mode, it explains that Builder Mode must be enabled first. `rsave`, `asave`, `bsave`, `wsave`, and `save` are registered: Builder Mode routes them to the safe builder export path, while normal player `save` explains that characters autosave.

Draft room records are normalized on load and before save/export. Every draft room carries `id`, `name`, `description`, `world_id`, `area_id`, `zone_id`, `exits`, `features`, `flags`, `tags`, and `plugin_data`; valid existing data is preserved and live world files are not modified.

`builder validate` reports grouped Errors, Warnings, and Info for unsafe ids, partial drafts, missing or empty room fields, ID-looking names, broken exits, reverse-exit mismatches, self-loops, and draft rooms that shadow live rooms. Visual Builder UI, AI Builder, combat, quests, shops, and spellcasting remain future work.


## Phase 4D Builder Workflow 3.0

Builder Mode now uses a canonical HUD instead of ad-hoc status spam. `builder status`, `bstatus`, and Builder-only `status` print the HUD on demand, showing current location, current room edit target, source, and dirty state. Target-changing and editing commands refresh it; passive commands such as `look`, movement, inventory, and score should not spam it.

Room editing supports `redit <room_id>`, `redit next`, and `redit previous` for cycling draft rooms. `rname` rejects blank names and warns about duplicate display names or names that match IDs. `rdesc` with no text opens the multiline in-MUD description editor; finish with `.end` or cancel with `.cancel`.

`exits` lists the six primary exits in `Direction -> destination` form, and `examine exit <direction>` / `x exit <direction>` inspect destination, reverse direction, and validity.

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


## Phase 4G Builder Data Contract

Builder mode now targets the canonical world data contract in `WORLD_DATA_SPECIFICATION.md`. Drafts remain editable overlays under `worlds/<world_id>/builder/`; imports merge into drafts first; exports produce import-compatible bundles; live package files are not mutated by Builder.

## Phase 4G Hotfix: templates and Builder scenery rendering

Builder Mode includes template helper commands:

- `builder template list` shows templates available under `worlds/<world_id>/builder/templates/`.
- `builder template show <template_name>` prints the template path and a short summary.
- `builder template copy <template_name> <new_filename>` copies the template to `worlds/<world_id>/builder/imports/`.
- Add `--force` to overwrite an existing import file deliberately.

The Shattered Realms starter templates are committed under `worlds/shattered_realms/builder/templates/`, so fresh downloads have import examples without requiring players to create folders or blank JSON files manually. Builder workspace preparation also creates `imports/`, `templates/`, and `examples/` automatically.

When Builder Mode renders a live room that has a draft room overlay, draft features are authoritative for nonportable scenery. This prevents migrated draft features such as `Old Gate` and `Fountain` from being displayed once as draft features and again as live seeded room objects. The dedupe uses normalized ids and display names, while portable runtime item instances continue to render normally.


## Starter Guildlands Content Pack v1 workflow

Builders can copy the starter expansion template with `builder template copy starter_guildlands_content_pack_v1.json copied_pack.json`, then run `builder import validate`, `builder import preview`, `builder import apply`, and `builder validate`. The pack expands Builder drafts only and should be reviewed before any future save/export/package step.

## Phase 4H localized Builder lists

Builder list commands are local by default: `alist` shows the current area, `zlist` shows the current area's zones, and `rlist`/`rooms` shows the current zone's rooms. Use explicit `all`, `area <area_id>`, `zone <zone_id>`, or VNUM ranges such as `1000-1029` to broaden or focus results. See `docs/BUILDER_LIST_COMMANDS.md`.

## Builder Test Isolation

Mutating Builder tests use the shared `isolated_builder_world` pytest fixture instead of the repository `worlds/shattered_realms/builder/` directory. The fixture copies the Shattered Realms package into `tmp_path`, points `BuilderWorkspace`, `MudRuntime`, and the world registry at that copy, and uses a temporary SQLite database. This keeps starter drafts byte-for-byte stable and prevents import/export/history/snapshot noise from being committed accidentally. See `docs/BUILDER_TEST_ISOLATION.md`.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.


## Entity source diagnostics

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B diagnostics

Builder/admin diagnostics include `worldtime`, `simulation`, `eprofile`, `eschedule`, `eneeds`, `egoals`, `erelationships`, `ememories`, and `econtext`.

## Phase 6C ability integration

The canonical AbilityExecutionService extends this system without replacing it. Ability damage is handed to CombatEngine, healing uses Actor resource APIs and HealingEvent records, effects are stored as canonical actor effect instances, costs use Actor resources, definitions and loadouts are world/Builder data, and future AI must select abilities through runtime authority.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7A reward boundary

Rewards are issued through `engine.rewards.RewardService` and persisted as reward packets. This document's subsystem remains the authority for its own domain; reward delivery calls canonical APIs rather than editing subsystem tables directly.
