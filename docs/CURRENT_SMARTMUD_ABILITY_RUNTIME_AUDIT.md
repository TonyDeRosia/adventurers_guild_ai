# Current Smart MUD Ability Runtime Audit (Phase 21B)

## Findings and production decision

### Before and after call graph

**Before:** `MudCommandEngine._cmd_use_ability` →
`AbilityRuntimeGateway.execute_result` → `AbilityRuntimeGateway.execute` →
`AbilityExecutionService.start_ability` → `execute_instant_ability`.  The
last method performed validation, target resolution, cost payment, cooldown,
effect invocation and proficiency improvement as one opaque operation.

**After:** cast and multiword skill command parsing →
`AbilityExecutionRequest` → `AbilityRuntimeService.execute` → definition
resolution → `validate_ability_use`/`AbilityTargetResolver` →
`SpellResourceCostService` calculation → `RuntimeResourceService` payment →
centralized recorded roll → `execute_effect_handler` → combat runtime
(`DamageService` authority) → Phase 20 death runtime when terminal →
proficiency improvement → cooldown persistence → event publication → command
result rendering.  `execute_effect_handler` is effect-only and cannot charge
costs, start generic cooldowns, or improve proficiency.

The exact six routes share that post-request graph: `cast armor`, `cast detect
magic`, `cast magic missile`, and `cast strength` originate in
`_cmd_use_ability`; `build campfire` and `set camp` originate in the command
router's multiword ability route.  Damage is absent for the five non-damaging
routes.  Magic Missile's handler calls `_apply_damage_component`, which
submits a `CombatActionRequest`; combat owns hostile engagement and invokes
the configured death runtime for terminal results.  Browser and Telnet both
render the resulting `CommandResult`, rather than running a separate gameplay
path.

Before Phase 21B, `MudCommandEngine._cmd_use_ability` parsed `cast` input and
called `AbilityRuntimeGateway`, while multiword survival commands were also
recognized by the survival command handler.  Both ultimately use
`AbilityExecutionService` for authored ability effects where available, but the
entry contract was command-shaped and did not provide an AI/item/script-safe
request or idempotency boundary.

`AbilityExecutionService` already owns the useful production authorities:
registry loading, grants/proficiency, canonical target resolution, legacy spell
mana calculation (`SpellResourceCostService`), resource mutation
(`RuntimeResourceService`), durable cooldown records, effect instances and
canonical damage dispatch.  Magic Missile's damage component reaches the
injected combat runtime, whose terminal result is handled by the Phase 20 death
runtime; the ability handler does not create corpses or rewards.

## Audit answers

* Cast and skill routes previously had separate parsing/front-door code; common
  ability validation and effects were largely in `AbilityExecutionService`.
* Costs are checked during validation and paid by `RuntimeResourceService`;
  migration does not pay during preview.  Existing cost timing remains defined
  by ability metadata.
* Cooldowns are durable in `actor_ability_cooldowns`; waits/combat remain owned
  by the Phase 19 combat runtime.  Proficiency improvement is centralized in
  `attempt_proficiency_improvement`.
* Historical command retries had no typed idempotency key.  The new bounded
  runtime ledger prevents a repeated committed request key from charging,
  damaging, applying effects, or improving twice in one process lifetime.
* NPC, item and script callers can now construct the same typed request; no AI
  decision-making or item activation migration is claimed in this phase.
* Existing persistence remains authoritative for resource, affect, cooldown,
  combat, damage and death projections.  No second persistence overlay was
  added.

## Phase 18A regression conclusion

The spellup assertion was correct: Magic Missile is intentionally learnable
and appears in `spells`, but is offensive and therefore must not appear in the
self-buff `spellup` narrative.  The regression was presentation leakage, not
an eligibility or fixture-state issue.  The command now retains the offensive
classification in diagnostics while omitting it from the player-facing output.

## Phase 21B.3 trace update

The verified input path is `WebTransportAdapter.handle_message` or
`TelnetTransportAdapter.handle_message` -> `MudRuntime.handle_input` ->
`MudCommandEngine._cmd_ability` -> `AbilityExecutionRequest` ->
`AbilityRuntimeService.execute` -> `AbilityExecutionService.execute_effect_handler` ->
`AbilityExecutionService._apply_damage_component`.  Structured Magic Missile damage receipts
are retained by `AbilityExecutionResult.damage_results`.  Terminal delegation is available only
when a `DeathRuntimeService` is injected; normal `MudRuntime` does not yet provide that wiring.

### Phase 21B.6 replay acceptance update

Transport-neutral request identity now reaches the canonical ability request
through both production adapters.  Durable duplicate receipts retain original
damage/death references, and prompt projections refresh canonical paid
resources before rendering.  See `ABILITY_PHASE_21B_FINAL_ACCEPTANCE.md`.


## Phase 21B closure update

Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.  The current evidence matrix and scope limitation are recorded in [ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md).
