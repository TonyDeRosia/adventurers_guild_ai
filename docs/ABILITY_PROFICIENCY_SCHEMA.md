# Ability Proficiency Schema

Learnable abilities persist proficiency on `actor_ability_progression.proficiency` independently from character level, spell tier, unlock requirements, training, and learned state.

Builder-authored ability records may define these fields in `plugin_data` without Python edits:

- `default_proficiency`: starting proficiency percentage for newly learned characters; clamped to 1..100.
- `maximum_proficiency`: proficiency cap; clamped to 1..100.
- `improvement_chance`: configurable chance hook for a successful use to attempt +1% improvement. `0` disables rolls; `1.0` makes the current deterministic implementation always improve.
- `improvement_difficulty`: stored difficulty hook for later formulas.
- `minimum_successful_uses`: anti-spam hook before rolls are eligible.
- `improvement_roll_cooldown_seconds`: anti-spam cooldown hook reserved for formula/runtime integration.
- `usage`: execution syntax shown by ability-aware help.
- `help`: short help/usage text for ability help fallbacks.

Successful ability execution calls the canonical improvement hook. Failed validation never calls it. Displays render the actor's persisted proficiency as `N%` and intentionally omit Rank, `/100`, status, cost, category, cooldown, and descriptions from compact SKILLS, SPELLS, and ABILITIES lists.
