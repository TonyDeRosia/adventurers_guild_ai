# FOOD FRESHNESS AND SPOILAGE

Phase 11D1 introduces the canonical survival needs and consumption foundation. SQLite is authoritative through `actor_need_state`, `actor_need_history`, `need_progression_events`, `consumption_sessions`, `consumption_results`, `survival_event_consumption`, and `survival_audit_events`.

World data lives in Builder/world-package collections: `actor_need_definitions`, `actor_needs_profiles`, `needs_offline_policies`, `need_threshold_profiles`, `consumable_profiles`, `consumable_portion_profiles`, `food_freshness_profiles`, `consumption_requirement_profiles`, `consumption_interruption_profiles`, `survival_message_profiles`, and `survival_render_profiles`.

The canonical runtime API is `engine.survival_needs.SurvivalNeedsService`. It initializes actor needs idempotently, migrates valid legacy `entity_needs` values, progresses needs from world time with bounded catch-up, resolves exact item instances for consumption, decrements servings atomically, and records idempotent consumption sessions.

Default content is conservative and nonlethal. Rest, sleep, beds, shelters, campfires, and campsites remain placeholders for Phase 11D2.
