# Current Smart MUD Ability Runtime Audit (Phase 21B)

## Findings and production decision

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
