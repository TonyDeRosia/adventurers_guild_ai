# Smart MUD World Data Specification v1.0

Phase 4G freezes the canonical Smart MUD world data contract before large-scale Shattered Realms expansion. This document defines the JSON architecture used by engine-owned rules, content-owned world packages, editable Builder drafts, and import/export bundles.

## Ownership Principles

* **Engine owns rules.** Engine code validates schemas, references, vnum ranges, permissions, import safety, and runtime interpretation.
* **World packages own content.** A world package supplies areas, zones, rooms, templates, spawns, metadata, and optional future libraries.
* **Builder drafts are editable overlays.** Builder changes live under `worlds/<world_id>/builder/` and shadow or extend package content until reviewed.
* **Live package files are not mutated by Builder.** Builder import, edit, validate, snapshot, and export operations must preserve live files.
* **Imports apply to Builder drafts first.** Import bundles merge into draft collections; promotion to package content is a separate future publishing process.
* **Exports produce import-compatible bundles.** A Builder export can be copied back into `builder/imports/` and validated/imported again.

## World Package Layout

Current package content lives under `worlds/<world_id>/` and may include:

```text
world.json
areas/areas.json
zones/zones.json
rooms/rooms.json
items/items.json
builder/                  # editable overlay, not live content
```

Future v1-compatible packages may add optional library files without changing engine rules:

```text
locations.json
features.json
item_templates.json
entity_templates.json
spawns.json
factions.json
religions.json
cultures.json
terrain_profiles.json
ambient_profiles.json
weather_profiles.json
lighting_profiles.json
music_profiles.json
dialogue_packages.json
loot_tables.json
encounter_tables.json
quest_templates.json
shop_templates.json
```

## Builder Draft Layout

Builder drafts live at `worlds/<world_id>/builder/`:

```text
areas.json
zones.json
rooms.json
features.json
item_templates.json
entity_templates.json
spawns.json
audit/*.jsonl
history/*.jsonl
snapshots/<timestamp>/
exports/builder_export_<timestamp>.json
imports/*.json
templates/
```

The Builder draft collection names map to import/export top-level keys as follows: `areas`, `zones`, `rooms`, `features`, `items`, `entities`, and `spawns`.

## Import/Export Bundle Layout

The canonical v1 import/export bundle remains:

```json
{
  "areas": {},
  "zones": {},
  "rooms": {},
  "features": {},
  "items": {},
  "entities": {},
  "spawns": {}
}
```

Future optional top-level keys are reserved but not applied by current importers: `locations`, `factions`, `religions`, `cultures`, `terrain_profiles`, `ambient_profiles`, `weather_profiles`, `lighting_profiles`, `music_profiles`, `dialogue_packages`, `loot_tables`, `encounter_tables`, `quest_templates`, and `shop_templates`. Unknown future keys must not crash validation; current tools should warn: `Future top-level collection <name> is not applied by this version.`

## ID and Naming Conventions

* Collection IDs use lowercase snake_case: `^[a-z0-9]+(?:_[a-z0-9]+)*$`.
* IDs are stable machine identifiers; names are player-facing display text.
* `world_id`, `area_id`, `zone_id`, and template reference fields store IDs, not display names.
* Vnums are numeric builder organization aids scoped by area ranges.
* Room IDs may be hand-authored, but generated assigned-room convention is `<area_id>_<vnum>`.
* Tags are lowercase semantic labels; flags are engine/plugin-readable booleans or enum-like markers.

## Area Model

Areas are major content modules and own vnum ranges. Required current fields:

* `id`
* `name`
* `description`
* `world_id`
* `vnum_start`
* `vnum_end`
* `room_vnum_start`
* `room_vnum_end`
* `object_vnum_start`
* `object_vnum_end`
* `mob_vnum_start`
* `mob_vnum_end`
* `spawn_vnum_start`
* `spawn_vnum_end`
* `zone_ids`
* `flags`
* `tags`
* `plugin_data`
* `created_at`
* `updated_at`

Recommended stable `plugin_data` keys are optional and non-enforced: `world_context`, `gameplay`, `visuals`, `soundscape`, `smellscape`, `lore`, `secrets`, `future_hooks`, and `ai_context`.

```yaml
plugin_data:
  world_context:
    location_id: ironhaven
    biome: temperate_city
    law_level: high
  gameplay:
    recommended_level_min: 1
    recommended_level_max: 10
    pvp_allowed: false
  ai_context:
    tone: busy starter city
    common_activities:
      - registration
      - training
      - trade
```

## Zone Model

Zones are reset, encounter, spawn, and ambient containers inside an area. Required current fields:

* `id`
* `name`
* `description`
* `world_id`
* `area_id`
* `vnum_start`
* `vnum_end`
* `room_ids`
* `flags`
* `tags`
* `plugin_data`
* `created_at`
* `updated_at`

