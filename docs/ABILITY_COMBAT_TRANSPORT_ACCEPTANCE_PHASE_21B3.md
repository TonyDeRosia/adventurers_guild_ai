# Phase 21B.3 combat and transport acceptance

## Current traced production path

`WebTransportAdapter.handle_message` and `TelnetTransportAdapter.handle_message` both call
`MudRuntime.handle_input`.  It routes through `MudCommandEngine._cmd_ability`, which parses
`cast magic missile <target>`, creates `AbilityExecutionRequest`, and calls
`AbilityRuntimeService.execute`.  The runtime validates through
`AbilityExecutionService.validate_ability_use`, captures targets and costs, pays costs with
`AbilityExecutionService._pay_costs`, runs the roll policy, and invokes the effect-only
`AbilityExecutionService.execute_effect_handler`.

Magic Missile's component is dispatched by `_apply_damage_component`.  Its structured receipt
now records `damage_result_id`, `ability_request_id`, canonical ability/source/target IDs,
HP-before/after, final amount, terminal status, and engagement ID when supplied by the combat
runtime.  `AbilityRuntimeService` stores this authoritative receipt in
`AbilityExecutionResult.damage_results` and in the durable idempotency summary.

When a host wires `AbilityExecutionService(death_runtime=DeathRuntimeService(...))`, terminal
receipts are passed to `link_terminal_ability_damage`, which constructs `DeathRequest`, invokes
`process_death` then `process_rewards`, and stores death/corpse/reward references in
`AbilityExecutionResult.death_results`.  The ability layer does not create a corpse, extract an
NPC, or calculate rewards.

## Honest acceptance status

`MudRuntime` now creates one canonical `DeathRuntimeService` and injects that exact instance
into `AbilityExecutionService` during `load_world()`.  Normal ability construction requires that
adapter, so terminal damage cannot silently skip Phase 20.  Browser and Telnet continue to share
the real transport boundary and renderer.  Dedicated end-to-end terminal transport fixtures are
still required; Phase 21C is therefore **not unblocked**.

Telnet tests use `TelnetTransportAdapter` in-process; they open no socket, avoid port conflicts,
and render ANSI text through `html_to_ansi_text`.  The default Telnet enablement remains unchanged.

### Phase 21B.6 replay acceptance update

Transport-neutral request identity now reaches the canonical ability request
through both production adapters.  Durable duplicate receipts retain original
damage/death references, and prompt projections refresh canonical paid
resources before rendering.  See `ABILITY_PHASE_21B_FINAL_ACCEPTANCE.md`.


## Phase 21B closure update

Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.  The current evidence matrix and scope limitation are recorded in [ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md).
