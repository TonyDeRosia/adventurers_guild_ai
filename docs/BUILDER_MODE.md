# Smart MUD Builder Mode

Builder Mode is the command-first foundation for safe in-game world editing.

## Permissions

Only accounts/characters with the `builder`, `admin`, or `owner` role can run Builder commands. Normal `player` and `helper` roles cannot see or use Builder internals.

## Workspace

Drafts are stored under `worlds/<world_id>/builder/` with these folders:

- `audit`
- `history`
- `snapshots`
- `exports`
- `imports`
- `templates`

Live world files are not overwritten by normal edit commands. `builder save` writes a safe export into `builder/exports` for manual promotion.

## Commands

Mode and lifecycle commands:

- `builder`, `build`, `builder on`, `builder off`
- `builder validate`
- `builder save`
- `builder reload`
- `builder snapshot`
- `builder history`

Room commands:

- `redit`, `rstat`, `rcreate`, `rset`, `rdesc`, `rname`, `rexits`, `rfeature`, `rdelete`

Exit commands:

- `exedit`, `excreate`, `exset`, `exdelete`

Feature commands:

- `fedit`, `fcreate`, `fset`, `fdesc`, `fdelete`

Item template commands:

- `oedit`, `ocreate`, `oset`, `odesc`, `odelete`, `ostat`

Entity template commands:

- `medit`, `mcreate`, `mset`, `mdesc`, `mdelete`, `mstat`

Spawn commands:

- `spawnedit`, `spawncreate`, `spawnset`, `spawndelete`, `spawnstat`

World inspection commands:

- `zstat`, `astat`, `wstat`

## Draft vs. Live Data

Builder edits create draft JSON records. Movement, interaction, rendering, and spawning remain runtime-owned and must continue to use runtime validation. Builder features can be discovered by draft-aware look/examine-style flows without hardcoding individual feature IDs.

## Validation

`builder validate` reports duplicate/missing IDs where represented in draft data, missing names, broken room exits, missing spawn entity templates, invalid wear slots, invalid entity types, invalid JSON/plugin data, and world-package compliance issues that can be checked safely from drafts.

## Audit, History, and Snapshots

Every Builder change records timestamp, account ID, character ID, world ID, action, target type, target ID, before/after snapshots where feasible, and reason when supplied. Audit JSONL files are written under `builder/audit` and mirrored to `builder/history`. Snapshots copy current draft files to a timestamped folder under `builder/snapshots`.

## Web and Telnet

Builder commands use normal command input. Web output remains semantic text/HTML through existing rendering paths, and telnet output remains plain/ANSI. A full web Builder UI is future work.

## Explicit Non-Goals

Phase 4A does not implement AI Builder, combat, quests, shops, spellcasting, or a redesigned UI.

## Local owner bootstrap

No account or character is silently promoted. For local development, grant yourself access explicitly with the CLI helper after the local SQLite database has an account or character:

```bash
python tools/bootstrap_owner.py --account local_dev --role owner
```

or, for a specific character:

```bash
python tools/bootstrap_owner.py --character Kraevok --role owner
```

The helper writes to `user_data/mud_state.db` by default. Use `--db /path/to/mud_state.db` when testing against another local database.

Supported persisted roles are `player`, `helper`, `builder`, `admin`, and `owner`. Builder commands allow `builder`, `admin`, and `owner`; `owner` is the top role and has all Builder/admin permissions. Restarting the app preserves the account and character roles in SQLite.

## Role inspection and grants

Use `whoami` in game to inspect account role, character role, and effective role. `score` also shows account and character roles.

Owners may grant roles in game with:

```text
grantrole <character/account> <player|helper|builder|admin|owner>
```

Non-owners are denied. Each CLI or in-game role grant is logged to SQLite with account, character when available, role, timestamp, and source.

## Phase 4B Builder runtime navigation note

