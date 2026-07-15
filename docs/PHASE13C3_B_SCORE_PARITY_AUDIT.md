# Phase 13C3-B SCORE Parity Audit

Primary reference: Adventurer's Lair `src/act.informative.c` `do_score`, reviewed from the upstream repository. The reference SCORE is a boxed character sheet with identity, resources, progression, carry/encumbrance, attributes, combat, currencies, quests, play time, status, hunger/thirst, and immortal diagnostics.

## Adventurer's Lair field parity

| Adventurer's Lair label/field | Gameplay meaning | Reference source system | Smart MUD canonical equivalent | Snapshot field | SCORE section | Status | Intentional difference |
|---|---|---|---|---|---|---|---|
| Name | Character identity | player record | Yes | `identity.display_name` | Character Identity | implemented | Stable fallback only if snapshot omits name. |
| Title | Player title | player record | Yes | `identity.title` / `title` | Character Identity | implemented | Hidden when empty unless supplied. |
| Race | Race selection | race/class system | No gameplay system yet | `race.availability` | Character Identity | unavailable | Shows honest `Unavailable`/`Not selected`, never Human. |
| Class | Class/track | class track system | No gameplay system yet | `character_class.availability` | Character Identity | unsupported | Shows `Not implemented`, never Adventurer. |
| Level | Progression level | class/progression | Yes | `level`, `progression.level` | Identity/Progression | implemented | Comes from snapshot only. |
| Alignment | Alignment score/status | player alignment | Partial | `alignment` | Character Identity | implemented with Smart MUD difference | Smart MUD displays canonical text/value supplied by snapshot. |
| Deity | Religion selection | deity/profile system | No | `mechanics.deity` if future snapshot supplies it | Character Identity | future phase | Placeholder is unavailable, not fabricated. |
| Hometown | Origin/hometown | player metadata | No | `mechanics.hometown` if future snapshot supplies it | Character Identity | future phase | Placeholder is unavailable, not fabricated. |
| Age | Character age | time/age helper | Partial | `age.display` | Character Identity | implemented with Smart MUD difference | No birthday mutation or real-time calculation in renderer. |
| Played time | Accumulated play time | player time | Yes when snapshot supplies it | `time.play_time` | Character Identity | implemented | Formatter lives before snapshot/display boundary. |
| Remorts | Prestige/remort count | remort system | No | future availability field | Progression | future phase | Not shown by default. |
| Experience | Current XP | progression | Yes | `progression.xp` | Progression | implemented | Number formatting only. |
| Experience to next level/TNL | XP remaining | class level curve | Yes | `progression.xp_to_next_level` | Progression | implemented | No level formula in SCORE. |
| Practice | Practice sessions | training | Partial | `progression.practice_points` | Progression | implemented with Smart MUD difference | Name comes from snapshot metadata when present. |
| Training | Training sessions | training | Partial | `progression.training_points` | Progression | implemented with Smart MUD difference | Name comes from snapshot metadata when present. |
| Quest points | Quest currency | quest system | Not canonical for SCORE yet | `progression.quest_points` only if supplied | Progression | future phase | Does not invent unsupported quest points. |
| Gold/currencies | Wallet | currency/player gold | Yes | `currency.*` | Currencies/Progression | implemented | Data-driven; omits ledger/premium internals. |
| Bank | Bank balance | bank/economy | Not in canonical snapshot by default | future `currency.bank` | Currencies | future phase | Not fabricated. |
| HP | Health current/max | resources/combat max | Yes | `resources.hp`, `resources.max_hp` | Resources | implemented | Display is read-only; no refill/sync. |
| Mana | Mana current/max | resources/combat max | Yes | `resources.mana`, `resources.max_mana` | Resources | implemented | Display is read-only. |
| Stamina | Stamina current/max | resources/combat max | Yes | `resources.stamina`, `resources.max_stamina` | Resources | implemented | Reference uses Move; Smart MUD uses Stamina. |
| Movement | Movement current/max | movement resource | Future/optional | `resources.movement`, `resources.max_movement` | Resources | future phase | Shown only if snapshot supplies it. |
| Base Stats/attributes | Core abilities | ability/race/affects | Yes | `attributes.*` | Primary Attributes | implemented | Fully data-driven; no hardcoded six-stat renderer. |
| Armor | Damage mitigation/AC | combat | Yes | `defense.armor` | Defense | implemented | Uses snapshot label/unit. |
| Evasion | Avoidance | combat | Yes | `defense.evasion` | Defense | implemented | Uses snapshot label/unit. |
| Accuracy | Hit chance/accuracy | combat | Yes | `offense.accuracy` | Offense | implemented | Does not calculate against equal-level target in renderer. |
| Hit bonus/Hitroll | Hit modifier | combat | Yes | `offense.hit_bonus` | Offense | implemented | Uses canonical stat projection. |
| Attack power | Physical offense | combat stats | Yes if published | `offense.attack_power` | Offense | implemented when supplied | Not hardcoded. |
| Damage bonus/Damroll | Damage modifier | combat | Yes | `offense.damage_bonus` | Offense | implemented | Uses canonical stat projection. |
| Spell power | Magic offense | combat stats | Yes if published | `offense.spell_power` | Offense | implemented when supplied | Not hardcoded. |
| Healing power | Healing scaling | combat stats | Yes if published | `offense.healing_power` | Offense | implemented when supplied | Not hardcoded. |
| Weapon damage | Equipped weapon profile | equipment/combat | Yes | `weapon_profile` | Damage | implemented | Renderer does not inspect equipment. |
| Unarmed damage | Fallback damage | combat | Yes | `unarmed_profile` | Damage | implemented | No fake 0-0 weapon. |
| Critical hit/spell/heal | Crit ratings | critical system | Yes | `criticals.*` | Criticals | implemented | Unit comes from stat metadata. |
| Critical avoidance | Anti-crit stat | combat stats | Yes if published | `defense.critical_avoidance`/`criticals` | Defense/Criticals | implemented when supplied | Not fabricated. |
| Spell Saves | Save value | saves | Split saves | `saves.*` | Saving Throws | implemented with Smart MUD difference | Smart MUD supports physical/mental/magic. |
| Resistances | Damage resist/vuln | constants/effects | Yes | `resistances.*` | Resistances | implemented | Data-driven custom resistances. |
| Initiative/speeds | Turn timing | combat speed | Yes | `speed.*` | Speed and Initiative | implemented when supplied | No better/worse implication. |
| Carry Capacity/current carry | Weight limits | inventory/equipment | Yes | `carrying.*` | Carrying and Encumbrance | implemented | Snapshot owns inventory scan. |
| Encumbrance | Burden state | carry thresholds | Yes | `encumbrance.*` | Carrying and Encumbrance | implemented | Labels from snapshot/world data. |
| Hunger | Need state | conditions | Partial | `survival.hunger` | Survival and Condition | implemented when supplied | No fake zero. |
| Thirst | Need state | conditions | Partial | `survival.thirst` | Survival and Condition | implemented when supplied | No fake zero. |
| Fatigue | Need state | survival | Partial | `survival.fatigue` | Survival and Condition | implemented when supplied | No fake zero. |
| Conditions/position | Posture and status | lifecycle/conditions | Yes | `survival.posture`, `conditions` | Survival/Identity | implemented | No hidden admin state. |
| Active affects | Buff/debuff list | affects | Yes | `effects` | Active Effects | implemented | Player-safe fields only. |
| PK status | PvP flag | player prefs | Future/optional | `mechanics.pk_status` | Status and Mechanics | implemented when supplied | Not fabricated. |
| Mount/followers/pets | Companions | companion systems | No | future companion fields | Companions | future phase | Section omitted by default. |
| World/zone/area/room | Location | world/room | Partial | `location.*` | Location | implemented when supplied | Normal display uses names only. |

