# Runtime Heartbeat

Smart MUD now uses one application-lifecycle-owned runtime heartbeat. The web host starts a single asyncio pulse task, the task wakes every 100 milliseconds, and `MudRuntime.process_runtime_pulse()` is the only bounded timed-work entry point. Browser refresh, character entry, commands, prompt rendering, and async polling do not create schedulers and do not advance combat.

Tony's Adventurer's Lair model was used as the behavioral target: a short base loop calls heartbeat work independently of player commands; violence runs on a two-second pulse; point updates, affects, prompt refresh, world time, zone/mobile work, and autosave run on longer pulse buckets. Network access to clone the reference repository was blocked in this container by `CONNECT tunnel failed, response 403`, so this patch documents the requested reference facts and prior repo audit notes rather than copying source.

## Pulse configuration

Shattered Realms defaults are held on `MudRuntime.pulse_config`:

- `base_pulse_ms`: 100
- `violence_pulse_count`: 20
- `mobile_pulse_count`: 100
- `point_update_pulse_count`: 750
- `zone_pulse_count`: 600
- `autosave_pulse_count`: 300
- `world_hour_pulse_count`: 750
- `corpse_decay_pulse_count`: 50
- `maximum_catchup_pulses`: 5

The heartbeat records missed pulses and advances skipped base pulses without executing skipped subsystem work. Due combat is checked in bounded work and a combat pulse is never intentionally executed twice for the same due interval.

## Subsystems

- Violence: `CombatRuntimeService.process_due_rounds()` runs from the heartbeat, not from commands.
- Point update: `RuntimeResourceService.process_due_regeneration()` runs on the configured long pulse and marks resident characters dirty when resources/state change.
- World time: fantasy time advances only on the world-hour bucket, not each base pulse.
- Autosave: dirty resident characters are saved in coalesced heartbeat batches.
- Corpse decay: corpse entities carry creation/decay metadata and are destroyed on the corpse-decay bucket.

## Admin diagnostics

- `pulseinfo`
- `pulsetrace`
- `pulseforce combat|point_update|autosave|corpse_decay`
- `residentlist`
- `residentstat <character>`
- `latencystat`, `latencystat reset`
- `commandtrace <trace-id>` placeholder for per-response development traces

## Windows status

Windows manual acceptance was not performed in this Linux container. Use the manual checklist in `docs/CORPSE_AND_DEATH_LIFECYCLE.md` and the task prompt on Tony's Windows project root.

## Heartbeat combat correction pass (main-v2)

Tony's current Adventurer's Lair keeps a single 0.10 second game loop heartbeat. `heartbeat()` dispatches subsystems by pulse buckets: scripts, once-per-second MSDP, zones, idle password checks, mobiles, `PULSE_VIOLENCE`, hourly tick work (`weather_and_time`, affects, `point_update`, prompts, quests, auction), autosave, usage, time save, and `extract_pending_chars()` every pulse. Combat is held in a resident `combat_list`; `set_fighting()` links a character into that list, `stop_fighting()` unlinks it, and `perform_violence()` walks the list on the violence bucket rather than discovering fights from durable storage each base pulse. `do_kill`/offensive commands establish fighting; normal repeated swings are violence-pulse work. Death flows through `damage()`/`update_pos()`/`die()`/`raw_kill()`, creates corpses with NPC/player corpse timers, emits death cry, extracts pending characters, and lets object update/timers decay corpses. `do_restore` mutates the in-game target when present and does not make an offline pfile a live combatant merely by restoring it.

Smart MUD now preserves the existing 100ms base heartbeat but gates combat through `violence_pulse_count` (20 for Shattered Realms, approximately two seconds). Nonviolence heartbeats do not call active encounter processing and do not print `[violence-pulse]`. Bounded catch-up keeps the crossed violence bucket in the bounded loop so a delayed scheduler dispatches one due violence bucket without duplicates.

Combat timing is resident and pulse-owned. A command-created opening attack remains the direct command response. After that, each active resident participant may act once per global violence pulse unless defeated, fled, dead, in another room, waiting, defending, or using a queued action/cooldown. Weapon speed no longer adds a second encounter-level two-second timer; explicit wait/cooldown state is the skip mechanism.

The opening Health-to-1 workaround was removed. Lethal opening damage now remains lethal and immediately enters the RuntimeLifecycleService death path: fighting state is stopped, queued target actions are canceled, death/corpse/reward/quest-credit side effects are idempotent, and no later violence pulse is required to kill the target.

Active encounters are represented by typed resident encounters and participants. SQLite remains for initial checkpoints, administrative/audit history, completion, and idempotent death transactions, but violence processing no longer SELECTs active encounters or participant lists per base heartbeat. Combat history is buffered in memory and flushed in bounded batches or on encounter completion instead of synchronously inserting a history row for every hit.

