# Phase 7A Reward and Loot Foundation

Phase 7A introduces the canonical `engine.rewards.RewardService` pipeline. Reward sources resolve into persistent `reward_packets` and `reward_entries`, then delivery records idempotent `reward_delivery_events`. Loot tables and treasure groups use deterministic caller-provided or stable derived seeds; repeated resolution with the same source, recipient, definition, and seed returns the same packet id.

The implemented foundation covers reward definitions, loot tables, treasure groups, currency awards, progression hooks, item-instance delivery through canonical runtime/store item APIs, pending-claim schema, corpse inventory state schema, resource-node state schema, validation, traces, and conservative Shattered Realms pilot content. Shops, crafting, full quests, group loot, mail, and economy balance remain separate systems.

Manual acceptance smoke commands: `builder on`, `rewardlist`, `loottablelist`, `treasurelist`, `deathlootlist`, `corpsedecaylist`, `nodelist`, `loottablepreview rat_common_loot 12345`, `loottablepreview rat_common_loot 12345`, `grantreward self starter_training_reward`, `rewardtrace <packet_id>`, `rewards`, and `claim all`.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.
