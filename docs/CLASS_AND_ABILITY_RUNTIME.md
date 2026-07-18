# Class and Ability Runtime

## Canonical class identity

The canonical player class key is `actor_progression_state.primary_class_id`. Character creation accepts aliases/user input only before validation, saves the canonical class ID in `MudCharacter.actor_data`, and initializes progression with the same ID. Runtime entry calls `MudRuntime._ensure_starter_progression`, which hydrates `primary_class_id`, `primary_class_track_id`, `race_id`, and display `class_name` from `ProgressionService.progression_identity_snapshot`.

Display names are derived from class profiles and tracks. SCORE renders the display name from the character display snapshot and does not use display text as a database key.

## Known ability source of truth

`AbilityExecutionService.get_actor_abilities(actor_id)` is the runtime source of truth for known abilities. It merges active ability grants, persisted `actor_ability_progression` rows, and live actor plugin grants, then filters through enabled ability definitions.

`MudRuntime._ensure_starter_progression` reconciles class ability progression. It uses authored class profile grants when present, otherwise a small current-runtime starter map for shipped classes. It adds expected class abilities and retires only legacy `source_type=starter_character` rows that are not part of the canonical class set.

## Ability name resolution and gateway

`AbilityRuntimeGateway` normalizes case, underscores, hyphens, repeated whitespace, and single/double quoted multi-word ability names. Prefix parsing is used for commands such as `cast 'magic missile' fox`, returning the ability ID and remaining target text.

The gateway distinguishes failures:

- `unknown_ability` for no matching definition;
- `not_known` for a definition the actor has not learned;
- `wrong_category` when a spell command names a skill;
- `handler_not_implemented` for definition-only abilities;
- downstream validation/resource/target reasons from `AbilityExecutionService`.

## Execution routing

`cast`, `invoke`, `perform`, and direct commands such as `kick`, `bandage`, and `bash` route through `MudCommandEngine._cmd_use_ability`, which delegates to `AbilityRuntimeGateway`. Direct commands no longer depend on a separate executable ability list.

## Spellup

`spellup` obtains known spells from `AbilityExecutionService.get_actor_abilities`, filters to enabled beneficial self-targeted spellup metadata, skips offensive/debuff entries, and executes each candidate through the same `AbilityExecutionService.execute_instant_ability` path used by normal instant casts. It reports cast, already-active, low-mana, and blocked counts.

## Active effects

Cast and spellup effect application use the existing ability effect persistence (`actor_effect_instances`) plus live actor effect containers. `aff`, `saff`, and SCORE-related affect views read the same canonical persisted/runtime effect state, so spellup duplicate checks and display are aligned.

## Migration/reconciliation behavior

Existing characters are preserved. The class identity repair is idempotent and only fills missing canonical identity fields when valid source data exists. Ability reconciliation is conservative: it retires only legacy automatic `starter_character` rows outside the actor's class progression and never deletes unknown-origin, awarded, trained, admin, or manually learned rows.

## Phase 18G command usability note

Phase 18G connects displayed active skills and spells to player input by using the canonical command registry, the Phase 18F ability gateway, and shared spell/target token resolution. Completed abilities execute through `execute_result(...)`; known definitions without mechanics continue to return `HANDLER_NOT_IMPLEMENTED` rather than `UNKNOWN_ABILITY`.
