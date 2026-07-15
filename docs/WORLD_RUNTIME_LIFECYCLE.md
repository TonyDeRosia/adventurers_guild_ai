
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

## Resident runtime combat authority update

Live combat now follows the documented resident-authority policy: world content is prepared once per generation; online characters and active NPCs attach to one resident `Actor`; active encounters, participants, targets, queued actions, and round numbers are owned by memory; ordinary violence resolves from resident indexes and queues in-memory output/prompt packets; SQLite is used for hydration, checkpoints, audit, death durability, logout, shutdown, and administrative inspection rather than per-hit authority.

Windows manual acceptance has not been performed in this Linux environment. Operators should run `restore self`, `perfstat reset`, `violenceprofile reset`, `sqltrace combat reset`, `kill spider`, let ten rounds execute, and verify that ordinary rounds report zero SQLite operations while prompts update immediately and dirty state flushes later.

## Phase 15B.11 resident room occupancy

Living NPC room rendering and combat target resolution now share `MudRuntime.resident_occupants_by_room`, backed by `CombatRuntimeService.resident_actors` and entity-instance/actor-id maps. Normal KILL/ATTACK/CONSIDER/DIAGNOSE target lookup is resident-memory only: no `refresh_content()`, world reload, entity rematerialization, or SQLite target query is used in the command hot path. See `docs/RESIDENT_ROOM_OCCUPANCY.md` for the authority table, target grammar, lifecycle invariants, diagnostics, and Windows acceptance steps.
