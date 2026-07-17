# MEDIT Phase 15C.1 Builder Usage

MEDIT uses the existing persistent Builder session and edits Builder drafts only. Open with `medit <id|vnum>`, create with `mcreate <id>`, inspect with `mstat`, list/search with `mlist`/`msearch`, copy with `mcopy <source> <destination>`, and delete with `mdelete <id>`.

Core nested editors support `back`, `quit`, `save`, `validate`, `preview`, `undo`, `redo`, and `help` where applicable. Descriptions use the shared multiline editor commands `.save`, `.end`, `.cancel`, `.show`, and `.clear`. Keyword/list editors support `list`, `add`, `remove`, `move`, `clear`, and `back`. Flag editors support number or name toggles plus `all`, `none`, and `clear`.

Functional foundation sections include identity, keywords, descriptions, traits/profile separation, attributes/resources, combat statistics, body profile and natural attacks, positions, mobile flags, permanent affects, pet/economy fields, equipment loadout, starting inventory, loot/corpse behavior, preview, validation, copy, and dependency-protected deletion.

Advanced ability, event-reaction, full autonomous AI, faction relationship graph, and scripting workflows are deliberately preserved as references for later phases rather than represented as complete editors in Phase 15C.1.
