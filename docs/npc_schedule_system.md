# NPC Schedule System (Phase 12A)

`engine.schedules.ScheduleService` is the canonical Builder-authored NPC schedule foundation. It selects deterministic activities from world time and persists runtime state in SQLite. It does not implement activity gameplay itself.

## Activity Dispatch

Schedule entries name activities such as `sleep`, `patrol`, `travel`, `eat`, `train`, `gather`, `craft`, `cook`, `shop`, `bank`, `converse`, `work`, and `return_home`. The service maps each activity to the existing canonical owner (`SurvivalNeedsService`, movement, `TrainingService`, `GatheringService`, `CraftingService`, `EconomyService`, or `ConversationService`). Phase 12A records the dispatch target and invokes only canonical movement for travel-style activities.

## World Time Integration

Selection uses the authoritative runtime world clock (`MudRuntime.get_world_time`) or an explicit world-time snapshot supplied by tests/replay. Host wall-clock time is used only for SQLite audit timestamps, never to choose activities.

## Builder Schedule Authoring

Builder-authored schedule JSON lives in the world's `schedules/` content and remains data-only. Entries support hourly windows, day/week filters, season and holiday fields, emergency/holiday overrides, conditions, priorities, location references, and fallback entries.

## Schedule Persistence

SQLite tables `npc_schedule_runtime` and `npc_activity_history` store current activity, interruption/resume state, trace data, world-time coordinates, transitions, and history for restart persistence and offline catch-up/replay.

## Runtime Activity Flow

1. Load the NPC's Builder-authored schedule id from canonical entity state/plugin data.
2. Validate schedule content.
3. Select the highest-priority matching entry for authoritative world time.
4. Persist transition and history.
5. Dispatch to canonical services. Travel moves one room step through existing room exits and runtime movement events; no teleportation is introduced.

## Future Living World Integration

Future phases can add autonomous economies, richer needs, or long-running work simulation by subscribing to schedule events and implementing behavior inside the existing canonical services. `ScheduleService` should remain the deterministic selector and dispatcher, not a duplicate AI or gameplay implementation.
