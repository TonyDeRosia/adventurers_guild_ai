# MEDIT TBA-Style OLC Presentation

Smart MUD's interactive OLC presentation intentionally follows a compact TBA/CircleMUD-style terminal workflow, based specifically on Anthony's customized Adventurer's Lair Builder.

The visual workflow is inherited; the architecture is not. Smart MUD continues to use its modern Builder draft, validation, persistence, and publish pipeline rather than the old TBA datastore or OLC internals.

Principles:

- Dense record-oriented menus that show the editable mobile as the working record.
- Direct numbered and lettered editing from the main menu.
- Inline long and detailed descriptions on MEDIT instead of dashboard cards.
- ANSI semantic colors may be applied by the shared transport/rendering layer while stripped text remains aligned and readable.
- Compact multi-column NPC and affect flag editors.
- Dedicated subsystem editors for stats, identity/traits, loadout/loot, scripts, combat abilities, and event reactions.
- Minimal permanent help; detailed help belongs behind explicit help commands.
- No modern dashboard conversion, boxed Unicode headers, inspector panels, or web forms for this phase.
- Web and telnet share one canonical text layout; transports may differ only in color encoding.
