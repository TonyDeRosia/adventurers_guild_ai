# Phase 19C Spell Resource Audit

## Legacy formula

Smart MUD now routes spell mana through `SpellResourceCostService`, matching the customized TBA `mag_manacost()` curve:

```text
cost = max(mana_max - mana_change * (actor_level - class_unlock_level), mana_min)
```

The class-specific unlock level is selected from the spell's `plugin_data.legacy_mana.class_unlock_levels`. For future multiclass actors, the current single-class progression source (`primary_class_id`/`class_id`) determines the curve until class-track grants store the granting track explicitly.

## Magic Missile metadata

Before Phase 19C, Magic Missile used generic ability costs: `mana` flat `5`, so Smart MUD ignored `mana_max`, `mana_min`, `mana_change`, and class unlock level.

After Phase 19C, Magic Missile carries the canonical legacy metadata:

| Field | Value |
| --- | ---: |
| mana_max | 25 |
| mana_min | 10 |
| mana_change | 3 |
| Adventurer unlock | 1 |
| Magic User/Mage unlock | 1 |

## Cost table

| Level | Cost |
| ---: | ---: |
| 1 | 25 |
| 2 | 22 |
| 3 | 19 |
| 4 | 16 |
| 5 | 13 |
| 6+ | 10 |

## Reductions

Reduction order is source-compatible integer arithmetic:

1. Compute the base level-scaled cost.
2. Empowered: `max(1, cost * 90 // 100)`.
3. Add Supreme Caster Discipline (5), Tactical Spell Memory (5), and Enchanter's Focus (10).
4. Cap the additive sum at 20%.
5. Apply `max(1, cost * (100 - reduction_pct) // 100)`.

## Payment timing and transparency

Validation computes the canonical cost before cast start. Failed resource validation spends zero mana and reports required and available mana, e.g. `You need 25 mana to cast Magic Missile, but you only have 8.` Successful instant casts pay full cost once through `RuntimeResourceService` so live actor, prompt/score projections, dirty-save state, and persistence remain aligned.

## Tested runtime character record

The Phase 19C smoke path creates a real Mage/Magic User character through `WebRuntime`, grants Magic Missile, sets mana to `30 / 30`, enters `emberwood_hunting_trail`, and verifies:

| Observation | Value |
| --- | --- |
| canonical class ID | `magic_user` via `mage` alias |
| level | 1 |
| Magic Missile unlock | 1 |
| reductions | none |
| computed cost | 25 |
| mana before cast | 30 |
| mana after one full-cost cast | 5 |
| failed second cast | 5 remains; rejection spends zero |
| persisted/reloaded mana | stored through `actor_resource_versions`/character sync |

## Starter mana balance

Current Smart MUD Mage starters use 50 maximum mana in normal runtime initialization, so a level-1 Magic Missile at 25 mana allows two full-cost casts from full mana. The smoke constrains mana to 30 to prove the low-mana second-cast path without changing starter balance. Adventurer starters are not primarily caster-capable in current class data, but Magic Missile retains the legacy Adventurer unlock for source compatibility.

## Regeneration audit

`RuntimeResourceService.process_due_regeneration()` clamps mana to maximum, skips dead actors and active combat actors, and improves recovery while resting/sleeping through the existing point-update policy. Phase 19C does not redesign regeneration; it documents and preserves the existing canonical resource mutator and maximum clamps.

## Natural weapon audit

The wolf punch-on-miss regression came from miss messages receiving no selected attack profile. The legacy isolated combat path now creates a zero-damage miss event carrying the same selected natural attack profile used for hit resolution, so forest wolf miss and hit messages both format from the authored bite profile rather than falling back to fist/punch wording.
