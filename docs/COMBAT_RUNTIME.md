# Adventurer's Lair Gameplay Stabilization Notes

This update replaces the normal player-facing numbered Smart MUD training marketplace with Adventurer's Lair-style `train` and `practice` command semantics. The data-driven `TrainingService` remains available for future builder/admin surfaces, but normal gameplay no longer routes `train`, `tr`, `practice`, `prac`, or `pr` through global numbered lessons, profession offers, spell offers, respec offers, or fallback trainers outside the current room.

Reference audit status: the remote `tbamud_adventurers_lair` repository could not be cloned in this execution environment because GitHub access returned `CONNECT tunnel failed, response 403`. The implemented behavior is therefore a faithful Smart MUD compatibility layer based on the requested Adventurer's Lair behavior, and this limitation should be re-audited on a network that can access Tony's repository.

## Training

`train` requires a current guild/trainer room. Listing shows available training sessions, six base stats with cap 20, and the supported stat/resource syntax only. Stat training costs one training session and changes the permanent runtime base stat exactly once. Resource training costs ten sessions and adds ten to max hit points, mana, or Move/Stamina.

## Practice

`practice` lists remaining practice sessions and active known abilities with proficiency percentages and descriptors. `practice <ability>` requires the current guild/trainer room, resolves partial names, rejects ambiguity/unknown abilities, spends one practice session, and increases proficiency without exceeding cap.

## Advancement currencies

Character entry no longer grants automatic demonstration attribute points. Existing legitimate progression is preserved. The admin inspection/correction command for Kraevok is:

```text
progressioninspect char_shattered_realms_kraevok
```

If the history shows only `starter_character` / `starter_demonstration` unspent attribute grants, remove the unspent demonstration balance with the progression repair/admin workflow; do not reset Kraevok or SQLite.

## Runtime combat

Combat now uses the existing canonical `CombatRuntimeService` with a MudRuntime-owned pulse thread. The pulse ticks every 200ms and processes eligible combat rounds on a real-time two-second cadence. The opening `kill` attack still resolves in the direct command response; later rounds are queued to the async channel.

## Persistence and performance

Active character combat persistence now updates resident characters and dirty state instead of loading/saving characters for each attack. Combat messages use resident active characters for room delivery. SQLite remains for encounter tables, history, outbound queue, death lifecycle, initial hydration, autosave, and shutdown checkpoints.

## Browser delivery

The browser uses adaptive polling: 150-250ms immediately after combat messages, approximately 1000ms while idle/playing, and slower polling for hidden tabs. Opening command output is direct and not duplicated through async output.

## Combat messages and death

Generic `dealing damage` prose was removed from normal attack messages. Messages now use attack nouns such as fist and bite and severity bands such as graze, glance, hit, strike, slam, crush, blast, shred, and pulverize. Existing lifecycle death/corpse/reward handling remains the canonical authority and is invoked once by combat runtime.

## Positions and regeneration

Ground `sit`, `rest`, `sleep`, `wake`, `stand`, `lay`, and `lie` are supported. Combat rejects sit/rest/sleep with Adventurer's Lair-style text. Position is stored on resident actor data and marks the character dirty for coalesced persistence. Regeneration remains an intentional follow-up area for deeper Adventurer's Lair parity.

## Tests and Windows status

Focused Linux tests were run in this environment and are reported in the PR/final response. Windows manual acceptance at `C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2` was not performed here.

## Adventurer's Lair stabilization follow-up (2026-07-14)

The previous alias/trainer patch is preserved: `tr`, `pr`, `buypractice`, `buyprac`, `buytrain`, `lay`, and `lie` continue to route to the existing player commands and trainer room definitions remain data-driven.

Remaining unfinished work addressed in this follow-up:

- Glory purchases now use canonical centralized costs (`GLORY_PRACTICE_COST = 250`, `GLORY_TRAIN_COST = 600`) and one SQLite transaction that debits EconomyService Glory ledger rows and grants exactly one progression session. Insufficient Glory reports the required cost and current balance and grants nothing.
- Attribute training now writes the permanent `character_attributes.permanent_modifier` component through the canonical attribute projection instead of relying on transient `setattr` state. Training affects only the trained permanent component and is capped at 20.
- Resource training records a persistent trained-resource bonus in character actor data and updates the command-facing maximum resource by +10 for hit/hp, mana, or move at a cost of ten training sessions.
- Training output reports changed values from before/after canonical state snapshots and suppresses unchanged fields.
- Practice listing and mutation route through `ProgressionService` projections and atomic mutation helpers. Rank, maximum rank, proficiency, cap, cost, and calculated gain are separate fields; command handlers no longer perform direct practice UPDATE statements.
- Posture remains owned by the command-position authority; survival services may consume rest/sleep context but ordinary ground rest/sleep does not require furniture or a campsite.
- Combat runtime continues to use monotonic `time.monotonic()` scheduling and a single background/manual pulse path guarded by encounter processing locks from the existing runtime service.
- `perfstat` and `perfstat reset` report/reset runtime, combat, practice, training, position, resident-cache, autosave, and regeneration counters for admins.
- `advancementinspect` and `advancementrepair <character> --dry-run|--apply` inspect attribute-point history and only remove proven unspent demonstration grants. The repair path is idempotent and writes spend history through the progression currency ledger.

