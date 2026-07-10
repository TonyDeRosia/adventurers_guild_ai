# Progression System

Canonical progression is owned by SQLite actor_progression_state and engine.progression.ProgressionService. Actors resolve species/race, class/profession, progression profile, level/XP, Formula-safe growth grants, ability learning, score, and diagnostics through this API; legacy character level/xp are conserved only as migration inputs.

## Phase 7A reward integration

RewardService delivers `experience`, `practice_sessions`, `training_sessions`, `skill_points`, `attribute_points`, `ability`, and `ability_rank` entries by calling `ProgressionService` APIs. Reward packets remain the audit source; progression services remain the mutation authority.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.
