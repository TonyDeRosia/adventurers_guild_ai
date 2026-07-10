# tbaMUD World Design Parity for Smart MUD

Smart MUD uses tbaMUD as a design reference only. It preserves proven builder workflow ideas without copying legacy file formats.

## Preserved Design Lessons

* Zone modularity keeps related rooms, resets, spawns, and ambience together.
* Vnum organization gives builders predictable numeric planning ranges.
* Builder-first workflow supports offline design before runtime publishing.
* Room, mobile/entity, object/item, and spawn data remain separated.
* Logical exit consistency is validated so navigation remains coherent.
* Area balance planning happens before large-scale content expansion.
* Resets and spawns are zone responsibilities rather than ad hoc room-only data.

## Smart MUD Changes

* JSON replaces `.wld`, `.zon`, `.mob`, `.obj`, `.shp`, and `.trg` files.
* Builder drafts replace direct live file editing.
* Generic optional location hierarchy replaces hardcoded fantasy geography.
* `plugin_data` provides stable extension points.
* Import/export bundles provide reviewable content movement.
* AI-readable metadata may describe tone and context, but AI does not own authoritative world state.