Focused verification added in `tests/test_adventurers_lair_unfinished_requirements.py` covers atomic Glory purchases, insufficient-Glory no-grant behavior, persistent permanent Strength training, practice projection/mutation separation, and advancement repair dry-run/apply idempotence.

Broad-suite status from this environment is recorded in the PR summary rather than claimed as Windows acceptance. Windows manual acceptance still must be performed under `C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2` with Kraevok and the existing `shattered_realms` world.

## Adventurer’s Lair runtime stabilization update

- Scheduler ownership is canonicalized in the FastAPI/WebRuntime lifecycle: startup creates one asyncio pulse task and shutdown cancels/awaits it. `MudRuntime` no longer starts a daemon scheduler thread in its constructor; it exposes `process_runtime_pulse()` as bounded work.
- Runtime pulses use monotonic real time for combat cadence, scheduler lag, duration metrics, in-memory message timestamps, and regeneration due checks. `advance_world_time()` remains for calendar/world simulation and no longer advances combat rounds.
- Active combat now keeps hydrated actors resident in `CombatRuntimeService.resident_actors`; ordinary round loads reuse those actors and mark entity actors dirty rather than writing NPC health after every hit.
- Live combat output is queued in bounded per-character memory queues with sequence metadata and delivered once without the `combat_outbound_messages` claim transaction. SQLite remains available for audit/history, not normal live delivery.
- Lethal combat resolution calls `RuntimeLifecycleService.process_defeat_or_death()` as the canonical death transition. It owns defeat marking, corpse creation, rewards/kill credit, respawn scheduling, and idempotency.
- Player-facing death policy follows the configured lifecycle transition; NPC deaths create one corpse/reward/credit path. Remaining parity work is documented as differences until Windows manual acceptance is performed.
- Posture remains command-owned; survival needs consumes posture data. Real-time regeneration applies deterministic posture multipliers: sleeping +4/tick, resting +2/tick, standing/sitting +1/tick, fighting/dead +0/tick, capped at maxima.
- Glory prices now match Tony’s Adventurer’s Lair defaults: `GLORY_PRACTICE_COST = 250` and `GLORY_TRAIN_COST = 600`.
- Permanent trained attributes use `character_attributes.permanent_modifier` as the writable authority; mutable `actor_data.trained_attributes` updates were removed.
- Permanent trained resource bonuses are recorded as `actor_progression_modifiers` rows and projected into `actor_resource_versions` maximums so HP, Mana, and Move survive restart/recalculation.
- Practice remains data-driven through progression profiles; ambiguous advancement repair is not broadened beyond existing safe behavior in this stabilization patch.
- Focused verification command: `python -m pytest -q tests/test_adventurers_lair_unfinished_requirements.py tests/test_smart_mud_performance_stabilization.py tests/test_live_combat_phase12c2.py tests/test_phase12a2_runtime_fixes.py`. Broad verification command: `python -m pytest -q`.
- Windows manual acceptance has not been performed in this Linux container. Tony should run the checklist from `C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2`, confirm one scheduler-start message, attack an Emberwood fox/wolf, observe automatic ~2s rounds without commands, inspect `perfstat`, verify death/corpse/reward once, test ground sit/rest/sleep regeneration, verify 250/600 Glory purchase gates, train HP/Mana/Move, restart, and confirm maximums persist.

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

### 2026-07-15 combat-start latency note

Smart MUD now follows the Adventurer's Lair responsiveness model more closely for combat start: the KILL command performs target lookup, resident encounter creation, one opening attack, prompt/message preparation, and response construction before the newly-created encounter is eligible for ordinary violence-pulse processing. Resident violence uses resident round state for attack event publication rather than synchronous SQLite round lookups. Repeated selects of an already-ready world join the existing generation and do not rerun entity materialization or combat warmup.

