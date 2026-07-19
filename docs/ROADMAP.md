
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

### Phase 21B update

Canonical ability requests now execute the shared lifecycle directly and return
a structured execution receipt. Phase 21C remains a separate future phase.

> **Phase 21B.3 status (2026-07-18):** Magic Missile structured damage receipts now preserve
> request/source/target/HP linkage and durable duplicate references.  Terminal death linkage is
> injectable but is not wired through normal `MudRuntime`; transport terminal acceptance remains
> unproven, so Phase 21C is not unblocked.

### Phase 21B.6 replay acceptance update

Transport-neutral request identity now reaches the canonical ability request
through both production adapters.  Durable duplicate receipts retain original
damage/death references, and prompt projections refresh canonical paid
resources before rendering.  See `ABILITY_PHASE_21B_FINAL_ACCEPTANCE.md`.


## Phase 21B closure update

Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.  The current evidence matrix and scope limitation are recorded in [ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md).

### Phase 21B12 verification

Completed focused verification for compact SKILLS presentation, canonical generic
NPC target resolution (including Forest Wolf and stable ordinals), targetability
catalog validation, safe missing targets, idempotent corpse creation, absolute
random 180--300 second NPC expiry, legacy migration, and SQLite restart expiry
persistence.  No Phase 21C work is included.  Browser/Telnet semantic parity is
covered by the existing production transport acceptance tests; manual server
observation remains a documented limitation.
