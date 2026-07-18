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
