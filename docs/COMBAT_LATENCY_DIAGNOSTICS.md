
## 2026-07-15 combat-start latency correction

Tony's Adventurer's Lair runtime model is the behavioral benchmark: boot loads mobile templates and message tables into resident memory, `set_fighting()` links actors into a resident combat list, command handling performs only command-critical work, and `perform_violence()` walks already-resident fighters on the violence heartbeat. It does not rediscover active combat from durable storage per swing, and descriptor output flushing is not coupled to combat persistence.

The Smart MUD production symptom was a `POST /api/mud/input` for `kill spider` staying open while the first two violence pulses ran. The misleading `opening_ms=0` line only measured the call site before the opening attack and did not include response construction, heartbeat interleaving, or socket send.

Measured hot-path audit in this change identified the blocking hot-path calls as synchronous SQLite round lookups inside `_execute_attack_direct()` during each attack publish (`_round(eid)` for `combat_attack_resolved` and `combat_damage_applied`) plus unconditional INFO/stdout violence logging. On Windows, the synchronous SQLite/console path can hold the shared FastAPI/heartbeat event loop long enough for the request response to wait behind combat work. The fix removes those per-attack SQLite round reads from resident violence by using `_resident_round(eid)`, suppresses empty-pulse INFO/stdout logging, and keeps new encounters ineligible for normal violence until a later pulse after the opening response has been built.

SQLite writes still exist for the initial encounter checkpoint and participant rows, because those are the minimal durable combat-start record. Normal resident violence no longer performs round-number SELECTs for combat message event publication. Audit history remains buffered and is flushed by existing lifecycle/completion paths instead of being forced into the response-critical path.

### Before profile artifact

Tony's Windows log remains the authoritative before artifact for this production issue:

- KILL opening metric: `opening_ms=0` (not end-to-end).
- First active violence pulse: `duration_ms=5625`, `actions=1`, `messages=2`.
- Second pulse: `duration_ms=219`, `actions=2`, `messages=2`.
- Later warm pulses: about `62 ms`, `63 ms`, `47 ms`, `155 ms`.
- Request symptom: the original `POST /api/mud/input` returned only after pulse 640 and pulse 660 completed.

### After invariants

- `start_encounter()` stamps resident encounters with `eligible_violence_pulse = current_pulse + 1`.
- `process_due_rounds()` ignores active encounters whose eligibility pulse has not arrived.
- `start_player_attack()` preserves that future eligibility after the opening attack and response-critical messages are prepared.
- Resident attack event publication uses `enc.round_number` through `_resident_round()` rather than opening SQLite connections.
- World loads are idempotent for an already-ready generation: repeated selects increment `world_load_joined_existing` / `duplicate_world_loads_prevented` and do not rematerialize or rerun warmup.
- Warmup duration now uses fractional milliseconds so sub-millisecond work is not reported as `0 ms`.

### Windows status

Not manually accepted on Windows in this environment. Tony should still run the documented manual acceptance sequence and share `commandtrace`, `violenceprofile`, `eventloopstat`, and `perfstat` output from Windows.

## Resident runtime combat authority update

Live combat now follows the documented resident-authority policy: world content is prepared once per generation; online characters and active NPCs attach to one resident `Actor`; active encounters, participants, targets, queued actions, and round numbers are owned by memory; ordinary violence resolves from resident indexes and queues in-memory output/prompt packets; SQLite is used for hydration, checkpoints, audit, death durability, logout, shutdown, and administrative inspection rather than per-hit authority.

Windows manual acceptance has not been performed in this Linux environment. Operators should run `restore self`, `perfstat reset`, `violenceprofile reset`, `sqltrace combat reset`, `kill spider`, let ten rounds execute, and verify that ordinary rounds report zero SQLite operations while prompts update immediately and dirty state flushes later.

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

## Phase 15B.11 resident room occupancy

Living NPC room rendering and combat target resolution now share `MudRuntime.resident_occupants_by_room`, backed by `CombatRuntimeService.resident_actors` and entity-instance/actor-id maps. Normal KILL/ATTACK/CONSIDER/DIAGNOSE target lookup is resident-memory only: no `refresh_content()`, world reload, entity rematerialization, or SQLite target query is used in the command hot path. See `docs/RESIDENT_ROOM_OCCUPANCY.md` for the authority table, target grammar, lifecycle invariants, diagnostics, and Windows acceptance steps.

## Phase 15B.12 performance note

The flee correction stays on the resident hot path: no content refresh and no SQLite target lookup are introduced for ordinary flee, movement, attack selection, or combat messaging.

## Phase 15B.13A SCORE/WORTH hotfix combat boundary

This hotfix repairs progression row decoding for display commands only.  It does not restore SQLite target resolution, `refresh_content()` in KILL, living-entity rebuilds from SQLite, progression reads in combat rounds, or resident combat invalidation.  The focused zero-SQL KILL boundary test currently reports `gameplay_sql_before_response == 8`; this hotfix does not add progression reads to combat, but the zero-SQL boundary remains an unresolved warning in this checkout.

Tony's Windows combat timings (combat start before first pulse, ordinary pulses around 31 ms with an observed 110 ms pulse) remain the acceptance benchmark.  Windows acceptance has not been claimed until Tony reruns the manual checks on the updated branch.
