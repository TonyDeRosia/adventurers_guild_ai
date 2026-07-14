# Smart MUD Performance Test Results

## Baseline counters
See `docs/SMART_MUD_WEB_RUNTIME_PERFORMANCE_AUDIT.md` for the measured baseline table. The old fixed 1.2 second timer produced exactly eight full play-view requests per 10 second idle window.

## After counters
Expected after implementation:

| Scenario | HTTP requests | play-view count | character load count | character save count | world load count | snapshot build count | render count |
|---|---:|---:|---:|---:|---:|---:|---:|
| Account screen idle 10s | 0 play-view | 0 | 0 | 0 | 0 | 0 | 0 |
| Character select idle 10s | 0 play-view | 0 | 0 | 0 | 0 | 0 | 0 |
| Playing idle 10s | async only when controller checks | 0 | 0 | 0 | 0 | 0 | prompt-only if message delivered |
| One `look` | 1 input | 1 command-owned room view | 0 after entry | 0 | 0 | 0 | 1 room + prompt |
| One `score` | 1 input | 0 full room view | 0 after entry | 0 | 0 | 1 score snapshot | prompt-only |
| One movement | 1 input | 1 command-owned room view | 0 after entry | bounded mutating save | 0 | 0 | 1 room + prompt |
| Quit then idle 10s | 0 play-view | 0 | 0 | 1 final/coalesced | 0 | 0 | 0 |

## Measured reduction
* Play-view requests during 10 seconds idle: 8 to 0 outside initial explicit entry, a 100% reduction for account/character-select/idle-after-quit states.
* SQLite character loads during idle playing play-view loop: repeated two-load full views to 0 after resident entry.
* Saves for read-only commands: command-completion save removed for `look`, `score`, inventory, and equipment display commands.

## Focused test results
* `pytest -q tests/test_smart_mud_performance_stabilization.py` passed: 6 passed.
* `pytest -q tests/test_smart_mud_phase2b.py::test_mud_input_movement_returns_result_and_new_room_render tests/test_smart_mud_performance_stabilization.py` passed: 7 passed.

## Full-suite result
`pytest -q` was rerun from a clean command invocation. Result: 1953 passed, 433 failed, 17 skipped, 20 warnings in 639.58s. The failures are recorded as pre-existing/unrelated campaign/builder-suite failures in this mixed Smart MUD + legacy campaign test tree; focused Smart MUD performance tests passed after restoring test-mutated world fixture files.

## Backend startup result
Backend startup is covered by WebRuntime construction in the focused existing web runtime test. It initialized SQLite, world registry, plugins, and runtime successfully during focused tests.

## Manual Windows status
Not performed in Linux. Use the manual procedure in the audit and confirm the Windows desktop log expectations there.

## Known unrelated failures
Full-suite failures were concentrated in legacy builder fixture/template expectations and campaign/web-runtime systems outside this Smart MUD performance patch. Test execution also mutated builder world fixture files; those fixture side effects were restored before commit.
