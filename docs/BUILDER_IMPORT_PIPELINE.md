# Builder Import Pipeline

Phase 4F adds a draft-only JSON import pipeline under `worlds/<world_id>/builder/imports/`. Imports never mutate live world package files and every apply operation records Builder audit/history entries.

## Workflow

1. Author JSON outside the client.
2. Save it as `worlds/shattered_realms/builder/imports/my_area.json`.
3. In game run:

```text
builder on
builder import list
builder import validate my_area.json
builder import preview my_area.json
builder import apply my_area.json
builder validate
builder reload
goto <new_room_id>
look
```

## Bundled format

```json
{
  "areas": {},
  "zones": {},
  "rooms": {},
  "features": {},
  "items": {},
  "entities": {},
  "spawns": {}
}
```

`builder export` writes the same bundle shape, so exports can be round-tripped through `builder import validate` and `builder import apply`.

## Commands

- `builder import list` lists JSON files in the imports directory.
- `builder import validate <filename>` checks safe IDs, area/zone/room references, ranges, duplicate vnums, exits, names, descriptions, and spawn/entity references without changing files.
- `builder import preview <filename>` reports add/update counts, conflicts, legacy warnings, and broken references without changing files.
- `builder import apply <filename>` merges records into Builder drafts.
- `builder import apply <filename> --merge` is the explicit merge form.
- `builder import apply <filename> --replace-drafts` snapshots first, then replaces draft collections.

Future feature-library work can promote room-local scenery features into reusable feature templates. For now, nonportable scenery should remain `portable: false` draft features.
