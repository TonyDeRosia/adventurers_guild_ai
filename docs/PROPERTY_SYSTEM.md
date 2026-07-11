# Property System

Phase 10B adds one canonical `PropertyService` for property definitions, runtime instances, leases, access grants, storage containers, home locations, and audit history. Runtime authority lives in SQLite tables initialized by `engine.property.init_property_schema`; world-authored definitions and profiles live under `worlds/<world_id>/property_*`.

## Canonical rules

- Houses, apartments, inn rooms, lockers, safe-deposit boxes, and organization storage all use the same property definition -> property instance -> lease/owner -> grant -> storage/audit path.
- Economy integration is through immutable quotes/transactions; PropertyService does not own currency.
- Stored items remain canonical `item_instances` and move to `owner_type=property_storage`.
- Private property defaults to deny unless an active owner/tenant/guest/key grant permits the requested action.
- Lease expiration invalidates tenant/key grants and preserves stored items.

## Manual acceptance commands

```text
property available
room rent
property info
keys
property invite <second player>
store <item>
retrieve <item>
property renew
propertytick <duration>
home set
locker
locker store <item>
locker retrieve <item>
```

Expected behavior: quotes come from EconomyService, leases and credentials persist, guests receive explicit grants, unrelated actors are denied, exact item instances move atomically, renewals are idempotent, expiration happens once, keys/grants are invalidated, retained items are preserved, and home locations persist for future recall systems.


## Phase 11B Perception Integration

Phase 11B adds `engine.perception.PerceptionService` as the single sensory boundary for stealth, concealment, search, tracking, scent, sound, trails, and observer knowledge. It queries canonical services, especially `EnvironmentService`, and stores restart-safe sensory state in SQLite.

## Phase 11C2 Gathering Integration

Gathered outputs are canonical item/reward payloads; Crafting, Economy, Profession/Progression, Environment, Perception, Quest, Achievement, Property, Organization/Faction, Living World, Builder, and score surfaces integrate by consuming GatheringService data or EventBus events. GatheringService does not price resources, mutate quest state directly, create a shadow inventory, destroy terrain, implement farming, run autonomous workers, or bypass canonical services.

## Phase 11D2 survival extension

Rest, sleep, rest-location profiles, rest quality, campfire profiles, campsite profiles, shelter context, runtime rest sessions, campfire instances, and campsite instances are routed through the canonical `engine.survival_needs.SurvivalNeedsService`. This preserves the existing EnvironmentService, PropertyService, GatheringService, CraftingService, QuestService, AchievementService, EventBus, item, and score boundaries while adding conservative starter content and diagnostics.

## Phase 11E Cooking Integration

Cooking is a canonical CraftingService specialization. The runtime uses recipe definitions, exact item-instance input reservations, crafting jobs, workstation profiles, production profiles, item quality, profession XP, and reward delivery for cooked outputs. SurvivalNeedsService remains authoritative for consumable profiles, portions, servings, freshness interpretation, spoilage, and need mutation. GatheringService remains authoritative for raw gathered materials. Builder/world-package content now includes cooking ingredient, substitution, preparation, serving-yield, consumable-output, nutrition, preservation, heat, failure, message, and render profile collections.
