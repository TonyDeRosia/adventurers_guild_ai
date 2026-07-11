# Live Combat Phase 12C2

Smart MUD live combat is driven by one canonical runtime pulse owned by `MudRuntime` and started once by the FastAPI application lifespan. The host timer only wakes the runtime; authoritative scheduling remains world-time based. Each pulse advances world time, lets existing survival/runtime-object consumers run, processes due combat encounters through `CombatRuntimeService`, and emits compact EventBus events such as `combat_pulse_processed`, `combat_round_started`, `combat_action_queued`, `combat_attack_resolved`, `combat_damage_applied`, flee, defense, and encounter-end events.

`CombatRuntimeService` remains authoritative for encounters, participants, targets, queued actions, timing, persistence, cleanup, and async output. `CombatEngine` remains the single-attack resolver for hit, critical, mitigation, damage, and attack result. `AbilityExecutionService` remains the ability validation/cost/cooldown/effect boundary and is used for queued combat abilities. Future AI bots may select legal combat actions, but they must never directly change HP or encounter state.

Asynchronous browser combat output is persisted in SQLite in a per-character outbound queue. The same semantic text pipeline renders command replies and delayed combat messages. Browser play view polling drains undelivered messages once, preserves order, and does not expose encounter IDs, raw EventBus payloads, Python reprs, or JSON to players. Attacker, victim, and observer perspectives are delivered only to active sessions in the combat room; disconnected or unrelated sessions do not receive unbounded output.

Round timing is stored on each participant as `next_action_world_time`. Opening attacks are resolved immediately and not replayed. Recurring rounds consume at most a bounded number of due encounters per pulse and publish backlog diagnostics for developers. Participants that are dead, fled, invalid, or no longer co-located are skipped, and encounters end when fewer than two hostile active sides remain.

Player default actions are represented by the SQLite combat action queue. `attack`, `kill`, and `hit` start or maintain combat without duplicating encounters. `attack` with no target while fighting focuses the current target; outside combat it asks for a target. Queued actions are replaced rather than stacked, consumed once, and revalidated at execution time. The queue supports `basic_attack`, `defend`, `ability`, `flee`, and an assist extension point.

`defend` queues a defensive turn, persists temporary participant metadata, publishes defense start/end events, and clears with encounter cleanup, death, or flee. Player output is: “You raise your guard and prepare for the next attack.” The implementation is runtime/formula-ready and does not hardcode command-handler damage math.

Deterministic mob retaliation uses the same participant timing and attack path as players. Authored natural weapons and content profiles choose wolf bite damage/verbs through combat content; there is no forest-wolf special case in command handlers. Authored abilities can be queued from `use`/`cast` while in combat and execute through `AbilityExecutionService`.

Normal movement consults authoritative active encounter participation. Engaged players see “You are fighting! Use FLEE to escape.” Flee uses canonical movement with an explicit combat bypass, publishes attempt/success/failure events, marks the participant fled, persists health, and updates/ends the encounter so old-room opponents stop attacking after separation.

Health conditions use shared runtime bands: unharmed, barely scratched, lightly wounded, wounded, badly wounded, near collapse, and dead. `combat`, `consider`, `diagnose`, and room/entity inspection present player-facing condition text without NPC exact HP. Combat messages use semantic categories for start, hit, miss, critical, defense, ability, flee, defeat, and end, with attacker/victim/observer perspectives.

Restart policy remains conservative: active encounters are cancelled on service initialization, queued actions do not replay, temporary combat state is cleared by encounter cleanup, persisted health remains in SQLite, and a player can start a new encounter after restart. `rules/combat.py` remains legacy-only and is not imported by live runtime combat. Builder/world packages own combat policies, profiles, content, messages, formulas, and Shattered Realms demonstration data. Phase 12C3 remains responsible for full loot, XP, rewards, quest kill-credit, and respawn refinements.

## Manual browser walkthrough

1. Enter Kraevok and travel by ordinary exits to the hunting trail.
2. Run `look`, `score`, `consider forest wolf`, `diagnose forest wolf`, `attack forest wolf`, and `combat`.
3. Stop typing. The runtime pulse should display later combat output automatically, including wolf retaliation and HP/condition changes.
4. Run `defend` and `combat`; defense should become the next queued action and not stack forever.
5. Try `west`; normal movement should be blocked while engaged.
6. Run `flee west` or another visible exit; success moves the character and stops old-room combat output, while failure leaves combat active.
7. Return, fight again, use one learned combat ability if available, and continue until the wolf reaches zero health. The wolf should stop acting, the encounter should end once, and existing lifecycle/dead/corpse behavior should remain intact.
8. Restart Smart MUD. Health should persist, no stale encounter/action should replay, and a new fight should start normally.
