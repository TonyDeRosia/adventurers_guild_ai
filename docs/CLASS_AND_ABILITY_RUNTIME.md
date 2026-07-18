# Class and Ability Runtime

## Progression authority

Smart MUD currently preserves its authored class starter progression. In `shattered_realms`, level-1 mages intentionally start with Armor, Detect Magic, Magic Missile, and Strength; adventurers start with Set Camp, Build Campfire, and Recall; warriors start with Kick, Bandage, Bash, and Rescue. These are reconciled as persisted `actor_ability_progression` rows, not display-only rows.

## Learned-grant invariant

`skills`, `spells`, command parsing, direct ability commands, cast, spellup, and gateway validation all consume `AbilityExecutionService.list_known_abilities` and its spell/skill filters. For every displayed row, `knows(actor, row.id)` must be true. Executing a displayed canonical ID may fail for target, resources, cooldown, position, or missing handler, but must not return unknown or not known.

## Character creation lifecycle

Character creation selects class/race, initializes progression state, reconciles class starter abilities idempotently, persists progression/proficiency rows, and hydrates the runtime actor. Reconciliation uses class progression metadata and does not duplicate grants on login.

## Spellup lifecycle

`spellup` enumerates `list_known_spells`, filters to beneficial `spellup_eligible` buffs, excludes Magic Missile and other harmful spells, executes candidates by canonical ID against self, and reports cast/already-active/low-mana/blocked counts.

## Displayed skills

Build Campfire and Set Camp are canonical active skills. They can be invoked by direct ability command names or generic `use` syntax, and currently return a real handler outcome when camp prerequisites are met or a truthful blocked/handler status when they are not.
