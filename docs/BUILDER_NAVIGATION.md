# Builder Navigation and Runtime Overlay

Phase 4B makes draft rooms visible through the runtime room graph for builder/admin/owner characters while Builder Mode is enabled. The lookup order is: BuilderWorkspace draft rooms first, then live world package rooms. Normal players continue to resolve only live world package rooms.

## Builder context

Builder context is tracked on the runtime character/session data: current room, last room, last created room, current area, current zone, and whether Builder Mode is enabled. Room creation, `goto`, `dig`, `link`, and `unlink` update this context through the runtime and BuilderWorkspace.

## Room navigation

`goto <room_id>` resolves exact room ids first. `goto <room name>` searches visible runtime room names. `goto here` shows the current draft/live source. `goto last` returns to the previous room when tracked. `goto home` returns to the live world start room. Successful `goto` persists the character location and renders the destination room through the canonical room renderer.

`rooms`/`rlist` lists live and draft rooms visible to the builder with id, name, area, zone, source, and exit count. `rfind`/`rsearch` search ids, names, descriptions, features, tags, area ids, and zone ids because they search merged room records.

## Map building

`dig <direction> <new_room_id> [room name] [--one-way]` creates a draft destination room when needed, links the current room to it, creates the reverse exit unless `--one-way` is present, moves the builder into the new room, and renders it.

`link <direction> <target_room_id>` creates a draft exit from the current room. `link both <direction> <target_room_id>` also creates the reverse exit. `unlink <direction>` removes the current draft exit.

`map`/`rmap` shows the current room and the eight basic adjacent directions: north, south, east, west, up, down, in, and out.

## Save, reload, and limits

`builder save` exports drafts under the builder workspace and does not promote or mutate live world package files. Promotion to live package is not implemented yet. `builder reload` refreshes use of saved drafts from BuilderWorkspace for the runtime overlay.

## Validation

`builder validate` reports draft graph issues such as missing names, broken exits, missing feature names, invalid item/entity fields, and invalid plugin JSON. Validation output is intended to be actionable before a future promotion workflow.

## Manual workflow

```text
builder on
rcreate test_room
rname Test Room
rdesc This is a test.
builder validate
builder snapshot
builder save
goto test_room
look

dig north north_road North Road
look

goto test_room
link north north_road
map
builder reload
```

`look` after `goto test_room` must render `Test Room`, not the starter room.

## Future work

Visual Builder UI, AI Builder, promotion to live packages, combat, quests, shops, and spellcasting remain future work.

## Phase 4C Canonical Room Graph Contract

Builder navigation now treats live package rooms plus builder draft rooms as one canonical runtime graph for builders with Builder Mode enabled. Rendering, `look`, movement, `goto`, `dig`, `link`, `unlink`, `map`/`rmap`, and validation must resolve exits from that same graph. If an exit is visible, movement uses that exact exit record or reports why it is blocked, closed, locked, hidden, missing a target, or pointing at a missing room.

Builder edit commands show a persistent `Currently editing:` block with room id, name, source, and dirty state. Room ids are lowercase underscore identifiers; human-readable room names belong in `rname` or the quoted room-name form of `dig`.

## Phase 4C Hotfix 2: Location versus editing target

Movement changes the current location. `redit` and `btarget` change only the edit target. `goto` while Builder Mode is enabled intentionally changes both location and edit target. `dig` creates/links the destination, moves the builder there, and selects the new room for editing. Normal directional movement does not secretly change the edit target.

Navigation and editing commands that succeed should render the canonical Builder Status block so builders can see both `Location` and `Currently editing`. `map`/`rmap`, `dig`, `link`, `unlink`, `goto`, `redit`, `rstat`, `rcreate`, `rname`, `rdesc`, `desc`, `builder validate`, `builder save`, `builder snapshot`, and `builder reload` all follow this convention where Builder Mode output is available.


## Phase 4D Navigation Polish

Builder navigation keeps the editing context visible through the canonical Builder HUD. `rooms` defaults to draft rooms and also supports `rooms draft`, `rooms live`, and `rooms all`, with the current editing target and current location at the bottom. `rfind` searches room IDs and display names by partial match.

`back` and `forward` are reserved for Builder navigation history while Builder Mode is enabled; they do not replace normal movement commands for players. Current compatibility keeps `goto last` available for the previous location while the history stack is expanded.

## Phase 4E Area, Zone, and VNUM Organization

Builder Mode now supports draft areas and zones before room creation. Builders can use `acreate`/`aset current`, `zcreate`/`zset current`, `rcreate <vnum>`, and `dig <direction> <vnum>` to create rooms with canonical `<area_id>_<vnum>` IDs while preserving explicit `custom` legacy room IDs. Builder status shows world, area, zone, location, edit target, and dirty state. Builder export includes `areas`, `zones`, `rooms`, `items`, `entities`, and `spawns`; validation warns on legacy loose rooms and checks area/zone/vnum consistency. See `docs/AREA_ZONE_VNUM_SYSTEM.md`.

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
