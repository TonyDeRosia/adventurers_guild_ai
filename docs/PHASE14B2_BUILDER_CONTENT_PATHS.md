# Phase 14B2 Builder Content Paths

The repository uses existing Builder content editing primitives rather than a second publication framework.

## Authoritative Path Inventory

| Content type | Live path | Draft path | Notes |
|---|---|---|---|
| abilities | package/world ability records loaded into `AbilityRegistry` | Builder draft JSON managed by `BuilderContentEditor` | Runtime consumes top-level `canonical_effects`; legacy `plugin_data.canonical_effects` adapts at load time. |
| effects | package/world `effect_templates` records | Builder draft JSON managed by `BuilderContentEditor` | Runtime effect instances persist in SQLite `actor_effect_instances`. |
| auras | ability canonical effects with operation `aura` and aura definition records where present | Builder draft JSON managed by `BuilderContentEditor` | Active state persists in `aura_instances` and `aura_membership`. |
| stances | ability canonical effects with operation `stance` | Builder draft JSON managed by `BuilderContentEditor` | Active state is a runtime effect tagged `stance` and `stance:<group>`. |
| transformations | ability canonical effects with operation `transform` | Builder draft JSON managed by `BuilderContentEditor` | Runtime actor combat projection is updated and effect state persists. |
| summons | ability canonical effects with operation `summon` and summon definition records where present | Builder draft JSON managed by `BuilderContentEditor` | Active relationships persist in `summon_relationships`; profiles in `summon_profiles`. |
| room effects | ability canonical effects with operation `create_room_effect` and room effect definition records where present | Builder draft JSON managed by `BuilderContentEditor` | Runtime instances persist in `room_effect_instances`. |
| ability messages | ability `messages` and effect `messages` fields | Builder draft JSON managed by `BuilderContentEditor` | Message placeholders are validated against the safe placeholder allow-list. |
| categories/schools | package/world `ability_categories` and `ability_schools` records | Builder draft JSON managed by `BuilderContentEditor` | Loaded by `AbilityRegistry`. |

## Runtime Stores

- Ability grants: `actor_ability_grants`.
- Cooldowns: `actor_ability_cooldowns`.
- Casts: `actor_ability_casts`.
- Actor effects: `actor_effect_instances`.
- Auras: `aura_instances`, `aura_membership`.
- Summons: `summon_relationships`, `summon_profiles`.
- Room effects: `room_effect_instances`, `room_effect_tick_claims`.
