# Phase 15B.14C Builder Behavior

This document records the implemented mobile Builder slice for Phase 15B.14C.

## Implemented behavior

* Mobile editing uses a TBA-style session scratch copy: drafts are loaded into `BuilderEditSession.working_record`, field commands mutate only that scratch record, and `save` validates and persists the object.
* Dirty quit prompts for save, discard, or cancel. `discard` restores the session savepoint. Session recovery metadata is written under the Builder session state directory.
* Mobile fields are edited with typed commands for name, keywords, descriptions, level, attributes, resources, body profile, combat references, loot/corpse data, behavior, flags, equipment/loadout references, inventory references, spawn/reset references, and scripts/triggers. Natural weapons keep a richer subsection with add, clone, set, delete, enable/disable, reorder, preview, and validation.
* `MobileTemplate` is the canonical mobile adapter. It imports legacy `natural_attacks`/top-level `natural_weapons` aliases, persists canonical `combat_profile.natural_weapons`, validates records, emits runtime projections, and computes diffs.
* Body-profile application uses the active world, not a hard-coded world id. It deep-merges body data into `combat_profile` and appends missing suggested natural weapons without shallow-replacing unrelated combat fields.
* Locks use an OS-file-lock protected compare-and-set update over `locks.json`. Lock ownership records account id, character id, session id, revision, timestamps, recoverable state, and disconnect state.
* Saves perform one service-level object transaction: draft update, revision increment, validation result, history entry, audit entry, and session savepoint update are committed through `BuilderService`.
* Preview uses the same canonical mobile adapter and runtime projection as testspawn, including LOOK, EXAMINE, CONSIDER, combat snapshot, natural weapon list, and sample combat messages.
* `builder testspawn` creates resident ephemeral actor records in an isolated private test environment structure on the character, including private room id, resident actor registration, occupancy metadata, combat registration flag, AI registration flag, natural weapons, attributes, resources, and cleanup state. `builder testclear` clears resident actors, occupancy, encounters, tasks, timers, corpses, and private-room metadata.
* Publish builds immutable generation packages with content hashes and a manifest. Activation verifies hashes, normalizes content, builds immutable registries, exposes an in-memory active content generation pointer, records the previous generation, and preserves the existing-live-mob policy that existing actors retain their template projection until death/despawn while new spawns use the active generation.
* Rollback runs through the same activation path as forward activation.

## Remaining limitations

* The production runtime still needs deeper direct integration points for every live movement/combat registry; this phase exposes the Builder-side resident/runtime projections and generation pointer without changing the combat latency architecture.
* Windows manual acceptance is not claimed until Tony performs the documented manual tests.
