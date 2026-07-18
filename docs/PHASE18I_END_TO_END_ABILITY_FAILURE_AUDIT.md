# Phase 18I End-to-End Ability Failure Audit

## Reproduced failure

The production command path had two divergent behaviors: display rows came from `AbilityExecutionService.list_known_abilities`, while the cast path could still hand the full post-command text to the gateway as an ability query. The broken fallback let `magic wolf`, `magic missile wolf`, and `armor self` be treated as ability names instead of a spell phrase plus target.

## Root causes traced

- Ability/target text was combined in `MudCommandEngine._cmd_use_ability` when `resolve_spell_tokens` did not return `RESOLVED`: it assigned `aid = defined or query`, which passed the whole player argument to the gateway.
- Quote boundaries were lost in `AbilityRuntimeGateway.tokenize_ability_input`: `shlex.split` converted `'magic missile' wolf` into a single `magic missile` token followed by `wolf`, but `resolve_spell_tokens` compared that token to canonical spell-name tokens and failed to consume exactly the quoted spell text.
- `armor self` failed for the same combined-query reason: the parser/gateway path could pass the whole string as a name rather than retaining `armor` as the spell and `self` as target text.
- Displayed-but-not-known failures were caused by command paths not consistently using the exact canonical learned projection and by re-resolution after parsing. The repaired path executes pre-resolved spell IDs with `execute_by_id`.
- Spellup was capable of reporting zero useful candidates when candidate enumeration and execution did not share the same canonical known-spell rows. The current command enumerates `list_known_spells`, excludes harmful spells, and executes each buff by canonical ID.
- Display rows are no longer synthesized from formatting fallbacks for `skills` and `spells`; they are rows returned by canonical learned/progression state.

## Trace fields now available

The parser publishes debug-level structured events through the ability event bus for `cast_parse_started`, `cast_spell_text_resolved`, and `cast_target_text_extracted`. Each includes actor ID, raw input, parsed spell text or matched text, consumed token count, target text, ability ID, and status.

## Verification summary

The Phase 18I integration tests create new characters through `MudRuntime.create_character`, enter them into `shattered_realms`, run `spells` through `MudRuntime.handle_input`, and exercise casting/spellup through the shared runtime command dispatcher. They assert that displayed spells are known, pre-resolved IDs never return unknown/not-known, quoted spell names strip closing quotes, and target text is not included in canonical spell names.
