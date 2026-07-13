# Phase 13C3-A3H Damage Source Migration

| Source | File/function | Current path | New canonical path | Migration status | Test |
|---|---|---|---|---|---|
| Player/NPC melee and rounds | `engine.combat_runtime.CombatRuntimeService.submit_action` / `_execute_attack_direct` | CombatActionRequest to CombatEngine and RuntimeResourceService | Already canonical; lifecycle records truthful statuses | Migrated | `pytest tests/test_phase13c3_a3h_lifecycle.py` |
| Ability direct damage | `engine.abilities.AbilityExecutionService._apply_damage_component` | Builds `CombatActionRequest(source_type='ability')` when runtime is attached | Canonical submit_action | Existing migration retained | Existing ability runtime tests |
| DOT/effect damage | `CombatActionRequest(attack_kind='damage_over_time', source_type='effect')` | Supported by submit_action; effect instance/source ids persist in request history | Canonical submit_action with action id/source id in history | Gateway migrated; broad content library not added | `pytest tests/test_phase13c3_a3h_lifecycle.py` |
| Environmental/survival/trap/hazard | `CombatActionRequest(source_type='environment'/'survival'/'trap'/'hazard')` | Supported by submit_action and reward policy skips non-character killers | Canonical submit_action; no player reward unless authored with a character killer | Gateway migrated; authored hazard catalog not expanded | Static direct-health check plus lifecycle tests |
| Admin/debug damage | Combat runtime action requests | Must use submit_action for persistent gameplay; persistence-free simulations remain documented exceptions | Canonical where runtime action used | No new admin bypass added | Static direct-health check |
| RuntimeResourceService | `engine.runtime_resources.RuntimeResourceService.apply_damage` | Only low-level resource mutation service may subtract health | Remains the canonical mutation layer | Allowed exception | Existing runtime resource tests |
| Initialization/hydration | actor/entity load/save code | Sets current health from persisted state | Not gameplay damage | Allowed exception | Static direct-health check |

## Regression rule

Normal gameplay code outside `RuntimeResourceService` should not directly subtract health. A focused static regression test searches runtime gameplay modules for `health -=`, `hp -=`, and equivalent direct subtraction patterns. Initialization, hydration, persistence, and low-level resource-service mutations are documented exceptions.
