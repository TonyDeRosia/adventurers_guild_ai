# Phase 21B.5 Production Acceptance

## Current focused evidence

`tests/test_phase21b5_production_acceptance.py` constructs a normal
`MudRuntime`, loads `shattered_realms`, and uses a production-materialized
NPC.  It submits terminal Magic Missile through `WebTransportAdapter` and
`TelnetTransportAdapter`, not a private ability handler.

The Browser case verifies the shared `DeathRuntimeService` identity and the
authoritative command receipt: Magic Missile's damage receipt contains the
request and target identifiers plus authoritative HP transition, and its death
receipt links the damage, credited killer, corpse, and extraction.  The corpse
is queried from the canonical room projection after extraction.  The Telnet
case verifies the same runtime receipt is preserved in transport metadata and
that rendered output/prompt contain no HTML.

## Defects repaired by this acceptance slice

* Normal command casts passed persisted character IDs into combat while the
  resident combat map used `character:` IDs.  Combat now normalizes active
  persisted IDs at its boundary; Magic Missile no longer returns a successful
  zero-damage result.
* Command and Telnet responses previously discarded the authoritative ability
  receipt.  Both transport paths now retain it without reconstructing gameplay
  state from narrative text.

## Remaining acceptance work

Phase 21B is **not yet complete**.  Durable restart idempotency, duplicate
transport submission, nonterminal/failure coverage, event-chain assertions,
heartbeat assertions, and normalized Browser/Telnet parity remain to be added
before Phase 21C can be considered unblocked.
