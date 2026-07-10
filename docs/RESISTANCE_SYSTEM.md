# Resistance System

Phase 5E adds a canonical, traceable stat-source pipeline without implementing combat execution.

## Ownership table

| Concern | Definition owner | Runtime owner | Calculation owner | Renderer |
|---|---|---|---|---|
| Item identity | item template | item instance | n/a | item renderer |
| Equipped slot | slot profile | SQLite item instance | Actor equipment bridge | equipment renderer |
| Item stat bonus | item template modifier declaration | source item instance | Formula Engine / Phase 5E resolver | score/diagnostics |
| Active effect | effect template | SQLite effect instance | Formula Engine / Phase 5E resolver | affects/score |

## Canonical modifier record

Runtime bonuses use `CanonicalModifier` records with IDs, source type, source instance/template IDs, owner actor ID, target domain/key, operation, priority, stacking group/policy, visibility, timestamps, and metadata. Anonymous bonuses are not emitted.

## Operation order

1. Base input collection.
2. Add/subtract.
3. Multiply/divide.
4. Percentage increase/reduction.
5. Minimum/maximum constraints.
6. Override by priority and stable modifier ID.
7. Clamp.
8. Numeric finite normalization.

Lower-priority or stacking-losing modifiers remain visible in traces as inactive. Division by zero, NaN, and infinity are errors.

## Stacking

Stacking is grouped by explicit `stacking_group`, never display name. Supported policies are `unique`, `replace`, `refresh`, `stack`, `highest_only`, `lowest_only`, and `independent`. Source instance IDs remain present so duplicate item names do not merge.

## Runtime rules

Equipped SQLite item instances activate immutable template modifiers. Inventory, room, dropped, or destroyed items do not contribute. Effect templates are definitions; `actor_effect_instances` stores active runtime state and persists across restart according to policy. Effects and equipment never directly mutate Actor base attributes or derived statistics.

## Builder and JSON

World collections exist for `equipment_slot_profiles`, `effect_templates`, `resource_profiles`, `resistance_profiles`, `combat_formulas`, and `modifier_types`; matching Builder draft files/templates are included for client authoring and import/export.

## Non-goals

No attack commands, combat rounds, damage, healing, casting, aggro, respawning, AI decisions, loot, shops, trainers, or population maintenance are implemented. Future combat must consume resolved Actor values instead of recalculating them.

## Manual acceptance commands

```text
builder on
cplist
formula list
resourcelist
resistlist
slotlist
effectlist
score
score attributes
score combat
score equipment
score resistances
actorstat self
actor modifiers self
derivedstat self attack_power
get iron sword
wield iron sword
equipment
equipmenttrace self
actor modifiers self
derivedstat self attack_power
score combat
unwield
derivedstat self attack_power
actor modifiers self
effect apply self blessed_example
affects
saff
spellup
effectstat <effect_instance_id>
actor modifiers self
score effects
score attributes
score resistances
```
