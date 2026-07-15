# Corpse and Death Lifecycle

This patch tightens the existing canonical combat/lifecycle path rather than adding another combat engine or lifecycle authority.

## Combat and death

Opening attacks remain direct command-response attacks, but the opening path no longer adds an extra forced damage packet or completes a hidden death before the first normal violence pulse. Later attacks are driven by the heartbeat violence pulse. NPC death now queues an explicit attacker-visible attack/death line and uses the existing lifecycle handoff for corpse creation, reward processing, kill credit, respawn scheduling, and encounter cleanup.

Player death remains policy-driven through the existing lifecycle respawn schedule. Administrative `restore`, `restore self`, `restore all`, and `restorestat` now restore HP, Mana, Move/Stamina, standing posture, dirty marking, prompt-invalidating resident projection, and one deliberate admin save checkpoint.

## Resident authority

Actual character entry hydrates once and registers a resident actor with a hydration-generation counter. Ordinary commands no longer rehydrate and re-register online characters. Logout saves once, removes the active character, unregisters actor state, cancels queued combat actions, and removes the resident combat actor so logged-out characters stop point-update regeneration.

## Corpse behavior

`create_corpse()` writes source, owner, room, creation monotonic time, decay seconds, and container state. The heartbeat corpse-decay pulse moves contents back to the room and destroys the corpse once. `get all corpse`, `get all cor`, `get all from corpse`, and numbered corpse resolution now use the same entity resolver as `look in corpse`, with a corpse fallback for common abbreviations.

## Movement and flee

Normal movement while fighting is rejected with an explicit `Use FLEE` message. `flee` routes through the canonical combat runtime, moves through a valid exit when possible, cancels queued actions for the fleeing actor, and asks encounter cleanup to end fights that no longer have valid opposition.

## Loot correction

The runtime no longer invents starter weapons during corpse parser handling. Basic wolf corpse contents come from the authored `forest_wolf` loot table; the Wolf Pelt quest item remains available through authored loot. Old persisted corpses may still contain historical items until they decay or are looted.

## Manual Windows checklist status

Not executed here. Tony should pull the branch on Windows, start Smart MUD, verify one heartbeat-start path, use `pulseinfo`, `residentstat`, `restore self`, `kill fox`, idle for two-second rounds, inspect/loot corpses with `get all corpse` and `get all cor`, test movement block/flee, quit Kraevok, enter Player, and confirm Kraevok no longer appears in `residentlist` or regeneration diagnostics.

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
