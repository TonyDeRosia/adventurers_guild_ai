# Smart MUD Runtime Entity System

Phase 3A adds a shared runtime entity foundation for world occupants and non-item things that can exist in rooms. The supported entity types are `player`, `npc`, `mob`, `object`, `container`, `corpse`, `door`, `shop`, `pet`, and `summon`; this phase implements the foundation for `npc`, `mob`, `object`, `container`, and `corpse` without combat, AI behavior, Builder Mode, shops, doors, pets, or summons.

## Template vs. Instance

World packages provide immutable templates. Runtime code normalizes `worlds/<world>/npcs/*.json` records into entity templates with type, name, keywords, descriptions, faction, level, default room, state, flags, and plugin data. Templates are stored as read-only mapping proxies and are not mutated during play.

SQLite stores mutable entity instances in `entity_instances`. Instances own runtime location, ownership, state, flags, timestamps, plugin data, and destruction metadata. Restart-safe entities are loaded from SQLite rather than recreated from templates.

## Runtime Authority

`MudRuntime` is the authority for entity state. Transports, renderers, plugins, and world packages must not directly modify entity location or state. They must call runtime APIs such as `spawn_entity`, `despawn_entity`, `move_entity`, `find_entity`, `find_room_entities`, `find_visible_entities`, `resolve_entity_keywords`, `update_entity_state`, and `destroy_entity`.

## Ownership and Location

Entities reserve both ownership and location fields: `owner_type`, `owner_id`, and `current_room_id`. Room-visible entities use `owner_type='room'` and `current_room_id=<room>`. Containers can later own contained entities or items without replacing the Phase 2E item system.

## Visibility Model

Room rendering asks `MudRuntime.find_visible_entities()` for visible room entities. Display order remains room name, description, players, NPCs, mobs, objects/items/corpses, then exits. Phase 2E item instances still render as room objects and remain compatible with inventory and equipment.

## NPC and Mob Foundation

NPC and mob templates seed deterministic persistent instances idempotently through `room_entity_seeds`. NPCs and mobs can exist in rooms, have keywords, descriptions, level, simple state, and appear in room output. No AI behavior, dialogue expansion, combat, attack commands, or mob tactics are implemented.

## Corpse Foundation

`corpse` is reserved as an entity type with normal room location, owner/source metadata via state/plugin data, and optional future `decay_at` data. This is only a persistence and rendering foundation for later combat death flows.

## Events

Entity APIs publish `entity_spawned`, `entity_despawned`, `entity_moved`, `entity_state_changed`, `entity_destroyed`, `room_entities_changed`, plus typed spawn events `npc_spawned`, `mob_spawned`, and `corpse_spawned`. Payloads include entity id, entity type, world id, room id, template id, source system, and optional account/character/session ids.

## Future Compatibility

The model intentionally leaves behavior systems outside Phase 3A. Future AI, combat, Builder Mode, doors, shops, pets, summons, mounts, and full containers can attach to the same runtime entity APIs without taking state authority away from `MudRuntime`.

## Phase 3B Living Runtime

Phase 3B expands the same entity foundation into living runtime instances. Templates now normalize spawn rules, wander rules, dialogue packages, behavior flags, visibility flags, profile placeholders, script hooks, and plugin data. Runtime instances expose canonical fields for state, health/mana/stamina, spawn origin, visibility, movement state, dialogue state, custom state, and persistence metadata.

`MudRuntime` now exposes `populate_world`, `find_entities`, `change_entity_state`, `teleport_entity`, `return_to_spawn`, `reset_entity`, `respawn_entity`, `create_corpse`, `get_dialogue`, and `talk_to_entity` alongside the existing spawn/move/despawn/destroy APIs. Visibility is enforced by `find_visible_entities`; hidden or invisible entities are not rendered by the canonical room renderer.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.

## Phase 4A Builder Foundation

Smart MUD supports an in-game Builder foundation for authorized `builder`, `admin`, and `owner` roles. Builder commands are registered in the command registry and are hidden from normal players. Draft edits are persisted under `worlds/<world_id>/builder/` rather than being written directly to live world package files.

The Builder workspace uses `audit`, `history`, `snapshots`, `exports`, `imports`, and `templates` folders. Room, exit, feature, item template, entity template, and spawn edits go through Builder services so runtime validation and permission checks remain authoritative. `builder validate` checks draft consistency; `builder save` creates a safe export; `builder reload` reloads drafts where safe; `builder snapshot` captures the current draft state; and `builder history` reads audit records.

Future work may add a richer semantic web Builder UI and AI-assisted Builder tools, but Phase 4A intentionally does not add AI Builder, combat, quests, shops, or spellcasting.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.
