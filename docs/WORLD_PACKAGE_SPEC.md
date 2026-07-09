# Smart MUD World Package Specification

Smart MUD worlds are installable data packages under `worlds/<world_id>/`. The engine loads packages; it does not contain world lore, races, classes, NPCs, items, quests, rooms, spells, factions, or genre assumptions.

## Required runtime package content

Every package must contain `manifest.json` and these runtime gameplay/content directories:

- `rules/`
- `areas/`
- `rooms/`
- `zones/`
- `npcs/`
- `items/`
- `quests/`
- `shops/`
- `trainers/`
- `classes/`
- `races/`
- `skills/`
- `spells/`
- `abilities/`
- `factions/`
- `lore/`
- `dialogue/`
- `intelligence/`
- `colors/`

Missing runtime gameplay/content folders are fatal validation errors.

## Auto-created Builder workspace

Builder workspace directories are runtime-prepared infrastructure, not gameplay assets and not fatal install requirements. Startup and registry validation create these folders when missing:

- `builder/`
- `builder/audit/`
- `builder/history/`
- `builder/snapshots/`
- `builder/imports/`
- `builder/exports/`
- `builder/templates/`

## Manifest authority

The manifest is the authority for loading a world. Required fields are: `world_id`, `display_name`, `author`, `description`, `version`, `engine_version_required`, `minimum_engine_version`, `maximum_engine_version`, `dependencies`, `required_plugins`, `optional_plugins`, `world_type`, `default_starting_area`, `default_starting_room`, `supported_languages`, `supported_character_slots`, `builder`, `load_priority`, and `package_guid`.

`world_type` is descriptive metadata only. The engine never branches by genre.

## Validation

Before loading, Smart MUD refuses invalid packages with descriptive errors. Validation checks required runtime folders, manifest fields, duplicate package IDs, exits to valid rooms, NPC room references, item template references, quest NPC references, trainer class references, spell schools, class abilities, and race records. Builder workspace folders are prepared automatically and are never fatal validation errors.

## Phase 4A Builder Foundation

Smart MUD supports an in-game Builder foundation for authorized `builder`, `admin`, and `owner` roles. Builder commands are registered in the command registry and are hidden from normal players. Draft edits are persisted under `worlds/<world_id>/builder/` rather than being written directly to live world package files.

The Builder workspace uses `audit`, `history`, `snapshots`, `exports`, `imports`, and `templates` folders. Room, exit, feature, item template, entity template, and spawn edits go through Builder services so runtime validation and permission checks remain authoritative. `builder validate` checks draft consistency; `builder save` creates a safe export; `builder reload` reloads drafts where safe; `builder snapshot` captures the current draft state; and `builder history` reads audit records.

Future work may add a richer semantic web Builder UI and AI-assisted Builder tools, but Phase 4A intentionally does not add AI Builder, combat, quests, shops, or spellcasting.

## Phase 4B Builder runtime navigation note

Builder-created draft rooms now participate in a runtime world graph overlay for builder/admin/owner users with Builder Mode enabled. Runtime lookup merges live world package rooms with BuilderWorkspace drafts, with drafts overriding live rooms for builders only. `goto`, `look`, `rooms`/`rlist`, `rfind`/`rsearch`, `dig`, `link`, `unlink`, and `map`/`rmap` use this merged lookup and the canonical room renderer. Normal players do not see builder-only metadata or draft-only rooms. Draft saves export BuilderWorkspace content; promotion to live packages is not implemented yet. See `docs/BUILDER_NAVIGATION.md`.

## Smart MUD Phase 4C Builder Workflow 2.0

Phase 4C standardizes Builder Mode around a canonical room graph: live world rooms are merged with draft rooms for authorized builders, while normal players continue to see only live package content. Room rendering, look/exits, movement, goto, dig, link/unlink, map/rmap, and builder validation are required to use that shared graph so displayed exits match traversable exits.

Builder commands maintain an explicit editing context and print a `Currently editing:` block for room-editing workflows. `rname` and `rdesc` edit only the selected room target. Room ids must be safe lowercase underscore ids; room names may contain spaces. The primary workflow is `dig <direction> <room_id> ["Room Name"] [--one-way]`, with self-loops blocked unless explicitly allowed. Known limits: visual Builder UI, AI Builder, combat, shops, quests, and spellcasting remain future work and are not introduced by this phase.

## Builder draft room normalization

Builder draft rooms exported from `builder/exports/` are normalized workspace records. Each draft room includes `id`, `name`, `description`, `world_id`, `area_id`, `zone_id`, `exits`, `features`, `flags`, `tags`, and `plugin_data`. Missing fields in old partial drafts are filled with safe defaults before save/export. This normalization applies to builder drafts only; live package files are not changed by builder save/export.
