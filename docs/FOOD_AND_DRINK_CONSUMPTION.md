# FOOD AND DRINK CONSUMPTION

Phase 11D1 introduces the canonical survival needs and consumption foundation. SQLite is authoritative through `actor_need_state`, `actor_need_history`, `need_progression_events`, `consumption_sessions`, `consumption_results`, `survival_event_consumption`, and `survival_audit_events`.

World data lives in Builder/world-package collections: `actor_need_definitions`, `actor_needs_profiles`, `needs_offline_policies`, `need_threshold_profiles`, `consumable_profiles`, `consumable_portion_profiles`, `food_freshness_profiles`, `consumption_requirement_profiles`, `consumption_interruption_profiles`, `survival_message_profiles`, and `survival_render_profiles`.

The canonical runtime API is `engine.survival_needs.SurvivalNeedsService`. It initializes actor needs idempotently, migrates valid legacy `entity_needs` values, progresses needs from world time with bounded catch-up, resolves exact item instances for consumption, decrements servings atomically, and records idempotent consumption sessions.

Default content is conservative and nonlethal. Rest, sleep, beds, shelters, campfires, and campsites remain placeholders for Phase 11D2.

## Phase 11D2 survival extension

Rest, sleep, rest-location profiles, rest quality, campfire profiles, campsite profiles, shelter context, runtime rest sessions, campfire instances, and campsite instances are routed through the canonical `engine.survival_needs.SurvivalNeedsService`. This preserves the existing EnvironmentService, PropertyService, GatheringService, CraftingService, QuestService, AchievementService, EventBus, item, and score boundaries while adding conservative starter content and diagnostics.

## Phase 11E Cooking Integration

Cooking is a canonical CraftingService specialization. The runtime uses recipe definitions, exact item-instance input reservations, crafting jobs, workstation profiles, production profiles, item quality, profession XP, and reward delivery for cooked outputs. SurvivalNeedsService remains authoritative for consumable profiles, portions, servings, freshness interpretation, spoilage, and need mutation. GatheringService remains authoritative for raw gathered materials. Builder/world-package content now includes cooking ingredient, substitution, preparation, serving-yield, consumable-output, nutrition, preservation, heat, failure, message, and render profile collections.
