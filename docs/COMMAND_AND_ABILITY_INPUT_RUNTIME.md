# Command and Ability Input Runtime

## Canonical command registry

`engine.command_registry.CommandRegistry` is the canonical command registry. Each command can now carry:

- canonical command word;
- explicit aliases;
- stable minimum abbreviation;
- ability ID for direct ability commands;
- command category/status/help metadata.

## Command abbreviation algorithm

Resolution order is:

1. exact canonical command;
2. exact explicit alias;
3. configured minimum abbreviation;
4. longer unambiguous prefix whose length satisfies the command's minimum abbreviation;
5. ambiguous/unknown typed failure.

Prefixes shorter than the configured minimum do not resolve unless they are explicit aliases. Ambiguous commands return candidates instead of selecting by insertion order.

Phase 18G configured minimum abbreviations include `cast (c)`, `kick (ki)`, `bash (bas)`, `bandage (band)`, `look (l)`, `affects (aff)`, and the six movement abbreviations `n/e/s/w/u/d`.

## Spell token parsing

The Phase 18G spell resolver lives on the Phase 18F ability gateway and is reusable outside `cast` as `resolve_spell_tokens(...)`. It:

- normalizes case and repeated whitespace;
- honors single-quoted and double-quoted phrases via shared tokenization;
- filters to actor-known spells for normal player casting;
- matches canonical names, IDs, short names, and aliases;
- supports token-by-token prefixes such as `mag mis` for `Magic Missile`;
- returns consumed spell-token count and the remaining target text.

## Spell/target boundary

For unquoted input, the resolver scores possible spell token spans and consumes only the winning span. The rest of the input is preserved as target text. Example: `c magic goblin` resolves `magic` to `magic_missile` when unambiguous and leaves `goblin` as the target.

## Target abbreviations

Canonical target resolution now supports exact visible room matches first, then unambiguous visible prefixes. Ambiguous target prefixes return `INVALID_TARGET` without spending resources.

## Direct skill routing

`kick`, `bash`, and `bandage` route through `_cmd_direct_ability`, canonicalize the command word, and then enter the same Phase 18F ability gateway used by `cast` and `use`.

## Action delays versus cooldowns

Cooldowns remain ability-specific readiness timers tracked by the ability service. Full legacy WAIT_STATE/action-delay parity is documented as deferred until the customized TBA source is available; this pass does not conflate cooldowns with action delay.
