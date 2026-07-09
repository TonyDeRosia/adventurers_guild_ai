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
