# Combat formula profile (Phase 19A)

`data/defaults/combat_formula_profile.json` declares the typed, versioned
default `smartmud.tba_custom_physical.v1` profile.  `PhysicalFormulaProfile`
validates its identity, version, and 5–95 hit bounds.  A world `rules/combat.json`
is an optional override; missing overrides select this default.  Warmup records
the profile source and marks combat **unavailable**, rather than ready, if no
profile validates.

All integer divisions in `engine/physical_combat.py` use `trunc_toward_zero`,
which preserves C-style truncation for negative values.
