# Smart MUD Ability Runtime (Phase 21B)

`engine.abilities.AbilityRuntimeService` is the canonical public boundary for
active abilities.  It accepts `AbilityExecutionRequest`, performs preview or
execution, and returns structured `AbilityExecutionResult`.  Browser/Telnet
commands only parse text, resolve an ability ID, create this request, and render
the returned message.

## Contract

Requests include stable request/actor/world/ability IDs, invocation type
(`CAST_COMMAND`, `SKILL_COMMAND`, `ITEM_ACTIVATION`, `NPC_AI`, `SCRIPT`,
`PASSIVE_TRIGGER`, `ADMIN_TEST`), typed targets, source IDs, tick/engagement
metadata, preview/debug flags and an idempotency key.  Validation and cost
previews are explicit, non-mutating operations.

The runtime delegates common work to the existing production
`AbilityExecutionService`: definition/ownership validation, target resolution,
spell costs, resource payment, proficiency progression, durable cooldowns,
effect handlers, and DamageService/combat/death integration.  Effects remain
specialized; they must not independently pay common costs, grant proficiency,
or create corpses/rewards.

## Validation and idempotency

The underlying deterministic validation order is actor, definition/grant,
target, materials, resources and cooldown.  The request wrapper exposes stable
failure codes where available and retains detailed legacy traces.  A successful
request is recorded by `idempotency_key` (or request ID) in a bounded in-memory
ledger; a retry returns `DUPLICATE_IGNORED` and publishes
`ability.duplicate_ignored`.

## Next phase

Phase 21C should route flee, assist, rescue, kick and bash through this same
contract before broad spell migration.

## Canonical orchestration update

`AbilityRuntimeService.execute` owns the active-request lifecycle: idempotency,
definition and non-mutating validation, target/cost receipt capture, payment,
roll record, effect-only invocation, improvement, cooldown, and structured
result construction. `AbilityExecutionService.execute_effect_handler` is the
legacy-effect adapter; direct `execute_instant_ability` remains compatibility
only and is not the production command path.

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
