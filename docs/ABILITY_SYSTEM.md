# Smart MUD Phase 6C Ability System

Phase 6C introduces one canonical Ability architecture for skills, spells, heals, buffs, debuffs, techniques, natural attacks, monster powers, item-granted actions, passives, administrative test actions, and future AI-selected actions. Ability type is metadata for display and filtering, not an execution branch.

## Canonical runtime flow

Actor → AbilityDefinition → target validation → resource validation → cooldown validation → state validation → cast/activation timing → Formula Engine data → CombatEngine damage, canonical HealingEvent healing, and EffectService-compatible effect instances → EventBus events → lifecycle handoff where combat damage kills a target.

## Source ownership

Runtime grants live in SQLite `actor_ability_grants` and are source-traceable by `source_type`, `source_id`, and `source_instance_id`. Multiple grants for the same ability may coexist; revoking one source does not revoke unrelated sources. World JSON owns definitions and seed/loadout data.

## Builder and world collections

Implemented collections are `abilities`, `ability_loadouts`, `ability_schools`, `ability_categories`, `cooldown_groups`, `targeting_profiles`, `healing_profiles`, and `casting_profiles`, with mirrored Builder drafts under `worlds/<world_id>/builder/`.

## Commands

Player commands: `abilities`, `skills`, `spells`, `ability <name>`, `use <ability> [target]`, `cast <ability> [target]`, `invoke`, `perform`, `cancel`, `cooldowns`, and `spellup [cast]`.

Builder/Admin commands: `abilitylist`, `abilitystat`, `abilitycreate`, `abilityclone`, `abilityset`, `abilitydelete`, `abilityvalidate`, `abilitypreview`, `abilitytrace`, `loadoutlist`, `loadoutstat`, `loadoutcreate`, `loadoutclone`, `loadoutset`, `loadoutability`, `loadoutdelete`, `loadoutvalidate`, `abilitygrant`, `abilityrevoke`, `actorabilities`, `abilitycooldowns`, and `abilitycasts`.

## Future AI boundary

AI may select from validated actor abilities in a future phase, but it must call the same AbilityExecutionService and cannot bypass target, resource, cooldown, cast, damage, healing, effect, lifecycle, or EventBus authority.
