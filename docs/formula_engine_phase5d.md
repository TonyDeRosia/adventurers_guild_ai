# Smart MUD Formula Engine and Modifier Pipeline (Phase 5D)

Phase 5D introduces a deterministic, architecture-only Formula Engine. It is the single gateway for derived values such as attack rating, armor, critical chance, parry, block, dodge, movement speed, cast speed, threat, carry capacity, spell power, healing power, resistances, regeneration, and future Builder-defined statistics.

No gameplay formulas, combat balancing, equipment math, skill math, spell math, threat generation, or AI decisions are implemented in this phase.

## Formula Registry

The registry stores formula metadata without executing formulas: ID, display name, description, version, dependencies, inputs, outputs, validation metadata, plugin owner, Builder owner, world overrides, and plugin data. Worlds and future plugins can replace formula definitions without changing engine Python.

## Modifier Pipeline

Modifiers are contributions, not formulas. Each modifier records a unique ID, source, category, priority, stacking rule, duration, target stat, operation, value, conditions, and plugin data. Supported operations are add, subtract, multiply, divide, minimum, maximum, override, percentage increase, percentage reduction, clamp, and custom.

## Stacking

The registry supports policies for unique, replace, refresh duration, stack, highest only, lowest only, and Builder custom. These policies decide which contributions are visible to a formula trace; they do not balance gameplay.

## Tracing

Formula Engine calls return a final value, formula name, modifier list, calculation trace, execution time, and diagnostic metadata so Builder/Admin tools can inspect every step.

## Actor Integration

Actors expose `get_derived_value`, which delegates to the Formula Engine. Permanent derived-stat caching remains invalidatable and is not used as an authority for calculations.

## Builder Diagnostics

Read-only commands are available for Builder/Admin roles: `formula list`, `formula show`, `formula trace`, `formula validate`, `formula debug`, `modifier list`, `modifier trace`, `modifier debug`, `actor formulas`, and `actor modifiers`.

## Import/Export and JSON Collections

Builder drafts now recognize `formulas.json`, `modifier_types.json`, and `future_formula_templates.json`. Existing imports continue to work, and unknown modifier/formula data is surfaced as validation warnings where possible.

## Validation

Validation covers duplicate formula IDs, missing dependencies, circular dependencies, invalid operations, unknown target stats, reserved names, version conflicts, and unknown modifier types. Plugin ownership and world override fields are retained as extension points for Phase 5E and later.

## Phase 5E execution safety extension

Phase 5E adds `engine.phase5e.SafeExpression` and canonical modifier execution. The supported expression language is numeric constants, named inputs, arithmetic, parentheses, and `min`, `max`, `clamp`, `floor`, `ceil`, `round`, and `abs`. Arbitrary Python execution, imports, attribute access, comprehensions, loops, and mutation are rejected.
