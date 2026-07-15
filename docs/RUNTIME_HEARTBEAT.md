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