Builder-created draft rooms now participate in a runtime world graph overlay for builder/admin/owner users with Builder Mode enabled. Runtime lookup merges live world package rooms with BuilderWorkspace drafts, with drafts overriding live rooms for builders only. `goto`, `look`, `rooms`/`rlist`, `rfind`/`rsearch`, `dig`, `link`, `unlink`, and `map`/`rmap` use this merged lookup and the canonical room renderer. Normal players do not see builder-only metadata or draft-only rooms. Draft saves export BuilderWorkspace content; promotion to live packages is not implemented yet. See `docs/BUILDER_NAVIGATION.md`.

## Smart MUD Phase 4C Builder Workflow 2.0

Phase 4C standardizes Builder Mode around a canonical room graph: live world rooms are merged with draft rooms for authorized builders, while normal players continue to see only live package content. Room rendering, look/exits, movement, goto, dig, link/unlink, map/rmap, and builder validation are required to use that shared graph so displayed exits match traversable exits.

Builder commands maintain an explicit editing context and print a `Currently editing:` block for room-editing workflows. `rname` and `rdesc` edit only the selected room target. Room ids must be safe lowercase underscore ids; room names may contain spaces. The primary workflow is `dig <direction> <room_id> ["Room Name"] [--one-way]`, with self-loops blocked unless explicitly allowed. Known limits: visual Builder UI, AI Builder, combat, shops, quests, and spellcasting remain future work and are not introduced by this phase.

## Phase 4C Hotfix 2: Builder polish and draft integrity

Builder output now uses one canonical `Builder Status:` block. The block separates the builder's current location from the current edit target so moving around and editing a room are visibly different:

```text
Builder Status:
Location:
  Room: testies_2
  Name: Testies 2
  Source: draft

Currently editing:
  Type: room
  Room: testies_2
  Name: Testies 2
  Source: draft
  Dirty: yes
```

If no edit room is selected, the edit section reads `Currently editing: none`. Builder-only status is never shown to normal players.

Room ids are machine identifiers and must be lowercase snake_case with no spaces, uppercase letters, or punctuation other than underscores. Room names are human display names and may contain spaces and capitalization. `rname` rejects ID-looking names such as `testies_two` unless the builder explicitly uses `rname --force testies_two`; room-id migration is reserved for a future command.

`desc <text>` is a Builder Mode alias for `rdesc <text>`. Outside Builder Mode, it explains that Builder Mode must be enabled first. `rsave`, `asave`, `bsave`, `wsave`, and `save` are registered: Builder Mode routes them to the safe builder export path, while normal player `save` explains that characters autosave.

Draft room records are normalized on load and before save/export. Every draft room carries `id`, `name`, `description`, `world_id`, `area_id`, `zone_id`, `exits`, `features`, `flags`, `tags`, and `plugin_data`; valid existing data is preserved and live world files are not modified.

`builder validate` reports grouped Errors, Warnings, and Info for unsafe ids, partial drafts, missing or empty room fields, ID-looking names, broken exits, reverse-exit mismatches, self-loops, and draft rooms that shadow live rooms. Visual Builder UI, AI Builder, combat, quests, shops, and spellcasting remain future work.


## Phase 4D Builder Workflow 3.0

Builder Mode now uses a canonical HUD instead of ad-hoc status spam. `builder status`, `bstatus`, and Builder-only `status` print the HUD on demand, showing current location, current room edit target, source, and dirty state. Target-changing and editing commands refresh it; passive commands such as `look`, movement, inventory, and score should not spam it.

Room editing supports `redit <room_id>`, `redit next`, and `redit previous` for cycling draft rooms. `rname` rejects blank names and warns about duplicate display names or names that match IDs. `rdesc` with no text opens the multiline in-MUD description editor; finish with `.end` or cancel with `.cancel`.

`exits` lists the six primary exits in `Direction -> destination` form, and `examine exit <direction>` / `x exit <direction>` inspect destination, reverse direction, and validity.
