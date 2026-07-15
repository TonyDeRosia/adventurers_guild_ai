# Persistence Boundaries

## Immediate durable transactions

Immediate transactions are reserved for operations where loss, duplication, or reordering is unacceptable: economy spending, ownership-changing item transfer, death idempotency, corpse creation, final reward claim, quest reward claim, explicit admin checkpoint, logout, and shutdown.

## Deferred work

Ordinary damage, healing, regeneration, target changes, wait states, round history, command history, scrollback, and transient combat status are resident mutations. They mark actors or encounters dirty and are eligible for bounded, coalesced persistence later.

## Worker contract

A single bounded persistence worker should own durable flushes. It may coalesce duplicate actor/encounter saves, preserve per-actor ordering, retry failures, record dead-letter diagnostics, and flush on clean shutdown. It must never mutate resident combat state while writing SQLite and must not run blocking SQLite work on FastAPI request or heartbeat tasks.

## Phase 15B.9 Combat Startup Latency Hot Path Audit

Root cause removed: `CombatRuntimeService.start_player_attack()` and NPC `start_actor_attack()` still refreshed the `CombatContentRegistry` during ordinary combat startup. On Windows this meant the `kill wolf` path could rebuild combat content before producing the first visible packet. The startup path now relies on the world-load/admin `refresh_content()` boundary and performs resident actor lookup only.

Resident startup flow after READY:

```text
kill command -> visible resident target lookup -> resident player actor lookup -> resident NPC actor lookup -> resident encounter lookup/create -> resident targets -> opening attack -> in-memory packet/prompt queue
```

Removed from ordinary player/NPC combat startup:

- `refresh_content()` calls from `start_player_attack()` and `start_actor_attack()`.
- Unconditional player `Actor` reconstruction on every kill command when a resident actor already exists.
- Unconditional NPC `Actor` reconstruction on every kill command when a resident actor already exists.

SQLite policy for this phase:

- Live command traces continue to suppress encounter, participant, target, action queue, and action-consumption writes.
- Direct non-session test/admin calls may still mirror encounter/participant/action state for compatibility and audit.
- Character saves are durability checkpoints for non-active direct calls; active live characters remain coalesced through resident dirty state.
- Death lifecycle, corpse, reward, respawn, restart cancellation, command history, and final/autosave durability remain SQLite-backed by design.

Combat caches that survive ordinary gameplay now include the warmed content registry, formula engine wiring, combat stat service wiring, resident actor map, resident encounter map, resident participant target state, resident action queues, combat output queues, natural-weapon/message warmup data, and prompt/resource packet snapshots. These caches may be invalidated by equipment, buff/debuff, body, level, race/class, builder publish, world-generation changes, or explicit admin reload; ordinary attacks do not refresh them.

Instrumentation points available in traces/counters include target resolution, resident actor lookup, encounter creation, opening attack resolution, response construction, response sent, message queue latency, packet delivery latency, first/warm violence pulse duration, prompt queue/delivery counters, and resident player/NPC cache hit/miss counters.

Measured on this Linux CI container (Windows manual testing still required):

| Measurement | Observed |
| --- | ---: |
| Warmup trace focused test | 0.15 s total test runtime |
| Cold startup visible packet | not Windows-verified |
| Warm startup visible packet | not Windows-verified |
| First violence pulse | regression test environment observed ~2700-2900 ms in one legacy direct test path |
| Prompt delivery | instrumented via `prompt_delivery_ms`; not Windows-verified |
| Packet delivery | instrumented via `combat_message_delivery_latency_ms`; not Windows-verified |

Remaining limitations: target visibility can still depend on the broader room/entity runtime, direct compatibility calls can still persist audit rows synchronously, and Windows manual testing is required before declaring the player-visible `kill wolf` latency fixed.
