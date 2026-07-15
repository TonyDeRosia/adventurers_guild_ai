# Phase 13C3-B2 Primary/Secondary Stat Parity Audit

Reference target: TonyDeRosia/tbamud_adventurers_lair. The requested repository could not be fetched reliably from this execution environment during implementation, so this audit is conservative and is based on the Smart MUD prior Phase 13C3 Adventurer's Lair audit plus the requested source file list and known field categories from the prompt. No C formulas, structs, macros, tables, or file formats were copied.

## Adventurer's Lair SCORE and stat field parity

| Reference field / behavior | Player-facing label family | Source value or macro family in AL | Gameplay consumers | Players | NPCs/mobs | Smart MUD equivalent before | Smart MUD canonical stat ID | Formula ID | Phase status | Intentional difference |
|---|---|---|---|---:|---:|---|---|---|---|---|
| Strength | Strength | strength ability score / GET_STR-style access | melee force, hit/damage/carry checks | yes | yes | attribute definitions | `strength` | consumed by `attack_power`, `damage_bonus`, `carry_capacity`, `physical_save` | implemented | Smart MUD keeps authored semantic role `physical_power` instead of hardcoding a six-stat engine. |
| Intelligence | Intelligence | intelligence ability score | spell scaling, mana, knowledge checks | yes | yes | attribute definitions | `intelligence` | `spell_power`, `max_mana`, `magic_save`, `mental_save`, `casting_speed` | implemented | Smart MUD uses data-driven formulas. |
| Wisdom | Wisdom | wisdom ability score | saves, healing, spell control | yes | yes | attribute definitions | `wisdom` | `healing_power`, `mental_save`, `magic_save`, `max_mana`, `initiative` | implemented | Smart MUD distinguishes healing and spell power. |
| Dexterity | Dexterity | dexterity ability score | accuracy, evasion, initiative/speed | yes | yes | attribute definitions | `dexterity` | `accuracy`, `evasion`, `initiative`, `attack_speed`, `movement_speed`, criticals | implemented | Smart MUD exposes ratings, not tbaMUD roll text. |
| Constitution | Constitution | constitution ability score | HP, physical endurance, saves | yes | yes | attribute definitions | `constitution` | `max_health`, `max_stamina`, `physical_save`, `critical_avoidance`, `recovery_speed` | implemented | Resource maxima remain internal to normal SCORE. |
| Charisma | Charisma | charisma ability score | social/presence/leadership hooks | yes | yes | attribute definitions | `charisma` | future social/presence checks | implemented as primary, noncombat | No fake combat bonus is added. |
| Hit roll / attack accuracy | Hit Roll / Accuracy | hitroll/accuracy modifier family | hit resolution in fight code | yes | yes | partial combatstats | `accuracy`, `hit_bonus` | `accuracy`, `hit_bonus`, `attack_hit_resolution` | implemented | Split into rating and authored hit bonus. |
| Damage roll / damage bonus | Damage Roll / Damage Bonus | damroll/damage modifier family | physical damage | yes | yes | partial combatstats | `attack_power`, `damage_bonus` | `attack_power`, `damage_bonus`, `physical_damage_resolution` | implemented | Attack power and flat damage bonus are distinct. |
| Armor / armor class | Armor | armor/ac family | physical mitigation | yes | yes | armor stat | `armor` | `armor`, `armor_mitigation` | implemented | Higher armor is better in Smart MUD display. |
| Evasion / avoidance | Evasion | avoidance/evasion family | opposed hit resolution | yes | yes | evasion stat | `evasion` | `evasion`, `attack_hit_resolution` | implemented | Displayed as a rating. |
| Saving throws | Saves | save arrays/macros | spell/effect resistance | yes | yes | partial saves | `physical_save`, `mental_save`, `magic_save` | same IDs plus `saving_throw_resolution` | implemented | Collapsed into three explicit save channels. |
| Weapon damage | Weapon damage | equipped weapon dice/damage data | attack damage | yes | yes | legacy summary strings | `weapon_profile` | `weapon_damage_min`, `weapon_damage_max` | implemented | Structured profile; absent when unarmed. |
| Unarmed damage | Unarmed damage | bare-hand damage | attack damage without weapon | yes | yes | partial summary | `unarmed_profile` | `unarmed_damage_min`, `unarmed_damage_max` | implemented | Always structured and active if no weapon. |
| Critical stats | Critical hit fields | critical hit modules | critical chance/damage | yes | yes | partial criticals | `critical_melee`, `critical_spell`, `critical_heal`, `critical_avoidance`, `critical_damage` | matching formula IDs where authored | implemented where authored; critical damage documented for future formula metadata | Smart MUD distinguishes melee/spell/heal crits. |
| Spell combat | Spell power / spell critical | spell damage functions | spell damage/saves | yes | yes | partial spell stats | `spell_power`, `critical_spell`, `magic_save` | `spell_power`, `spell_damage_resolution` | implemented | Ability coefficients drive spell damage. |
| Healing combat | Healing power / heal critical | healing spells | healing amount/clamp | yes | yes | partial healing | `healing_power`, `critical_heal` | `healing_power`, `healing_resolution` | implemented | Healing clamps through resource maximum. |
| Resistances | Resistances | damage type resistance family | typed mitigation | yes | yes | resistance dict | data-driven resistance IDs | direct resistance aggregation + `resistance_mitigation` | implemented | Renderer supports published IDs without code changes. |
| Carrying/encumbrance | Carrying | carried weight/capacity | encumbrance state | yes | yes | display-layer calculation | `current_carry_weight`, `carry_capacity`, `encumbrance_percent`, `encumbrance_state` | `current_carry_weight`, `carry_capacity`, `encumbrance_percent` | implemented | Display consumes canonical combat stat carrying projection. |
| Attack/cast/recovery/movement speed | Speed | speed/timing fields where present | timing systems | yes | yes | formulas existed | `initiative`, `attack_speed`, `casting_speed`, `recovery_speed`, `movement_speed` | matching formula IDs | implemented in snapshot; display only active authored fields | Future runtime systems may expand consumers. |

## Smart MUD stat model summary

* Primary stat definitions are world-authored in `worlds/shattered_realms/attributes/attributes.json` and include Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma.
* Semantic roles are `physical_power`, `agility`, `endurance`, `intellect`, `willpower`, and `presence`; Shattered Realms maps them to the six current attributes.
* Secondary stat formulas are world-authored in `worlds/shattered_realms/formulas/stat_formulas.json` and resolved through `CombatStatService`.
* Normal SCORE no longer renders prompt-style current HP/mana/stamina/movement pairs. Current resources remain prompt-owned.
* `CharacterDisplaySnapshotService` now prefers the canonical `CombatStatService` snapshot for attributes, secondary stats, damage profiles, carrying, encumbrance, and source versions.
* `combatstats` and combat resolution use the same canonical `CombatStatSnapshot` service path.

## Deterministic legacy NPC/mob migration policy

NPCs/mobs are projected through the same actor-stat path as players. If a template or runtime actor lacks persisted player attributes, Smart MUD resolves deterministic defaults from the world-authored attribute defaults, then overlays template/instance/equipment/effect/resistance inputs. This avoids random migration and avoids requiring NPCs to own `MudCharacter` rows.

## Manual Windows acceptance status

Not performed in this Linux container. Suggested Windows command sequence after launching the game client: `score`, `sc`, `combatstats`, `combatstats offense`, `combatstats defense`, `combatstats saves`, `combatstats resistances`, and `combatstats damage`.
