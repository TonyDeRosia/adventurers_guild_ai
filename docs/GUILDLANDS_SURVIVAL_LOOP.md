# Complete Guildlands Survival Loop

Phase 11F Part 3 proves the first end-to-end Guildlands survival gameplay loop without adding parallel gameplay systems. The vertical slice remains data-driven and routes each mutation through the canonical runtime authorities: `GatheringService`, `CraftingService` cooking, `SurvivalNeedsService`, `EconomyService`, `PropertyService`, quest/EventBus routing, and SQLite persistence.

## Gameplay Walkthrough

1. Complete the existing Emberleaf starter quest.
2. Accept the existing Wolf Pelts starter quest.
3. Travel to the Emberwood hunting area and defeat the starter forest wolf through combat.
4. Loot the corpse for the authored pelt objective.
5. Process the same corpse with the Builder-authored `starter_forest_wolf_corpse_processing` profile:
   - `skinning` extracts `starter_wolf_pelt_skinning` and yields exactly one `wolf_pelt`.
   - `butchering` extracts `starter_wolf_meat_butchering` and yields exactly two `small_meat`.
   - `harvesting` extracts `starter_wolf_torn_hide_harvesting` and yields exactly one `torn_hide`.
6. Cook harvested `small_meat` with the existing `cooked_small_meat` recipe at a lit campfire workstation.
7. Eat the cooked serving through `SurvivalNeedsService.consume_item()` so hunger, servings, and the exact item instance update atomically.
8. Sell remaining harvested/cooked materials through `EconomyService.quote_sale()` and `confirm_sale()` so ledger entries and currency balances are recorded.
9. Rent a Wayfarer's Mug inn room through `PropertyService.quote_rent()` and `confirm_rent()` so rent payment, lease, and access grants persist.
10. Sleep in the rented inn bed through `SurvivalNeedsService.start_sleep()` and `complete_rest()`.
11. Restart/recreate services and verify inventory/cooking output metadata, currency, ledger, property lease/access, needs, fatigue, profession extraction rows, and completed jobs remain in SQLite.

## Corpse Processing

Corpse extraction is implemented as Builder-authored gathering content. `corpse_extraction_profiles` maps actor templates to extraction operations, resource definitions, and corpse-scoped node definitions. Runtime extraction uses `GatheringService.process_corpse()`, which materializes the configured corpse node, starts/completes the normal gathering session, records `corpse_resource_extractions`, and publishes `corpse_processed`.

The idempotency boundary is `(corpse_instance_id, resource_definition_id)`. Repeating skinning, butchering, or harvesting for the same corpse/resource returns `corpse_resource_already_extracted` instead of producing duplicate items.

## Cooking Integration

Cooking remains the existing CraftingService specialization. The starter loop uses the existing `cooked_small_meat` recipe, exact `small_meat` item instances, campfire workstation validation from `SurvivalNeedsService`, cooking quality resolution, servings, freshness metadata, and preservation-compatible freshness profiles.

## Economy Integration

Sales use EconomyService quotes and confirmations. The loop does not mutate currency directly: sale transactions create immutable transaction rows, ledger entries, buyback records, and actor currency balance updates. Rent payments also delegate to EconomyService through PropertyService quote/payment APIs.

## Property Integration

The inn-room step uses existing Wayfarer's Mug property definitions. Renting creates a persistent lease, updates the property instance, grants tenant access, records property audit events, and publishes property events. Sleeping uses survival rest locations (`inn_bed`) rather than any property-local sleep implementation.

## Restart Persistence

The focused regression recreates service instances on the same SQLite database to verify restart-safe state for corpse extraction records, completed cooking jobs and output servings/freshness, consumed serving counts, actor currency, property leases, needs/fatigue, and EventBus-published canonical events.

## Builder Survival Authoring

Builder/world content owns the survival loop data: corpse extraction profiles, resource definitions, resource node definitions, yield profiles, cooking recipes, campfire/rest profiles, shop definitions, and property definitions. Designers can adjust yields, operations, recipes, stores, and inn rooms without introducing new runtime systems.
