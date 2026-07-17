# Phase 15B.40 TBA OLC Reference Menus

## Source snapshot

The requested archive `tbamud_adventurers_lair-main(1).zip` was searched for under `/workspace` and `/` and was not present in this execution environment. Because the exact uploaded archive was unavailable, this document records the phase's authoritative menu contract from the supplied phase text and marks source-backed verification as pending until the archive is restored.

- Archive filename requested: `tbamud_adventurers_lair-main(1).zip`
- Extracted path: unavailable in this container
- Source tree root: unavailable in this container
- Source SHA: unavailable; uploaded archive is intended authoritative snapshot
- Required source files to inspect when restored: `src/oedit.c`, `src/medit.c`, `src/redit.c`, `src/zedit.c`, `src/aedit.c`, `src/qedit.c`, `src/dg_olc.c`, `src/dg_olc.h`, `src/oasis.c`, `src/oasis.h`, `src/genolc.c`, `src/genolc.h`, `src/oasis_list.c`, `src/oasis_copy.c`, `src/shop.c`, `src/interpreter.c`, `src/comm.c`, `src/modify.c`, `src/constants.c`, `src/structs.h`.

## OEDIT authoritative visual contract

Primary menu shape, modeled after Adventurer's Lair/TBA Oasis OEDIT:

```text
-- Item number : [<vnum/id>]
1) Keywords
2) S-Desc
3) L-Desc
4) A-Desc
5) Type
6) Extra flags
7) Wear flags
8) Weight
9) Cost
A) Cost/Day
B) Timer
C) Values
D) Applies menu
E) Extra descriptions menu
M) Min Level
P) Perm Affects
S) Script
W) Copy object
X) Delete object
Q) Quit
```

Expected interaction model: each visible choice immediately enters a prompt, submenu, flag picker, list manager, copy/delete confirmation, or quit save/discard/abort prompt. A grouped dashboard is not a functional substitute.

## MEDIT authoritative visual contract

MEDIT must be a numbered current-value mobile editor, not a grouped summary. The current phase minimum is a primary menu exposing aliases/keywords, short/long/detailed descriptions, level, alignment, race/class where supported, stats/resources, armor/combat data, positions, sex, action/affect flags, attacks, equipment, carried inventory, behavior/script status, and save/quit.

## Remaining editors

REDIT, ZEDIT, AEDIT, QEDIT, DG trigger editing, shop editing, help/social editors, and related Oasis/DG files remain source-backed audit targets. Until the archive is available, their final option order, edit modes, save prompts, copy/delete behavior, permissions, locking, and disk/runtime save semantics are classified `NEEDS-VERIFICATION`.
