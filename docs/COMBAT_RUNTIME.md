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
