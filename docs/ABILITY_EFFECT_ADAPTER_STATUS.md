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
