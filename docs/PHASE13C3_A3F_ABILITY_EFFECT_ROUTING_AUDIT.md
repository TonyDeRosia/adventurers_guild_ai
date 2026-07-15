# Phase 13C3-A3F Ability Effect Routing Audit

| Effect type | Current function | Current mutation path | Canonical target service | Migration status |
|---|---|---|---|---|
| `deal_damage` / damage components | `AbilityExecutionService._apply_damage_component` | Temporary natural weapon then combat resolver | `CombatRuntimeService.submit_action` / `CombatResolutionService` | Request schema and runtime gateway are available; combat-queued ability results are recorded in history. |
| `heal` / healing components | `AbilityExecutionService.apply_healing` | `RuntimeResourceService.apply_healing` | RuntimeResourceService, with combat result containers | Canonical for resources; normal healing does not resurrect dead actors. |
| `modify_resource` / costs | `_pay_costs` | `RuntimeResourceService.pay_cost` | RuntimeResourceService | Canonical; arbitrary attribute mutation is not accepted as a resource cost. |
| `apply_affect` / effects_applied | `_apply_effect` | Persistent `actor_effect_instances` plus actor effect container | RuntimeEffectService where installed; actor effect instance store fallback | Partially migrated; persisted runtime effect rows are authoritative for reload. |
| `remove_affect` / effects_removed | ability data bucket | Not broadly implemented | RuntimeEffectService | Documented as remaining hook; protected/source-filter semantics must be routed through RuntimeEffectService. |
| `create_campsite` | `_apply_registered_effect` | `survival_needs.create_campsite` | Survival needs service | Canonical noncombat handler. |
| `create_campfire` | `_apply_registered_effect` | `survival_needs.create_campfire` | Survival needs service | Canonical noncombat handler. |
| `teleport_home` / Recall | `_apply_registered_effect` | state store room change | Runtime movement/recall service when present | Existing public behavior retained; no combat mutation. |
| `send_message` | `_apply_registered_effect` | structured ability result message | Command renderer | Canonical display-only handler. |
