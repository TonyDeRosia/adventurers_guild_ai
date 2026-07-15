# Phase 13C3-A Smart MUD Character and Combat Stat Audit

## Current-state audit

| Feature | Current canonical source | Persistence source | Current consumers | Current defects | Migration requirement | Planned authoritative source |
|---|---|---|---|---|---|---|
| `Actor.attributes` | `engine/actors.py` placeholder defaults | `characters.actor_data` where present | legacy score/render tests | Transient/display-oriented, not authoritative | Preserve valid legacy values | `character_attributes` rows plus world attribute definitions |
| `Actor.resources` | Actor dataclass and runtime character fields | `characters.hp_current`, `mana_current`, `stamina_current` | score/prompt/combat helpers | Maximums were static defaults | Current values remain persisted and clamped | `CombatStatService` derived max formulas |
| `derived_statistics_cache` | Actor placeholder cache | actor JSON | old FormulaEngine traces | Stale placeholder cache | Treat as non-authoritative | Formula-backed derived stat definitions |
| FormulaEngine | `engine/formulas.py` modifier trace engine | builder formula JSON | ability/economy traces | Not tied to character attributes | Keep safe expression principle | `CombatStatService` safe formula layer over authored formulas |
| `character_stats` | legacy key/value table | SQLite | tests only | Not typed, no permanent/modifier split | Leave compatible | New normalized `character_attributes` table |
| `characters.data` / `actor_data` | mixed runtime JSON | SQLite/runtime objects | snapshot builders | Display projection risk | Read valid legacy attributes only | Projection, not authority |
| Equipment modifiers | item JSON `modifiers` | inventory/equipment state | item/equipment commands | No generic stat pipeline | Map item modifiers to `StatModifier` | generic modifier collection |
| Affect definitions | `character_affects` + effect containers | SQLite/actor JSON | affects display | Not stat-aware | Context/test affects via modifiers | generic modifier model |
| Combat runtime | `engine/combat*.py` | transient | combat commands | Uses local calculations | Consume snapshots later | `CombatStatService` |
| Ability calculations | ability runtime | world ability JSON | ability commands | separate from canonical stats | Feed attributes into future formulas | formula authority |
| Progression | character level/xp | characters table | score/training | not stat-integrated | level formula input | combat formula inputs |
| Display snapshots/SCORE | display snapshot service | none | score | could show untruthful placeholders | Do not expand SCORE | attributes/combatstats projections only |
| Builder content | builder JSON | world builder files | builder commands | no statdef/attribute workflow | draft-isolated files | attribute/formula/statdef commands |
| World package formulas | combat/formula placeholders | world JSON | limited tests | incomplete derived schema | seed definitions | `worlds/shattered_realms/formulas/*` |

## Implemented architecture

* Published attributes live in `worlds/shattered_realms/attributes/attributes.json` and Builder drafts in `worlds/shattered_realms/builder/attributes.json`.
* Canonical persisted per-character state is `character_attributes(character_id, attribute_id, base_value, permanent_modifier, created_at, updated_at, source, metadata_json)`.
* `CharacterAttributeService` migrates missing rows idempotently from world defaults or valid legacy actor attributes, clamps to authored min/max, and calculates immutable `CalculatedAttribute` breakdowns.
* Generic `StatModifier` supports add, subtract, multiply, percentage_add, percentage_multiply, set_minimum, set_maximum, and override.
* Stacking order is: collect eligible modifiers, sort by `(priority, modifier_id)`, apply all `stack`, collapse non-stack groups by highest/lowest/replace/unique_by_source/unique_by_group, then apply operation order in the sorted sequence. Attribute authored clamps are applied last.
* Derived stats live in `worlds/shattered_realms/formulas/derived_stats.json`; formula expressions live in `worlds/shattered_realms/formulas/stat_formulas.json`.
* `CombatStatService` calculates resources, offense, defense, saves, criticals, resistances, unarmed/weapon damage projections, speed, and carrying/encumbrance from the same attribute/modifier pipeline.

## Remaining issues

* Existing SCORE is intentionally not rebuilt in Phase A.
* Race/class point-buy, leveling stat gains, and NPC AI remain out of scope.
* Builder mutation commands are conservative draft-workflow foundations; full editing UX can deepen in later phases.
