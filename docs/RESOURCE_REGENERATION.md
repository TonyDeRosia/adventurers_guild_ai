# RESOURCE REGENERATION

Phase 11C1 adds the reusable canonical gathering foundation. All harvesting, mining, lumberjacking, fishing, skinning, scavenging, excavation, depletion, regeneration, and yield behavior routes through one `engine.gathering.GatheringService` pipeline.

Implemented foundation:

- data-driven resource, node, capacity, regeneration, availability, environment, gathering, tool, yield, cost, interruption, cooldown, profession XP, message, render, and access profile collections;
- SQLite-authoritative runtime node instances and gathering sessions;
- deterministic materialization, success/yield/quality/rare-yield foundations;
- world-time capacity depletion and bounded regeneration catch-up;
- exact tool-instance validation hooks and durability hooks;
- audit/history/regeneration/result tables and diagnostics traces;
- Builder/world-package import, preview, apply, export, and validation registration.

Phase 11C2 remains responsible for full gameplay commands, balance, profession XP awards, quest/achievement score presentation, fishing minigames, and pilot content rollout.
