# Ability Runtime Reliability — Phase 21B.2

## Implemented boundary

`AbilityRuntimeService` accepts an injected `AbilityRandomProvider`. Its production
provider returns inclusive percent rolls (1–100), while acceptance tests inject a
sequence provider. Success policies are recorded in the execution receipt:
`ALWAYS_SUCCEEDS`, `LEARNED_PERCENT_ROLL`, `OPPOSED_ROLL`,
`EFFECT_HANDLER_DEFINED`, and `PASSIVE_NO_ROLL`. Existing migrated content defaults
to `ALWAYS_SUCCEEDS`, preserving historical behavior.

The existing actor `wait_state` field remains the sole wait-state representation.
The runtime rejects a waiting actor before resource payment or effect dispatch and,
when a definition requests a duration, applies it once on effect commit. A zero
configured duration is explicitly represented in the receipt.

Committed requests are stored in `ability_execution_ledger`, uniquely scoped by
world, actor, life generation, and idempotency key. The JSON summary contains only
stable receipt primitives. Retention is 30 days and expired rows are purged during
commit. Preview and validation failures are not committed.

The historical instant executor remains compatibility-only; canonical command paths
use `execute_effect_handler`, which is effect-only and cannot pay costs, mutate
cooldowns, or improve proficiency.

## Evidence and limitations

`tests/test_phase21b2_runtime_reliability.py` proves preview/duplicate roll safety
and cross-runtime SQLite duplicate suppression. Browser/Telnet share the command
runtime request path; their comprehensive transport and terminal-death integration
coverage remains outside this narrowly scoped reliability patch. Damage/death
receipts continue to expose the structured results returned by the existing combat
and Phase 20 services.

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
