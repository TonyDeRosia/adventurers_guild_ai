# Resident Runtime Authority

Smart MUD now treats live gameplay state as resident memory first. SQLite remains the durable checkpoint and recovery store, not the authority consulted during ordinary combat commands or violence pulses.

## Tony Adventurer's Lair audit

The mandatory reference could not be cloned from this environment because GitHub HTTPS returned `CONNECT tunnel failed, response 403`; the public repository landing page was reachable through web search and confirms the Adventurer's Lair repository keeps runtime state outside version control. The implementation target is therefore the observed TBA-style resident model requested for this branch: `boot_db()` loads world records once, descriptors process input and queue output before heartbeat work, `perform_violence()` walks a resident `combat_list`, `set_fighting()` and `stop_fighting()` link/unlink resident character pointers, `hit()`/`damage()` mutate resident hit points and positions, `die()`/`raw_kill()`/`make_corpse()` perform bounded death cleanup, `point_update()` and autosave periodically save dirty characters, and normal combat never reloads rooms, mobs, objects, or round state from disk.

## Authority matrix

| Subsystem | Current runtime authority | Desired runtime authority | Persistence authority | Live SQLite path | Dirty/flush/recovery |
| --- | --- | --- | --- | --- | --- |
| World package, rooms, zones, areas | `MudRuntime.active_world` and registries | `ResidentWorldRuntime`-style loaded generation | World package files plus materialization tables | Selection/materialization only | World load once; restart reloads package |
| Entity templates, item templates | World registries | Immutable resident projections | World package | None in combat | Rebuild at world generation only |
| NPC actors | `CombatRuntimeService.resident_actors` | One resident `Actor` per live NPC | `entity_instances` checkpoints | No ordinary violence reads/writes | Dirty entity set; death/logout/shutdown flush |
| Player actors | `active_characters` plus resident actor | One resident `Actor` per online character | `characters`/`character_stats` | Login/save only | Dirty character coalescing; autosave/logout flush |
| Resources, position, lifecycle | Resident `Actor.resources` and `combat_profile` | Resident actor | Character/entity checkpoint rows | No ordinary damage writes | Mark actor dirty; death immediate transaction |
| Encounters, participants, targets, queued actions, waits, rounds | `ResidentCombatEncounter` and `ResidentCombatParticipant` | Resident encounter index | Combat tables are checkpoint/audit/legacy | No normal round discovery reads | Dirty encounters and audit buffers; completion flush |
| Combat output, prompts, condition | In-memory output queues | In-memory ordered packets | Optional scrollback later | No pre-delivery writes | Drain via async messages; optional deferred history |
| Corpses, loot, rewards, quests | Runtime lifecycle services | Resident death transition until durable boundary | SQLite durable transaction | Lethal transition only | Idempotent death/reward/corpse transaction |
| Resets | Runtime materialization services | Resident world reset profiles | Materialization audit rows | Boot/reset only | Restart can reconcile from durable rows |

## Resident world, actor, encounter, and participant architecture

`CombatRuntimeService` owns resident active combat maps and actors. Encounter rounds, participant targets, queued actions, wait pulses, contribution damage, and audit buffers live in memory. `Actor` now carries resident generation/source/owner/version metadata, and duplicate registry registration is rejected so projections cannot become competing live authorities.

## Hot-path SQLite inventory

The KILL critical path is constrained to session lookup, resident target lookup, resident encounter creation, opening attack, resident resource mutation, output packet construction, prompt snapshot, and dirty marking. The violence path begins from resident encounters and resident participants. It does not query SQLite for active encounters, participants, targets, current round, queued actions, wait state, or combat status.

## Zero-SQL invariant

After world readiness, actor hydration, and encounter creation, ordinary nonlethal violence rounds must have: zero connections, zero statements, zero commits, zero lock waits, zero character loads/saves, zero NPC hydration reads, zero entity damage writes, zero output writes, zero round-number reads, and zero action-queue operations. Compatibility combat tables remain as checkpoint/audit/legacy tables only.

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

## Phase 15B.12 movement authority

`MudRuntime.move_resident_actor()` is the canonical resident movement mutation. It updates the resident actor location, active player `room_id`, resident room occupancy index, dirty state, and movement event in one operation. Flee and normal directional movement both use this path.
