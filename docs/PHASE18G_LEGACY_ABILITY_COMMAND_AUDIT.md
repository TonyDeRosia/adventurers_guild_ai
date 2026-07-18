# Phase 18G Legacy Ability Command Audit

## Source verification status

The requested customized TBA/CircleMUD ZIP is not present in this container or repository checkout. I searched `/workspace` for ZIP archives and for legacy `src/interpreter.c` paths and found no uploaded legacy source. Therefore this pass does **not** claim complete legacy parity for formulas or messages.

Command/table behavior implemented in this pass is limited to the explicit legacy examples supplied in the Phase 18G prompt:

| Legacy command | Minimum abbreviation | Smart MUD canonical command | Ability ID |
|---|---:|---|---|
| `cast` | `c` | `cast` | n/a |
| `kick` | `ki` | `kick` | `kick` |
| `bash` | `bas` | `bash` | `bash` |
| `bandage` | `band` | `bandage` | `bandage` |
| `look` | `l` | `look` | n/a |
| `affects` | `aff` | `affects` | n/a |
| `north` | `n` | `north` | n/a |
| `east` | `e` | `east` | n/a |
| `south` | `s` | `south` | n/a |
| `west` | `w` | `west` | n/a |
| `up` | `u` | `up` | n/a |
| `down` | `d` | `down` | n/a |

## Smart MUD source audited

- `engine/command_registry.py`: command metadata, aliases, command resolution.
- `engine/mud_commands.py`: web/Telnet command dispatch, `cast`, direct ability commands, `skills`, `spells`, `spellup`.
- `engine/abilities.py`: Phase 18F execution gateway, ability/spell resolution, target resolution, resource checks, cooldown checks, effects, damage, healing, EventBus publication.
- `worlds/shattered_realms/abilities/abilities.json`: current canonical definitions for Kick, Bash, Bandage, Magic Missile, Armor, Bless, and Strength.

## Current-pipeline failure points found

1. The command registry accepted arbitrary prefixes by dictionary membership rather than stable minimum abbreviations.
2. `kick`, `bash`, and `bandage` existed as direct handlers, but abbreviated forms such as `ki`, `bas`, and `band` did not reliably canonicalize before entering `_cmd_direct_ability`.
3. `cast` reused generic ability-prefix logic, which only matched full leading ability phrases and could not split `c magic goblin` into spell tokens plus target tokens.
4. Quoted and unquoted multi-word spell input did not share a token resolver.
5. Target lookup matched exact names or whole words but not unambiguous visible prefixes such as `gob` for `Goblin`.
6. Ambiguous command/target cases were either collapsed or could fall through as generic unknown failures.

## Implemented behavior extraction notes

Because the legacy ZIP is unavailable, ability mechanics continue to use the existing Smart MUD Phase 18F definitions in `worlds/shattered_realms/abilities/abilities.json`:

- Kick: stamina cost, physical damage, cooldown, self-target rejection.
- Bash: stamina cost, physical damage, cooldown, self-target rejection.
- Bandage: stamina cost, healing/effect, cooldown.
- Magic Missile: mana cost, arcane damage, cooldown, hostile target required.
- Armor: mana cost, Armor affect, refreshable effect.
- Bless: mana cost, Bless affect, refreshable effect.
- Strength: mana cost, Strength affect, refreshable effect.

## Bandage compatibility note

The prompt warns that custom `do_bandage` may contain an inverted success/failure branch. The legacy source required to verify that branch was not available. This pass does not copy or correct that suspected custom behavior; it preserves Smart MUD's existing canonical Bandage handler until the customized source can be inspected.
