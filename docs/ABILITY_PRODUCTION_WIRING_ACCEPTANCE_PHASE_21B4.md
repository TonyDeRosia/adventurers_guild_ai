# Phase 21B.4 production wiring acceptance

## Production composition

`MudRuntime.__init__` creates the canonical `CombatRuntimeService` and then one
`DeathRuntimeService`, backed by the runtime SQLite database.  `load_world()`
creates `AbilityExecutionService` with that exact instance and sets
`require_death_runtime=True`.  The ability service therefore cannot silently
use a no-op terminal adapter in a normal playable runtime.

The terminal path is:

```text
MudCommandEngine -> AbilityRuntimeService -> Damage receipt
  -> AbilityExecutionService.link_terminal_ability_damage
  -> MudRuntime.death_runtime.process_death -> process_rewards
```

The adapter only maps Phase 20 callbacks to existing `MudRuntime` operations:
combat cleanup, corpse creation, NPC extraction, and a death-cry event.  Corpse
creation and extraction remain owned by `DeathRuntimeService`; reward formulas
remain owned by Phase 20B.  Browser and Telnet adapters both retain their
existing shared `MudRuntime.handle_input` boundary.

## Safeguard and scope

Normal-world construction now raises if a death adapter is missing, while
isolated ability/unit service construction remains supported by the default
`require_death_runtime=False`.  The focused composition test proves identity,
not merely adapter capability.  This change adds no migrations or abilities.

Transport-level terminal acceptance, durable restart, and parity evidence still
need dedicated deterministic fixtures before Phase 21C can honestly be marked
unblocked.

### Phase 21B.6 replay acceptance update

Transport-neutral request identity now reaches the canonical ability request
through both production adapters.  Durable duplicate receipts retain original
damage/death references, and prompt projections refresh canonical paid
resources before rendering.  See `ABILITY_PHASE_21B_FINAL_ACCEPTANCE.md`.


## Phase 21B closure update

Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.  The current evidence matrix and scope limitation are recorded in [ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md).
