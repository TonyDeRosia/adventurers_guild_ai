# Builder MEDIT Specification

## Phase 16B visible interaction requirements

MEDIT is a draft-first mobile editor. The normal main menu and section menus are production UI, not placeholders for hidden help. A first-time Builder must be able to understand each visible field by reading the ordinary screen.

### Main menu

Every main MEDIT section displays a one-line explanation of what that section controls: identity, keywords, descriptions, stats/resources, combat, natural weapons, body profile, positions, mobile flags, permanent affects, equipment, inventory, loot/corpse, combat abilities, event reactions, faction, scripts, spawns, and diagnostics.

### Identity model

* `name` / Display Name: player/admin-facing mobile name shown in Builder menus, previews, logs, and administrative tools.
* `id` / Stable Mobile ID: immutable internal identifier used by references and draft files.
* `vnum` / Legacy VNUM: optional numeric compatibility identifier for classic MUD workflows.
* `species` / Species-Race: biological or lore identity stored as a named reference.
* `gender` / Sex-Gender Presentation: descriptive/pronoun presentation.
* `size`: physical scale used by combat readability, equipment/body assumptions, movement, and validation.
* `classification`: broad creature taxonomy such as humanoid, animal, undead, construct, dragon, elemental, etc.
* `entity_type` / NPC Role: gameplay role/function such as guard, merchant, trainer, quest giver, caster, boss, pet, or civilian.
* `enabled`: Yes/No lifecycle flag controlling whether normal publish/activation/spawn workflows may use the mobile.
* `tags`: Builder-only search and organization labels with no direct gameplay effect.

`entity_type` is no longer presented as vague “Entity type” in Identity. It is shown as `NPC Role`. Creature Classification and Size are separate fields and must never display each other's values.

### Pickers

Finite Identity values use numbered pickers. Required pickers include Sex/Gender Presentation, Creature Classification, Size, Enabled, and NPC Role. Pickers accept numbers and case-insensitive names. Enabled additionally accepts yes/no, true/false, enabled/disabled, and on/off.

Species is a reference-like picker. Because Smart MUD currently stores species as a named value rather than creating a species registry record, the picker must honestly say so, show common built-ins, show values already used by mobiles, provide search, provide custom named entry where permitted, provide clear where optional, and provide back/cancel.

### Recommendations and examples

When authored values support it, MEDIT displays contextual recommendations without applying them automatically. Example: Human recommends Humanoid classification and Medium size; Wolf recommends Animal classification and Medium size. `apply recommended` may be used in supported pickers.

World-specific examples should be limited in the default view and may be expanded by examples commands.

### Wrong-context commands

Inside MEDIT, recognized world commands must be contextualized. `medit 1500` explains that another mobile would normally be opened but an edit session is active. `mlist all` is identified as a read-only mobile-list world command while preserving editor state. `look` and similar commands identify the active editor context and safe editor commands.

### Save confirmation

`save`/`S` must persist the mobile draft through the Builder draft mutation path, update revision, clear dirty state, and display an explicit save report including mobile name, revision, unsaved changes, validation, publish readiness, and current editor context. A Builder log/audit line such as `[builder] Saved mobile draft <id> revision=<n>` must accompany the save path.

### Production-path testing

Tests for visible MEDIT behavior must exercise production-visible output, including the API/browser route where possible. Helper-renderer tests are useful but not sufficient to prove the ordinary web scrollback path.
