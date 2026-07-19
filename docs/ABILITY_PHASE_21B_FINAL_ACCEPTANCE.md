# Phase 21B Final Acceptance

## Phase 21B.6 transport replay evidence

The production `TransportMessage` now accepts optional transport-neutral
`request_id` and `idempotency_key` metadata.  Browser and Telnet adapters pass
that identity unchanged to `MudRuntime.handle_input`; the shared parser creates
the canonical `AbilityExecutionRequest`.  Player command text is unchanged.

`tests/test_phase21b6_final_acceptance.py` constructs normal `MudRuntime`,
loads `shattered_realms`, materializes a persistent NPC, and uses the real web
and Telnet adapters.  Terminal replay returns `DUPLICATE_IGNORED` and preserves
the original damage/death receipt lists; it does not pay mana again or restore
the extracted NPC.  The restart case creates a new `MudRuntime` against the
same SQLite directory and proves the durable ledger returns the same receipt.

The repair also refreshes the resident character from canonical resource rows
before rendering the response.  This fixes the immediate prompt/projection
showing stale pre-cast mana while the restart correctly showed paid mana.

Telnet's authoritative result remains at
`response.metadata['result']['ability_result']`; Browser uses the same field.
Telnet rendering remains ANSI/plain text and never serializes browser HTML.

## Scope and status

The Phase 21B closure matrix is now complete.  See
[ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md) for the passing
transport failure, non-damaging, event-chain, duplicate, and heartbeat evidence.
Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.


## Phase 21B closure update

Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.  The current evidence matrix and scope limitation are recorded in [ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md).
