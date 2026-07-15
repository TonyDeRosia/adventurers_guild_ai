# Phase 13C3-B SCORE Snapshot Contract

Phase 13C3-A3E freezes the `CharacterDisplaySnapshot` contract target for the later SCORE rebuild.  This document is a contract only; the SCORE layout must not be rebuilt in this phase and display code must not perform hidden stat calculations.

## Schema version

`CharacterDisplaySnapshot.schema_version` is frozen for Phase 13C3-B as:

```text
phase13c3-b.snapshot.v1
```

Runtime producers may expose older compatibility snapshots, but SCORE-ready data should identify whether each section is available, unavailable, or a placeholder.

## Required SCORE stat-entry metadata

Every stat entry intended for SCORE must include:

- `stat_id`
- `label`
- `value`
- `unit`
- `display_format`
- `display_order`
- `display_group`
- `active`
- `inactive_reason`
- `source_version`

## Identity and progression section

The snapshot must include canonical values or explicit availability metadata for name, title, race, class, level, alignment, age, played time, experience, experience to next level, practice, training, quest points, location, world, zone, and area.  Missing systems must remain explicit placeholders; producers must not invent race/class/level-up data.

## Combat section

The snapshot must include current/max resources, the six core attributes, offense, defense, saves, resistances, criticals, weapon damage profile, unarmed damage profile, speed, carrying, encumbrance, conditions, affects, and mechanic activity.  Resource values must come from canonical runtime resource state rather than stale character JSON.

## Display boundary

`mud_displays.py` remains a renderer.  It must not calculate derived combat values for SCORE; it may only render fields supplied by the snapshot/service layer.
