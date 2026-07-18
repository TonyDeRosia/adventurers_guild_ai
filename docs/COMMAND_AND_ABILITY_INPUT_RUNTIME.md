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