Recommended future zone fields or `plugin_data` keys: `zone_type`, `danger_level`, `population_level`, `guard_presence`, `crime_level`, `ambient_profile_id`, `weather_profile_id`, `music_profile_id`, `lighting_profile_id`, `terrain_profile_id`, `spawn_table_ids`, `encounter_table_ids`, `reset_rules`, and `script_hooks`.

Rooms inherit ambience, weather, terrain, law, danger, reset, and spawn context from zones unless they override it.

## Room Model

Rooms are small navigable locations. Current draft required fields:

* `id`
* `name`
* `description`
* `world_id`
* `area_id`
* `zone_id`
* `vnum`
* `exits`
* `features`
* `flags`
* `tags`
* `plugin_data`

Room philosophy: rooms should describe only what is unique; zones and profiles provide defaults. Future planned, non-required fields include `short_description`, `long_description`, `feature_refs`, `local_features`, `spawn_points`, `script_hooks`, `ambient_override`, `terrain_override`, `lighting_override`, and `weather_override`.

Rooms must not duplicate hardcoded `continent`, `kingdom`, or `region` fields. Broader context resolves through `room -> zone -> area -> location hierarchy`.

## Feature Library Model

`features.json` is the future reusable feature library. Feature fields:

* `id`
* `name`
* `keywords`
* `short_description`
* `long_description`
* `portable`
* `visible`
* `interactions`
* `flags`
* `tags`
* `plugin_data`

Current rooms may embed local features under `room.features`. Future preferred form may reference reusable features:

```yaml
feature_refs:
  - guild_fountain
  - notice_board
```

Local room features remain v1-compatible and must not be broken.

## Item, Entity, and Spawn Models

Item templates (`items` / `item_templates.json`) describe reusable object content. Current validation requires names and validates known wear slots when present. Recommended fields include `id`, `name`, `description`, `item_type`, `keywords`, `wear_slots`, `flags`, `tags`, and `plugin_data`.

Entity templates (`entities` / `entity_templates.json`) describe reusable mobiles/NPC-like records without implementing AI behavior. Recommended fields include `id`, `name`, `description`, `entity_type`, `flags`, `tags`, and `plugin_data`.

Spawns (`spawns.json`) connect entity templates to rooms/zones with future reset semantics. Recommended fields include `id`, `entity_template_id`, `room_id`, `zone_id`, `spawn_vnum`, `quantity`, `respawn_rule`, `flags`, `tags`, and `plugin_data`. Resets and spawns are zone responsibilities.

## Future System Models

The following are reserved extension collections, documented but not enforced: shop templates, quest templates, factions, religions, cultures, dialogue packages, loot tables, and encounter tables. They must remain data-only until their owning gameplay systems are implemented. Phase 4G does not implement shops, quests, combat, classes, skills, spells, or AI behavior.

## Generic Location Hierarchy

`locations.json` is optional v1 future-supported data. The engine core must not require fantasy-specific hierarchy names.

```text
World
  Location Node
    Location Node
      Area
        Zone
          Room
```

Location node fields:

* `id`
* `name`
* `description`
* `world_id`
* `parent_id`
* `location_type`
* `sort_order`
* `area_ids`
* `child_location_ids`
* `flags`
* `tags`
* `plugin_data`

`location_type` examples include `continent`, `kingdom`, `empire`, `nation`, `province`, `region`, `city`, `district`, `planet`, `star_system`, `sector`, `dimension`, `plane`, `station`, `ship`, `facility`, and `custom`. Current worlds are not required to provide `locations.json`.

## Profile Libraries

Optional future profile files are `terrain_profiles.json`, `ambient_profiles.json`, `weather_profiles.json`, `lighting_profiles.json`, and `music_profiles.json`. Profiles reduce duplication, allow rooms to inherit consistent environment behavior, and help renderers or AI-readable metadata understand area tone without repeating metadata in every room. Profiles do not own live state.

## `plugin_data` Conventions

`plugin_data` is a JSON object preserved on areas, zones, rooms, features, item templates, entity templates, and spawns. Engine validators may verify it is an object but should not discard unknown nested keys. Plugins must namespace game-specific data when possible and avoid storing authoritative engine state there.

## Inheritance Rules

Resolution order is: engine defaults -> world defaults -> location node context -> area `plugin_data.world_context` -> zone profile/plugin defaults -> room fields and overrides -> local feature/template metadata. Child values override parent defaults only for the specific key supplied. Missing future fields are not errors.

## Validation Rules

Current validation enforces or warns for safe IDs, required current fields, area/zone/room references, vnum ranges, duplicate vnums within an area, exit targets, feature names, item names/wear slots, entity names/types, and spawn template references. Validation must preserve `plugin_data`, permit local room features, avoid requiring location hierarchy files, and avoid requiring rooms to duplicate world context fields.

