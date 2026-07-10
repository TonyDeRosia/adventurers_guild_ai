# Living Entity Runtime

Phase 3B turns passive runtime entities into living runtime objects while keeping `MudRuntime` the only authority for state changes. The feature is a foundation only: combat, Builder Mode, AI decision making, quests, shops, spellcasting, and pathfinding remain intentionally unimplemented.

## Entity lifecycle

1. Immutable world package records are normalized into read-only entity templates.
2. Spawn definitions are applied by `MudRuntime.populate_world()` / `spawn_entity()`.
3. Mutable instances are persisted in SQLite `entity_instances`.
4. Runtime APIs move, reset, despawn, destroy, respawn, and change entity state.
5. Room rendering asks `MudRuntime.find_visible_entities()` and never reads package JSON directly.

## Templates

Templates include identity, descriptions, type, race/class/gender/level/size/alignment, spawn and wander rules, dialogue packages, behavior flags, visibility flags, profile placeholders, script hooks, and plugin data. Templates are immutable mapping proxies and are never changed during play.

## Instances

Instances expose canonical runtime fields such as `instance_id`, `template_id`, `room_id`, `owner_type`, `owner_id`, `current_state`, health/mana/stamina, spawn/update/reset timestamps, spawn origin, alive/visible booleans, movement/dialogue/custom state, and plugin data. These values are derived from SQLite rows plus instance state JSON.

## Spawn pipeline

World package NPC records provide spawn rules such as spawn room, spawn count, maximum population, respawn delay, spawn probability, and initial state. `populate_world()` seeds entities through `room_entity_seeds`, so repeated world loading is idempotent and does not duplicate NPCs. Direct spawns use `spawn_entity()` and publish lifecycle events.

## Movement pipeline

Entity movement must use `move_entity()`, `teleport_entity()`, or `return_to_spawn()`. Movement updates the SQLite room location, publishes `entity_moved`, and causes room population change events. The implementation is deterministic and does not perform pathfinding.

## State machine

Supported states include `idle`, `standing`, `sitting`, `sleeping`, `resting`, `wandering`, `following`, `guarding`, `trading`, `training`, `healing`, `casting`, `dead`, `corpse`, and `despawned`. `change_entity_state()` validates these names and publishes `entity_state_changed`.

## Behavior and visibility flags

Behavior flags such as `sentinel`, `aggressive`, `passive`, `merchant`, `trainer`, `healer`, `banker`, `quest_giver`, `scavenger`, `guard`, `pet`, `mount`, `immobile`, `friendly`, and `hostile` are stored for future systems. Visibility flags such as `hidden`, `invisible`, `builder_hidden`, and `future_stealth` affect `find_visible_entities()` now.

## Dialogue packages

Dialogue packages support greeting, farewell, idle speech, talk responses, keyword responses, and future quest hooks. The runtime supports `talk`, `greet`, and `hello` commands, with optional `about <keyword>` lookup. Responses come from package data only; no AI generation is used.

## Corpse foundation

`create_corpse()` creates a corpse entity with `current_state='corpse'`, a source entity id, and `is_alive=false`. Future combat may transform a living entity into a corpse and later despawn it, but this phase implements only the runtime persistence/rendering foundation.

## EventBus integration

Living entity operations publish canonical events: `entity_spawned`, `entity_despawned`, `entity_destroyed`, `entity_reset`, `entity_moved`, `entity_state_changed`, `entity_dialogue`, and room population change events. Payloads include entity/template/room/world identifiers plus account/session/transport metadata when provided by callers.

## Future integration boundaries

- AI may subscribe to events or request runtime APIs, but must not own state.
- Combat may call `change_entity_state()` and `create_corpse()`, but must not bypass SQLite runtime instances.
- Builder Mode may edit package templates in a draft workspace, but live instance transitions still go through `MudRuntime`.


## Phase 3C Dialogue Entry Points

The interaction layer routes `talk`, `greet`, and `hello` through the existing runtime dialogue package for visible NPCs and mobs. Dialogue remains deterministic and template-backed; Phase 3C does not add AI decision making or combat behavior. Entity interaction attempts publish interaction EventBus events alongside existing entity dialogue events.

## Phase 3D command registry note

Smart MUD now tracks player, placeholder, future builder/admin, future combat, future magic, future economy, and future quest commands through a canonical command registry. The `commands` and `help` commands use registry metadata so classic MUD command coverage is deliberate without adding combat, AI, Builder Mode, shops, quests, spellcasting, or world expansion.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.
