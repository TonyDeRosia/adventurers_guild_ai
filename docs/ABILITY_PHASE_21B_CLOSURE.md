# Phase 21B Closure

## Status

**Phase 21B — IN PROGRESS.**  The scope is the canonical
runtime and the six migrated abilities; it does **not** claim completion of the
73-ability catalog.  **Phase 21C — NOT UNBLOCKED.**

The final acceptance slice uses the normal Browser/Telnet adapters and
`MudRuntime`; it does not introduce an acceptance-only gameplay path.  Armor
is not selected because the shipped player-class catalog has no `adventurer`
class although Armor is authored for that class.  The production-supported
alternative is **Set Camp**.

| Requirement | Implementation location | Test location and exact test | Result | Remaining limitation |
|---|---|---|---|---|
| Browser insufficient mana | `engine/abilities.py` | `tests/test_phase21b7_closure_acceptance.py::test_transport_insufficient_mana_is_structured_and_non_mutating[WebTransportAdapter]` | PASS | None |
| Telnet insufficient mana | `engine/abilities.py`, `smart_mud/transport.py` | `test_transport_insufficient_mana_is_structured_and_non_mutating[TelnetTransportAdapter]` | PASS | None |
| Insufficient-mana parity | `smart_mud/transport.py` | `test_insufficient_mana_transport_parity` | PASS | None |
| Browser wait rejection | `engine/abilities.py` | `test_transport_wait_rejection_precedes_payment[WebTransportAdapter]` | PASS | None |
| Telnet wait rejection | `engine/abilities.py`, `smart_mud/transport.py` | `test_transport_wait_rejection_precedes_payment[TelnetTransportAdapter]` | PASS | None |
| Wait semantics parity | `engine/abilities.py` | `test_transport_wait_rejection_precedes_payment` | PASS | None |
| Browser non-damaging ability | `engine/mud_commands.py`, `engine/abilities.py` | `test_set_camp_transport_parity_and_duplicate_is_non_consequential` | PASS | Set Camp rather than Armor, for documented authored-class constraint |
| Telnet non-damaging ability | `smart_mud/transport.py` | `test_set_camp_transport_parity_and_duplicate_is_non_consequential` | PASS | Same |
| Non-damaging parity and replay | `engine/abilities.py` | `test_set_camp_transport_parity_and_duplicate_is_non_consequential` | PASS | None |
| Terminal event chain/linkage | `engine/abilities.py`, `engine/death_runtime.py` | `test_terminal_event_chain_links_death_and_suppresses_duplicate_consequences` | PASS | None |
| Duplicate consequence suppression | `engine/abilities.py` | `test_terminal_event_chain_links_death_and_suppresses_duplicate_consequences` | PASS | None |
| Dead-target heartbeat prevention | `engine/combat_runtime.py` | `test_terminal_event_chain_links_death_and_suppresses_duplicate_consequences` | PASS | None |
| Attacker combat normalization | `engine/mud_runtime.py`, `engine/combat_runtime.py` | `test_terminal_event_chain_links_death_and_suppresses_duplicate_consequences` | PASS | None |
| Focused Phase 18–21B regression | Existing regression modules | Focused command in this document's validation record | NOT COMPLETE | Final terminal run not captured |
| Full repository suite | Repository test suite | `pytest -q` | NOT COMPLETE | Runner detached before a final result; early failures require classification |

## Observed terminal event chain

`ability.requested` → `ability.definition.resolved` →
`ability.target.resolved` → `ability.cost.calculated` →
`ability.resource.paid` → `ability.effect.started` →
`ability_damage_applied` → `death.requested` → `death.claimed` →
`death.corpse.created` → `death.npc.extracted` →
`death.foundation.completed` → `death.rewards.completed` →
`death.completed` → `ability.damage.completed` → `ability.death.completed`.

`ability_request_id`, `ability_id`, `damage_result_id`, `death_id`,
`engagement_id`, and `world_id` are preserved through the death events.  A
stable duplicate identity emits only `ability.duplicate_ignored`; it returns
the original damage/death receipts and does not republish the listed
consequences.

### Phase 21B12 verification

Completed focused verification for compact SKILLS presentation, canonical generic
NPC target resolution (including Forest Wolf and stable ordinals), targetability
catalog validation, safe missing targets, idempotent corpse creation, absolute
random 180--300 second NPC expiry, legacy migration, and SQLite restart expiry
persistence.  No Phase 21C work is included.  Browser/Telnet semantic parity is
covered by the existing production transport acceptance tests; manual server
observation remains a documented limitation.
