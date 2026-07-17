# Next Runtime Phase Spec — Phase 16B

## Decision

Proceed with Phase 16B unchanged: persistent exit and door state parity is the next implementation phase. This phase must not implement containers, object use, NPC AI, DG triggers, broad Builder UI, or unrelated combat changes.

## Required runtime contract

Implement a canonical door/exit state owner for runtime movement. The owner may live inside `engine/mud_runtime.py` only if it can remain testable and non-duplicative; otherwise introduce a narrow module dedicated to exit state. The contract must provide:

- lookup by world id, room id, and direction;
- reset/default state from canonical room/reset data;
- mutable closed/open and locked/unlocked state;
- key reference validation;
- hidden/discovered state if current Smart MUD room data exposes it;
- one-way exit behavior without manufacturing reverse exits;
- persistence through `engine/mud_state_store.py` or the existing canonical persistence layer;
- event publication for state changes;
- restart survival tests.

## Source evidence to inspect before coding

### Smart MUD

- `engine/mud_runtime.py` — current movement and command execution owner.
- `engine/mud_commands.py` — parser/command adapters for movement and door verbs.
- `engine/world_registry.py` — canonical room/exit data access.
- `engine/zone_resets.py` — reset application and ordering.
- `engine/mud_state_store.py` — persistence owner.
- `worlds/shattered_realms/rooms/rooms.json` — room/exit data.
- `worlds/shattered_realms/resets/resets.json` — reset inputs.
- Existing movement, room, reset, and persistence tests under `tests/`.

### Adventurer's Lair

- `src/act.movement.c` — movement and door verbs.
- `src/act.item.c` — key/use interactions that affect locks.
- `src/db.c` — room/exit loading and zone reset application.
- `src/structs.h` — room direction, exit flags, key fields.
- Zone/world files defining door reset commands.

The customized Adventurer's Lair repository could not be cloned from this environment during Phase 16A.1 because GitHub access returned `CONNECT tunnel failed, response 403`. If implementation access is still blocked, use only previously documented behavior and mark remaining source-specific details as unverified.

## Commands in scope

- Directional movement aliases.
- `open` and `close` for exits.
- `lock` and `unlock` for exits.
- `pick` only if an existing command path is present; otherwise document as deferred.
- `look`/room rendering only where necessary to reveal door/hidden-exit state.

## Persistence requirements

- Store only runtime deltas needed to survive restart and reset correctly.
- Do not duplicate immutable room definitions.
- Include a deterministic key: world id, room id, direction.
- Persist closed/open, locked/unlocked, discovered/hidden runtime state if supported, updated timestamp, reset source if relevant.
- Load persisted state before player movement can observe it.

## Tests required for completion

- Movement blocked by closed door.
- Movement blocked by locked door without key.
- Unlock/open/move success with valid key.
- Lock/close state persists across restart.
- Reset reapplies default door state according to reset rules.
- One-way exit does not require a reverse exit.
- Hidden exit is not shown until discovery if existing Smart MUD data supports hidden exits.
- Events are emitted for door state changes.
- Builder/content validation tests continue to pass or baseline deltas are documented.

## Explicit exclusions

- Containers and nested inventory.
- Object consumption, lights, potions, scrolls, wands, staves.
- Corpse looting/decay changes.
- NPC AI/aggression/scavenging.
- DG triggers or special procedure runtime.
- Broad Builder UI/editor redesign.
- Direct C architecture translation.

## Acceptance standard

Phase 16B is complete only when the production movement path, persistence path, reset path, and tests all agree on one authoritative exit state model and the implementation documents any remaining Adventurer's Lair source uncertainty.

## Phase 15C.0 Builder MEDIT/OEDIT Parity Audit

Phase 15C.0 produced permanent design specifications for future Mob Builder and Object Builder work:

- `docs/BUILDER_MEDIT_SPECIFICATION.md` defines MEDIT parity requirements, stats, NPC flags, AFF flags, loadout/loot, combat abilities, event reactions, scripts, dependency checks, and the 15C implementation sequence.
- `docs/BUILDER_OEDIT_SPECIFICATION.md` defines OEDIT parity requirements, object type values, extra/wear flags, applies, permanent affects, extra descriptions, scripts, dependency checks, and the 15D implementation sequence.

The specifications are intentionally architectural. They require behavioral parity through Smart MUD Builder sessions, drafts, validation, preview, publish, activation, and rollback; they explicitly forbid porting TBA C code, bitvectors, file formats, menu architecture, or compatibility wrappers.
