# Phase 12C1 Runtime World Object Lifecycle and MUD Color Rendering

## Runtime World Object Model
Smart MUD uses the existing SQLite-backed campsite and campfire runtime tables for this phase rather than introducing a second object system. Records carry lifecycle metadata in `metadata_json`: object type, owner/creator actor, source ability, source service, authored uniqueness group, replacement policy, parent object id, created world time, expiration world time, keywords, and description source.

## Temporary Object Lifecycle and Authored Expiration
Temporary skill/spell objects require an authored lifecycle policy. Campsites and campfires read `duration_minutes` from world package profiles; the command engine does not hardcode durations. Expiration uses authoritative world time via `process_due_runtime_objects(world_time)`, which runs during runtime startup and world-time advancement.

## Owner Uniqueness and Replacement Policies
Campsites and campfires use owner-scoped uniqueness groups. Creating a new campsite replaces the previous active campsite for that owner and retires any child campfire. Creating a new campfire replaces that owner's previous active campfire. Different owners can still maintain separate active objects.

## Parent/Child Lifecycle
Campfires store their campsite parent object id in metadata. Parent expiration, dismantling, replacement, or destruction retires dependent campfires. Startup and lifecycle processing also clean orphaned campfires.

## Runtime Object Events
The survival service publishes compact serializable events including `runtime_object_created`, `runtime_object_replaced`, `runtime_object_expired`, `runtime_object_state_changed`, `runtime_object_parent_removed`, `campsite_established`, `campsite_dismantled`, `campfire_built`, `campfire_lit`, and `campfire_extinguished`. Future AI observers may consume events but must not directly mutate runtime objects.

## Commands, Lookup, and Room Refresh
Normal player commands inspect with `camp`, `campsite`, `campfire`, `look campfire`, and `examine campfire`; creation requires `set/make/establish camp` or `build/make/create campfire`. Visible mutations request canonical room refreshes. LOOK and examine use the shared target pipeline for runtime objects and exclude expired/replaced/dismantled records.

## Default White Presentation
Room descriptions, NPCs, mobs, objects, campsites, campfires, corpses, and features default to white unless Builder-authored color markup is present. Speech remains white under the existing dialogue role.

## Builder MUD Color Markup
Supported inline color tokens are `&w` white, `&r` red, `&g` green, `&y` yellow, `&b` blue, `&m` magenta, `&c` cyan, and `&n` reset. Renderers escape HTML, strip arbitrary ANSI, close spans at field boundaries, reset ANSI at field boundaries, and provide readable plain text by stripping markup.

## Color Safety and Validation
Builder validation should call `validate_mud_color_markup` for colorable fields. It reports unsupported tokens, raw ANSI, embedded HTML/script/style, and invalid control characters. Builders author text, not browser HTML or arbitrary ANSI.

## Manual Browser Test Guide
Run: `skills`, `set camp`, `look`, `look campsite`, `build campfire`, `look`, `look campfire`, `light campfire`, `look`, `examine campfire`, `campfire status`. Move to another room, `set camp`, `look`, return to confirm old campsite/campfire are gone. Advance world time past expiration and confirm objects disappear and no internal IDs or Builder text appear. Verify default white text and one test record containing safe color markup such as `A white room with &rred warning&n and &ccyan magic&n.`
