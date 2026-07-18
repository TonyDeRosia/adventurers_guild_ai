# Command and Ability Input Runtime

## Cast parsing model

`cast` and `c` now parse spell invocation as two values: a canonical spell ID and remaining target text. The cast command never sends the entire post-command argument string to generic ability execution as the ability name.

The internal parse result is shaped as a spell invocation result with status, ability ID, canonical name, matched text, consumed token count, target text, match type, and ambiguity candidates.

## Quoted spell input

If the first non-space character is `'` or `"`, the parser captures text up to the matching closing quote as the spell phrase, removes both quotes, skips spaces after the quote, and preserves the remainder as target text. Unterminated quotes return `UNTERMINATED_QUOTE` and do not spend mana or enter the gateway.

Examples:

- `c 'magic missile' wolf` resolves spell text `magic missile` and target `wolf`.
- `c "magic missile" wolf` resolves spell text `magic missile` and target `wolf`.

## Unquoted spell input

Unquoted input is matched from the beginning of the argument with actor-known spell token prefixes. The resolver supports full names and per-token prefixes such as `magic`, `magic missile`, and `mag mis` for `Magic Missile`. It records exactly how many leading tokens were consumed and returns the remaining words to target resolution.

## Execution by canonical ID

Once the parser resolves a spell ID, `MudCommandEngine._cmd_use_ability` calls `AbilityRuntimeGateway.execute_by_id`. The gateway then validates knowledge, target rules, resources, cooldowns, and handlers for that exact canonical ID without reconstructing the spell name from raw text.

## Phase 18K command/ability invocation integrity

Phase 18K keeps command dispatch single-pass while allowing exact multiword active ability invocations to win over generic help fallback. `build campfire` is a player skill invocation for `build_campfire`; Builder/admin `build` remains available through the Builder command path when used as Builder syntax.

Active skills expose invocation metadata in the skill display. `Build Campfire` shows `command: build campfire`; `Set Camp` shows `command: set camp`. If an active ability lacks an implemented handler, the canonical ability gateway returns `HANDLER_NOT_IMPLEMENTED` rather than allowing a help-topic collision to be the only outcome.

Cast parsing continues to resolve quoted, full, and abbreviated spell names before passing remaining words as target text. Named target failures are target failures; target text is not appended back into the spell name.

## Phase 19C spell resources and natural weapons

Phase 19C adds canonical legacy spell mana costs via `SpellResourceCostService`. Magic Missile uses `mana_max=25`, `mana_min=10`, `mana_change=3`, and class-specific unlock level 1 for Adventurer and Magic User/Mage, producing costs 25/22/19/16/13/10 by level. Cast and spellup validation consume the same service result; low-mana cast failures now show required and available mana. Resource payment is centralized through `RuntimeResourceService` so live score/prompt state and persistence stay aligned. The forest wolf natural attack miss path now carries the selected bite profile rather than falling back to punch wording.
