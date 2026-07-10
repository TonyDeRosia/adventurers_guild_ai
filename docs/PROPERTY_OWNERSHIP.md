# Property Ownership

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
