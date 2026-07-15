# Phase 12D5 runtime identity, idempotency, and AI-readiness contracts

Smart MUD uses SQLite as the authority for canonical runtime lifecycle state. Permanent actor identity (`character:<id>` or `entity:<entity_id>`) is not sufficient to identify one living occurrence, because respawnable entities reuse template, spawn, and sometimes actor identity across multiple lives.

## Identity audit

- Characters: persistent character rows and `character:<character_id>` actor IDs identify the permanent player actor.
- Entity instances: `entity_instances.entity_id` identifies the current runtime entity instance; `state.lifecycle_id` identifies its current living incarnation.
- Spawn declarations/materializations: content spawn IDs remain the authored spawn source and are stored as `state.source_spawn_id` plus content materialization rows.
- Combat participants: `combat_participants` stores encounter, actor, entity/character, target, contribution, and lifecycle IDs for the participant row.
- Death transactions: `combat_death_transactions.death_id` identifies one death occurrence; uniqueness is scoped by world, actor, and lifecycle ID.
- Corpses: corpses are runtime `entity_instances` with `entity_type='corpse'`; corpse state stores `death_id`, `source_entity_id`, and `source_lifecycle_id`.
- Loot/rewards: reward packets keep source type/source ID/source instance ID; combat corpse loot uses the death ID as the source instance when available.
- Quest credit: quest event consumption is keyed by quest instance, objective, and event ID; death events must use the death ID as the event ID.
- Runtime objects and outbound messages: runtime object identity remains service-owned; browser output uses `combat_outbound_messages.message_id` plus atomic claim fields.

## Lifecycle/incarnation design

Living NPC and mob entity instances receive a persisted `state.lifecycle_id` when spawned or materialized. The lifecycle ID is stable for that living incarnation and changes when a new entity is spawned for respawn/rematerialization. It is internal-only and must not be displayed to normal players.

## Idempotency and concurrency contracts

- Death idempotency is `world_id + actor_id + lifecycle_id`; retrying lethal handling for the same life returns no duplicate side effects, while a later life can die normally.
- Corpse idempotency is death-scoped: `create_corpse` reuses an existing corpse only for the same death ID, or for legacy calls matching both source entity and lifecycle.
- Reward and quest systems should use death IDs as source instance/event IDs so each eligible recipient/objective is credited once per death and eligible again on later deaths.
- Browser output drain uses a SQLite `BEGIN IMMEDIATE` claim-and-deliver transaction. Current browser semantics are at-most-once delivery after the server claims rows for a character.
- Combat action consumption uses a SQLite `BEGIN IMMEDIATE` claim to transition exactly one queued row to consumed; replaced/cancelled rows are not executable after restart.
- The current SQLite runtime is a single-writer design. Multiple processes must add an explicit lease before sharing one runtime database.

## Future AI boundary

AI actors may observe events and request legal actions through canonical services only. They must never mutate HP directly, write combat tables directly, create corpses, grant rewards, respawn themselves, mark output delivered, change lifecycle IDs, or bypass target validation.
