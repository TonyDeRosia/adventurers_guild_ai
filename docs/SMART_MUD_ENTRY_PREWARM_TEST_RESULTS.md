# Smart MUD Entry Prewarm Test Results

## Focused results

Focused checks run in this environment:

- `python -m py_compile engine/projection_cache.py engine/mud_runtime.py engine/mud_commands.py smart_mud/world_registry.py` passed.
- `pytest tests/test_score_worth_latency_backend.py tests/test_smart_mud_runtime.py -q` was run and passed.

## Full-suite counts

Full suite was run with `pytest -q`. Result in this Linux container: **1959 passed, 432 failed, 17 skipped, 20 warnings in 704.51s**. The failures are broad legacy/builder/web-runtime failures outside the focused entry/prewarm/autosave slice; examples include missing builder templates/content-pack files and legacy campaign/web-runtime expectation mismatches. No Windows manual run was performed.

## Entry timing

Runtime counters added for:

- `character_entry_total_ms`
- `actor_registration_ms`
- `essential_snapshot_ms`
- `initial_room_render_ms`
- `prompt_render_ms`

The focused suite validates import/runtime wiring; live timing should be read from developer diagnostics during manual/runtime acceptance.

## Warm-up timing and cache metrics

Runtime counters added for:

- `warmup_queue_ms`
- `warmup_build_ms`
- `warmup_cache_hits`
- `warmup_cancelled`
- `stale_task_rejected`
- `projection_cache_hits`
- `projection_cache_misses`
- `projection_invalidations`

Background warm-up is best-effort and starts only after successful character entry when an event loop is running.

## Invalidation counts

Projection invalidations are centralized in `ProjectionCacheRegistry.INVALIDATION_GRAPH`. Mutating command boundaries call `mark_character_dirty`, which increments dirty state and invalidates targeted projections by reason.

## Autosave counts

Runtime counters added for:

- `autosave_attempts`
- `autosave_successes`
- `autosave_skipped_clean`
- `autosave_failures`

`ActiveCharacterAutosaveService.scan_once()` scans active resident characters, skips clean characters, and saves dirty characters through the existing coordinated save method.

## Memory/cache counts

Private projection cache limits:

- maximum active-character projection cache entries: 256
- maximum entries per character: 32
- maximum warm-up queue depth: 64
- maximum concurrent warm-up tasks: 2

Quit/logout evicts private per-character projection cache entries and cancels pending warm-up work.

## Manual Windows status

Not performed. Manual acceptance steps for Windows:

1. Start the desktop app.
2. Log in.
3. Remain at Character Select.
4. Confirm no full character data loads.
5. Enter Kraevok.
6. Observe entry timing.
7. Wait a few seconds for background warm-up.
8. Run `score`.
9. Run `worth`.
10. Run `equipment`.
11. Equip/remove an item.
12. Run `score` again.
13. Change currency if a safe test command exists.
14. Run `worth` again.
15. Quit.
16. Remain at Character Select.
17. Re-enter.
18. Close app cleanly.

Expected: one character load on entry; SCORE/WORTH/equipment prewarm; no fixed lag; targeted invalidation after mutation; no repeated SQLite reloads for active characters; autosave skips clean state and saves dirty state; quit flushes once and evicts private caches; re-entry loads fresh persisted state.

## Remaining issues

- Full legacy suite has unrelated failures in broad builder/campaign/web-runtime areas in this environment.
- Windows desktop acceptance was not performed.
- Reconnect grace remains disabled by default; no permanent global character cache was added.
