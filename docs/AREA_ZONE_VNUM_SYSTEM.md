# Area, Zone, and VNUM System

Smart MUD Builder Mode organizes draft worldbuilding as `World -> Area -> Zone -> Rooms`, with reserved hooks for future objects, mobs/NPCs, spawns, shops, and quests. Builder drafts remain under `worlds/<world_id>/builder/` and do not mutate live package files.

## Area Model

Draft and package areas use lowercase snake_case IDs and display names that may contain spaces and capitalization. The canonical fields are `id`, `name`, `description`, `world_id`, `vnum_start`, `vnum_end`, `room_vnum_start`, `room_vnum_end`, `object_vnum_start`, `object_vnum_end`, `mob_vnum_start`, `mob_vnum_end`, `spawn_vnum_start`, `spawn_vnum_end`, `zone_ids`, `flags`, `tags`, `plugin_data`, `created_at`, and `updated_at`.

## Zone Model

Zones also use lowercase snake_case IDs. A zone belongs to one area through `area_id`, and its `vnum_start`/`vnum_end` must sit inside the parent area range. Canonical fields are `id`, `name`, `description`, `world_id`, `area_id`, `vnum_start`, `vnum_end`, `room_ids`, `flags`, `tags`, `plugin_data`, `created_at`, and `updated_at`.

## VNUM and ID Strategy

Room vnums are numeric, but Smart MUD IDs remain descriptive strings. Normal room creation uses `<area_id>_<vnum>`, such as `guildhall_1001`. Future object, mob, and spawn IDs should follow `guildhall_obj_1301`, `guildhall_mob_1501`, and `guildhall_spawn_1701`; this phase only implements room creation.

## Builder Workflow

1. Create or select an area with `acreate <area_id> <start> <end> "Area Name"` or `aset current <area_id>`.
2. Create or select a zone with `zcreate <zone_id> <start> <end> "Zone Name"` or `zset current <zone_id>`.
3. Create rooms with `rcreate <vnum>` or link new rooms with `dig <direction> <vnum> "Room Name"`.
4. Use `rcreate custom <room_id>` or `dig <direction> custom <room_id>` only for explicit legacy/custom room IDs.

## Validation and Legacy Rooms

`builder validate` checks safe IDs, area overlap, zone overlap, zone ownership, room area/zone assignments, vnum ranges, duplicate room vnums in an area, and generated ID conventions. Loose legacy rooms without an area or zone are warnings, not destructive errors, and should later be migrated by a future room move command.

## Export Format

Builder export includes `areas`, `zones`, `rooms`, `items`, `entities`, and `spawns`. Older exports without areas or zones load safely because draft normalization creates empty collections.

## Phase 4E organized room workflow hotfix

Builders can now finish the practical area/zone/vnum workflow without mutating live world package files. Draft exports remain under the builder workspace.

Canonical workflow:

```text
builder on
acreate test_area 100 110 "Test Area"
zcreate test_zone 100 110 "Test Zone"
rcreate 101
rname Test Room 101
rdesc This room belongs to the test zone.
rooms area test_area
rooms unassigned
rassign test_two area current zone current vnum 102
builder validate
builder save
builder export
```

Operational commands:

- `aset current <area_id>` selects the current area and shows the Builder HUD. If the selected area does not contain the current zone, the current zone is cleared.
- `zset current <zone_id>` selects the zone and also selects that zone's parent area.
- `rcreate <vnum>` creates an organized draft room with `area_id`, `zone_id`, and `vnum` from the current area and zone. It rejects duplicate vnums and out-of-range vnums with guidance.
- `dig <direction> <vnum> "Name"` creates an organized linked draft room using the current area and zone and reports the created room plus both link directions.
- `rooms unassigned` and `rooms legacy` list loose draft rooms where `area_id` and `zone_id` are blank and `vnum` is null. Legacy rooms are warnings, not validation failures.
- `rassign <here|room_id> area <area_id|current> zone <zone_id|current> vnum <number>` explicitly assigns a loose or existing room to an area, zone, and vnum.
- `rmove <here|room_id> [area <area_id>] zone <zone_id> vnum <number>` moves an assigned room to another zone/vnum. If the room was unassigned, it uses the assignment workflow and says so.
- Assigned rooms keep their existing room IDs in Phase 4E. The generated convention is `<area_id>_<vnum>`, and Builder warns when the current ID does not match it.
- `rrenameid <room_id> <new_room_id>` is registered as a placeholder only. Safe room ID migration is deferred because exits, spawns, builder history, and other references must be rewritten atomically.
- `builder export`, `build export`, `builder save`, `build save`, `bsave`, `wsave`, and `asave changed` route to the safe builder export/save behavior.

`builder status`, `astat`, `zstat`, and `rstat` should be used as guidance screens: they show current area, current zone, current room, edit target, room organization status, vnum, and the next suggested `rassign` command for legacy rooms.

`builder validate` groups Errors, Warnings, and Info. Organization warnings include legacy loose rooms, assigned room ID convention mismatches, rooms missing vnums, empty areas/zones, and range overlaps. Organization errors include missing referenced areas/zones, duplicate vnums within an area, out-of-range room vnums, and zone/area mismatches.
