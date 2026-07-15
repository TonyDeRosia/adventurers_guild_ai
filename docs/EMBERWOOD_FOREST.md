# Emberwood Forest

Status: implemented as Shattered Realms starter content owned by the world package, editable in Builder drafts, and populated by `ZoneResetService`.

## Audit and migration

* Existing live rooms had `emberwood_hunting_trail`, `emberwood_edge`, `emberwood_game_trail`, and `abandoned_watchpost`; Builder had additional partial rooms with sandbox text.
* `old_gate_road` had two `north` exits. The route is now unambiguous: `north` enters `emberwood_hunting_trail`; `east` preserves access to `old_gate_checkpoint`.
* Live `zones.json` was empty. Emberwood now has one live zone, `emberwood_forest`.
* The stale `population_definitions` record for `room_id=forest_path` was removed.
* Static room NPC ownership and legacy default-room ownership for `forest_wolf` were removed; recurring population belongs to `emberwood_forest_population`.

## Canonical IDs

* World: `shattered_realms`
* Area: `emberwood_edge` (`Emberwood Forest`, levels 1-5)
* Zone: `emberwood_forest` (migrated from the previous Builder-only `emberwood_edge` zone)
* Reset profile: `emberwood_forest_population`

## Room map and VNUMs

| Room ID | VNUM | Notes |
|---|---:|---|
| `emberwood_edge` | 1210 | Forest boundary |
| `emberwood_game_trail` | 1211 | Animal-track trail |
| `forest_trail` | 1212 | Central junction |
| `wolf_trail` | 1213 | Wolf-marked trail |
| `wolf_den` | 1214 | Wolf lair |
| `woodland_camp` | 1215 | Safe observation/rest room, no recurring hostile spawn |
| `fern_hollow` | 1216 | Fern hollow |
| `mossy_creek` | 1217 | Creek crossing |
| `fallen_oak` | 1218 | Fallen oak cover |
| `briar_thicket` | 1219 | Thorn thicket |
| `fox_burrow` | 1220 | Burrow bank |
| `old_hunters_blind` | 1221 | Safe observation room, no recurring hostile spawn |
| `deep_emberwood` | 1222 | Deep forest |
| `spider_glade` | 1223 | Webbed glade |
| `ancient_ember_grove` | 1224 | Bear grove |
| `emberwood_hunting_trail` | 1225 | Quest wolf entrance |

Cardinal exits are reciprocal. The requested diagonal/loop segment was normalized to cardinal directions: `spider_glade east <-> wolf_den west` and `wolf_den east <-> ancient_ember_grove west`.

## Creature roster and balance snapshot

Snapshots were produced with current Shattered Realms formula services.

| Creature | Level | Health | Armor | Evasion | Hit bonus | Dam bonus | Accuracy | Crit melee | Physical save | Damage | Type | Aggression | Intended level |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|
| `forest_wolf` | 1 | 18 | 0 | 24 | 5 | 3 | 25 | 6 | 16 | 2-5 | piercing | territorial | 1 |
| `emberwood_fox` | 1 | 30 | 0 | 30 | 5 | 3 | 31 | 5 | 17 | 1-2 | piercing | non-aggressive | 1 |
| `wild_boar` | 2 | 55 | 3 | 18 | 7 | 5 | 26 | 6 | 20 | 2-5 | physical | territorial | 2-3 |
| `giant_wood_spider` | 3 | 45 | 1 | 24 | 8 | 5 | 33 | 7 | 22 | 2-6 | piercing | aggressive | 3 |
| `dire_forest_wolf` | 4 | 75 | 2 | 26 | 11 | 7 | 38 | 10 | 25 | 4-8 | piercing | aggressive | 4 |
| `emberwood_stag` | 2 | 60 | 1 | 22 | 6 | 4 | 34 | 6 | 20 | 1-3 | piercing | non-aggressive | 2 |
| `ashback_bear` | 5 | 120 | 6 | 18 | 10 | 9 | 32 | 8 | 27 | 5-10 | physical | aggressive | 5 |

No fake poison was added for spiders because no canonical poison application was wired in this task.

## Population plan

`emberwood_forest_population` is `when_empty`, interval 600 seconds, and uses typed `SPAWN_ENTITY` commands with count limits. Safe rooms `woodland_camp` and `old_hunters_blind` have no recurring hostile spawns.

## Quest, loot, and corpse compatibility

The entrance wolf remains `forest_wolf`, reachable from Old Gate Road, and keeps `starter_wolf_death_loot`, `wolf_common_loot`, and guaranteed `wolf_pelt` behavior. All creature deaths continue through canonical lifecycle/corpse/loot services.

## Builder and loading

Builder drafts were manually synchronized with live package data because no complete promotion workflow was used. A full application/package reload is required for new topology unless a running server explicitly invokes its existing safe reload path; hot reload was not manually verified.

## Windows manual acceptance

Not performed in this Linux container. Use `C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2`, pull `main-v2`, start Smart MUD, log in as Kraevok, and run the requested movement, reset, combat, corpse, loot, and restart checks.