## Migration Rules

Migrations should be additive, timestamped when records support timestamps, and reversible through Builder snapshots. Legacy loose rooms may be normalized into Builder drafts with area, zone, and vnum assignments. Live package files are not rewritten by Builder migrations.

## Backward Compatibility Rules

Existing Builder drafts using `areas`, `zones`, `rooms`, `features`, `items`, `entities`, and `spawns` remain valid. Future optional collections may appear in bundles as ignored warnings. Current worlds without `locations.json` or profile libraries remain valid v1 worlds.

## tbaMUD Design Parity

Smart MUD preserves tbaMUD lessons: zone modularity, vnum organization, builder-first workflow, room/mobile/object/spawn separation, logical exit consistency, area balance planning, offline design before building, and resets/spawns as zone responsibilities. Smart MUD changes the storage and workflow: JSON instead of `.wld/.zon/.mob/.obj/.shp/.trg`, Builder drafts instead of direct live file editing, a generic location hierarchy instead of hardcoded fantasy geography, `plugin_data` extension points, import/export bundles, and AI-readable metadata without AI owning state.

## Phase 4G Hotfix Notes

Builder import templates live in `worlds/shattered_realms/builder/templates/`. They are normal JSON bundles using the v1.0 top-level collections (`areas`, `zones`, `rooms`, `features`, `items`, `entities`, and `spawns`) unless explicitly marked as a future-key or validation-failure example.

To create an import file, copy a template into `worlds/shattered_realms/builder/imports/` with `builder template copy area_zone_room_template.json my_area.json`, then run `builder import validate my_area.json` before previewing or applying it. Current engines preserve `plugin_data` on areas, zones, rooms, local room features, and global feature records. Future collections such as `locations`, `factions`, and `ambient_profiles` are warning-only in this phase.

Builder rendering now treats draft room features as the preferred Builder view of nonportable scenery for a room. If a draft room exists for a live room, nonportable live room scenery with the same normalized id or display name is not appended a second time. Portable item instances remain visible because they represent real runtime inventory/item state rather than static scenery.


## Phase 4H content-pack records

Starter Guildlands Content Pack v1 demonstrates external JSON authoring for the current Builder bundle keys: `areas`, `zones`, `rooms`, `features`, `items`, `entities`, and `spawns`. Entity `plugin_data.ai_profile` is explicitly non-authoritative metadata for future AI, and spawn records are placeholders until reset/spawn runtime systems exist.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.


## Legacy NPC declaration migration guidance

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B schedules and living seeds

Schedules live under `worlds/<world_id>/schedules/schedules.json`. Builder drafts use `builder/schedules.json`, `relationship_seeds.json`, `memory_seeds.json`, `need_profiles.json`, and `goal_profiles.json`.

## Phase 6C ability integration

The canonical AbilityExecutionService extends this system without replacing it. Ability damage is handed to CombatEngine, healing uses Actor resource APIs and HealingEvent records, effects are stored as canonical actor effect instances, costs use Actor resources, definitions and loadouts are world/Builder data, and future AI must select abilities through runtime authority.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7A reward data

Reward definitions live at `worlds/<world_id>/reward_definitions/reward_definitions.json`; loot tables at `worlds/<world_id>/loot_tables/loot_tables.json`; treasure groups at `worlds/<world_id>/treasure_groups/treasure_groups.json`; death-loot, corpse-decay, resource-node, and currency profiles follow the same collection directory pattern. Validation rejects unsafe ids, invalid reward types, invalid roll modes, invalid chance/quantity bounds, and loot table recursion cycles.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.

## Phase 7C crafting integration

Phase 7C adds `engine.crafting.CraftingService` as the single canonical crafting and production service. Recipes are Builder/world-package data; exact runtime item instances are selected and reserved; jobs persist in SQLite and advance by world time; costs use EconomyService; outputs use RewardService; profession rewards use canonical profession/progression state; and crafted item instances retain quality and provenance without mutating item templates. Salvaging and refining are normal recipe types, while quests, final trainers, autonomous AI production, random affixes, auction houses, and final enchantment remain outside this phase.


## Phase 8A Quest Integration

Phase 8A introduces `engine.quests.QuestService`, `QuestEventRouter`, `ConversationService`, and `WorldStateService` as the canonical quest and authored narrative-state foundation. Quests are Builder/world-package data, consume canonical EventBus-style events idempotently, branch deterministically, persist runtime state in SQLite, and hand rewards to RewardService instead of mutating items, XP, currencies, abilities, progression, Actor stats, or world records directly. Future AI may propose text or actions, but QuestService validates all outcomes; unrestricted scripts remain forbidden.
