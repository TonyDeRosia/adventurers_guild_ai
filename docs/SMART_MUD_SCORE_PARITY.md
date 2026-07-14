# Smart MUD SCORE Parity

Status: Partial. This pass corrects the existing SCORE renderer and snapshot contract without starting Phase 15A or zone reset work.

## Approved visible mortal fixture

```text
╔═══════════════════════════════════════════════════════════════════════════════╗
║ CHARACTER STATUS                                                              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Name: Aster                  Title: the Bold                                  ║
║ Race: Human                  Class: Warrior                                   ║
║ Level: 7                     Age: 22 years old                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║ Exp: 12345                           TNL: 55                                  ║
║                                                                               ║
║ Carry Capacity: 42 / 100 (Moderate)                                           ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Base Stats: Str 14 (+0) Dex 13 (+0) Con 12 (+0)                               ║
║             Int 11 (+0) Wis 10 (+0) Cha 8 (+0)                                ║
║                                                                               ║
║ Armor: 12       Evasion: 7     Spell Saves: 10                                ║
║                                                                               ║
║ Offense: Hitroll +4 Damroll +3 Accuracy: 82%                                  ║
║                                                                               ║
║ Critical hit: 5 Critical Spell: 2 Critical Heal: 1                            ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Currencies                                                                    ║
║ Gold:       99 Diamonds:      0 Glory:      0 Bank:        4                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Quests completed: 0                                           Quest Points: 9 ║
║ Not currently on a quest.                                                     ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Play time: 1 day, 2 hours                                                     ║
║ Status: Standing Hunger: Satisfied Thirst: Quenched                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

## Intentional Smart MUD divergence

Implemented: normal SCORE omits current HP, maximum HP, current Mana, maximum Mana, current Move/Stamina, maximum Move/Stamina, and Alignment. These systems remain canonical prompt/resource/combat systems and are not moved elsewhere in SCORE.

## Field authority matrix

| Field | Status | Canonical authority | Persistence source | Gameplay consumer | Projection dependency | Invalidation reason |
|---|---|---|---|---|---|---|
| Name/title | Implemented | CharacterDisplaySnapshotService | characters/data identity | command/session identity | identity,title | identity/title mutation |
| Race | Partial | progression/race assignment surfaced through CharacterDisplaySnapshotService | actor_progression_state.race_id or character data | attributes/progression | race, world definitions | race mutation |
| Class/class track | Partial | progression/class-track assignment surfaced through CharacterDisplaySnapshotService | actor_progression_state primary_class_id/primary_class_track_id or character data | progression/abilities | class,class track, world definitions | class mutation |
| Level/XP/TNL | Implemented | ProgressionDisplayAdapter/ProgressionService | actor_progression_state or legacy character fields | leveling | progression | XP/level mutation |
| Age/birthday | Partial | snapshot age provider | character birth fields plus world calendar when available | calendar/lifecycle | birth state, calendar | calendar/birth mutation |
| Carrying | Implemented | CombatStatService carrying snapshot / CarryingDisplaySource | inventory/equipment runtime | encumbrance | carrying,equipment,inventory | item/equipment mutation |
| Attributes | Implemented | CombatStatService/AttributeDisplaySource | character attributes/equipment/effects | combat/resource formulas | attributes,effects,equipment | stat/effect/equipment mutation |
| Armor/evasion/spell saves | Implemented | CombatStatService | formula definitions and actor state | combat hit/spell resolution | combat statistics | combat-stat mutation |
| Hitroll/damroll/accuracy | Implemented | CombatStatService | formula definitions and actor state | hit/damage resolution | combat statistics | combat-stat mutation |
| Unarmed dice | Partial | CombatStatService unarmed_profile | body/combat formulas | unarmed attacks | weapon state, unarmed profile | equipment/combat formula mutation |
| Criticals | Implemented | CombatStatService | formula definitions and actor state | melee/spell/heal critical resolution | critical statistics | combat-stat mutation |
| Currencies | Implemented | EconomyService/CurrencyDisplaySource | economy balances | shops/rewards/banking | currencies, bank balance | economy mutation |
| Quests | Partial | QuestService snapshot data | actor_quest_instances/history | journal/rewards | quest history, active quest, Show VNUMs | quest mutation |
| Play time | Implemented | session lifecycle snapshot time | accumulated played seconds plus active session | session accounting | play-time display generation | session tick/save |
| Status/survival/conditions | Partial | actor runtime/survival snapshot | actor posture/survival state | movement/combat/survival | position,target,hunger,thirst,intoxication | actor/survival mutation |
| Summonable/show VNUMs | Partial | player preference authority | preferences/identity snapshot | summon permission/builder display | preferences | preference mutation |
| Immortal poof/builder zone | Partial | identity and Builder editing context snapshot | character prefs/builder context | immortal movement/builder | poof text,builder zone | preference/builder mutation |

## Golden fixture coverage

Implemented focused coverage: framed width, left-aligned title, exact dividers and blank rows, no HP/Mana/Move/Alignment row, no modern sections, no unavailable/not implemented placeholders, fixed currency order, numeric spell saves, zero/normal play-time formatting, immortal poof and Builder zone rows.

Partial remaining fixture expansion: separate complete-string cases for every requested encumbrance threshold, active quest VNUM, birthday, sitting/fighting, condition notices, and transport visible-text equivalence.

## Windows testing status

Not run in this Linux container. Manual Windows acceptance should enter existing `Kraevok`, run `score`, and compare visible text after stripping ANSI/HTML to the fixed 81-column contract. No SQLite reset, world recreation, or character recreation is required by this code change.

## Remaining differences

Partial: canonical persisted Kraevok data was not present in this container, so no one-time repair command was applied. If live Windows Kraevok still lacks race/class/birth fields, use existing progression/admin tools to assign valid world definitions without changing the renderer. Valid IDs must be selected from `data/worlds/shattered_realms` progression definitions in the target checkout.

## 2026-07-14 SCORE identity regression repair

### Failure

Live `sc`/`score` could expose the internal projection exception `score_projection_incomplete field=identity.race` when an existing character had no runtime `race_name` and the display snapshot had not resolved canonical progression IDs.

### Root cause

The SCORE formatter correctly requires complete fields, but `CharacterDisplaySnapshotService` populated Race and Class from transient runtime fields (`race_name`, `race`, `class_name`, `character_class`, `char_class`) instead of resolving the durable `actor_progression_state` row. Legacy characters whose canonical row was missing identity IDs, or whose runtime object had only legacy/raw IDs, therefore produced an incomplete SCORE projection.

### Canonical identity sourcing

`ProgressionService.get_actor_progression(character_id, "player")` is the single SCORE snapshot query for progression state. `ProgressionService.progression_identity_snapshot()` resolves:

- `race_id` through `ProgressionContent.get("race_profiles", race_id)` and displays the definition `name`.
- `primary_class_id` through `ProgressionContent.get("class_profiles", primary_class_id)` and displays the base class definition `name`.
- `primary_class_track_id` through `class_tracks`; the track must belong to the selected class before its player-facing name can become the display class name.
- `species_id` through `species_profiles` for validation and future gameplay.

### Legacy migration behavior

Character entry calls the idempotent legacy progression repair before SCORE prewarm. The repair preserves an existing valid canonical row, then reads valid legacy `race_id`, `primary_class_id`, `class_id`, class/profession, and track IDs from the character record/actor data, then falls back to the validated `player_starter` progression profile only when no valid legacy value exists. It records migration metadata in `actor_progression_state.metadata_json` and never rewrites inventory, equipment, currencies, quests, room, effects, role, level, or experience.

Admins can inspect or explicitly run the same repair path in-game:

- `progressioninspect char_shattered_realms_kraevok`
- `progressionrepair char_shattered_realms_kraevok --dry-run`
- `progressionrepair char_shattered_realms_kraevok --apply`

Automatic character-entry migration should repair Kraevok; use the apply form only if inspection shows an unrepaired row after re-entering.

### Player-facing error boundary

Normal players no longer receive raw `score_projection_incomplete ...` text. If SCORE still encounters an incomplete projection, the command logs character ID, world ID, entry ID, projection generation, and missing field server-side and returns: `Your character data could not be loaded completely. Please contact an administrator.` Failed builds are marked failed and are not cached as valid SCORE content.

### Cache invalidation behavior

SCORE cache keys and invalidation now include progression identity and birth-state dependencies in addition to existing character, progression, currency, inventory, equipment, effects, location, and world-definition dependencies. Character-entry identity repair invalidates identity-dependent projections before SCORE is rebuilt.

### Kraevok verification status

Linux focused tests include Kraevok-like legacy identity repair and SCORE rendering through canonical definitions. Windows acceptance was not run in this container. Tony should verify on Windows with the existing world and existing `char_shattered_realms_kraevok` character.

### Windows acceptance steps

1. Stop Smart MUD.
2. Open PowerShell and run `cd "C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2"`.
3. Pull or update the `main-v2` branch.
4. Start Smart MUD.
5. Log into the existing account.
6. Enter Kraevok (`char_shattered_realms_kraevok`).
7. Type `score` or `sc`.
8. Confirm a complete framed SCORE sheet appears.
9. Confirm no `score_projection_incomplete` text appears.
10. Type `score` again.
11. Confirm the second call remains correct and uses the cache.
12. Run `progressioninspect char_shattered_realms_kraevok`.
13. Confirm resolved race ID/name, class ID/name, and track are valid.
14. Restart Smart MUD.
15. Re-enter Kraevok and confirm repaired identity persists.

### Remaining partial systems

Calendar aging remains a lifecycle compatibility value rather than a complete world-calendar feature. Survival displays consume canonical/display-authority values initialized during entry for legacy characters; broader survival simulation remains documented in survival-system docs. HP, Mana, Move, and Alignment remain omitted from normal SCORE by the approved parity contract.

## 2026-07-14 combat legitimacy addendum

SCORE combat fields were re-audited against the canonical combat path. The active combat fields that demonstrably affect real gameplay are Armor, Evasion, Spell Saves, Hitroll/Hit Bonus, Damroll/Damage Bonus, Accuracy as a hit-chance input, Critical hit, Critical Spell, Critical Heal, and the Unarmed Damage profile. Initiative, Attack Speed, Casting Speed, Recovery Speed, Movement Speed, Parry, and Block remain explicitly inactive until the runtime scheduler or defense resolver consumes them. Presence remains non-combat/partial and is not invented as a combat stat.

Live combat now consumes the same `CombatStatService` snapshot family used by SCORE. Weapon averages may remain display-friendly, but live damage rolls the canonical profile min/max per action.