Corpse timing uses durable UTC fields (`created_at_utc`, `decay_at_utc`). Monotonic time is only process-local scheduling input. Older corpse state is migrated conservatively on decay processing, expired corpses drop contents to the room, are removed from entity resolution, and are destroyed once.

NPC death output is ordered through the lifecycle path: final-hit text, collapse/death text, corpse creation, loot/reward/kill-credit side effects, encounter completion, and prompt/room invalidation. Player death uses the configured Adventurer's Lair position thresholds: positive health recovers above stunned, 0 to -2 stunned, -3 to -5 incapacitated, -6 to -10 mortally wounded, and -11 or lower dead; player corpse/loss/respawn policy remains explicit configuration and is not hidden in heartbeat code.

Point update remains a long-tick heartbeat subsystem and is delegated to RuntimeResourceService/formula configuration rather than hard-coded in the heartbeat. Restore now distinguishes online and offline targets: online restore mutates resident state and checkpoints deliberately; offline restore loads a temporary character, restores persistent fields, saves, and does not register a resident actor or regeneration/combat participant.

Test-resource cleanup keeps the runtime scheduler non-owning in MudRuntime; the FastAPI lifecycle owns async tasks. Focused heartbeat tests exercise shutdown by constructing temporary runtimes without starting extra scheduler threads.

SQL measurement counters for the resident hot path are exposed through `performance_counters`: active encounter SELECTs during violence processing remain at `combat_encounter_sql_reads == 0`; combat audit writes are counted as buffered/flushed rows; initial encounter checkpoints, final completion, death transactions, and autosaves remain permitted writes.

Windows manual acceptance was not performed in this Linux container. Tony should run `pulseinfo`, `pulsetrace`, `perfstat reset`, a live Emberwood Fox fight, corpse restart check, offline restore check, and the focused pytest group on Windows before declaring Windows acceptance.

## 2026-07-15 violence pulse stabilization note

The reported defect was a one-encounter violence pulse that appeared as `active_encounters=1`, `processed_encounters=1`, `actions=3`, with about 1664 ms in combat and about 3170 ms in the full runtime pulse.  The implementation now profiles resident violence work with `violenceprofile` / `violenceprofile reset`, uses resident queued actions for normal combat, avoids SQLite action-queue consumption during ordinary rounds, and reports action counts separately from message counts.  Windows acceptance was not performed in this Linux container.

## Phase: player recovery, RESTORE, death, and performance-counter schema

Tony's Adventurer's Lair was requested as the behavioral reference. Network access to clone the private/public GitHub reference was blocked in this container with `CONNECT tunnel failed, response 403`; implementation therefore preserves the audited Smart MUD parity assumptions already encoded in `engine.character_state`: HP > 0 is living, 0..-2 stunned, -3..-5 incapacitated, -6..-10 mortally wounded, and -11 or lower dead. Stunned is not dead.

Smart MUD now exposes administrator `restore self`, `restore <online character>`, `restore <offline character>`, `restore all`, `restorestat`, `adminstatus`, `pointinfo`, `perfstat validate`, and `perfstat schema`. RESTORE authority uses canonical role/immortal level, not character title text. Online restore mutates the resident actor/character, clears stale combat state, invalidates prompt/SCORE projections, marks dirty, and performs one deliberate checkpoint save. Offline restore loads one temporary stored character, updates canonical persisted fields, saves once, and does not register a resident actor.

Point-update recovery runs through the existing runtime heartbeat/resource path, not a new scheduler. The configured interval is six seconds in Smart MUD's runtime resource service. Standing/resting/sleeping multipliers are 1/2/4; fighting/dead actors are blocked. Boundary recovery from stunned/incapacitated/mortally wounded queues `You regain consciousness.`, marks the resident dirty, invalidates prompt/SCORE, and async polling reports `prompt_changed`, `resource_changed`, and `position_changed`.

Player death at the true death threshold is idempotently routed through the existing runtime lifecycle/resource path. The current Shattered Realms policy restores the player immediately at the current room with full HP/Mana/Move, clears stale combat state, queues an explanatory death/return message, marks dirty, and writes the next normal checkpoint without leaving players trapped at zero HP. Corpse/inventory-loss policies remain conservative for player characters pending fuller Adventurer's Lair parity.

Performance counters now have a canonical `CounterDefinition` registry with typed defaults, category, reset policy, classification, and description. The inventory includes live combat SQL counters such as `combat_sql_round_history_insert`. `perfstat validate` lists schema problems read-only; `perfstat schema` displays registered key/type/category/reset/current validity; `perfstat reset` rebuilds typed reset values while preserving scheduler/configuration objects and recomputing live gauges.

Focused regression coverage was added in `tests/test_admin_restore_recovery_perf_schema.py` for zero-HP recovery visibility, RESTORE self/target/all/offline behavior, schema validation/reset, and true-death respawn.

