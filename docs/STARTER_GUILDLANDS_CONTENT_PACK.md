# Starter Guildlands Content Pack v1

Phase 4H adds `starter_guildlands_content_pack_v1.json`, the first real external Builder import pack for Shattered Realms. It is authored as data only and imports into Builder drafts without changing live package files.

## What it adds

- 44 new `starter_guildlands_<vnum>` draft rooms spread across all ten Starter Guildlands zones.
- 44 local room features that can be looked at or examined.
- 10 reusable top-level feature records for future feature-library support.
- 10 starter-safe item template records.
- 12 entity template records with non-authoritative `plugin_data.ai_profile` metadata.
- 20 spawn placeholder records that reference entity templates and pack rooms.

The pack does not add combat, quests, shops, classes, skills, spells, visual Builder UI, AI behavior, or reset/spawn execution.

## Copy, validate, preview, and apply

Use Builder Mode commands:

```text
builder template list
builder template copy starter_guildlands_content_pack_v1.json copied_pack.json
builder import validate copied_pack.json
builder import preview copied_pack.json
builder import apply copied_pack.json
builder validate
```

The template lives at:

```text
worlds/shattered_realms/builder/templates/starter_guildlands_content_pack_v1.json
```

A copy-ready reference example lives at:

```text
worlds/shattered_realms/builder/examples/starter_guildlands_content_pack_v1.json
```

## Testing applied rooms

After applying into an isolated or development Builder workspace, inspect the draft room graph with Builder room commands and validate the workspace:

```text
builder validate
rstat starter_guildlands_1002
rstat starter_guildlands_1084
rstat starter_guildlands_1273
```

The rooms are intentionally draft records until a builder chooses to save/export/package them through the normal pipeline.

## Future AI metadata

Entity templates include `plugin_data.ai_profile` fields for personality, speech style, daily role, goals, fears, relationships, memory seed, and behavior notes. These fields prepare authored individuality for a later AI layer, but they are metadata only. They do not schedule NPCs, choose actions, mutate runtime state, or make AI authoritative.

## Spawn placeholders

The `spawns` collection connects entity templates to draft rooms with spawn vnums in the Starter Guildlands spawn range. Each record is marked as a placeholder because Smart MUD does not yet implement a reset or spawn execution system for this content pack.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.

## Phase 5B starter population

Blacksmith Harl, Training Master Borik, Apprentice Mage Lina, Healer Sella, and Tavern Keeper Jory include conservative profile and simulation metadata with valid work/home room references.
