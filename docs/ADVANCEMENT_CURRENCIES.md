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

- Glory purchases now use canonical centralized costs (`GLORY_PRACTICE_COST = 100`, `GLORY_TRAIN_COST = 250`) and one SQLite transaction that debits EconomyService Glory ledger rows and grants exactly one progression session. Insufficient Glory reports the required cost and current balance and grants nothing.
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
