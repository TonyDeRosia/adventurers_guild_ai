# OBJECT EDITOR

Phase 15B.14 modernizes Smart MUD Builder around a single canonical BuilderService. Tony's Adventurer's Lair/TBA Oasis OLC remains the behavioral reference: builders choose an editor command, work in a temporary menu/session, preview, validate, save, and publish. Smart MUD deliberately does not copy C implementation; all mutations flow through draft JSON collections in the existing builder workspace.

## TBA/Oasis audit summary

TBA medit, redit, oedit, zedit, sedit, aedit, hedit, and tedit create temporary edit structures, lock the target descriptor, present numbered menus, validate obvious references, and require an explicit save path. Zone editing centers on reset commands. Prototype saves update disk prototypes; live mobs may require explicit refresh or reset behavior depending on subsystem. DG scripts attach by trigger references. Builders preview by stat/show commands, moving through rooms, resets, and test loads.

## Smart MUD gap analysis

Before Phase 15B.14, Smart MUD had draft files and command-level BuilderWorkspace helpers, but editor behavior was fragmented, JSON-oriented, and lacked one facade for OLC, future GUI, import/export, locks, undo/redo, picker UX, draft testspawn, and generation publishing. This document family defines the canonical path.

## Architecture

* BuilderService is the canonical mutation facade.
* BuilderWorkspace remains persistence/audit/event infrastructure.
* Interactive editors show TBA-like menus but write only drafts.
* Publish creates immutable generation output under builder/generations and records the active generation pointer for atomic runtime swap.
* Validation and preview are service methods and are therefore shared by commands, future GUI, web editor, batch importers, and JSON import/export.

## Workflows

1. Open an editor such as medit forest_wolf.
2. BuilderService acquires an edit lock.
3. The editor presents numbered sections, preview, validate, save draft, publish, and quit.
4. Section mutations push undo history before draft writes.
5. Preview renders player-facing look/examine/combat/spawn output from drafts.
6. Publish validates and writes a new generation.

## Validation

Validation reports errors and warnings with fix guidance for missing descriptions, missing attacks, invalid exits, broken references, missing templates, duplicate IDs, missing body profiles, bad spawns, missing scripts, and missing combat profiles.

## Preview

Preview shows LOOK/EXAMINE-style output, exits/spawns for rooms, combat messages for mobiles, and loot/equipment summaries for objects without touching live runtime objects.

## Locks and recovery

Edit locks are keyed by collection and id, store builder name and timestamp, and can be overridden through admin unlock flows. Stale lock policy is documented as administrative recovery to avoid silent concurrent edits.
