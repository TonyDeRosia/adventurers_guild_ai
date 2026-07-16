# Phase 15B.22 Builder Usability / Oasis OLC Audit

Reference requested: `https://github.com/TonyDeRosia/tbamud_adventurers_lair`.

## Access status

The implementation attempted to fetch the reference repository before coding:

```text
git clone --depth 1 https://github.com/TonyDeRosia/tbamud_adventurers_lair
fatal: unable to access 'https://github.com/TonyDeRosia/tbamud_adventurers_lair/': CONNECT tunnel failed, response 403
```

Because the environment blocked GitHub with a 403 CONNECT tunnel response, this pass could not directly inspect the requested `src/oasis.c`, `src/oasis.h`, `src/oasis_list.c`, `src/medit.c`, `src/oedit.c`, `src/redit.c`, `src/zedit.c`, `src/genolc.c`, `src/genmob.c`, `src/genobj.c`, `src/genwld.c`, `src/genzon.c`, `src/interpreter.c`, or `src/constants.c` files. The remaining comparison below is therefore intentionally conservative and based only on established Circle/TBA Oasis workflow expectations already represented in Smart MUD's BuilderService/OLC surface.

## Smart MUD behavior improved in this pass

- `mlist` and `olist` now use aligned, scan-friendly list tables instead of placeholder text.
- Builder list location context resolves from the actor's mapped room before falling back to selected builder area/zone attributes, avoiding misleading `Current zone: none` output while standing in a mapped room.
- `alist` and `zlist` are routed through the same BuilderContentQueryService list renderer used by `mlist`/`olist`, keeping Builder discovery formatting consistent.
- List columns are hidden when they contain no useful data, with VNUM/ID/name/title retained as core Builder identity columns.
- Validation text now explains specific missing Builder data such as missing VNUM, keywords, descriptions, body profile, AI, natural attacks, spawns, or loot.

## Remaining differences from Oasis / TBA-style OLC

- Direct TBA source parity is not claimed because the reference repository could not be fetched in this environment.
- Smart MUD still uses draft JSON-backed BuilderService sessions rather than Circle/TBA's in-memory `OLC_*` descriptor structs. This is intentional; the phase explicitly forbids replacing BuilderService or draft architecture.
- `scan` remains on the existing look/glance command path in this pass; a full multi-room TBA-style scan with darkness/invisibility/closed-exit line-of-sight requires runtime visibility APIs that were not changed here.
- Numeric picker follow-up state is not implemented here; multiple editor matches render the existing picker and ask the Builder to refine/select rather than guessing.
- `astat`/`zstat` summary expansion and Windows manual testing remain incomplete in this environment.

## Files requested for audit

- `src/oasis.c`: blocked by GitHub 403; no direct audit completed.
- `src/oasis.h`: blocked by GitHub 403; no direct audit completed.
- `src/oasis_list.c`: blocked by GitHub 403; no direct audit completed.
- `src/medit.c`: blocked by GitHub 403; no direct audit completed.
- `src/oedit.c`: blocked by GitHub 403; no direct audit completed.
- `src/redit.c`: blocked by GitHub 403; no direct audit completed.
- `src/zedit.c`: blocked by GitHub 403; no direct audit completed.
- `src/genolc.c`: blocked by GitHub 403; no direct audit completed.
- `src/genmob.c`: blocked by GitHub 403; no direct audit completed.
- `src/genobj.c`: blocked by GitHub 403; no direct audit completed.
- `src/genwld.c`: blocked by GitHub 403; no direct audit completed.
- `src/genzon.c`: blocked by GitHub 403; no direct audit completed.
- `src/interpreter.c`: blocked by GitHub 403; no direct audit completed.
- `src/constants.c`: blocked by GitHub 403; no direct audit completed.
