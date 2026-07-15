
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
