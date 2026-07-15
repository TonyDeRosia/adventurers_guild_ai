# Phase 13C3-A2 Canonical Stat Runtime Audit

## Authoritative runtime sources

| Runtime value | Canonical source | Classes / methods |
| --- | --- | --- |
| Equipped item instance IDs and slots | SQLite `item_instances` rows where `owner_type='equipment'`, `owner_id=<character_id>`, `equipped_slot` populated, `destroyed_at IS NULL` | `MudRuntime.find_equipped_items()`, `CharacterAttributeService.equipment_snapshot()` |
| Inventory item instances and quantities | SQLite `item_instances` rows where `owner_type IN ('character','actor')`, `owner_id=<character_id>`, `stack_count` | `MudRuntime.find_inventory_items()`, `CombatStatService._weight()` |
| Item template weight and modifiers | Published world item/weapon/armor templates plus runtime-normalized item `template` payload | `MudRuntime._load_item_templates()`, `CharacterAttributeService._template_maps()`, `_item_modifiers()` |
| Container contents / reductions | Structured item `contents` and template `container.weight_reduction_percent` when present; recursive traversal is depth/visited guarded | `CombatStatService._weight()` |
| Weapon damage profile | Equipped canonical weapon item instance resolved against published `weapon_templates` or normalized item template weapon fields | `CharacterAttributeService.equipment_snapshot()`, `CombatStatService.get_damage_profile()` |
| Armor value | Equipped canonical armor item instances resolved against published `armor_templates`; aggregate feeds `equipment_armor` | `CharacterAttributeService.equipment_snapshot()`, `CombatStatService._variables()` |
| Item/enchantment/upgrade modifiers | Validated modifier declarations on template `modifiers`, instance `plugin_data.modifiers`, and `plugin_data.enchantments.modifiers` | `CharacterAttributeService._item_modifiers()` |
| Active affects and durations | SQLite `actor_effect_instances`, active and unsuspended rows, template-authored modifiers | `RuntimeEffectService.get_active_effects()`, `RuntimeEffectService.get_effect_modifiers()`, `CharacterAttributeService.collect_modifiers()` |
| Conditions / posture / combat state / situational context | Explicit calculation context dictionary; normal attributes/combatstats pass neutral current-character context | `CharacterAttributeService.collect_modifiers()`, `CombatStatSnapshot.context` |
| Current resources | Runtime character fields (`hp`, `mana`, `stamina`) and persisted character columns where present | `CombatStatService.get_combat_snapshot()`, `synchronize_resources()` |
| Formula definitions | Published `worlds/<world>/formulas/stat_formulas.json` and derived stat definitions | `CombatStatService.reload_definitions()`, `FormulaEngine.evaluate_expression()` |

## Runtime behavior

* `SafeFormula` has been retired from `engine.character_stats`; derived statistics now evaluate through `FormulaEngine.evaluate_expression()`.
* `EquipmentStatSnapshot` is immutable and carries slots, equipped instances, resolved templates, weapon projection, armor instances, modifier sources, total equipped weight, and a deterministic version hash.
* Modifier operation order is: base/permanent value, stack resolution, additive/subtractive/multiply/percentage operations in priority order, overrides, authored min/max modifiers, definition clamps, rounding.
* Resource maximum snapshots clamp current values when above maximum, do not refill current values below maximum, update live runtime fields, attempt persisted updates only when a clamp occurs, and publish `resource_maximum_changed` / `resource_current_clamped` when an event bus is available.
* Attribute migration now records `world_id`, `character_id`, and `migration_version` in `character_attribute_migrations`; the row records the attributes changed on that migration pass.
* Snapshot source versions hash formula definitions, stat definitions, equipment version, migration version, and active modifier declarations so equipment/effect/formula changes invalidate stale values.

## Publish and reload behavior

Published runtime definitions remain the source of truth. Builder drafts are kept separate under `worlds/<world>/builder/`. The runtime services reload by constructing fresh `CharacterAttributeService` / `CombatStatService` instances or calling their `reload_definitions()` methods; no global hot reload is claimed for already-running runtimes unless the owning runtime explicitly rebuilds these services.

## Combat authority note

The legacy `engine.combat.CombatEngine` still has a separate Actor/equipment path for some direct combat resolution. The canonical stat service now exposes accurate armor, evasion, accuracy, damage, critical, saves, and resistances for integration, but paths that instantiate `CombatEngine` directly without `CombatStatService` remain legacy and should be treated as not yet fully migrated.
