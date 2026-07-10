# Entity Duplication Audit (Phase 5A)

## Reproduction

The audit covered the three reported Starter Guildlands rooms under fresh and simulated upgraded SQLite databases. A fresh database is created by `MudRuntime(Path.cwd(), tmp_path)` followed by `load_world("shattered_realms")`. An upgraded database is simulated by inserting a pre-Phase-5A `entity_instances` row without a `content_materializations` row, then loading the world.

| Room | Area | Zone | Expected NPC | Template | Runtime result after repair |
| --- | --- | --- | --- | --- | --- |
| `blacksmith_stall` | Starter Guildlands content | Starter Guildlands zone | Blacksmith Harl | `blacksmith_harl` | one runtime instance |
| `spell_practice_circle` | Starter Guildlands content | Starter Guildlands zone | Apprentice Mage Lina | `apprentice_mage_lina` | one runtime instance |
| `training_yard` | Starter Guildlands content | Starter Guildlands zone | Training Master Borik | `training_master_borik` | one runtime instance |

Repeated startup, repeated `materialize_world_content`, repeated `materialize_room_content`, repeated room look/render, Builder diagnostics, and runtime reload keep the same instance IDs in the regression suite.

## Affected Rooms

The content has three active legacy room NPC declarations in `rooms.json`: `training_yard` lists `training_master_borik`, `spell_practice_circle` lists `apprentice_mage_lina`, and `blacksmith_stall` lists `blacksmith_harl`. The same NPC templates also carry `default_room_id` values in `npcs.json`. The runtime currently bridges template `default_room_id` into entity spawn declarations named `legacy_<room>_<template>`.

## Fresh Database Results

Fresh SQLite materialization produced exactly one live row in `entity_instances` for each affected room/template pair. Each row is referenced by exactly one `content_materializations` row for the corresponding `entity_spawn` declaration. The ordinary room renderer receives only `entity_instances` from `get_room_contents`; spawn declarations and materialization records are only included when Builder metadata is explicitly requested.

Conclusion: duplicates are not inherent to fresh canonical materialization after the repair.

## Upgraded Database Results

A simulated pre-Phase-5A database with an existing legacy Harl row but no `content_materializations` marker reproduced the unsafe upgrade condition: before repair, `materialize_entity_spawn` would not recognize the existing row and would create a second Harl row. The fix adopts matching preexisting rows for the same world, room, and template when no materialization marker exists, records their IDs in `content_materializations`, and only spawns the quantity shortfall.

Existing databases that already contain two live rows are not destructively modified. They are reported by `entityaudit` as duplicate risks for manual review.

## Entity Source-Flow Diagram

```text
Canonical runtime path:
entity template / NPC template
  -> _load_entity_templates
  -> _live_entity_spawns legacy bridge from default_room_id
  -> materialize_entity_spawn
  -> content_materializations(entity_spawn, declaration_id, instance_ids_json)
  -> entity_instances rows
  -> find_room_entities / get_room_contents
  -> find_visible_entities
  -> _current_room
  -> render_room

Legacy declaration diagnostics path:
rooms[].npcs / rooms[].entities and template.default_room_id
  -> _legacy_room_entity_declarations
  -> rcontents / entityaudit only
  -> never ordinary player rendering

Old upgrade hazard path:
pre-Phase-5A room_entity_seeds or direct entity_instances row
  -> no content_materializations marker
  -> old materialize_entity_spawn created a second row
  -> renderer correctly displayed both rows
```

## SQLite Findings

Relevant tables are `entity_instances`, `room_entity_seeds`, and `content_materializations`. Legacy campaign tables such as `npc_instances`, `mob_spawns`, and `mob_instances` are separate campaign-engine persistence and are not read by the Smart MUD canonical room-content renderer.

For quantity-1 starter NPC declarations, the invariant is:

- one `content_materializations` row per declaration;
- one instance ID in `instance_ids_json`;
- one non-destroyed `entity_instances` row for that ID;
- no ordinary renderer source other than that instance row.

The added audit command prints instance ID, template ID, display name, room ID, source spawn ID, alive/visible state, created timestamp, matching declarations, materialization records, and duplicate-risk groups.

## Materialization Findings

`load_world` calls `materialize_world_content`. Room look and movement do not materialize content; they query already materialized runtime rows. Builder diagnostics also query content and do not materialize by themselves. `populate_world` is a backward-compatible alias to materialization and remains idempotent.

The repaired `materialize_entity_spawn` first checks for an existing materialization row. If none exists, it adopts matching live rows before spawning missing quantity. This prevents an upgraded database from getting a second row simply because the marker is absent.

## Renderer Findings

The ordinary room renderer is not the root cause. Its inputs come from `find_visible_entities`, which is populated by `get_room_contents(...)["entity_instances"]`. Templates, spawn declarations, legacy room NPC declarations, and materialization rows do not enter ordinary player rendering. If two live rows exist, rendering both is correct because two legitimate NPCs can share a display name.

## Legacy Source Findings

The active legacy source is template `default_room_id` plus room `npcs` declarations in Starter Guildlands content. The runtime bridge uses template `default_room_id` to create compatibility spawn declarations. Direct room NPC declarations are retained for diagnostics but are not rendered as living entities.

## Proven Root Cause

The proven upgrade root cause is missing adoption of existing pre-Phase-5A entity rows when no `content_materializations` marker exists. A legacy row can exist in `entity_instances` for the same room/template, and the old materializer would create a new canonical row for the generated `legacy_<room>_<template>` spawn because it only checked `content_materializations`.

Fresh databases did not need destructive cleanup. Existing already-duplicated databases need audit-first repair because the safe survivor cannot be chosen by display name alone.

## Why Existing Automated Tests Missed It

Existing tests covered fresh materialization and item idempotency but did not simulate an upgraded database containing preexisting entity rows without materialization records. They also did not require diagnostics to show legacy declarations beside runtime rows.

## Safe Repair Design

The narrow repair is an adoption step in `materialize_entity_spawn`:

1. if a materialization row exists, return it;
2. otherwise find live matching rows by stable room ID and template ID, optionally already tied to the same spawn;
3. adopt up to the declaration quantity by recording those IDs;
4. spawn only missing quantity;
5. record extra matching rows as duplicate candidates in metadata without deleting them.

No name-based deduplication or destructive database cleanup is performed.

## Migration Impact

Fresh databases continue to create one runtime instance per quantity-1 declaration. Upgraded databases with one legacy row now adopt it. Upgraded databases with already duplicated rows keep all rows until a builder reviews the audit output.

## Backward Compatibility Impact

Legacy-only worlds that rely on template `default_room_id` still materialize entities through the compatibility spawn bridge. Room-level NPC declarations remain visible in Builder diagnostics and audit output but do not add ordinary rendered NPCs.

## Regression Test Plan

New tests cover fresh counts, upgrade adoption, idempotent repeated materialization, renderer source integrity, legitimate same-name duplicate instances, duplicate-risk diagnostics, and Builder-only access to `entityaudit`.

## Manual Verification Plan

For each affected room:

```text
look
rcontents here
mstat <entity instance id>
sstat <spawn id>
entityaudit here
builder materialize status
builder materialize apply
look
```

Expected result: Blacksmith Harl, Apprentice Mage Lina, and Training Master Borik each appear exactly once unless `entityaudit` reports a preexisting duplicate risk that requires manual data review. After restart and Builder reload, repeat `look` and `rcontents here`; counts should remain stable.
