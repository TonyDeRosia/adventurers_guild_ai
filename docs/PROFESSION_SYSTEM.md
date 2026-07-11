# Profession System

Profession profiles define noncombat identity, ranks, curves, grants, and requirements. Crafting/tasks/trainers remain separate future systems.

## Phase 7C crafting integration

Phase 7C adds `engine.crafting.CraftingService` as the single canonical crafting and production service. Recipes are Builder/world-package data; exact runtime item instances are selected and reserved; jobs persist in SQLite and advance by world time; costs use EconomyService; outputs use RewardService; profession rewards use canonical profession/progression state; and crafted item instances retain quality and provenance without mutating item templates. Salvaging and refining are normal recipe types, while quests, final trainers, autonomous AI production, random affixes, auction houses, and final enchantment remain outside this phase.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.

## Phase 11C1 Gathering Foundation Integration

Phase 11C1 introduces `engine.gathering.GatheringService` as the single canonical foundation for resource definitions, node definitions, runtime node state, capacity/depletion, world-time regeneration, requirements, tools, sessions, deterministic yields, quality, rare-yield hooks, diagnostics, and Builder collections. It is intentionally a reusable foundation: Phase 11C2 will add the full gameplay rollout for harvesting, mining, lumberjacking, fishing, skinning, scavenging, excavation, profession XP presentation, quest/achievement integration, and pilot content.