## Resident runtime combat authority update

Live combat now follows the documented resident-authority policy: world content is prepared once per generation; online characters and active NPCs attach to one resident `Actor`; active encounters, participants, targets, queued actions, and round numbers are owned by memory; ordinary violence resolves from resident indexes and queues in-memory output/prompt packets; SQLite is used for hydration, checkpoints, audit, death durability, logout, shutdown, and administrative inspection rather than per-hit authority.

Windows manual acceptance has not been performed in this Linux environment. Operators should run `restore self`, `perfstat reset`, `violenceprofile reset`, `sqltrace combat reset`, `kill spider`, let ten rounds execute, and verify that ordinary rounds report zero SQLite operations while prompts update immediately and dirty state flushes later.

## Phase 15B.9 Combat Startup Latency Hot Path Audit

Root cause removed: `CombatRuntimeService.start_player_attack()` and NPC `start_actor_attack()` still refreshed the `CombatContentRegistry` during ordinary combat startup. On Windows this meant the `kill wolf` path could rebuild combat content before producing the first visible packet. The startup path now relies on the world-load/admin `refresh_content()` boundary and performs resident actor lookup only.

Resident startup flow after READY:

```text
kill command -> visible resident target lookup -> resident player actor lookup -> resident NPC actor lookup -> resident encounter lookup/create -> resident targets -> opening attack -> in-memory packet/prompt queue
```

Removed from ordinary player/NPC combat startup:

- `refresh_content()` calls from `start_player_attack()` and `start_actor_attack()`.
- Unconditional player `Actor` reconstruction on every kill command when a resident actor already exists.
- Unconditional NPC `Actor` reconstruction on every kill command when a resident actor already exists.

SQLite policy for this phase:

- Live command traces continue to suppress encounter, participant, target, action queue, and action-consumption writes.
- Direct non-session test/admin calls may still mirror encounter/participant/action state for compatibility and audit.
- Character saves are durability checkpoints for non-active direct calls; active live characters remain coalesced through resident dirty state.
- Death lifecycle, corpse, reward, respawn, restart cancellation, command history, and final/autosave durability remain SQLite-backed by design.

Combat caches that survive ordinary gameplay now include the warmed content registry, formula engine wiring, combat stat service wiring, resident actor map, resident encounter map, resident participant target state, resident action queues, combat output queues, natural-weapon/message warmup data, and prompt/resource packet snapshots. These caches may be invalidated by equipment, buff/debuff, body, level, race/class, builder publish, world-generation changes, or explicit admin reload; ordinary attacks do not refresh them.

Instrumentation points available in traces/counters include target resolution, resident actor lookup, encounter creation, opening attack resolution, response construction, response sent, message queue latency, packet delivery latency, first/warm violence pulse duration, prompt queue/delivery counters, and resident player/NPC cache hit/miss counters.

Measured on this Linux CI container (Windows manual testing still required):

| Measurement | Observed |
| --- | ---: |
| Warmup trace focused test | 0.15 s total test runtime |
| Cold startup visible packet | not Windows-verified |
| Warm startup visible packet | not Windows-verified |
| First violence pulse | regression test environment observed ~2700-2900 ms in one legacy direct test path |
| Prompt delivery | instrumented via `prompt_delivery_ms`; not Windows-verified |
| Packet delivery | instrumented via `combat_message_delivery_latency_ms`; not Windows-verified |

Remaining limitations: target visibility can still depend on the broader room/entity runtime, direct compatibility calls can still persist audit rows synchronously, and Windows manual testing is required before declaring the player-visible `kill wolf` latency fixed.

## Phase 15B.11 resident room occupancy

Living NPC room rendering and combat target resolution now share `MudRuntime.resident_occupants_by_room`, backed by `CombatRuntimeService.resident_actors` and entity-instance/actor-id maps. Normal KILL/ATTACK/CONSIDER/DIAGNOSE target lookup is resident-memory only: no `refresh_content()`, world reload, entity rematerialization, or SQLite target query is used in the command hot path. See `docs/RESIDENT_ROOM_OCCUPANCY.md` for the authority table, target grammar, lifecycle invariants, diagnostics, and Windows acceptance steps.

## Phase 15B.12 flee and natural attacks

Flee uses the resident combat service's Dexterity-primary contested formula, then delegates successful movement to `MudRuntime.move_resident_actor()` so resident actor location and occupancy remain synchronized. NPC attack snapshots now preserve resident natural attack data before attack resolution, preventing nonhumanoid starter creatures from using humanoid fist messaging.
