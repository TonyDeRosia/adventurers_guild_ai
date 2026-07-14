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
