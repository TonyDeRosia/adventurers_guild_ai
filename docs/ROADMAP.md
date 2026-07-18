
## Phase 11D1

Canonical survival needs, consumables, portions, freshness foundations, SQLite state, commands, and Builder collections are introduced. Phase 11D2 owns rest/sleep/shelter/camp systems.

## Phase 20B — Kill Rewards, Player Death Penalties, Quest Credit, and Respawn

Implemented as a ledger-backed reward/disposition extension to the Phase 20A death foundation. The next recommended scope is **Phase 21 — Combat Commands and Physical Skills**: flee, assist, rescue, kick, bash, backstab, bandage, whirlwind, and other customized physical abilities, with every damaging ability routed through Ability Runtime → Target Resolution → Resource/Wait Validation → DamageService → DeathRuntimeService.

## Phase 21B — Canonical Ability Runtime

A transport-neutral `AbilityRuntimeService` now accepts typed requests from
cast and skill command routes and is available to NPC AI, scripts and item
activation callers. It delegates to the existing resource, target, effect,
combat and death authorities and bounds duplicate retries with an idempotency
ledger. Next: **Phase 21C — Core Physical Combat Commands**: flee, assist,
rescue, kick and bash through this runtime.
