# Builder List Commands

Phase 4H localizes Builder lists by default so large worlds do not dump every draft record during routine editing. The behavior follows the classic Oasis lesson that builders usually want the current editing neighborhood first, while Smart MUD keeps its own Area/Zone/VNUM draft model and JSON import/export format.

## Local defaults and explicit global lists

- `alist` / `areas` shows the current area and hints that `alist all` lists every area.
- `zlist` / `zones` shows zones in the current location area by default, falling back to the selected Builder area.
- `rlist` / `rooms` shows rooms in the current zone by default.
- `all` is always explicit: `alist all`, `zlist all`, and `rlist all` are global listings.
- Listings over 50 records warn builders to narrow by zone, area, or VNUM range.

## Filters

Supported list filters are shared across Builder list commands where meaningful:

```text
all
current
<id>
area <area_id>
zone <zone_id>
<number>
<number>-<number>
<number> <number>
```

Examples:

```text
alist current
alist all
zlist area starter_guildlands
zlist guildhall_crossing
zlist 1000-1029
rlist zone guildhall_crossing
rlist area starter_guildlands
rlist 1000
rlist 1000-1029
rooms 1000 1029
```

Reversed ranges such as `rlist 1099-1000` are rejected with a clear error. Non-numeric bad ranges such as `rlist 1000-east` print usage guidance.

## Rooms compatibility

`rooms` remains compatible with existing Builder workflows:

- `rooms` matches `rlist` and lists the current zone.
- `rooms all` lists all draft rooms.
- `rooms draft` is local by default; `rooms draft all` is global.
- `rooms live` is local by default; `rooms live all` is the explicit global form for live listings when live listing support is expanded.
- `rooms unassigned` and `rooms legacy` stay global because those records have no zone or area context.

## Placeholder mob and object lists

`mlist` and `olist` do not implement mob or object placement systems in this phase. They now report the current zone and show future-shaped syntax such as `mlist zone <zone_id>`, `mlist 1500-1599`, `olist zone <zone_id>`, and `olist 1300-1399`.

## Why global dumps are not default

Starter Guildlands already contains enough rooms for global room output to become noisy. Future worlds may have hundreds or thousands of rooms, so local defaults keep Builder workflows fast and predictable while retaining explicit global inspection for audits and exports.
