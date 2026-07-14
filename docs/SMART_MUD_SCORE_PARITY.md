# Smart MUD SCORE Parity

## Adventurer's Lair audit

Reference inspected: `src/act.informative.c`, especially `ACMD(do_score)`, `encumbrance_text()`, condition label helpers, class/race/progression accessors, carry macros, and immortal conditionals. The upstream raw file is minified in this environment, so this audit records the player-visible contract rather than C implementation details.

The normal SCORE is a boxed `Score` sheet. It presents, in order: name/title, race/class/level, age/alignment, optional birthday text, experience/TNL, practice/train/quest/remort advancement currencies, carrying weight and item count with encumbrance text, six base attributes, AL combat summary values, currencies, quest summary when present, played time, hunger/thirst, condition messages, and immortal-only diagnostics.

## Displayed lines and ownership

| Line | Canonical runtime owner | Builder ownership | Gameplay owner | Projection dependency | Notes |
|---|---|---|---|---|---|
| Name/title | `CharacterDisplaySnapshot.identity` | `build_score_document()` | Resident actor identity | `score` projection | Title is appended to name like AL visible identity. |
| Race/class/level | snapshot race/class/progression | `build_score_document()` | race/class/progression authorities | `score` projection | Availability states are shown only until full gameplay systems exist. |
| Age/alignment | snapshot age/alignment | `build_score_document()` | lifecycle/identity/alignment authorities | `score` projection | Birthday message is conditional. |
| Experience/TNL | `ProgressionDisplayAdapter` | `build_score_document()` | progression service | `score` projection | Display formats only. |
| Practices/trains/quest points/remorts | progression snapshot | `build_score_document()` | progression/training/quest authorities | `score` projection | Defaults to zero when the canonical snapshot omits optional currencies. |
| Carrying/items/encumbrance | `CombatStatService` carrying snapshot or runtime carrying fields | `build_score_document()` | item ownership/carry authority | `score` projection | Display no longer sums inventory weights. |
| STR/INT/WIS/DEX/CON/CHA | `CombatStatService` attributes | `build_score_document()` | attribute authority | `score` projection | Only formatted from canonical attribute entries. |
| Armor/hitroll/damroll/spell save/critical | `CombatStatService` combat sections | `build_score_document()` | combat stat service | `score` projection | Modern offense/defense/speed/resistance sections are removed from normal SCORE. |
| Currency | `CurrencyDisplaySource`/economy service | `build_score_document()` | economy service | `score` projection | Data-driven currency order remains canonical. |
| Quest summary | `CharacterDisplaySnapshot.quest_summary` | `build_score_document()` | quest runtime | `score` projection | Displayed only if supplied. |
| Played time | snapshot time source | `build_score_document()` | lifecycle/play-time authority | `score` projection | AL-style sentence. |
| Hunger/thirst | survival snapshot | `build_score_document()` | runtime needs authority | `score` projection | No generalized survival panel. |
| Conditions | snapshot conditions | `build_score_document()` | lifecycle/effect authority | `score` projection | Only condition lines, not a modern effects dashboard. |
| Immortal information | snapshot source versions, detailed/admin mode only | `build_score_document()` | runtime authorities | `score` projection | Normal players do not see diagnostics. |

## Removed from normal SCORE

Primary Statistics heading, Secondary Combat Statistics headings, Damage Profile, Criticals section, Resistance section, Speed section, Mechanics section, Location section, Companions section, dashboard grouping, snapshot diagnostics for normal players, active effects panel, resource HP/Mana/Move rows, and display-only carry weight summing.

## Remaining differences and deferred fields

* The exact Adventurer's Lair color tokens are approximated through Smart MUD semantic roles; themes may recolor but should not reorganize default SCORE.
* Race/class gameplay is still surfaced through snapshot availability if canonical data is absent.
* Quest details, birthdays, remorts, and condition wording depend on canonical runtime snapshots being populated.
* Windows manual testing was not performed in this Linux container.

## Testing performed

* Visual parity unit coverage strips color through `render_display_plain()` and verifies line order, labels, removed headings, omitted prompt resources, frame width, and immortal-only diagnostics.
* Snapshot authority coverage verifies the renderer consumes `CharacterDisplaySnapshot` values and the carrying collector no longer performs display-layer inventory summing.
