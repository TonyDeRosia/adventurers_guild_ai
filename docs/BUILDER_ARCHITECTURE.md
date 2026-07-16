# Builder architecture status

Phase 15B.14B converts the previous menu renderer into a canonical BuilderService-centered path for mobile editing.

## Current architecture before the fix

The repository had a `BuilderWorkspace` storage layer, a `BuilderService` facade, and command handlers in `engine/mud_commands.py`. The service rendered menus, wrote whole draft collections, tracked advisory locks, and exported generation files. Older builder commands still called workspace helpers directly.

## Implemented architecture

* `BuilderService` is the mutation authority for the new interactive mobile editor, direct natural-weapon edits, clone, publish, activation, testspawn, undo, and redo.
* `BuilderSessionManager` keeps active `BuilderEditSession` instances in memory and routes subsequent input before normal command dispatch.
* `medit` is the completed first editor slice for natural weapons, preview, validation, testspawn, save, undo, redo, and quit.
* Natural weapons are canonical at `combat_profile.natural_weapons`; legacy `natural_attacks` is migrated on load and not persisted as a competing schema.
* Attack families, body profiles, and natural weapon profiles are editable builder collections rather than Python-only combat suggestions.
* Mutations require builder permission plus an owned lock unless an admin override is explicit.
* History records are object-level before/after records instead of whole-world snapshots.
* Draft records carry `_builder_revision`, and session writes pass an expected revision.
* Validation returns structured issue records with severity, code, collection, object ID, field path, message, and fix hint.
* Preview reads the canonical runtime-shaped natural weapon data used by combat adapters.
* Testspawn materializes an ephemeral resident-like draft mob payload in a private builder room on the actor for runtime command adapters to inspect and clear.
* Publish writes an immutable generation package with manifest, hashes, schema versions, validation report, migration report hooks, and rollback metadata. Activation is explicit and updates `active.json` only after manifest verification.
* Live mob update policy: new spawns use the newly activated generation; existing live mobs retain old combat state until death/despawn.

## TBA behavioral audit

The referenced tbaMUD repository is a C codebase with traditional OLC concepts such as descriptor/editor state, scratch copies, menu sections, save confirmation, zone-oriented building, and attack type menus. Smart MUD copies those behaviors at the workflow level while improving with searchable string IDs, typed validation, object history, generation packaging, rollback, private test rooms, and GUI-compatible service APIs. No C code was copied.

## Remaining limitations

This pass makes `medit` real for the natural-weapon/runtime-combat path. `redit`, `oedit`, `aedit`, and `zedit` still need the same full typed section coverage. Some legacy command handlers still use older `BuilderWorkspace` helpers and should be incrementally migrated behind `BuilderService` wrappers.

## Windows manual acceptance

Do not mark Windows acceptance complete until Tony manually runs the requested tests A-E on Windows.
