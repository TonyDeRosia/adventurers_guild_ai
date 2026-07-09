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
