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
