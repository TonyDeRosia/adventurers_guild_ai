# Phase 21B Representative Acceptance Transcript

* Magic Missile: `CAST_COMMAND` resolves its canonical ID and target, validates
  legacy mana cost, pays once through RuntimeResourceService, dispatches its
  damage component through combat, and emits ability events. Terminal combat
  damage proceeds to the existing Phase 20 death/corpse/reward pipeline.
* Insufficient mana: validation returns the existing required/available mana
  diagnostics before effect dispatch; preview performs no mutation.
* Armor, Detect Magic and Strength retain the existing ability effect path and
  persisted affect behavior through the same runtime service.
* `build campfire` and `set camp` definitions use the same registry and effect
  contract; their effects call the canonical survival service rather than
  creating persistence state in a command handler.
* A repeated request ID/idempotency key returns `DUPLICATE_IGNORED`: one
  successful request is the only one allowed to pay, damage, apply an effect or
  improve proficiency.

Browser and Telnet continue to render `CommandResult` messages after the same
runtime result; no transport-specific gameplay path was introduced.

## Canonical lifecycle acceptance

The runtime receipt now records request identity, validation, resolved targets,
calculated and paid costs, roll/proficiency fields, cooldown policy, structured
effect and damage results, messages, and failure information. The compatibility
instant executor is no longer invoked by the request boundary.

## Phase 21B.2 reliability evidence

The runtime now has an injectable percent/random provider, durable SQLite
idempotency (30-day bounded retention), and receipt-level wait-state policy data.
`tests/test_phase21b2_runtime_reliability.py` recreates the service against the same
database and proves a duplicate is ignored without another execution.
