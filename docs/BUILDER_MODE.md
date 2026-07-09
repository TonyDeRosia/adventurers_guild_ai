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
