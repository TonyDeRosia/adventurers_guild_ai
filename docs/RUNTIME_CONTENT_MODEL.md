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
