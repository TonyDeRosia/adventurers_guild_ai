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
