# Phase 15B.40 Smart MUD Current OLC Menus

## OEDIT before this phase

Production `oedit <id>` rendered an object dashboard headed `Object Builder`, `Object Editor`, `Type-specific sections`, and `Grouped sections`. It listed completion counts by section and included instructional workflow text, but it did not make the TBA-style field menu the primary surface.

## OEDIT after this phase

Production `oedit <id|vnum>` now starts a persistent Builder edit session and renders a TBA-style current-value menu. The primary rows are `1) Keywords`, `2) S-Desc`, `3) L-Desc`, `4) A-Desc`, `5) Type`, `6) Extra flags`, `7) Wear flags`, `8) Weight`, `9) Cost`, `A) Cost/Day`, `B) Timer`, `C) Values`, `D) Applies menu`, `E) Extra descriptions menu`, `M) Min Level`, `P) Perm Affects`, `S) Script`, `W) Copy object`, `X) Delete object`, and `Q) Quit`.

Implemented production routes:

- Text/list fields route to list, prompt, or multiline editors.
- Extra, wear, and permanent affect flags route to numbered toggle menus.
- Type-specific values, applies, scripts, and extra descriptions route to canonical list managers where runtime-specific support is still modernized.
- Copy routes to a destination-ID workflow.
- Delete checks dependencies before confirmation.
- Quit uses the shared session save/discard/cancel semantics.
- Validate, preview, undo, and redo remain available as secondary commands.

## MEDIT current state

`medit <id|vnum>` already creates a shared Builder edit session and renders a numbered current-value mobile menu. Phase 15B.40 keeps that primary menu and adds tests preventing it from being treated as a grouped summary.

## Remaining OLC editors

REDIT, ZEDIT, AEDIT, QEDIT, script/trigger editing, shop editing, help/social editing, and desktop visual Builder are not fully implemented in this phase. Their current Smart MUD state is implementation/specification pending and should not be claimed complete from documentation-only menus.
