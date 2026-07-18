# Builder UX Guidelines

Smart MUD Builder is a draft-first, self-documenting world-building IDE. Editors must teach first-time builders while preserving fast command-driven workflows for experienced builders.

## Philosophy

- The Builder itself is the documentation; help commands expand information but must not be the only way to discover it.
- Menus explain current state, safe next actions, available commands, and publish readiness before builders ask.
- Field editors explain meaning, runtime usage, valid values, defaults, examples, warnings, related fields, and safe recovery commands inline.
- Validation is educational: every issue explains what happened, why it matters, how to fix it, whether it blocks publish, and what happens if ignored.
- Draft/save/publish remains the required workflow. UX improvements must not replace BuilderService or create parallel builders.

## Persistent Context Standard

Every Builder screen must answer these questions without relying on memory:

- Where am I?
- What editor is open?
- What object is being edited?
- Which submenu or field is active?
- Are changes saved or modified?
- Did validation pass?
- Is publish blocked?
- What commands are safe right now?

Use a persistent status block with editor, object name, submenu, mode, modification state, validation issue counts, publish readiness, and unsaved-change state.

## Field Presentation Standard

Every editable field must display:

- **What It Is**: the plain-language definition of the field.
- **Why It Exists**: why builders should care about the data.
- **Runtime Usage**: how preview, validation, publish, AI, combat, spawn, search, or lore systems consume it.
- **Current Value**: formatted as `none` when blank.
- **Required/Optional**: whether blank input is acceptable.
- **Publishing Impact**: whether missing or invalid data blocks publish/save or is a quality warning.
- **Runtime Impact**: whether the field changes generated runtime behavior.
- **Inheritance**: whether the value is explicit or supplied by related profiles/defaults.
- **Legal Values**: all enum or flag choices, numbered when selectable.
- **Common Values**: frequently used entries grouped by concept where possible.
- **Recommended Values**: practical guidance by level, NPC role, or content archetype.
- **Examples**: concrete content examples such as `human — Town Guard` or `dragon — Ancient Red Dragon`.
- **Related Fields**: sections that should be reviewed next, such as Body Profile, AI, Faction, Loot, or Spawns.
- **Safe Commands**: `list`, `values`, `examples`, `inspect`, `help`, `details`, `advanced`, `clear`, and `back` where appropriate.

## Enum and Picker Standard

Do not ask builders to memorize enum values. When legal values exist:

- Display all values inline before input.
- Number values for selection when the editor supports it.
- Allow typing either the value or a number when practical.
- Explain rejected values by naming the entered value and showing accepted alternatives.

## Inspector Mode

Every field should support `inspect`. Inspector output must include:

- Current value.
- Default.
- Recommended values.
- Runtime effect.
- Validation state.
- Referenced by.
- Related fields.
- Inheritance behavior.
- Publish status.

Inspector mode is for deeper inspection; it is not a substitute for visible field education.

## Search Standard

Builder sessions should accept `search <query>` and `find <query>` for Builder concepts and data. Search results should return matching concepts such as species, dragon, undead, merchant, health, loot, faction, AI, body profile, and spawn references, with enough context to jump to the relevant section.

## Validation Standards

Validation output uses consistent severities: `INFO`, `WARNING`, `ERROR`, and `BLOCKING`.

Each validation entry answers:

- What happened?
- Why does this matter?
- How do I fix it?
- Is publish blocked?
- What happens if ignored?

Never simply report missing fields. Explain why health, mana, size, creature classification, species, body profile, keywords, and related data matter to runtime and publishing.

## Invalid Input and Recovery Standards

Avoid generic `Invalid input`. Rejection messages must include:

- The exact input that was rejected.
- What the Builder expected.
- How to recover.
- A safe command to redisplay values or leave the prompt.

Example: `"dragonman" is not a known value for Creature Classification. Expected one of: ... Try list to view supported values, or back to cancel.`

## World Command Recovery

If a builder types a world command such as `medit`, `mlist`, `redit`, `goto`, `look`, or `inventory` while inside an editor, explain that they are currently editing an object and list safe editor commands: `back`, `save`, `cancel`, `quit`, and `preview`. Do not treat these as meaningless invalid input.

## Menu Layout Standards

- Use readable headers, subheaders, spacing, and aligned rows.
- Put persistent context first, then editable fields, then commands.
- Keep field rows scannable: number, label, current value, and a one-line description.
- Use consistent footer vocabulary across Builder editors.
- Prefer professional IDE language: Preview, Validate, Save, Undo, Redo, Return, Close.

## Help Standards

Every Builder menu and field prompt must accept `?`, `help`, `explain`, `details`, `advanced`, `commands`, `menu`, `options`, `show`, `list`, `values`, `examples`, `default`, and `defaults` when contextually meaningful. These commands must never produce generic invalid-input responses.

Searchable help should support topics such as `help dragon`, `help health`, `help faction`, `help loot`, and `help flags`.

## Future Builder Requirements

All future Builder editors must adopt the same contextual help, educational validation, safe cancellation, status bar, footer commands, searchable help, inspector mode, save clarity, and undo/redo change summaries before being considered feature complete.

## Phase 16B visible-by-default MEDIT guidance

MEDIT identity screens must explain field purpose, current value, required/optional status, runtime effect, publish effect, and safe commands before the Builder types `help`, `?`, `inspect`, `examples`, `list`, or `values`. Hidden help may expand the explanation, but the ordinary menu must be sufficient for first-time use.

Finite Identity fields must use numbered pickers rather than blind free text. Pickers must show display names, short explanations, current selection, recommendations when available, examples from authored world data where inexpensive, and clear/back commands when applicable.

Booleans must render as human-readable Yes/No with consequences. `Enabled: Yes` means the mobile may participate in normal publish, activation, and spawn workflows; `Enabled: No` retains the draft while normal runtime use is blocked or skipped by lifecycle checks.

MEDIT uses `NPC Role` for the existing `entity_type` field: a gameplay role/function used by Builder search, recommendations, AI defaults, validation hints, and previews. Creature taxonomy is a separate `classification` field; physical scale is a separate `size` field; biological/lore identity is `species`.

Species is currently a named reference on the mobile draft, not an automatically-created registry record. Species pickers should show common built-ins, values already used by other mobiles, search, custom named entry, clear, and back.

Wrong-context commands inside an active editor must be recognized and explained. Commands such as `medit`, `mlist`, and `look` must not produce only generic invalid input; the response must identify the active editor context and safe commands.

Saving a Builder editor must explicitly confirm that the mobile draft was saved, include the mobile name, draft revision, dirty state, validation summary, publish readiness, current editor context, and a Builder audit/log line. Character autosave logs are not sufficient evidence of Builder draft persistence.

Future editors must follow production-path integration testing: verify ordinary browser/API output, such as `/api/mud/input`, not only helper methods, and prove visible options are displayed before asking for input.

## Interactive OLC visual presentation

Smart MUD's interactive OLC presentation intentionally follows a compact TBA/CircleMUD-style terminal workflow, based specifically on Anthony's customized Adventurer's Lair Builder. This is a visual and interaction inheritance only: Smart MUD still uses its modern draft/publish Builder architecture, validation, locking, and canonical data model rather than the old TBA datastore or OLC internals.

Builder screens should prefer dense record-oriented menus, direct numbered or lettered editing, inline descriptions where they help the builder act quickly, ANSI semantic colors, compact multi-column flag editors, dedicated subsystem editors, minimal permanent help, and one canonical layout shared by web and telnet. Builder UX must not be converted into a modern dashboard, card layout, web form, wizard, or inspector panel for these terminal-first OLC flows.
