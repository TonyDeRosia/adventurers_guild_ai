# ORGANIZATION ROLES AND PERMISSIONS

See [Organization System](ORGANIZATION_SYSTEM.md). Phase 8B implements this area through the canonical `engine.organizations.OrganizationService`, data collections under `worlds/<world_id>/organization_*`, SQLite runtime tables, audit events, and data-driven roles/permissions. The implementation is intentionally foundational: faction warfare, guild perks, banks, loot rolling, alliances, elections, kingdoms, and autonomous AI organization control remain non-goals.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.
