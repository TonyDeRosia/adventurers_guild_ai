# Starter World Migration

Phase 4F adds `builder migrate starter` to copy the live Shattered Realms starter package into Builder draft files without rewriting live package files.

## Draft outputs

The command writes normalized draft collections under `worlds/shattered_realms/builder/`:

- `areas.json`
- `zones.json`
- `rooms.json`
- `features.json`
- `item_templates.json`
- `entity_templates.json`
- `spawns.json`

A snapshot is created first. Existing live room IDs are preserved for compatibility.

## Starter area

`starter_guildlands` uses vnum range `1000-1999`, room range `1000-1299`, object range `1300-1499`, mob range `1500-1699`, and spawn range `1700-1799`.

## Starter zones

- `guildhall_crossing`: `1000-1029`
- `registrar_hall`: `1030-1049`
- `training_grounds`: `1050-1079`
- `market_lane`: `1080-1119`
- `wayfarers_mug`: `1120-1149`
- `old_gate_road`: `1150-1179`
- `east_farmland`: `1180-1209`
- `emberwood_edge`: `1210-1239`
- `abandoned_watchpost`: `1240-1269`
- `rat_cellar`: `1270-1299`

Known starter assignments include `guildhall_crossing_square` at vnum `1000`, `guildhall_archway` at `1001`, `guildhall_registrar_office` at `1030`, `training_yard` at `1050`, `market_lane` at `1080`, `tavern_common_room` at `1120`, and `old_gate_road` at `1150`.

## Mapping rules

Room descriptions prefer `long_description`, then `description`, then `short_description`, then an empty string with validation warnings. Live exits using `destination_room_id` are normalized to Builder `target_room_id`. Live room scenery objects such as `old_gate` and `fountain` become nonportable room features rather than inventory items.

After migration, the Builder HUD for the starting room reports `starter_guildlands`, `guildhall_crossing`, vnum `1000`, and organized status instead of legacy/unassigned.

## Phase 4F Hotfix: committed organized starter drafts

Fresh downloads now include the organized Shattered Realms starter Builder drafts under `worlds/shattered_realms/builder/`. The live package files remain unchanged; the committed Builder drafts are the default editable organized starter layer that Builder Mode overlays at runtime.

Use `builder validate` to verify the committed starter draft layer. The starting room `guildhall_crossing_square` is assigned to `starter_guildlands`, zone `guildhall_crossing`, vnum `1000`, and should report `Status: organized` in `rstat`.

`builder migrate starter` remains available to reset or regenerate the starter drafts from the live Shattered Realms package. Regeneration should update the draft JSON files only; do not commit runtime audit, history, snapshot, export, local database, or user-data artifacts.

To exchange the organized starter layer, run `builder export`, then place the exported bundle in the Builder import folder and run `builder import validate <file>` before applying it.
