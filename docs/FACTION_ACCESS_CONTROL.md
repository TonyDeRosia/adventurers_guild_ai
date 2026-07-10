# Smart MUD Phase 8C Faction Foundation

Phase 8C adds a canonical `engine.factions.FactionService` for organization-linked factions, actor reputation, standing tiers, deterministic diplomacy, access decisions, reward eligibility, and traceable event/history storage. A faction is not a second organization identity: `OrganizationService` remains authoritative for organization definitions, instances, memberships, roles, permissions, relationships, group combat attribution, and shared quest context. Faction definitions reference organization IDs and keep reputation separate from membership.

## Runtime authority

SQLite tables owned by `FactionService` are `actor_faction_reputation`, `faction_reputation_events`, `faction_reputation_history`, `faction_standing_cache_placeholder`, `faction_access_audit`, `faction_relationships`, and `faction_reward_claims`. Reputation mutation flows through `modify_reputation`, `set_reputation`, or `reset_reputation`; other subsystems must call the service rather than writing balances directly. Event IDs and source tuples provide retry-safe idempotency for quest completions, combat deaths, membership events, and script/admin changes.

## Builder/world data

Implemented collections are `faction_definitions`, `faction_reputation_profiles`, `faction_standing_tier_profiles`, `faction_membership_reputation_policies`, `faction_diplomacy_profiles`, `faction_hostility_profiles`, `faction_access_profiles`, `faction_guard_response_profiles`, `faction_economy_modifier_profiles`, `faction_reward_profiles`, `faction_reputation_decay_profiles`, `faction_combat_reputation_profiles`, `faction_title_profiles`, and `faction_message_profiles`. Live package files use `worlds/<world_id>/<collection>/<collection>.json`; Builder drafts use `worlds/<world_id>/builder/<collection>.json`. Old bundles remain valid because these collections are optional additions.

## Integration boundaries

Quest, conversation, economy, rewards, item, movement, combat behavior, hostility, and world-state integrations should query `FactionService` for reputation, standing, access, modifiers, and traces. `FactionService` does not duplicate quest state, reward delivery, economy balances, combat decisions, world state, organization membership, or AI strategy. Faction hostility is only an input to canonical hostility and combat-behavior rules; safe-room/lifecycle rules remain authoritative, and no faction PvP, law, bounty, politics, warfare, territory, election, or autonomous diplomacy system is introduced.

## Starter Guildlands pilot

Starter data defines `guildlands_town`, `town_guard_faction`, `blacksmiths_circle_faction`, `healers_order_faction`, `adventurers_guild_faction`, and hidden `cellar_vermin_faction`. The standard standing profile is data-authored and includes hated, hostile, unfriendly, neutral, friendly, honored, revered, and exalted ranges. Decay is disabled by default. Guard response is defensive and warning/deny oriented; attack-on-sight is not enabled by starter data.

## Manual acceptance outline

Inspect with `factionlist`, `factionstat guildlands_town`, `factionstat town_guard_faction`, `reputation self`, and `standing self guildlands_town`. Quest, shop, access, guard, combat, and restart acceptance should confirm that reputation events are idempotent, history-backed, standing-aware, and persisted after restart.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.
