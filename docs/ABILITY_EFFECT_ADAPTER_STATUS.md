# Ability Effect Adapter Status

| Category | Status | Authority |
|---|---|---|
| Damage/death | PRODUCTION_WIRED | Combat/Damage runtime then Phase 20 death runtime |
| Mana/resource costs | PRODUCTION_WIRED | SpellResourceCostService + RuntimeResourceService |
| Affects | PRODUCTION_WIRED | AbilityExecutionService runtime effect persistence |
| Camp/campfire room state | PRODUCTION_WIRED | Survival needs service adapter |
| Healing | PRODUCTION_WIRED | RuntimeResourceService canonical healing |
| Movement | PARTIALLY_WIRED | Existing registered effect adapter |
| Item activation | PLACEHOLDER | Typed request supported; no item command migration claimed |
| Summoning | PARTIALLY_WIRED | Existing summon runtime hooks |
| NPC AI/scripts | PARTIALLY_WIRED | Typed request supported; decision/scheduler migration pending |

## Phase 21B update

| Adapter | Status | Evidence |
|---|---|---|
| canonical effect handler | PRODUCTION_WIRED | `AbilityRuntimeService` invokes `execute_effect_handler` after common lifecycle work. |
| damage component adapter | PRODUCTION_WIRED | Magic Missile dispatches through `_apply_damage_component` to combat runtime. |
| camp/campfire adapter | PRODUCTION_WIRED | Registered effects call the survival-needs authority. |
| legacy instant executor | PARTIALLY_WIRED | Retained for compatibility callers; production requests no longer delegate to it. |

> **Phase 21B.3 status (2026-07-18):** Magic Missile structured damage receipts now preserve
> request/source/target/HP linkage and durable duplicate references.  Terminal death linkage is
> injectable but is not wired through normal `MudRuntime`; transport terminal acceptance remains
> unproven, so Phase 21C is not unblocked.
