# Phase 15B.13A Runtime Authority Audit

Smart MUD now treats SQLite as durability and the resident runtime as live authority. The table below records the audited gameplay concepts and the expected boundary.

| Concept | Canonical authority | Duplicate authorities removed/blocked | Consumers | Persistence layer | Synchronization path |
| --- | --- | --- | --- | --- | --- |
| Player location | `MudCharacter.room_id` plus resident `Actor.identity.current_location`, updated only by `move_resident_actor` | Direct command mutation and combat hot-path persistence | movement, prompt, room render, targeting, combat | character autosave | dirty character autosave |
| NPC location | resident occupancy index and resident actor location | SQL room lookups for living targetable NPCs | look, kill, consider, assist, AI movement | entity autosave/shutdown/admin | dirty resident entity flush |
| Room occupants | `resident_occupants_by_room` | `entity_instances.current_room_id` as target/LOOK authority | LOOK, KILL, CONSIDER, ASSIST, combat start | entity instances | load/spawn/admin rebuild only |
| Visible entities | resident room occupancy for living actors; durable item/corpse stores for non-living content | independent SQL discovery for living NPCs | render room, target lookup | item/entity tables | load/materialization/admin |
| Combat encounters | `combat_runtime.resident_encounters` | active encounter SQL discovery during heartbeat | violence pulse, status, cleanup | combat tables | deferred/audit writes |
| Combat participants | `ResidentCombatEncounter.participants` | SQL participant refresh in runtime pulse | violence, targeting, cleanup | combat_participants | deferred/audit writes |
| Targets | resident participant `target_actor_id` | SQL target lookup in hot command path | attack rounds, status, messages | combat_participants | deferred/audit writes |
| Queued actions | resident participant/action state | SQL rediscovery during ordinary rounds | violence pulse | combat_action_queue for API idempotency | explicit submit/deferred writes |
| Prompt | prompt projection from live character resources | stale combat packet prompt | web/telnet transports | none, except character resources | immediate invalidation/packet queue |
| Equipment | active character equipment snapshot | ad-hoc SQL in combat math | score, combat stats, prompt deps | character save | resident character autosave |
| Natural attacks | combat content registry + resident actor profile | repeated SQL/content rediscovery | combat resolution | world content files | world load/cache warmup |
| Movement | `move_resident_actor` | direct `room_id`/entity room mutation for normal/flee/admin runtime paths | commands, flee, schedules, render | character/entity save | dirty autosave/entity flush |
| Character condition | resident Actor resources/lifecycle | stale persisted hp/position during combat | prompt, combat, score | character save | resource sync/dirty autosave |
| Combat messages | in-memory output queues | SQLite outbound queue as delivery authority | async/direct responses | audit/history only | immediate enqueue |

## Movement audit

Normal movement and entity movement route through `move_resident_actor`. Flee delegates to combat runtime, which uses the same resident actor and occupancy concepts after a successful escape. Restore clears combat with `clear_actor_combat_state` before syncing resources. Death/respawn and admin extraction are still durable lifecycle operations, but runtime cleanup owns live combat state before persistence.

## Combat audit

The heartbeat walks `resident_encounters` and their resident participants. Target resolution for player combat starts from resident room occupancy. SQL encounter and participant tables are retained for durability, diagnostics, idempotent API requests, and restart cleanup, not as ordinary runtime authority.

## Prompt audit

Prompt rendering is a projection over live character resource fields. Combat message enqueue marks prompt packets when resources change; movement invalidates room/prompt projections through the dirty character path.

## Combat cleanup audit

The canonical cleanup routine is `clear_actor_combat_state`/encounter completion in combat runtime. Required cleanup scope: targets, queued actions, participant status, prompt invalidation, wait/action state, resident participant membership, and resident encounter completion.

## SQLite boundary audit

SQLite is permitted for loading, saving, autosave, shutdown/crash recovery, builder/admin diagnostics, materialization, and durable audit trails. Ordinary gameplay command traces now include `gameplay_sql_before_response`, `gameplay_sql_response_render`, `gameplay_sql_total`, and statement samples so violations are visible per request.

## Remaining limitations

Non-living room content (items and corpses) is still read from durable runtime tables during room rendering. Living NPC/mob LOOK and KILL authority no longer comes from those SQL room scans. Full zero-SQL room rendering requires resident item and corpse indexes in a follow-up phase.
