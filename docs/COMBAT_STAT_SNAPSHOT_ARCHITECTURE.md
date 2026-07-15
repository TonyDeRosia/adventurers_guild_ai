# Combat stat snapshot architecture

Phase 15B.10 removes the hot-path fan-out where `CombatStatService.get_combat_snapshot()` rebuilt an `ActorStatInput` for every derived stat through `_combat_value()`, `get_breakdown()`, `get_encumbrance()`, resistance resolution, and weapon damage profile resolution. The canonical path is now resident sources -> one normalized `ActorStatInput` -> one primary-stat pass -> derived combat values -> one cached `CombatStatSnapshot`.

## Root causes fixed

* Snapshot fan-out: the snapshot builder called `_combat_value()` with the original actor, and every value re-entered `build_actor_stat_input()`, `get_primary_stats()`, `_variables()`, `equipment_snapshot()`, and `_source_versions()`.
* SQLite fan-out: `equipment_snapshot()` preferred `runtime.find_equipped_items()` for active runtime actors, which is SQLite-backed in `MudRuntime`; repeated re-entry multiplied that query path during opening attacks and violence pulses.

## Normalized input and snapshot cache

`CombatStatService` owns two bounded resident caches:

* `_input_cache`, keyed by actor id plus actor/source generations and stable signatures for attributes, test equipment, and situational modifiers.
* `_snapshot_cache`, keyed by actor id plus the normalized source-version hash.

The cached `ActorStatInput` carries already-resolved equipment, effects, resource projection, and inventory weight so later derived-stat helpers operate on resident data instead of reconstructing sources.

## Resident equipment and inventory policy

`CharacterAttributeService.equipment_snapshot()` first accepts a resident `EquipmentStatSnapshot` or resident equipment projection from the actor. Runtime SQLite equipment lookup is disabled when a real runtime with performance counters is present unless `active_combat_sql_fallback_allowed` is explicitly enabled for legacy/offline use. Inventory weight calculation reuses the normalized input resource projection and the already-built equipment snapshot.

## Generation invalidation

Stable snapshots are invalidated by actor/source generations: actor, attribute, equipment, effect, body, ability, level, stance, template, and world content generation. Ordinary health loss, target changes, and round increments do not participate in the stable cache key; current resources are dynamic state and should be passed separately when a formula explicitly depends on resource percentage.

## Formula and EventBus findings

Formula definitions are loaded by `reload_definitions()` and evaluated during snapshot build; this patch does not introduce per-attack formula compilation. EventBus was not changed because the profiled bottleneck was snapshot/stat and SQLite fan-out, not subscriber dispatch.

## Manual Windows acceptance

Not performed in this Linux container. Tony should run the requested Windows steps (`statcache reset`, `sqltrace combat reset`, `violenceprofile reset`, `kill spider`, ten rounds, inspect `statcache`, `sqltrace combat`, `violenceprofile`, equip/unequip, fight again, flush/restart) before accepting the build on Windows.
