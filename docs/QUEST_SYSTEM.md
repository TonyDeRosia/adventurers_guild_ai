# Quest System

Phase 8A adds the canonical authored quest and narrative-state foundation. QuestService owns quest runtime state, stage state, objective state, event consumption, timers, history, and RewardService handoff. Definitions remain Builder/world-package data; runtime mutation is SQLite-authoritative.

## Boundaries

- Quests, conversations, objectives, branches, and world-state definitions are data, not scripts.
- Objective progress consumes stable canonical events idempotently.
- Rewards are requested from RewardService with `source_type=quest`; quests never mutate XP, currency, items, abilities, Actor stats, or progression directly.
- World state changes go through WorldStateService and append history.
- Conversations can call QuestService actions but never edit quest tables directly.
- Unsupported custom actions fail safely; unrestricted Python and command execution are forbidden so authored content cannot bypass canonical service ownership.

## Manual acceptance commands

Builder: `builder on`, `questlist`, `queststat cellar_rat_problem`, `stagelist cellar_rat_problem`, `objectivelist cellar_rat_problem_kill`, `conversationlist`, `questvalidate cellar_rat_problem`, `questpreview cellar_rat_problem self`.

Player: `talk tavern_keeper_jory`, `reply 1`, `accept cellar_rat_problem`, `quests`, `quest cellar_rat_problem`, kill configured rats, `turnin cellar_rat_problem`. Crafting: `accept first_craft`, `craft training_sword`, advance crafting time, `quests`. World state: `worldstateset world shattered_realms tutorial_complete true`.

## Phase 8B Organization Integration

Phase 8B adds the canonical `OrganizationService` for parties, guilds, clans, NPC organizations, roles, permissions, invitations, applications, shared quest context, group combat attribution, and organization audit history. These systems provide context only and call existing canonical services for combat, quests, rewards, economy, progression, crafting, and world state.


## Phase 8C faction integration note

Phase 8C adds `FactionService` as the canonical owner of faction reputation, standing, diplomacy interpretation, access decisions, faction reward eligibility, and reputation history. Factions link to `OrganizationService` identities; organization membership, roles, permissions, group combat attribution, quests, rewards, economy, combat, and world state remain owned by their existing canonical services. Subsystems must call `FactionService` rather than mutating faction reputation directly. Faction warfare, laws, territory conquest, elections, autonomous politics, and PvP faction rules remain outside this foundation.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.

## Phase 9B Achievement Integration

Phase 9B routes canonical subsystem events into `engine.achievements.AchievementService`. The achievement service owns achievement/title/accolade/collection runtime state, consumes EventBus events idempotently, and delegates reward delivery to `RewardService` instead of mutating XP, currency, items, abilities, faction reputation, organization roles, quest state, or Actor statistics directly.


## Phase 10A Written Content Integration

Written communication and readable content now route through `engine.written_content.WrittenContentService`. The canonical model is document instance -> immutable content version -> owner/placement/access -> delivery or publication -> read state -> audit. Integrations should call the service instead of writing mail, board, book, note, journal, or sign rows directly. Postage and service fees are quoted/settled through `EconomyService`; organization and faction decisions remain delegated to their canonical services; quest and achievement progress consumes written-content events.

Builder/world packages may include written document, content, access, retention, render, sanitization, mail service, board, posting, moderation, readable item, book, and journal profile collections. External messaging, unrestricted markup, executable links, arbitrary file attachments, AI-generated authoritative mail, and cross-server messaging remain forbidden.

## Phase 10B Property Integration

Smart MUD now includes the canonical `PropertyService` (`engine.property`) for Builder-authored property definitions, SQLite property instances, leases, access grants, property storage containers, actor home locations, and immutable property audit events. Related systems should integrate by service boundary: EconomyService for money, OrganizationService/FactionService for membership and reputation checks, WrittenContentService for notices, Quest/Achievement systems via property events, and canonical item instances for storage.


## Phase 11B Perception Integration

Phase 11B adds `engine.perception.PerceptionService` as the single sensory boundary for stealth, concealment, search, tracking, scent, sound, trails, and observer knowledge. It queries canonical services, especially `EnvironmentService`, and stores restart-safe sensory state in SQLite.

## Phase 11C2 Gathering Integration

Gathered outputs are canonical item/reward payloads; Crafting, Economy, Profession/Progression, Environment, Perception, Quest, Achievement, Property, Organization/Faction, Living World, Builder, and score surfaces integrate by consuming GatheringService data or EventBus events. GatheringService does not price resources, mutate quest state directly, create a shadow inventory, destroy terrain, implement farming, run autonomous workers, or bypass canonical services.

## Phase 11D2 survival extension

Rest, sleep, rest-location profiles, rest quality, campfire profiles, campsite profiles, shelter context, runtime rest sessions, campfire instances, and campsite instances are routed through the canonical `engine.survival_needs.SurvivalNeedsService`. This preserves the existing EnvironmentService, PropertyService, GatheringService, CraftingService, QuestService, AchievementService, EventBus, item, and score boundaries while adding conservative starter content and diagnostics.

## Phase 11E Cooking Integration

Cooking is a canonical CraftingService specialization. The runtime uses recipe definitions, exact item-instance input reservations, crafting jobs, workstation profiles, production profiles, item quality, profession XP, and reward delivery for cooked outputs. SurvivalNeedsService remains authoritative for consumable profiles, portions, servings, freshness interpretation, spoilage, and need mutation. GatheringService remains authoritative for raw gathered materials. Builder/world-package content now includes cooking ingredient, substitution, preparation, serving-yield, consumable-output, nutrition, preservation, heat, failure, message, and render profile collections.
