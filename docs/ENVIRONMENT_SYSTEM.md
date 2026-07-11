# Phase 11A Environment System

Smart MUD now has one canonical `EnvironmentService` in `engine/environment.py`. The service is the shared boundary for climate profiles, authored seasons, deterministic daylight periods, moonlight foundations, SQLite weather state, forecasts, room environment resolution, light sources, visibility, exposure, and movement/combat/living-world/quest context hooks.

Pipeline: world time -> climate profile -> weather state -> room environment -> light and visibility -> actor exposure/context hooks -> canonical systems and EventBus presentation. The service does not own actors, movement, combat, quests, achievements, properties, items, or room definitions.

Manual acceptance commands: `weather`, `forecast`, `season`, `time`, `dayperiod`, `environment`, `environmenttick <minutes>`, `roomlight`, `light <item>`, `extinguish <item>`, `visibilitytrace self <target>`, `weathertrace world default`, `environmenttrace <room>`, `exposuretrace self`, and `environmentaudit`.


## Phase 11B Perception Integration

Phase 11B adds `engine.perception.PerceptionService` as the single sensory boundary for stealth, concealment, search, tracking, scent, sound, trails, and observer knowledge. It queries canonical services, especially `EnvironmentService`, and stores restart-safe sensory state in SQLite.

## Phase 11C1 Gathering Foundation Integration

Phase 11C1 introduces `engine.gathering.GatheringService` as the single canonical foundation for resource definitions, node definitions, runtime node state, capacity/depletion, world-time regeneration, requirements, tools, sessions, deterministic yields, quality, rare-yield hooks, diagnostics, and Builder collections. It is intentionally a reusable foundation: Phase 11C2 will add the full gameplay rollout for harvesting, mining, lumberjacking, fishing, skinning, scavenging, excavation, profession XP presentation, quest/achievement integration, and pilot content.
