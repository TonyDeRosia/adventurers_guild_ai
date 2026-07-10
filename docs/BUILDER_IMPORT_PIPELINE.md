# Builder Import Pipeline

Phase 4F adds a draft-only JSON import pipeline under `worlds/<world_id>/builder/imports/`. Imports never mutate live world package files and every apply operation records Builder audit/history entries.

## Workflow

1. Author JSON outside the client.
2. Save it as `worlds/shattered_realms/builder/imports/my_area.json`.
3. In game run:

```text
builder on
builder import list
builder import validate my_area.json
builder import preview my_area.json
builder import apply my_area.json
builder validate
builder reload
goto <new_room_id>
look
```

## Bundled format

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

`builder export` writes the same bundle shape, so exports can be round-tripped through `builder import validate` and `builder import apply`.

## Commands

- `builder import list` lists JSON files in the imports directory.
- `builder import validate <filename>` checks safe IDs, area/zone/room references, ranges, duplicate vnums, exits, names, descriptions, and spawn/entity references without changing files.
- `builder import preview <filename>` reports add/update counts, conflicts, legacy warnings, and broken references without changing files.
- `builder import apply <filename>` merges records into Builder drafts.
- `builder import apply <filename> --merge` is the explicit merge form.
- `builder import apply <filename> --replace-drafts` snapshots first, then replaces draft collections.

Future feature-library work can promote room-local scenery features into reusable feature templates. For now, nonportable scenery should remain `portable: false` draft features.

## Phase 4F Hotfix: committed organized starter drafts

Fresh downloads now include the organized Shattered Realms starter Builder drafts under `worlds/shattered_realms/builder/`. The live package files remain unchanged; the committed Builder drafts are the default editable organized starter layer that Builder Mode overlays at runtime.

Use `builder validate` to verify the committed starter draft layer. The starting room `guildhall_crossing_square` is assigned to `starter_guildlands`, zone `guildhall_crossing`, vnum `1000`, and should report `Status: organized` in `rstat`.

`builder migrate starter` remains available to reset or regenerate the starter drafts from the live Shattered Realms package. Regeneration should update the draft JSON files only; do not commit runtime audit, history, snapshot, export, local database, or user-data artifacts.

To exchange the organized starter layer, run `builder export`, then place the exported bundle in the Builder import folder and run `builder import validate <file>` before applying it.


## Phase 4G World Data Specification Alignment

The canonical data contract is now defined in [WORLD_DATA_SPECIFICATION.md](WORLD_DATA_SPECIFICATION.md). Import/export bundles remain `{"areas": {}, "zones": {}, "rooms": {}, "features": {}, "items": {}, "entities": {}, "spawns": {}}`. Future optional keys such as `locations`, `factions`, `religions`, `cultures`, `terrain_profiles`, `ambient_profiles`, `weather_profiles`, `lighting_profiles`, `music_profiles`, `dialogue_packages`, `loot_tables`, `encounter_tables`, `quest_templates`, and `shop_templates` are reserved. Current import validation must not crash on those keys; unsupported collections are reported as future ignored warnings and are not applied.

## Phase 4G Hotfix: import templates and empty-folder guidance

Builder workspace preparation now creates `imports/`, `templates/`, and `examples/` under `worlds/<world_id>/builder/` automatically. Fresh Shattered Realms downloads include ready-to-copy templates in `worlds/shattered_realms/builder/templates/`:

- `empty_bundle_template.json`
- `area_zone_room_template.json`
- `bad_duplicate_vnum_test.json`
- `future_keys_test.json`
- `feature_library_template.json`

Use these commands inside the game:

```text
builder template list
builder template show area_zone_room_template.json
builder template copy area_zone_room_template.json my_area.json
builder import validate my_area.json
builder import preview my_area.json
builder import apply my_area.json --merge
```

`builder template copy` writes to `worlds/<world_id>/builder/imports/` and refuses to overwrite an existing import file unless `--force` is supplied. When `builder import list` finds no JSON files, it prints the import folder path and the exact template-copy commands needed to get started.

`bad_duplicate_vnum_test.json` is intentionally invalid and should fail validation with a duplicate-vnum error. `future_keys_test.json` contains future top-level collections such as `locations`, `factions`, and `ambient_profiles`; current validation warns that those collections are not applied, but it must not crash.


## Starter Guildlands Content Pack v1

The built-in template `starter_guildlands_content_pack_v1.json` can be copied with `builder template copy starter_guildlands_content_pack_v1.json copied_pack.json`, validated with `builder import validate copied_pack.json`, previewed with `builder import preview copied_pack.json`, and applied with `builder import apply copied_pack.json`. It is a merge-style Builder draft bundle using `areas`, `zones`, `rooms`, `features`, `items`, `entities`, and `spawns`.

## Phase 4H localized Builder lists

Builder list commands are local by default: `alist` shows the current area, `zlist` shows the current area's zones, and `rlist`/`rooms` shows the current zone's rooms. Use explicit `all`, `area <area_id>`, `zone <zone_id>`, or VNUM ranges such as `1000-1029` to broaden or focus results. See `docs/BUILDER_LIST_COMMANDS.md`.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.

## Phase 5B living-world import/export

Builder import bundles may include schedules, relationship seeds, memory seeds, need profiles, and goal profiles alongside existing content collections.

## Phase 6C ability integration

The canonical AbilityExecutionService extends this system without replacing it. Ability damage is handed to CombatEngine, healing uses Actor resource APIs and HealingEvent records, effects are stored as canonical actor effect instances, costs use Actor resources, definitions and loadouts are world/Builder data, and future AI must select abilities through runtime authority.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7A reward boundary

Rewards are issued through `engine.rewards.RewardService` and persisted as reward packets. This document's subsystem remains the authority for its own domain; reward delivery calls canonical APIs rather than editing subsystem tables directly.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.
