# Smart MUD Zone Resets (Phase 15A)

Status: **Partial implementation**. `ZoneResetService` is the canonical reset authority for typed reset profiles, validation, immutable plan compilation, preview, manual execution, bounded history persistence, and one-shot scheduler tick integration. It reconciles missing runtime population and does not reload worlds or resident characters.

## Adventurer's Lair behavior audit
Network access to `TonyDeRosia/tbamud_adventurers_lair` was blocked in this environment (`git clone` returned HTTP CONNECT 403), so no C code was copied. The implemented behavior follows the requested audit categories at an architectural level: reset profiles have mode/interval/priority, commands create mobiles and objects, attach objects to mobiles/containers/equipment, restore door state through runtime authority when present, enforce maximum counts, support conditional chains, provide manual/preview execution, and record action results.

## Canonical ownership
* Reset definitions live in world packages or Builder drafts; SQLite stores only runtime schedule/history.
* Startup materialization remains owned by item placements/spawns/materializers.
* Recurring resets are owned by reset profiles and validated for duplicate ownership where declarations are explicit.
* Ambiguous existing content is not silently migrated.

## Profile schema
Implemented fields: `reset_profile_id`, `world_id`, `zone_id`, `display_name`, `enabled`, `reset_mode`, `reset_interval_seconds`, `priority`, `commands`, `metadata`, `definition_version`, and optional bounded policy fields.

## Command schemas
Implemented command types: `SPAWN_ENTITY`, `SPAWN_ITEM`, `GIVE_ITEM`, `EQUIP_ITEM`, `PUT_ITEM`, and `SET_EXIT_STATE`. PUT_ITEM uses the same canonical ownership transfer surface as items; deeper container semantics remain **Partial** pending fuller container authority.

## Modes, conditions, and policies
Implemented modes: `always`, `when_empty`, `manual_only`, `never`.
Implemented conditions: `always`, `if_previous_succeeded`, `if_previous_created`, `if_reference_exists`, `if_room_empty`, `if_zone_empty`, `if_count_below_limit`.
Implemented failure policies: `continue`, `skip_dependents` validation, and `abort_profile`; dependency skipping is **Partial** for complex graph chains.

## Count scopes
Implemented scopes: `room`, `zone`, `world`, and `template_global`. Counts use live runtime instance tables and ignore destroyed instances.

## Scheduler integration
`ZoneResetService.tick(world_id)` is a bounded canonical pulse hook candidate. It does not start a second loop or per-profile worker.

## Persistence
Tables: `zone_reset_runtime`, `zone_reset_runs`, and `zone_reset_action_results`. History retention is bounded to 500 runs.

## Events
Published events include `zone_reset_previewed`, `zone_reset_started`, `zone_reset_action_skipped`, `zone_reset_action_succeeded`, `zone_reset_action_failed`, and `zone_reset_completed`. Definition/schedule events are reserved for the Builder promotion path.

## Safety
Resets never remove players, player-owned items, active combatants, or persistent unique content. Existing entities are not rebuilt from templates; missing population is filled only.

## Existing content migration report
Current Shattered Realms population sources found: live room `npcs`/`objects` arrays, `item_placements`, Builder `spawns`, Builder template placeholder spawns, and materialization helpers. Classification: live room décor remains static package content; `item_placements` remain startup materialization; Builder template spawns marked `placeholder_no_runtime_reset` require manual review; Phase 15A test reset is recurring reset and manual-only; no ambiguous content was deleted.

## Windows manual status
Not performed in this Linux container. See `docs/BUILDER_RESETS.md` for exact Windows steps.

## Emberwood Forest population profile

`emberwood_forest_population` is the canonical recurring population profile for `shattered_realms` zone `emberwood_forest`. It uses `when_empty`, a 600 second interval, typed `SPAWN_ENTITY` commands, room-scoped limits for common wildlife, zone-scoped limits for `dire_forest_wolf`, and a zone maximum of one `ashback_bear`.
