
## 2026-07-15 ready-generation idempotency

World activation now treats an already-loaded, combat-ready world generation as resident state. Calls from world select, character list, browser initialization, or session restoration that name the active ready world attach to the existing generation rather than calling materialization and combat warmup again.

Counters added by the runtime path:

- `world_load_requests`
- `world_load_actual`
- `world_load_joined_existing`
- `entity_materialization_runs`
- `combat_warmup_runs`
- `duplicate_world_loads_prevented`

Required invariant for one loaded generation: package load, entity materialization, combat warmup, and `world_loaded` hook each run once. Concurrent multi-process protection is not claimed here; this change covers repeated requests in one resident runtime.
