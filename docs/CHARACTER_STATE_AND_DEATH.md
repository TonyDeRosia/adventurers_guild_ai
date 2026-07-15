
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

## Heartbeat combat correction pass (main-v2)

Tony's current Adventurer's Lair keeps a single 0.10 second game loop heartbeat. `heartbeat()` dispatches subsystems by pulse buckets: scripts, once-per-second MSDP, zones, idle password checks, mobiles, `PULSE_VIOLENCE`, hourly tick work (`weather_and_time`, affects, `point_update`, prompts, quests, auction), autosave, usage, time save, and `extract_pending_chars()` every pulse. Combat is held in a resident `combat_list`; `set_fighting()` links a character into that list, `stop_fighting()` unlinks it, and `perform_violence()` walks the list on the violence bucket rather than discovering fights from durable storage each base pulse. `do_kill`/offensive commands establish fighting; normal repeated swings are violence-pulse work. Death flows through `damage()`/`update_pos()`/`die()`/`raw_kill()`, creates corpses with NPC/player corpse timers, emits death cry, extracts pending characters, and lets object update/timers decay corpses. `do_restore` mutates the in-game target when present and does not make an offline pfile a live combatant merely by restoring it.

Smart MUD now preserves the existing 100ms base heartbeat but gates combat through `violence_pulse_count` (20 for Shattered Realms, approximately two seconds). Nonviolence heartbeats do not call active encounter processing and do not print `[violence-pulse]`. Bounded catch-up keeps the crossed violence bucket in the bounded loop so a delayed scheduler dispatches one due violence bucket without duplicates.

Combat timing is resident and pulse-owned. A command-created opening attack remains the direct command response. After that, each active resident participant may act once per global violence pulse unless defeated, fled, dead, in another room, waiting, defending, or using a queued action/cooldown. Weapon speed no longer adds a second encounter-level two-second timer; explicit wait/cooldown state is the skip mechanism.

The opening Health-to-1 workaround was removed. Lethal opening damage now remains lethal and immediately enters the RuntimeLifecycleService death path: fighting state is stopped, queued target actions are canceled, death/corpse/reward/quest-credit side effects are idempotent, and no later violence pulse is required to kill the target.

Active encounters are represented by typed resident encounters and participants. SQLite remains for initial checkpoints, administrative/audit history, completion, and idempotent death transactions, but violence processing no longer SELECTs active encounters or participant lists per base heartbeat. Combat history is buffered in memory and flushed in bounded batches or on encounter completion instead of synchronously inserting a history row for every hit.

Corpse timing uses durable UTC fields (`created_at_utc`, `decay_at_utc`). Monotonic time is only process-local scheduling input. Older corpse state is migrated conservatively on decay processing, expired corpses drop contents to the room, are removed from entity resolution, and are destroyed once.

NPC death output is ordered through the lifecycle path: final-hit text, collapse/death text, corpse creation, loot/reward/kill-credit side effects, encounter completion, and prompt/room invalidation. Player death uses the configured Adventurer's Lair position thresholds: positive health recovers above stunned, 0 to -2 stunned, -3 to -5 incapacitated, -6 to -10 mortally wounded, and -11 or lower dead; player corpse/loss/respawn policy remains explicit configuration and is not hidden in heartbeat code.

Point update remains a long-tick heartbeat subsystem and is delegated to RuntimeResourceService/formula configuration rather than hard-coded in the heartbeat. Restore now distinguishes online and offline targets: online restore mutates resident state and checkpoints deliberately; offline restore loads a temporary character, restores persistent fields, saves, and does not register a resident actor or regeneration/combat participant.

Test-resource cleanup keeps the runtime scheduler non-owning in MudRuntime; the FastAPI lifecycle owns async tasks. Focused heartbeat tests exercise shutdown by constructing temporary runtimes without starting extra scheduler threads.

SQL measurement counters for the resident hot path are exposed through `performance_counters`: active encounter SELECTs during violence processing remain at `combat_encounter_sql_reads == 0`; combat audit writes are counted as buffered/flushed rows; initial encounter checkpoints, final completion, death transactions, and autosaves remain permitted writes.

