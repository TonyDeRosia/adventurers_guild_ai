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

## Phase 9B Achievement Integration

Phase 9B routes canonical subsystem events into `engine.achievements.AchievementService`. The achievement service owns achievement/title/accolade/collection runtime state, consumes EventBus events idempotently, and delegates reward delivery to `RewardService` instead of mutating XP, currency, items, abilities, faction reputation, organization roles, quest state, or Actor statistics directly.


## Phase 10A Written Content Integration

Written communication and readable content now route through `engine.written_content.WrittenContentService`. The canonical model is document instance -> immutable content version -> owner/placement/access -> delivery or publication -> read state -> audit. Integrations should call the service instead of writing mail, board, book, note, journal, or sign rows directly. Postage and service fees are quoted/settled through `EconomyService`; organization and faction decisions remain delegated to their canonical services; quest and achievement progress consumes written-content events.

Builder/world packages may include written document, content, access, retention, render, sanitization, mail service, board, posting, moderation, readable item, book, and journal profile collections. External messaging, unrestricted markup, executable links, arbitrary file attachments, AI-generated authoritative mail, and cross-server messaging remain forbidden.

## Phase 10B Property Integration

Smart MUD now includes the canonical `PropertyService` (`engine.property`) for Builder-authored property definitions, SQLite property instances, leases, access grants, property storage containers, actor home locations, and immutable property audit events. Related systems should integrate by service boundary: EconomyService for money, OrganizationService/FactionService for membership and reputation checks, WrittenContentService for notices, Quest/Achievement systems via property events, and canonical item instances for storage.
