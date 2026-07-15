# Smart MUD Combat Legitimacy and Adventurer's Lair Parity Audit

Status date: 2026-07-14.

## Adventurer's Lair source access

The audit attempted to clone `https://github.com/TonyDeRosia/tbamud_adventurers_lair` into `/tmp/tbamud_adventurers_lair`, but this execution environment returned `CONNECT tunnel failed, response 403`. No C source was copied. The parity facts below are therefore limited to the behavior already recorded in this repository's prior Adventurer's Lair audit documents and the behavior contract provided for this task. Windows/manual acceptance should repeat the C-source audit in an environment with repository access.

## Behavioral reference captured for this fix

* Hit chance is a clamped 5%-95% contest with base 30, attacker level, hitroll/accuracy, strength, intelligence, wisdom, level gap, concealment/situational modifiers, defender evasion, defender level, posture, and automatic-hit handling for helpless targets.
* Weapon and unarmed damage are rolled per action, not averaged for live combat.
* Player unarmed profile follows the parity contract: `dice_count = min(4, 1 + level / 30)`, `die_size = min(7, 2 + level / 20)`, `flat_bonus = max(0, level / 30)`.
* Physical armor is higher-is-better mitigation: `post_armor = max(minimum_damage, raw_damage * 100 / (100 + max(0, armor - armor_penetration)))`.
* Resistance is a typed percentage stage after armor unless true damage or the action flag bypasses it.
* Criticals are resolved from melee/spell/heal ratings by path. For damaging attacks Smart MUD now applies critical after armor and resistance to match the documented parity ordering requirement.
* Saving throws are defender success chances. Defender saves increase success; attacker penetration/spell power and attacker level advantage decrease defender success.
* Partial-save declarations are normalized to remaining percentages, with compatibility support for old reduction-style declarations.

## Smart MUD authority graph

Canonical path:

`MudCommandEngine attack/cast/use` -> `CombatRuntimeService` encounter/participants/round queue -> typed `CombatActionRequest` -> `CombatResolutionContext` -> `CombatStatService` snapshot -> `CombatResolutionService` hit/save/damage/critical/mitigation pipeline -> `RuntimeResourceService` resource mutation and zero-health evaluation -> `RuntimeLifecycleService` defeat/death/corpse/reward/combat termination -> outbound combat messages and projection invalidation.

Compatibility-only path:

`CombatEngine.resolve_attack_legacy_for_migration_tests` remains available only when no `CombatStatService` is injected and is guarded against normal runtime use.

## Stat legitimacy matrix

| SCORE combat field | Definition source | Runtime source | Formula ID / expression | Real consumer | Invalidation | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Armor | `derived_stats.json`, formula registry | `CombatStatService.defense.armor` | `armor = equipment_armor`; `armor_mitigation = max(minimum_damage, raw_damage * 100 / (100 + max(0, armor - armor_penetration)))` | `CombatResolutionService` armor stage when `armor_applies` and non-true damage | equipment/effect/stat source versions | `test_armor_scaling_flags_resistance_flags_true_damage_and_partial_save_semantics` | Implemented for canonical snapshots; fixture construction for direct actor equipment remains integration-sensitive |
| Evasion | derived stat definitions | `CombatStatService.defense.evasion` | consumed by `attack_hit_resolution` | hit chance projection/resolution | equipment/effect/stat source versions | existing hit/miss tests | Implemented |
| Spell Saves | derived save stats | `CombatStatService.saves` | `saving_throw_resolution = 50 + defender_save - difficulty - attacker_stat - level_difference + ability_proficiency + situational_modifier` | save resolution | effect/stat source versions | `test_saving_throw_direction_stronger_attacker_lowers_defender_success` | Implemented |
| Hitroll / Hit Bonus | derived offense | `CombatStatService.offense.hit_bonus` | `attack_hit_resolution` | hit chance | equipment/effect/stat source versions | hit resolution tests | Implemented |
| Damroll / Damage Bonus | derived offense | `CombatStatService.offense.damage_bonus` | `physical_damage_resolution = base_damage + attack_power + damage_bonus` | damage base stage exactly once | equipment/effect/stat source versions | `test_damage_bonus_applies_once_and_weapon_roll_is_not_average` | Implemented |
| Accuracy | derived offense | `CombatStatService.offense.accuracy` | parity hit projection formula | hit chance and SCORE projection source | stat source versions | hit resolution tests | Implemented as meaningful hit input; SCORE still displays the rating field rather than a target-specific live opponent line |
| Critical hit | derived criticals | `CombatStatService.criticals.critical_melee` | `critical_resolution` | melee/weapon/unarmed damage critical path | effect/stat source versions | critical path in focused tests | Implemented |
| Critical Spell | derived criticals | `CombatStatService.criticals.critical_spell` | `critical_resolution` | spell attack critical path | effect/stat source versions | focused critical flag tests | Implemented |
| Critical Heal | derived criticals | `CombatStatService.criticals.critical_heal` | healing critical branch | healing path | effect/stat source versions | `test_healing_kind_clamps_to_maximum_and_uses_healing_result` | Implemented |
| Unarmed Dice | formulas | `CombatStatService.unarmed_profile` | parity min/max formulas from level | unarmed live damage roll and SCORE profile | level/stat source versions | damage roll tests | Implemented |
| Initiative / speed fields | derived definitions | `CombatStatService.speed` inactive | speed formulas exist | not consumed by scheduler yet | source versions | documented | Inactive |
| Parry / Block | formulas return zero | not shown as normal active SCORE fields | `parry_resolution=0`, `block_resolution=0` | no defense resolver | source versions | documented | Inactive |
| Presence | primary attribute | mechanics metadata says non-combat | N/A | no combat consumer | attribute source versions | documented | Partial / non-combat |

## Confirmed defects fixed

1. Damage bonus double application: weapon profile min/max formulas no longer embed `damage_bonus`; canonical physical damage adds `damage_bonus` once.
2. Weapon/live damage averaging: live resolution now performs a deterministic per-action roll across the canonical profile bounds using the seeded roller and action/round identity.
3. Unarmed contract: unarmed min/max derive from the Adventurer's Lair parity dice contract instead of ad-hoc strength-only formulas.
4. Hit chance: live resolution now uses a component projection with base chance, attacker and defender level, hit bonus, accuracy, strength, intelligence, wisdom, evasion, posture, range, concealment, clamp, and automatic-hit reason.
5. Armor: formula changed from flat subtraction to AL-style scaling and honors `armor_applies`.
6. Critical ordering: damaging criticals now multiply after armor and resistance.
7. Saving throw direction: attacker spell power/penetration and level advantage now reduce defender success rather than increasing it.
8. Partial saves: old ambiguous `partial_percent` is adapted; explicit remaining/reduction fields are supported.
9. Typed action flags: runtime now constructs `CombatResolutionContext` from typed `CombatActionRequest` fields instead of relying on a metadata-only subset.

## Intentional/current differences and limits

* Smart MUD keeps the Python service architecture rather than CircleMUD fighting pointers.
* Speed/initiative, parry, block, and presence are not claimed as completed combat mechanics.
* The environment could not fetch Adventurer's Lair C source, so this patch does not claim a fresh direct line-by-line C audit.
* Normal player messages remain player-facing and hide formula IDs; diagnostics remain in result traces and stored history.
* Offhand/dual-wield remains Partial unless a world profile explicitly routes extra actions through `CombatRuntimeService`.

## Windows manual status

Not performed in this Linux CI/container. Use the acceptance checklist in `docs/COMBAT_RUNTIME.md` with the existing Kraevok character and do not recreate the world or reset SQLite.
