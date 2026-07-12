# Phase 13C1G-A Canonical Display Audit

| Field/category | Canonical service/module | Persistence source | Display adapter | Compatibility fallback | Visibility rule | Tests |
|---|---|---|---|---|---|---|
| Progression: level, XP, next requirement, TNL, practice/training points | `engine.progression.ProgressionService` | `actor_progression_state`, `actor_advancement_currency_events`, `actor_ability_progression` | `ProgressionDisplayAdapter` | `LegacyCharacterDisplayAdapter` for ad-hoc tests only | Player's own totals only | `tests/test_phase13c1g_a_display_authority.py` |
| Progression: quest points | Quest/reward progression state when present | quest/progression tables | `ProgressionDisplayAdapter` | legacy character field | Own visible balance only | focused display tests |
| Attributes: base/permanent/equipment/effect/temporary/final | Actor attribute resolution / runtime actor state | character data plus effect/equipment services | `AttributeDisplaySource` | legacy adapter | Hide admin-only modifiers; show normalized totals | focused display tests |
| Combat: armor/evasion/accuracy/hit/damage/saves/resistances/criticals | `FormulaEngine`, actor calculated-stat authority, combat actor state | actor/runtime stats and formula inputs | `CombatDisplaySource` | legacy adapter | No hidden formulas or trace rows | focused display tests |
| Combat: weapon/unarmed damage | Combat equipment/formula authority | equipment/item instances | `CombatDisplaySource` | legacy adapter | Summary only, no internal IDs | focused display tests |
| Carrying: item instances, stack/container/equipped weight, capacity, encumbrance, count limit | Runtime item ownership/carrying service; isolated compatibility until service exists | `item_instances`, `character_equipment` | `CarryingDisplaySource` | contained compatibility summing only | Owned/equipped visible items only | focused display tests |
| Currency: definitions, balances, names, ordering, pluralization | `engine.economy.EconomyService` | `actor_currency_balances`, currency profiles | `CurrencyDisplaySource` | legacy `currency/gold/silver/copper` only outside configured runtime | Active player-facing currencies only | economy/display tests |
| Survival: posture, hunger, thirst, fatigue, exposure, combat, conditions | `SurvivalNeedsService` and combat runtime | survival need/runtime state tables | `SurvivalDisplaySource` | legacy fields | Visible player statuses only | survival/display tests |
| Effects: instances, duration, stacks, visible modifiers | Effect runtime/templates | effect instance and character affect tables | `EffectDisplaySource` | legacy effects list | Skip hidden/secret/admin-only | effect/display tests |
| Time: play time, last login, age, birthday, world time | runtime session/account state and living-world time | session/character/living-world tables | `TimeDisplaySource` | legacy fields | Player-safe natural times | prompt/display tests |
| Ability legality: grants/enabled/passive/targets/resources/cooldowns | `AbilityExecutionService.validate_ability_use` | ability grants/progression/cooldowns | `AbilityDisplaySnapshotService` | `trace_ability` diagnostics only | Safe reason/message, no traces in player display | ability legality tests |
| Ability legality: posture/combat/room/environment/equipment/items/effects/prereqs | `validate_ability_use` plus survival/combat/runtime context | combat runtime, campsite/campfire, room tags, actor/effect state | `AbilityDisplaySnapshotService` | none for live commands | Specific reason codes/messages | ability legality tests |
| Recall destination/camp/campfire | ability `plugin_data`, `SurvivalNeedsService` runtime objects | ability definitions, campsite/campfire tables | `validate_ability_use` | none | Safe natural messages | ability legality tests |
| Prompt presentation preferences | `PlayerPresentationPreferenceService` | `character_presentation_preferences` | prompt commands/rendering | character attributes when no service is present | Validate preset/template/theme/width | preference tests |

## Notes

Display builders render only `CharacterDisplaySnapshot` or `AbilityDisplaySnapshot` data. Runtime commands should use the runtime-owned services; broad field probing is isolated to compatibility adapters and legacy snapshot construction for older tests.
