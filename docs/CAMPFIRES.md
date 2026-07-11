# Campfires

Phase 11D2 campfires are temporary runtime objects owned by `SurvivalNeedsService` and stored in `campfire_instances`, with idempotent fuel records in `campfire_fuel_events`. Profiles live in `campfire_profiles` and reference EnvironmentService light-source profile IDs rather than creating a second light engine.

Commands include `light campfire`, `extinguish campfire`, `add fuel`, and `inspect campfire`. Starter content provides `basic_campfire` with conservative heat, light, duration, and rest-quality modifiers.

## Phase 11E Cooking Integration

Cooking is a canonical CraftingService specialization. The runtime uses recipe definitions, exact item-instance input reservations, crafting jobs, workstation profiles, production profiles, item quality, profession XP, and reward delivery for cooked outputs. SurvivalNeedsService remains authoritative for consumable profiles, portions, servings, freshness interpretation, spoilage, and need mutation. GatheringService remains authoritative for raw gathered materials. Builder/world-package content now includes cooking ingredient, substitution, preparation, serving-yield, consumable-output, nutrition, preservation, heat, failure, message, and render profile collections.
