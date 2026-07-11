# Live Combat Runtime Architecture

Phase 12B1 establishes `engine.combat_runtime.CombatRuntimeService` as Smart MUD's canonical live combat runtime. `engine/combat.py` remains the canonical single-attack resolver: it calculates hit, critical, mitigation, damage, state messages, and death handoff data for one attack between canonical `Actor` objects. `CombatRuntimeService` owns persistent encounters, participants, current targets, queued/default actions, round scheduling, SQLite history, EventBus publication, Actor synchronization, validation, flee, cleanup, and restart behavior.

## SQLite encounter schema

The runtime creates idempotent tables through the normal runtime schema path:

- `combat_encounters`: encounter id, world, room, status, start time, current round, next round time, timestamps, end reason, metadata.
- `combat_participants`: actor id/type, character/entity reference, side, current target, participation state, initiative, action timing, contribution totals, fled/defeated flags, metadata.
- `combat_action_queue`: reserved queue table for basic attacks, abilities, flee, defend, and assist.
- `combat_round_history`: one row per resolved action with outcome, damage/healing, compact JSON result, and world time.

SQLite is authoritative for mutable encounter state. Encounters are not in-memory-only.

## Participant lifecycle and round processing

`attack`, `kill`, and `hit` resolve a visible runtime entity, convert both combatants to canonical Actors, validate legality, create or reuse an active encounter, join participants on opposing sides, set reciprocal targets, execute a real opening attack, persist changed resources, publish combat events, and schedule the next round. Runtime world-time advancement calls `process_due_rounds()`, which processes active encounters in deterministic initiative order. Default Phase 12B1 actions are basic attacks; NPCs use `CombatEngine.attack_profile()`, which resolves authored natural weapons such as the forest wolf's `wolf_bite` profile through world-package combat content.

## Target validation and protection policies

Combat initiation rejects missing targets, self-targets, dead targets, different-room targets, incapacitated attackers, non-attackable entities, and protected/no-kill policies. Protection is data-driven through world-package `combat_policy` and flags/tags such as `protected`, `trainer_protected`, `no_kill`, and `attackable`; Borik is protected by authored data, not by a Python name check. Shattered Realms remains demonstration content, not final game design.

## Actor synchronization

The service converts `MudCharacter` and runtime `entity_instances` into canonical Actors, including health, resources, location, authored stats, body profile, combat behavior references, ability loadout references, and natural weapon profile references. After attacks, changed health/resource/combat state is written back to character rows and entity state JSON so reconstruction preserves health changes.

## Events

The runtime publishes serializable EventBus events including encounter start/end, participant joined, target set, round started, action started/completed, attack resolved, damage applied, participant fled, and participant defeated. Payloads contain stable IDs and values, not mutable Actor objects.

## Restart policy

Phase 12B1 uses the conservative cancellation-on-restart policy: constructing `CombatRuntimeService` marks active encounters ended with `cancelled_on_restart`. Health changes are preserved, no opening attacks are replayed, and participants are not left silently stuck in combat. Future phases can resume valid encounters without replacing the schema.

## Legacy combat boundary

`rules/combat.py` is legacy campaign compatibility only. Live Smart MUD runtime code must not import `rules.combat.CombatEngine`. The normal runtime path is `MudCommandEngine -> CombatRuntimeService -> engine.combat.CombatEngine`.

## Browser manual test guide

1. Enter a character and travel to `emberwood_hunting_trail`.
2. Run `look`, `consider forest wolf`, `diagnose forest wolf`, `attack forest wolf`, and `combat`.
3. Allow world time/commands to advance enough for due rounds; the wolf retaliates through its natural attack.
4. Run `flee` or `flee <direction>` and verify movement, persisted location, and encounter update/end.
5. Restart the runtime and verify health remains changed and no active encounter remains stuck.

## Future phases

Phase 12B2/12B3 can add richer ability queueing, AI-selected legal actions through `CombatBehaviorService`, reward/loot distribution, group contribution, pursuit, pets, advanced status effects, and improved observer messaging. Future AI bots may select legal actions but must never directly mutate combat state.
