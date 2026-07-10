# Progression System

Canonical progression is owned by SQLite actor_progression_state and engine.progression.ProgressionService. Actors resolve species/race, class/profession, progression profile, level/XP, Formula-safe growth grants, ability learning, score, and diagnostics through this API; legacy character level/xp are conserved only as migration inputs.

## Phase 7A reward integration

RewardService delivers `experience`, `practice_sessions`, `training_sessions`, `skill_points`, `attribute_points`, `ability`, and `ability_rank` entries by calling `ProgressionService` APIs. Reward packets remain the audit source; progression services remain the mutation authority.
