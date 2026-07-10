# Runtime Content Synchronization Audit

## Proven root cause

Blacksmith Stall was rendered from two incompatible sources. Builder-visible room rendering appended draft `rooms.blacksmith_stall.features` entries named `Iron Sword` and `Training Sword`; those records were created by the starter migration from live `rooms.objects` and were marked `portable: false`. The get/take resolver correctly searched SQLite `item_instances` through `get_visible_room_items()`, so when no matching runtime item instances existed the renderer showed sword definition/draft-feature records that commands could not resolve.

The live room also used `objects: ["training_sword", "iron_sword"]` as ambiguous room declarations. The old `_seed_room_items()` inserted `room_item_seeds` and item rows separately and used the seed row as the idempotency marker. A stale database could therefore contain a seed marker without corresponding live instances, preventing repair and proving that the marker and created instances were not one canonical materialization record.

## Blacksmith Stall records audited

- Room load: `worlds/shattered_realms/rooms/rooms.json` loads `blacksmith_stall`; Builder actors may overlay `worlds/shattered_realms/builder/rooms.json`.
- Blacksmith Harl: entity template `blacksmith_harl` has `default_room_id`/legacy spawn semantics and is now materialized as one SQLite entity instance through `content_materializations`.
- Iron Swords: explicit item placement `blacksmith_stall_iron_swords_once` creates two SQLite item instances from template `iron_sword`.
- Training Sword: explicit item placement `blacksmith_stall_training_sword_once` creates one SQLite item instance from template `training_sword`.
- Renderer source after fix: `MudRuntime.get_room_contents()` separates resolved features, item instances, entity instances, players, and exits.
- Get source after fix: `pickup_item()`, `bulk_get()`, and keyword resolution use the same item-instance bucket returned by the canonical runtime APIs.

## Old flow

```text
Item template / live room objects / Builder draft features
    -> renderer merged draft features into room objects
    -> get/take searched SQLite item_instances only
```

## Corrected flow

```text
Template/Definition
    -> Placement Declaration / Seed / Spawn
    -> Runtime Materializer
    -> SQLite Runtime Instance
    -> Room Query
    -> Renderer and Commands
```

Static features such as `blacksmith_anvil` remain definition-backed scenery and never enter the item-instance bucket.
