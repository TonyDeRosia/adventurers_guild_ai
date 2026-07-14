# SMART MUD SCORE/WORTH Latency Audit

Date: 2026-07-14. Environment: Linux container in `/workspace/smartmud`; Windows manual acceptance remains to be run on Windows and was not claimed here.

## Root cause

The remaining visible five-second symptom was a backend/read-path issue compounded by cursor reporting:

* `worth` built a full `CharacterDisplaySnapshot`, including progression, currency, combat, carrying, effects, inventory, equipment, and rendering-only data, although WORTH only displays currencies/progression-style value data.
* Read-only commands could still call the character save coordinator when a resident character was dirty from earlier mutations, violating the side-effect-free SCORE/WORTH contract.
* Currency display constructed an `EconomyService` from the display adapter when no runtime service was supplied.
* The web response normalized `async_cursor` from `result.view.async_cursor`; prompt-only command responses did not include that field, so the frontend could receive `0` even after the server cursor had advanced.

No fixed five-second sleep was found in SCORE/WORTH command handlers. The 5s async poll cadence remains only the idle poll interval and is not required for direct command display.

## Changes implemented

* Added runtime-owned cached EconomyService and ProgressionService instances.
* Added source-version-aware in-process display and worth snapshot caches keyed by actor, world, level/xp/currency/location/equipment/inventory/effect counts, and actor source-version metadata.
* Added `CharacterWorthSnapshot` so WORTH consumes a lightweight progression/currency projection instead of full score display state.
* Changed SCORE to continue requesting exactly one `CharacterDisplaySnapshot` per command invocation; unchanged repeated requests reuse the immutable cached snapshot.
* Changed WORTH to avoid `CharacterDisplaySnapshot` entirely.
* Changed read-only command processing to skip character saves, preserving pending dirty state for the next mutating/final save.
* Added prompt-only command responses' `async_cursor` and kept web normalization from resetting the frontend cursor to zero.
* Added optional `[mud-latency]` debug lines gated by `MudRuntime.performance_debug`.

## Measured command timings

Command timings were measured with monotonic `time.perf_counter()` for five direct command-handler runs each. These are Linux container timings against a resident synthetic Kraevok-like character and are not Windows acceptance timings.

| Command | Runs (ms) | Min | Max | Mean | Median | 95th percentile |
|---|---:|---:|---:|---:|---:|---:|
| `eq` | 1.940, 1.960, 2.189, 2.671, 4.351 | 1.940 | 4.351 | 2.622 | 2.189 | 4.351 |
| `score` | 3.258, 3.697, 4.089, 4.591, 4.741 | 3.258 | 4.741 | 4.075 | 4.089 | 4.741 |
| `sc` | 3.427, 4.154, 5.119, 5.129, 5.507 | 3.427 | 5.507 | 4.667 | 5.119 | 5.507 |
| `score compact` | 3.257, 3.306, 3.578, 3.605, 3.795 | 3.257 | 3.795 | 3.508 | 3.578 | 3.795 |
| `score full` | 3.577, 3.981, 4.839, 5.179, 5.744 | 3.577 | 5.744 | 4.664 | 4.839 | 5.744 |
| `worth` | 1.202, 1.279, 1.434, 1.597, 2.330 | 1.202 | 2.330 | 1.568 | 1.434 | 2.330 |
| `combatstats` | 307.598, 314.679, 320.264, 334.158, 382.498 | 307.598 | 382.498 | 331.839 | 320.264 | 382.498 |
| `attributes` | 1.866, 1.939, 1.979, 2.029, 2.030 | 1.866 | 2.030 | 1.969 | 1.979 | 2.030 |

## Operation counts from focused instrumentation/tests

For one SCORE request after character entry:

* SQLite queries: 0 from the display snapshot path in the focused resident-character test.
* Character loads: 0.
* Character saves: 0.
* CharacterDisplaySnapshot builds requested by SCORE command: 1.
* CombatStatService/CharacterAttributeService/RuntimeEffectService/RuntimeResourceService calls from score renderer after snapshot creation: 0; the renderer formats the immutable document/view model only.
* Equipment projections: 1 list projection within snapshot key/build.
* Inventory projections: 1 list projection within snapshot key/build.
* Effect projections: 1 visible effect projection reused for effects and active affects.
* Formula traces: 0 for normal SCORE; detailed diagnostics remain gated by detailed/admin mode.
* HTML render passes in command path: 0 for direct MUD narrative rendering.
* Plain/MUD render passes in command path: 1.

For one WORTH request after character entry:

* SQLite queries: 0 in the lightweight resident-character focused test.
* Character loads: 0.
* Character saves: 0.
* CharacterDisplaySnapshot builds: 0.
* Progression/economy projection: 1 lightweight `CharacterWorthSnapshot` build; repeated unchanged WORTH hits the worth cache.
* Combat/equipment/effect rendering data: 0 by WORTH command.
* Plain/MUD render passes in command path: 1.

## Cache invalidation behavior

The snapshot keys include character/actor ID and world ID. Cache misses occur when source-version metadata changes or when the resident character's level, xp, gold, room, inventory count, equipment count, effect count, or relevant actor source versions change. Runtime mutating commands invalidate the display snapshot service for that character after a successful non-read-only command save path. Current-resource-only prompt updates continue to be represented by prompt snapshots and do not force a full combat display recomputation unless the resident source-version key changes.

## Lock and event-loop findings

SCORE/WORTH run synchronously but now complete quickly in the local handler benchmarks. Broad runtime/database locks are not held during document formatting. SQLite command-history/scrollback writes remain synchronous but are timed separately and were not observed as multi-second blockers in these focused runs. Read-only SCORE/WORTH no longer enter character save persistence.

## Optional debug logging

Set `runtime.mud_runtime.performance_debug = True` (or set the attribute on the constructed `MudRuntime`) before running commands. Debug output is emitted only when enabled, for example:

```text
[mud-latency] command=score total_ms=...
[mud-latency] history_ms=...
[mud-latency] queries=0 formulas=0 cache_hit=true|false
```

## Windows manual acceptance steps

1. Start the backend on Windows and enter Kraevok.
2. Enable performance debug by setting `runtime.mud_runtime.performance_debug = True` in the local startup/debug hook before issuing commands.
3. Run `eq` five times.
4. Run `score` five times.
5. Run `worth` five times.
6. Run `score compact`.
7. Run `score full`.
8. Equip or remove an item.
9. Run `score` again.
10. Apply/remove an effect.
11. Run `score` again.

Expected: no fixed five-second delay; SCORE should appear in less than approximately half a second under normal local conditions; WORTH should appear nearly immediately; cache hits should be faster than first render; equipment/effect/currency/progression mutations should invalidate appropriate caches; no character saves or character reloads should be logged for SCORE/WORTH; async polling should use `after=<latest cursor>` rather than staying at zero; output content should remain correct.
