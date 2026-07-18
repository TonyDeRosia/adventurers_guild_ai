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

## Phase 18K invocation integrity

Room-visible NPCs are now registered into the shared live ActorRegistry so spell, skill, combat, and render paths resolve the same runtime instance. Build Campfire and Set Camp expose direct command syntax in skills; remaining combat work includes broader AI retaliation and complete direct-skill handlers.

## Phase 19C spell resources and natural weapons

Phase 19C adds canonical legacy spell mana costs via `SpellResourceCostService`. Magic Missile uses `mana_max=25`, `mana_min=10`, `mana_change=3`, and class-specific unlock level 1 for Adventurer and Magic User/Mage, producing costs 25/22/19/16/13/10 by level. Cast and spellup validation consume the same service result; low-mana cast failures now show required and available mana. Resource payment is centralized through `RuntimeResourceService` so live score/prompt state and persistence stay aligned. The forest wolf natural attack miss path now carries the selected bite profile rather than falling back to punch wording.
