# Perception System

Canonical PerceptionService coordinates actor senses, EnvironmentService context, concealment, evidence, deterministic detection, observer knowledge, presentation hooks, EventBus publication, and SQLite persistence for Phase 11B.

Manual acceptance commands: hide; stealth; search room; search north; tracks; inspect tracks; follow tracks; listen; smell; perceptiontrace; hidetrace.

## Phase 11C1 Gathering Foundation Integration

Phase 11C1 introduces `engine.gathering.GatheringService` as the single canonical foundation for resource definitions, node definitions, runtime node state, capacity/depletion, world-time regeneration, requirements, tools, sessions, deterministic yields, quality, rare-yield hooks, diagnostics, and Builder collections. It is intentionally a reusable foundation: Phase 11C2 will add the full gameplay rollout for harvesting, mining, lumberjacking, fishing, skinning, scavenging, excavation, profession XP presentation, quest/achievement integration, and pilot content.

## Phase 11C2 Gathering Integration

Gathered outputs are canonical item/reward payloads; Crafting, Economy, Profession/Progression, Environment, Perception, Quest, Achievement, Property, Organization/Faction, Living World, Builder, and score surfaces integrate by consuming GatheringService data or EventBus events. GatheringService does not price resources, mutate quest state directly, create a shadow inventory, destroy terrain, implement farming, run autonomous workers, or bypass canonical services.
