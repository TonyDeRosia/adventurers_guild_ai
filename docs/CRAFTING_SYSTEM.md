# Crafting System

Phase 7C introduces the canonical `engine.crafting.CraftingService` for deterministic recipes, input reservation, workstation validation, world-time production jobs, quality resolution, item provenance, profession experience, recipe knowledge, salvage, refining, and production-order foundations.

## Ownership and flow

Actor or production owner -> recipe definition -> profession and requirement validation -> workstation validation -> deterministic ingredient selection -> exact item reservation -> EconomyService cost transaction -> world-time job -> deterministic quality -> input consumption -> RewardService output delivery -> profession progression and audit events. Crafting code must not directly grant XP, mutate currency dictionaries, copy templates into inventory, or bypass canonical RewardService/EconomyService APIs.

## Runtime authority

SQLite tables include `crafting_jobs`, `crafting_input_reservations`, `crafting_input_reservation_entries`, `workstation_runtime_state`, `actor_profession_state`, `actor_recipe_knowledge`, and immutable `craft_previews`. Jobs are restart-safe and idempotent: completed jobs keep one reward packet and repeat completion returns the existing completed state.

## Builder and content

World packages and Builder drafts support `recipe_definitions`, `workstation_profiles`, `production_profiles`, `item_quality_profiles`, `crafting_quality_profiles`, `ingredient_substitution_profiles`, `crafting_message_profiles`, `profession_experience_curves`, and `profession_growth_profiles`. Pilot Shattered Realms content includes blacksmith, herbalist, cook, and salvager examples.

## Manual acceptance commands

Builder: `builder on`, `recipelist`, `recipestat iron_sword_recipe`, `workstationlist`, `professionlist`, `qualitylist`, `recipepreview iron_sword_recipe self 1`.

Player: `recipes`, `recipe iron_sword`, `craft preview iron_sword`, `craft iron_sword`, `crafting jobs`, `crafttick <required duration>`, `crafting cancel <job>`, and `salvage <eligible item>`.

## Boundaries

Quest integration, final trainers, autonomous AI production, random affixes, auction houses, player-to-player work orders, and final enchantment mechanics remain separate future systems.


## Phase 8A Quest Integration

Phase 8A introduces `engine.quests.QuestService`, `QuestEventRouter`, `ConversationService`, and `WorldStateService` as the canonical quest and authored narrative-state foundation. Quests are Builder/world-package data, consume canonical EventBus-style events idempotently, branch deterministically, persist runtime state in SQLite, and hand rewards to RewardService instead of mutating items, XP, currencies, abilities, progression, Actor stats, or world records directly. Future AI may propose text or actions, but QuestService validates all outcomes; unrestricted scripts remain forbidden.

## Phase 9B Achievement Integration

Phase 9B routes canonical subsystem events into `engine.achievements.AchievementService`. The achievement service owns achievement/title/accolade/collection runtime state, consumes EventBus events idempotently, and delegates reward delivery to `RewardService` instead of mutating XP, currency, items, abilities, faction reputation, organization roles, quest state, or Actor statistics directly.

## Phase 11C2 Gathering Integration

Gathered outputs are canonical item/reward payloads; Crafting, Economy, Profession/Progression, Environment, Perception, Quest, Achievement, Property, Organization/Faction, Living World, Builder, and score surfaces integrate by consuming GatheringService data or EventBus events. GatheringService does not price resources, mutate quest state directly, create a shadow inventory, destroy terrain, implement farming, run autonomous workers, or bypass canonical services.

## Phase 11D2 survival extension

Rest, sleep, rest-location profiles, rest quality, campfire profiles, campsite profiles, shelter context, runtime rest sessions, campfire instances, and campsite instances are routed through the canonical `engine.survival_needs.SurvivalNeedsService`. This preserves the existing EnvironmentService, PropertyService, GatheringService, CraftingService, QuestService, AchievementService, EventBus, item, and score boundaries while adding conservative starter content and diagnostics.

## Phase 11E Cooking Integration

Cooking is a canonical CraftingService specialization. The runtime uses recipe definitions, exact item-instance input reservations, crafting jobs, workstation profiles, production profiles, item quality, profession XP, and reward delivery for cooked outputs. SurvivalNeedsService remains authoritative for consumable profiles, portions, servings, freshness interpretation, spoilage, and need mutation. GatheringService remains authoritative for raw gathered materials. Builder/world-package content now includes cooking ingredient, substitution, preparation, serving-yield, consumable-output, nutrition, preservation, heat, failure, message, and render profile collections.
