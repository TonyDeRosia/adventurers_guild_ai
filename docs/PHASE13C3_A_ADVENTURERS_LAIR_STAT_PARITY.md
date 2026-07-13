# Phase 13C3-A Adventurer's Lair Stat Parity Audit

Reference reviewed: Adventurer's Lair `act.informative.c` `do_score`, including identity rows, HP/Mana/Move/Alignment, Exp/TNL, carry capacity and combat-score sections. The referenced implementation computes carry labels from carried weight divided by capacity and shows Light/Moderate/Heavy/Overloaded bands; Smart MUD stores these as world-authored thresholds instead of display code constants.

| AL SCORE field/label | Gameplay meaning | AL source concept | Smart MUD support before | Phase A equivalent | Difference | Phase |
|---|---|---|---|---|---|---|
| Name | character identity | character name | yes | unchanged | none | B display |
| Title | displayed title | title field | yes | unchanged | none | B display |
| Race | ancestry | race macros/table | placeholder | future race profile | not implemented yet | B/later |
| Class | class track | class display helper | placeholder | future class track | not implemented yet | B/later |
| Level | progression level | level macro | yes | formula input | none | A input |
| Age | character age | age helper | partial | identity field | no birthday display yet | B |
| Alignment | morality axis | alignment value | partial | future progression/social value | not combat authority | B |
| HP/Mana/Move | current/max resources | hit/mana/move max helpers | current persisted, max hardcoded | max_health/max_mana/max_stamina formulas | Move maps to stamina | A |
| Exp/TNL | progression | exp and next-level table | partial | level/xp input; TNL later | formula not rebuilt | B |
| Practice/Training | advancement currency | class/training data | partial | progression service | not in combatstats | later |
| Quest points | quest reward currency | quest system | partial | quest/economy systems | not stat foundation | later |
| Str/Dex/Con/Int/Wis/Cha | primary attributes | GET_* macros | placeholder Actor dict | world-defined attributes + character rows | authored defaults | A |
| Armor | physical mitigation input | AC/equipment | placeholder | derived armor stat | positive rating, not legacy AC sign | A |
| Evasion/Dodge | avoid attack rating | dodge/evasion functions | placeholder | evasion rating | named evasion | A |
| Parry/Block | defensive techniques | combat helpers | placeholder | modeled for future statdefs | not displayed until supported | later |
| Magical defense | magic defense input | saves/resist logic | placeholder | magic_save/resistances | separated model | A |
| Saves | resist effect rolls | saving throws | no canonical | physical/mental/magic_save | three-category model | A |
| Resistances | typed mitigation | resistance arrays | partial | typed percent map | enabled types in world defs | A |
| Critical avoidance | oppose crits | critical hit code | placeholder | critical_avoidance | rating | A |
| Accuracy/Hit bonus | hit resolution | hitroll/offensive hit | placeholder | accuracy + hit_bonus | separated rating/bonus | A |
| Attack rating/power | offense scaling | combat formulas | placeholder | attack_power | attack_rating deferred | A/later |
| Damage bonus | flat/scaled damage | damroll | placeholder | damage_bonus | formula-driven | A |
| Weapon damage | equipped weapon output | weapon data | partial templates | damage profile | no fabricated weapon | A |
| Unarmed damage | body attack | unarmed fallback | no | unarmed profile | humanoid starter formula | A |
| Spell/healing power | spell/heal scaling | spell systems | placeholder | spell_power/healing_power | formula hooks only | A |
| Armor penetration | bypass armor | combat concept | placeholder | model documented | not displayed until used | later |
| Critical melee/spell/heal/damage | crit chances/multiplier | critical modules | placeholder | critical_* stats | critical_damage deferred | A/later |
| Initiative/speeds | turn/cast/recovery/move pacing | combat timing | placeholder | speed section | rating scale starts at 100 | A |
| Reach/range | attack distance | weapon data | weapon templates | damage profile fields | not standalone stat | A |
| Carry weight/capacity/encumbrance | inventory burden | CAN_CARRY_W/IS_CARRYING_W | inventory weights partial | real inventory weight + formula capacity + world thresholds | thresholds authored | A |

## Intentional Smart MUD model choices

* Phase A adds `attributes`, `stats`, `combatstats`, and `statbreakdown`; it does not expand SCORE.
* Charisma remains social/leadership oriented and is not given fake combat math.
* Defensive and offensive units are documented as ratings unless marked as percent resistance.