## Current Smart MUD SCORE audit before this phase

| Area | Finding | Resolution in this phase |
|---|---|---|
| Handler | `MudCommandEngine._cmd_score` handled `score/sc` but treated first argument as legacy subsection. | Routes `score`, `sc`, `score compact`, `score full`, and `score detailed` through one handler and one snapshot request. |
| Renderer input | `build_score_document` accepted character and could build a snapshot as a compatibility fallback. | Live command passes one `CharacterDisplaySnapshot`; renderer uses the snapshot only for SCORE content. |
| Snapshot version | Snapshot default was `phase13c3a3c.v1`. | Snapshot schema and source version now use `phase13c3-b.snapshot.v1`. |
| Display-time calculations | Old renderer hardcoded six attributes and grouped combat dict values directly. | New renderer builds `ScoreViewModel` and `DisplayStat` rows; it formats values but does not compute gameplay. |
| Direct equipment/effect reads | Legacy snapshot service may adapt ad-hoc character fields; SCORE renderer did not isolate damage/effects well. | SCORE damage/effects render only `weapon_profile`, `unarmed_profile`, and `effects` from the snapshot. |
| Hardcoded labels/order | Old SCORE hardcoded Strength/Dexterity/etc. and a fixed combat chunk list. | Stat labels/order/visibility come from snapshot stat metadata where supplied; stable fallbacks remain for identity concepts. |
| Placeholder fields | Race/class placeholders were omitted or em-dash style. | Availability states distinguish available, unavailable, inactive, unsupported, not applicable, and hidden. |
| HTML | Generic span rendering lacked SCORE-specific semantic structure. | SCORE HTML uses `<section class="mud-score">`, section headings, `<dl>`, `<dt>`, and `<dd>` with escaping. |
| Text | Classic frame existed but sections were coarse. | Text frame is sectioned for identity, progression, resources, attributes, offense, defense, damage, criticals, saves, resistances, speed, carrying, survival, effects, mechanics, and location. |

## Final classification

Implemented: identity, title, level, alignment when supplied, age, played time, XP/TNL, practice/training when supplied, resources, data-driven attributes, offense, defense, damage profiles, criticals, saves, resistances, speed, carrying/encumbrance, survival needs when supplied, conditions, effects, mechanics when supplied, location when supplied, currencies.

Implemented with Smart MUD differences: class/race are availability placeholders until gameplay exists; movement is optional; saves are physical/mental/magic rather than one spell-save row; currency is data-driven rather than fixed gold/diamonds/glory/bank.

Unavailable/future phase: race gameplay, class gameplay, deity, hometown, remorts, bank, quests as SCORE systems, mounts, followers, pets, summons, criminal flags, AFK/invisible/hidden/mounted/grouped/casting/cooldown locks unless future snapshots supply player-safe mechanics.
