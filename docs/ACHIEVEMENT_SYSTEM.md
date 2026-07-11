# Smart MUD Phase 9B Achievement Foundation

Phase 9B introduces one canonical `engine.achievements.AchievementService` for achievements, milestones, titles, accolades, collections, criteria progress, reward handoff, and diagnostics.

Definitions are Builder/world-package JSON collections under `worlds/<world_id>/achievement_*`, `title_definitions`, `accolade_definitions`, and `collection_*`. Runtime state is SQLite-authoritative through `actor_achievement_state`, `actor_achievement_criteria_state`, `achievement_event_consumption`, `achievement_completion_history`, `achievement_progress_history`, `actor_titles`, `actor_accolades`, `actor_collection_state`, and `achievement_reward_claims`.

Canonical EventBus events are consumed idempotently by `AchievementEventRouter`; read-only commands do not publish progress events. Achievement rewards use `RewardService` with `source_type=achievement`. Titles and accolades are cosmetic, source-traceable, and never mutate Actor statistics.

Manual acceptance commands: `achievementlist`, `achievementstat first_blood`, `achievementpreview first_blood self`, `achievementtrace self first_blood`, `achievements`, `achievement first_blood`, `titles`, `title select rat_hunter`, `score achievements`, `score titles`, and `collections`.


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
