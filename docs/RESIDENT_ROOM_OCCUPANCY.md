# Resident Room Occupancy and Target Resolution

Phase 15B.11 replaces split room-entity authority with a resident index owned by `MudRuntime`.

## Before-fix authority table

| Source | Data type | Owner/writer | Readers | Key format | Room format | Entity format | LOOK | KILL | NPC AI/messages | Stale risk |
|---|---|---|---|---|---|---|---|---|---|---|
| `entity_instances` via `find_room_entities()` | SQLite rows projected to dicts | materialization/spawn/move/death | room renderer, targeted LOOK, dialogue | `entity_id` | `current_room_id` plus payload `room_id` | entity instance id | yes | indirectly | yes | medium: persisted state can exist without resident actor |
| `find_visible_entities()` | grouped dict lists | `MudRuntime` | `_current_room()`, LOOK, target look, previous combat target resolver | room id | caller-provided | entity dict | yes | previously yes through entity list | yes | medium before this phase |
| `CombatRuntimeService.resident_actors` | `dict[str, Actor]` | combat warmup/start/actor loading | combat validation, encounters, AI, messages | `character:<id>`/`entity:<instance>` | actor identity | actor id | no before fix | combat only | yes | high when visible NPC had no actor |
| `resident_occupants_by_room` | `dict[str, OrderedDict[str, None]]` | `MudRuntime` registration/move/spawn/death/despawn | LOOK, KILL, CONSIDER/DIAGNOSE, combat/NPC systems | canonical room -> ordered actor ids | canonical room id | resident actor id | yes | yes | intended authority | validator detects drift |

## Canonical architecture

`MudRuntime.resident_occupants_by_room` is the canonical room occupant index for living NPCs and mobs.  It maps a canonical room id to ordered resident actor ids.  Supporting maps are `entity_instance_to_actor_id` and `actor_id_to_entity_instance_id`.  Each occupant resolves to exactly one `CombatRuntimeService.resident_actors` entry.

## Room ID normalization

`MudRuntime.canonical_room_id()` trims whitespace, strips world prefixes, and normalizes supported `room_` aliases when the unprefixed id exists. Runtime comparisons for characters, entity payloads, actor identity locations, room indexes, and combat encounters go through canonical room strings.

## Registration and lifecycle

World load and admin rebuild call `rebuild_room_occupancy_admin_only()`, which registers all living room-owned NPC/mob instances as resident actors and adds them to the room index. `spawn_entity()` registers new living NPCs immediately. `move_entity()` updates the actor location and room index together. `update_entity_state()`, `despawn_entity()`, and `destroy_entity()` remove dead or extracted NPCs from occupancy.

## Target grammar

Target matching is token-aware and TBA-style:

* `bear`, `ashback`, `ashback bear`, `Ashback Bear`, and `1.bear` match `Ashback Bear`.
* `N.keyword` selects the Nth matching visible living room occupant in deterministic resident room order.
* Tokens come from display name and authored keywords. Whole tokens and whole keyword phrases match before optional token-prefix matching.
* Accidental unrelated substrings do not match: `boar` does not match `bear`.

## Visibility and attackability

LOOK and KILL both enumerate the same resident room occupants. KILL first resolves a visible living occupant, then combat validation reports protected or non-attackable targets separately. Missing visible targets log `[target-resolution-integrity]` with player, room, visible actor, instance, template, actor-location, and room-index diagnostics.

## Diagnostics

Commands:

* `occupancystat` reports indexed rooms, occupants, and actors.
* `occupancyvalidate` checks actor/index/mapping consistency.
* `occupancy room [room]` lists resident actor ids in a room.
* `occupancy actor <actor>` reports an actor's resident location.

## TBA behavioral parity

TBA maintains a single linked character list per room and both LOOK and `get_char_room_vis()`/KILL scan that same resident list. Smart MUD mirrors that behavior by rendering and resolving living NPCs from one ordered resident occupancy index rather than rebuilding content or querying SQLite during target resolution.

## Phase 15B.12 flee invariant

After successful flee the actor must be absent from the old room's `resident_occupants_by_room` entry and present in the destination room entry. Failed flee does not mutate occupancy.
