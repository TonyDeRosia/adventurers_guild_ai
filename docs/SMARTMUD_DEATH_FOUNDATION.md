# SmartMUD death foundation (Phase 20A)

`engine.death_runtime.DeathRuntimeService` is the sole terminal processing
boundary. Its states are `ALIVE -> DEFEATED_PENDING_DEATH -> DEATH_PROCESSING
-> DEAD_PROCESSED`, with NPCs advancing to `REMOVED`. A player remains
`DEAD_PROCESSED` pending Phase 20B respawn.

The SQLite `death_ledger` key combines world, victim, life/spawn generation,
and terminal damage event. `BEGIN IMMEDIATE` makes the claim atomic. A completed
result is persisted and duplicate callers receive it without repeating corpse,
item, random, or extraction work. The implementation’s adapter stages are
combat cleanup, trigger/cry, corpse/transfers, gold/loot, then disposition;
network delivery is outside the transaction.

Attribution retains both immediate and credited source. Master/owner links are
walked for at most 20 hops, cycles are safe, and the first player wins. Phase
20B is deliberately reserved for XP, Glory, bounty, quest credit, penalties,
and respawn.
