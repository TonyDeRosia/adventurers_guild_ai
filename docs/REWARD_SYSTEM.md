# Phase 7A Reward and Loot Foundation

Phase 7A introduces the canonical `engine.rewards.RewardService` pipeline. Reward sources resolve into persistent `reward_packets` and `reward_entries`, then delivery records idempotent `reward_delivery_events`. Loot tables and treasure groups use deterministic caller-provided or stable derived seeds; repeated resolution with the same source, recipient, definition, and seed returns the same packet id.

The implemented foundation covers reward definitions, loot tables, treasure groups, currency awards, progression hooks, item-instance delivery through canonical runtime/store item APIs, pending-claim schema, corpse inventory state schema, resource-node state schema, validation, traces, and conservative Shattered Realms pilot content. Shops, crafting, full quests, group loot, mail, and economy balance remain separate systems.

Manual acceptance smoke commands: `builder on`, `rewardlist`, `loottablelist`, `treasurelist`, `deathlootlist`, `corpsedecaylist`, `nodelist`, `loottablepreview rat_common_loot 12345`, `loottablepreview rat_common_loot 12345`, `grantreward self starter_training_reward`, `rewardtrace <packet_id>`, `rewards`, and `claim all`.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.

## Phase 7C crafting integration

Phase 7C adds `engine.crafting.CraftingService` as the single canonical crafting and production service. Recipes are Builder/world-package data; exact runtime item instances are selected and reserved; jobs persist in SQLite and advance by world time; costs use EconomyService; outputs use RewardService; profession rewards use canonical profession/progression state; and crafted item instances retain quality and provenance without mutating item templates. Salvaging and refining are normal recipe types, while quests, final trainers, autonomous AI production, random affixes, auction houses, and final enchantment remain outside this phase.


## Phase 8A Quest Integration

Phase 8A introduces `engine.quests.QuestService`, `QuestEventRouter`, `ConversationService`, and `WorldStateService` as the canonical quest and authored narrative-state foundation. Quests are Builder/world-package data, consume canonical EventBus-style events idempotently, branch deterministically, persist runtime state in SQLite, and hand rewards to RewardService instead of mutating items, XP, currencies, abilities, progression, Actor stats, or world records directly. Future AI may propose text or actions, but QuestService validates all outcomes; unrestricted scripts remain forbidden.

## Phase 8B Organization Integration

Phase 8B adds the canonical `OrganizationService` for parties, guilds, clans, NPC organizations, roles, permissions, invitations, applications, shared quest context, group combat attribution, and organization audit history. These systems provide context only and call existing canonical services for combat, quests, rewards, economy, progression, crafting, and world state.


## Phase 8C faction integration note

Phase 8C adds `FactionService` as the canonical owner of faction reputation, standing, diplomacy interpretation, access decisions, faction reward eligibility, and reputation history. Factions link to `OrganizationService` identities; organization membership, roles, permissions, group combat attribution, quests, rewards, economy, combat, and world state remain owned by their existing canonical services. Subsystems must call `FactionService` rather than mutating faction reputation directly. Faction warfare, laws, territory conquest, elections, autonomous politics, and PvP faction rules remain outside this foundation.

## Phase 9B Achievement Integration

Phase 9B routes canonical subsystem events into `engine.achievements.AchievementService`. The achievement service owns achievement/title/accolade/collection runtime state, consumes EventBus events idempotently, and delegates reward delivery to `RewardService` instead of mutating XP, currency, items, abilities, faction reputation, organization roles, quest state, or Actor statistics directly.

## Phase 11C1 Gathering Foundation Integration

Phase 11C1 introduces `engine.gathering.GatheringService` as the single canonical foundation for resource definitions, node definitions, runtime node state, capacity/depletion, world-time regeneration, requirements, tools, sessions, deterministic yields, quality, rare-yield hooks, diagnostics, and Builder collections. It is intentionally a reusable foundation: Phase 11C2 will add the full gameplay rollout for harvesting, mining, lumberjacking, fishing, skinning, scavenging, excavation, profession XP presentation, quest/achievement integration, and pilot content.
