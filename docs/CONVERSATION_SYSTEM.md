# Conversation System

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


## Phase 8C faction integration note

Phase 8C adds `FactionService` as the canonical owner of faction reputation, standing, diplomacy interpretation, access decisions, faction reward eligibility, and reputation history. Factions link to `OrganizationService` identities; organization membership, roles, permissions, group combat attribution, quests, rewards, economy, combat, and world state remain owned by their existing canonical services. Subsystems must call `FactionService` rather than mutating faction reputation directly. Faction warfare, laws, territory conquest, elections, autonomous politics, and PvP faction rules remain outside this foundation.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.
