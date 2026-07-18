# Phase 17 Timing Architecture

Smart MUD has one authoritative runtime heartbeat. The web application owns a single asyncio task that sleeps until the next configured pulse and calls `MudRuntime.process_runtime_pulse`; command handling and polling do not advance time. Duplicate scheduler starts are counted and ignored.

## Audit of existing timing

* `app/web.py` contains the only long-running asyncio loop for runtime pulses.
* `MudRuntime.process_runtime_pulse` is the bounded synchronous pulse work unit.
* Combat rounds, point updates/regeneration, autosave, corpse decay, world clock advancement, active-effect expiration, and future AI/reset hooks now dispatch from that pulse.
* Existing `runtime_pulse(minutes)` remains an admin/test facade but delegates back through the same pulse work unit.
* Projection-cache background work is display warmup only and does not own game time.

## Pulse, tick, and world intervals

Configuration keys are `pulses_per_second`, `pulses_per_tick`, `ticks_per_game_hour`, `game_hours_per_day`, `days_per_month`, `months_per_year`, and `years`. Compatibility keys such as `base_pulse_ms`, `point_update_pulse_count`, and `world_hour_pulse_count` are still honored while mapping to the heartbeat model.

Runtime flow:

1. `runtime.pulse` fires every base pulse.
2. Every configured tick, regeneration and active-effect expiration run and `runtime.tick` fires.
3. World clock ticks emit `world.minute`, `world.hour`, `world.day`, `world.month`, and `world.year` as appropriate.
4. Threshold messages such as dawn/sunrise and sunset/nightfall are emitted as EventBus events and queued to online players.

## Active effects and derived stats

`ActiveEffectService` owns runtime effects. Effects have stable IDs, display names, sources, configured and remaining durations, categories, stacking/refresh metadata, messages, modifiers, flags, and permanent/equipment modes. Expiration removes only the expiring effect, publishes `character.effect.expired`, queues the wear-off message, invalidates projections, and rebuilds derived stats from base character attributes plus all remaining effect modifiers. It never subtracts modifiers from current totals.

## Position and regeneration

The authoritative player positions are standing, sitting, resting, sleeping, fighting, stunned, incapacitated, and dead. `stand`, `sit`, `rest`, `sleep`, and `wake` perform validated transitions and publish position events. Sleeping players get `In your dreams, or what?` for room look and do not receive room descriptions. Regeneration is driven by heartbeat ticks, clamps through `RuntimeResourceService`, skips dead actors, and uses configurable position-aware multipliers in a single resource update path.

## Subscription points

Future systems should subscribe to heartbeat events instead of creating new loops: NPC AI, wander/patrol, combat decisions, spell ticking, weather, seasons, crops, construction, cooldowns, resets, respawns, economy, and scripted events.
