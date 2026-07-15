
## Live player state, death, recovery, and combat-start reconciliation

Smart MUD now uses a canonical `CharacterActionState` projection for command eligibility. The projection derives command-facing state from canonical Health, stored position/posture, lifecycle state, combat state, and active encounter evidence. It prevents handlers from making independent eligibility decisions from only one stale field.

Tony's Adventurer's Lair `update_pos()` behavior was audited from the current reference source: positive Health preserves active positions above stunned; positive Health in stunned-or-worse restores standing; Health 0 through -2 is stunned; -3 through -5 is incapacitated; -6 through -10 is mortally wounded; -11 or lower is dead. Smart MUD reproduces those thresholds in `engine.character_state` without copying C source.

Attack validation now reconciles the attacker's Health/position/lifecycle state before validating. Generic `You cannot attack right now.` has been replaced with specific player messages for sleeping, sitting, resting, stunned, incapacitated, mortally wounded, dead, already fighting, absent targets, dead targets, and protected targets. Failed validation is read-only and must not save the character; command history remains separate from character persistence.

Character entry registers a canonical resident actor and reconciles stale positive-HP down positions through the same state projection. The repair is logged as `[state-reconcile]` and marks resident state dirty for the coalesced autosave path rather than forcing an immediate SQLite write.

The runtime pulse continues to use the existing scheduler. Regeneration now reconciles position after resource recovery; incapacitated and mortally wounded actors take bounded periodic suffering damage and are reconciled after each suffering tick. Dead actors are excluded from ordinary regeneration.

Admin commands:

- `stateinspect <character>` reports current/persisted Health, stored/derived position, combat/lifecycle state, active encounter, attack eligibility, block reason, and proposed repair.
- `staterepair <character> --dry-run` reports safe repairs without mutation.
- `staterepair <character> --apply` applies unambiguous position reconciliation through the canonical service and is intended to be idempotent.
- `combatstate <character>` reports encounter/target state with the same projection.

Normal command:

- `condition` reports Health condition, canonical position, movement eligibility, and fight eligibility without exposing database internals.

Performance counters now include combat validation attempts/rejections, rejection-by-reason, failed/read-only/combat-validation save guards, state reconciliations, stale position/combat/encounter repair counters, positive-health incapacitated repairs, periodic suffering ticks, and recovery transitions.

Windows status: not executed in this Linux container. Tony should run the documented manual acceptance flow on Windows, inspect Kraevok with `stateinspect char_shattered_realms_kraevok`, dry-run and apply `staterepair` only if unambiguous, then verify `condition`, `score`, `kill fox`, specific rejection text, and `perfstat` failed-command save counters.


## Runtime heartbeat/combat parity update

See `docs/RUNTIME_HEARTBEAT.md` and `docs/CORPSE_AND_DEATH_LIFECYCLE.md` for the current TBA-style heartbeat mapping, pulse constants, resident authority rules, coalesced autosave, restore behavior, movement/flee cleanup, corpse decay, corpse parser parity, async-poll hints, focused tests, broad-suite status, Windows manual status, and remaining differences.