Windows manual acceptance was not performed in this Linux container. Tony should run `pulseinfo`, `pulsetrace`, `perfstat reset`, a live Emberwood Fox fight, corpse restart check, offline restore check, and the focused pytest group on Windows before declaring Windows acceptance.

## 2026-07-15 combat-runtime stabilization update

Smart MUD follows Adventurer's Lair's single heartbeat / resident combat-list model for this work: a KILL/attack command creates the encounter and performs one opening attack, but does not leave a duplicate basic attack queued for the first violence pulse.  Normal player and NPC basic attacks use resident participant state (`queued_action`, target, wait pulses, and last action pulse) rather than live `combat_action_queue` rows.  `combat_action_queue` remains reserved for history/recovery compatibility, not as hot-round authority.

The Forest Wolf natural-weapon regression was traced to snapshot/profile fallback paths that allowed nonhumanoid NPC attacks to degrade to generic unarmed wording.  Entity natural weapon profile ids are carried onto resident actors; combat output now conjugates third-person attack verbs (`pulverizes`) while preserving second-person base verbs (`you pulverize`).  Stat snapshots are cached by actor/profile/equipment/effect/body/world-content generation inputs so current Health changes alone do not force offensive/defensive rebuilds.  Audit rows are buffered in memory during active rounds instead of being flushed synchronously on every hit.

Current Linux validation: focused heartbeat/combat tests passed; the broad suite was allowed to complete and exposed broad pre-existing/environmental failures outside the focused combat path.  Windows manual acceptance remains not performed.

## Phase: player recovery, RESTORE, death, and performance-counter schema

Tony's Adventurer's Lair was requested as the behavioral reference. Network access to clone the private/public GitHub reference was blocked in this container with `CONNECT tunnel failed, response 403`; implementation therefore preserves the audited Smart MUD parity assumptions already encoded in `engine.character_state`: HP > 0 is living, 0..-2 stunned, -3..-5 incapacitated, -6..-10 mortally wounded, and -11 or lower dead. Stunned is not dead.

Smart MUD now exposes administrator `restore self`, `restore <online character>`, `restore <offline character>`, `restore all`, `restorestat`, `adminstatus`, `pointinfo`, `perfstat validate`, and `perfstat schema`. RESTORE authority uses canonical role/immortal level, not character title text. Online restore mutates the resident actor/character, clears stale combat state, invalidates prompt/SCORE projections, marks dirty, and performs one deliberate checkpoint save. Offline restore loads one temporary stored character, updates canonical persisted fields, saves once, and does not register a resident actor.

Point-update recovery runs through the existing runtime heartbeat/resource path, not a new scheduler. The configured interval is six seconds in Smart MUD's runtime resource service. Standing/resting/sleeping multipliers are 1/2/4; fighting/dead actors are blocked. Boundary recovery from stunned/incapacitated/mortally wounded queues `You regain consciousness.`, marks the resident dirty, invalidates prompt/SCORE, and async polling reports `prompt_changed`, `resource_changed`, and `position_changed`.

Player death at the true death threshold is idempotently routed through the existing runtime lifecycle/resource path. The current Shattered Realms policy restores the player immediately at the current room with full HP/Mana/Move, clears stale combat state, queues an explanatory death/return message, marks dirty, and writes the next normal checkpoint without leaving players trapped at zero HP. Corpse/inventory-loss policies remain conservative for player characters pending fuller Adventurer's Lair parity.

Performance counters now have a canonical `CounterDefinition` registry with typed defaults, category, reset policy, classification, and description. The inventory includes live combat SQL counters such as `combat_sql_round_history_insert`. `perfstat validate` lists schema problems read-only; `perfstat schema` displays registered key/type/category/reset/current validity; `perfstat reset` rebuilds typed reset values while preserving scheduler/configuration objects and recomputing live gauges.

Focused regression coverage was added in `tests/test_admin_restore_recovery_perf_schema.py` for zero-HP recovery visibility, RESTORE self/target/all/offline behavior, schema validation/reset, and true-death respawn.
