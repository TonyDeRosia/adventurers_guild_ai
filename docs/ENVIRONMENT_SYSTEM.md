# Phase 11A Environment System

Smart MUD now has one canonical `EnvironmentService` in `engine/environment.py`. The service is the shared boundary for climate profiles, authored seasons, deterministic daylight periods, moonlight foundations, SQLite weather state, forecasts, room environment resolution, light sources, visibility, exposure, and movement/combat/living-world/quest context hooks.

Pipeline: world time -> climate profile -> weather state -> room environment -> light and visibility -> actor exposure/context hooks -> canonical systems and EventBus presentation. The service does not own actors, movement, combat, quests, achievements, properties, items, or room definitions.

Manual acceptance commands: `weather`, `forecast`, `season`, `time`, `dayperiod`, `environment`, `environmenttick <minutes>`, `roomlight`, `light <item>`, `extinguish <item>`, `visibilitytrace self <target>`, `weathertrace world default`, `environmenttrace <room>`, `exposuretrace self`, and `environmentaudit`.
