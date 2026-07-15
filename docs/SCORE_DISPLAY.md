# SCORE and WORTH Display Projection

## Phase 15B.13A hotfix status

SCORE and WORTH continue to use the existing Adventurer's Lair-compatible formatters.  The hotfix repairs the shared progression projection feeding those formatters rather than redesigning SCORE, removing fields, or substituting fabricated progression data.

The repaired projection preserves the established SCORE requirements: the 81-column Adventurer's Lair frame, current section order, numeric saves, encumbrance labels, currency order, play-time presentation, conditional unarmed/birthday rows, quest behavior, and admin rows.  The HP/Mana/Move/Alignment row remains outside SCORE because the prompt owns those resources.

WORTH continues to consume the shared display snapshot path.  The regression test verifies that a tuple-row progression connection can build SCORE, WORTH, and a repeated SCORE snapshot without the generic character-load failure or `score_projection_incomplete` text.

Windows status remains manual: Tony must pull the patch, fully restart Smart MUD, enter Kraevok, run `sc`, `score`, `worth`, `eq`, `restore self`, repeat `sc`, fight Dire Forest Wolf, then confirm `sc` and `worth` still render and the backend has no `progression_display_snapshot_failed`, `score_projection_incomplete`, or `ValueError at dict(row)` logs.
