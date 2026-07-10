# Runtime Content Model

Smart MUD distinguishes definitions, declarations, and instances.

- Feature definitions are nonportable environmental objects resolved from shared `feature_refs` or local room `features`.
- Item templates define reusable item data but are never live room contents by themselves.
- Item placements declare initial item instances with `id`, `item_template_id`, `room_id`, `quantity`, `seed_policy`, `flags`, `tags`, and `plugin_data`.
- Item instances are live SQLite objects with one location: room, inventory, equipment, container, or destroyed.
- Entity templates define NPC/mob data but are not live NPCs by themselves.
- Entity spawns declare initial entity instances with stable IDs and `spawn_policy`.
- Entity instances are live SQLite records with stable identity and mutable state.

The canonical room query is `MudRuntime.get_room_contents(room_id, viewer=None, include_builder_metadata=False)`.


## Runtime-instance-only entity rendering

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B living collections

World packages may include `schedules`, `need_profiles`, `goal_profiles`, `relationship_seeds`, and `memory_seeds`. These files seed live mutable SQLite records; they are not the live state store.
