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


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.