## 2026-07-15 RESTORE/resource authority recovery update

Reference audit: the current Tony Adventurer's Lair source was inspected through raw GitHub for `act.wizard.c`, `limits.c`, `fight.c`, and `interpreter.c` after direct `git clone` from this container was blocked by HTTP CONNECT 403. The observed `do_restore` path requires an explicit target, treats `all` as an abbreviation before normal character lookup, restores connected non-immortal players for `restore all`, sets hit/mana/move to effective maxima, calls position recalculation, logs the god command, tells the administrator each restored player for `all`, and sends the target a full-heal message. The single-target form rejects equal-or-higher immortal targets, sets hit/mana/move to maxima, optionally refreshes immortal skills/stat caps for sufficiently privileged restorers, calls affect total recalculation, and sends OK plus target notification. The observed point-update path ticks hunger/drunk/thirst, updates starvation trackers, regenerates hit/mana/move for positions at or above stunned, applies condition/poison penalties, and uses hit/mana/move gain functions that are modified by position, hunger/thirst starvation/dehydration, poison, clarity, and best regeneration multiplier. The observed death path uses `update_pos`, corpse/death cry handling, `die`, and `raw_kill`; `raw_kill` stops fighting and removes active affects.

Smart MUD implementation: online `Actor.resources` is the canonical resident resource authority. `MudCharacter.hp/mana/stamina`, prompt, SCORE, condition, and save payloads are synchronized projections. RESTORE, point update, damage/healing, and autosave now route current resource mutation through `RuntimeResourceService` operations including `set_current_to_maximum`, `restore_all_resources`, `apply_regeneration`, `apply_damage`, `set_survival_need`, `restore_survival_needs`, and `build_resource_snapshot`. The service validates bounds, increments persisted resource versions through `actor_resource_versions`, synchronizes resident character projections, invalidates prompt/SCORE, marks dirty, and publishes resource events.

RESTORE parsing now handles `self`/`me` and `all` before generic character lookup, so `restore all` cannot be resolved as a literal player named `all`. Online targets are restored through their resident actor without reloading SQLite or creating duplicate residents. Offline targets are loaded once, restored, saved once, and not registered as residents. RESTORE captures canonical before/after snapshots and reports Health, Mana, Move, Hunger, Thirst, Position, Lifecycle, harmful effects removed, and combat cleanup. Hunger and thirst are restored to canonical healthy full values (`24`/`24`, rendered as Full/Hydrated by presentation). Harmful removable effects are typed by poison/blind/curse/debuff/harmful/death/stun tags; beneficial, permanent, equipment-derived, racial, training, and administrative effects are preserved.

Point update now uses `RuntimeResourceService.apply_regeneration` instead of direct actor field writes, so zero-HP stunned players visibly recover through the canonical resident authority. Recovery queues a message, invalidates prompt/condition projections, marks the character dirty for the next autosave, and does not synchronously save. `pulseforce point_update` truly forces the due bucket. `pointinfo` reports heartbeat pulse, point-update interval, last/next point-update, resident registration, online state, eligibility, current position, HP/Mana/Move gain result, hunger/thirst modifiers, poison modifiers, and blocking reason. `pointtrace on|off` is admin-only and toggles the trace counter.

Death-state policy preserves Adventurer's Lair thresholds: 0 through -2 stunned, -3 through -5 incapacitated, -6 through -10 mortally wounded, and -11 or lower dead. Ordinary point update can recover stunned players but does not treat truly dead players as merely stunned; true death uses the visible player-return path already present in Smart MUD, clears combat, restores usable resources, queues a death/return message, and marks dirty.

Regression coverage includes the Windows split-brain fixture where resident Actor Health is canonical and MudCharacter fields are intentionally stale; `restore self` now outputs `0/100 -> 100/100`, prompt updates immediately to full HP, SCORE uses synchronized resources, harmful synthetic poison is removed, beneficial effects are preserved, one checkpoint save is written, and reload preserves the restored values. Coverage also asserts `restore all` special parsing, `pointinfo`, `pointtrace`, offline restore no-ghost behavior, performance schema validation/reset, zero-HP recovery, and true-death respawn. Linux container tests passed; Windows manual acceptance was not performed here and remains for Tony to execute with Kraevok/Player on the Windows path.

### 2026-07-15 combat-start latency note

Smart MUD now follows the Adventurer's Lair responsiveness model more closely for combat start: the KILL command performs target lookup, resident encounter creation, one opening attack, prompt/message preparation, and response construction before the newly-created encounter is eligible for ordinary violence-pulse processing. Resident violence uses resident round state for attack event publication rather than synchronous SQLite round lookups. Repeated selects of an already-ready world join the existing generation and do not rerun entity materialization or combat warmup.

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
