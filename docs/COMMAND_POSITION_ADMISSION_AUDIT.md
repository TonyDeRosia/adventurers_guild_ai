# Command Position Admission Audit

## Scope and result

The production command boundary is `MudCommandEngine.handle_command`.  Browser
and Telnet both enter through `MudRuntime.handle_input`, so admission there is
transport-neutral and occurs before deterministic handler dispatch, target
resolution, resource payment, or combat encounter creation.  Position is read
from the resident `Actor`, not the persisted `MudCharacter` projection.

The supplied archive was requested at `/mnt/data/src(1).zip`; it was not
present in this execution environment, so the reference-file inspection command
could not complete.  The policy below follows the minimum positions specified
in the task and preserves the documented Adventurer's Lair messages.

| Command family | Current handler | Previous check | TBA minimum | Smart MUD minimum | Enforcement | Test |
|---|---|---:|---:|---:|---|---|
| look / examine / scan | interaction / scan | none or local resolution | resting | resting | router policy | sleeping look rejected |
| score / report / inventory / equipment / skills / spells / spellup | display handlers | none | resting | resting | router policy | sleeping display rejected |
| cardinal/diagonal movement, run, walk | movement handler | movement-local | standing | standing | router policy | sleeping movement rejected |
| cast | ability execution | validation after ability parsing | sitting | sitting | router policy | sleeping cast has no payment/target resolution |
| camp / campfire / make camp | survival handler | handler-local | standing | standing | router policy | sleeping build rejected |
| kill / attack / kick / bash | combat foundation | combat validation after target resolution | fighting | fighting | router policy plus combat validation | sleeping kill has no encounter |
| wake | position handler | local posture transition | sleeping | sleeping | excluded from minimum policy | wake admitted while sleeping |
| sleep / rest / sit / stand | position handler | local posture transition | varies | transition-specific | excluded from minimum policy | existing posture tests |
| automatic combat rounds | `CombatRuntime.process_encounter_round` | heartbeat-local posture check | fighting-capable | fighting-capable | scheduler skips non-admitted actors | sleeping actor performs no round |

## Resolver audit

Combat target resolution uses `find_occupant` and resident actor identity, not
one `MudCharacter` or one template.  All visible living resident entities in
the room are candidates.  Keyword/ordinal matching preserves the canonical
resident room-presentation order, making `1.wolf`, `2.wolf`, and aliases stable
for Browser and Telnet.  Missing ordinals remain explicit resolution failures.

## Position model

`ActorPosition` is an explicit `IntEnum`: dead, mortally wounded,
incapacitated, stunned, sleeping, resting, sitting, fighting, standing.
Smart MUD already stores these values on the resident Actor's combat profile;
no second character position field was added.  Comparisons use enum ranks,
never alphabetical strings.  Mortally wounded is represented even where no
separate UI posture command currently creates it.
