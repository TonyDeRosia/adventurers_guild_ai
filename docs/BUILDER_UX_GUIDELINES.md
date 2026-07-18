# Builder UX Guidelines

Smart MUD Builder is a draft-first, self-documenting world-building IDE. Editors must teach first-time builders while preserving fast command-driven workflows for experienced builders.

## Philosophy

- The Builder itself is the documentation.
- Menus explain current state, safe next actions, and available commands.
- Field editors explain meaning, runtime usage, valid values, defaults, examples, warnings, and related commands.
- Validation is educational: every issue explains what happened, why it matters, how to fix it, whether it blocks publish, and what happens if ignored.
- Draft/save/publish remains the required workflow. UX improvements must not replace BuilderService or create parallel builders.

## Help Standards

Every Builder menu and field prompt must accept `?`, `help`, `explain`, `commands`, `menu`, `options`, `show`, `list`, `values`, `examples`, `default`, and `defaults` when contextually meaningful. These commands must never produce generic invalid-input responses.

Searchable help should support topics such as `help dragon`, `help health`, `help faction`, `help loot`, and `help flags`.

## Field Standards

Each editable field should include:

- Description.
- Runtime usage.
- Current value.
- Legal values for enums/flags/references.
- Recommended/default values when known.
- Examples.
- Related fields.
- Warnings and common mistakes.
- Safe commands including help, list, examples, default, clear, and back.

## Validation Standards

Validation output uses consistent severities: `INFO`, `WARNING`, `ERROR`, and `BLOCKING`.

Each validation entry answers:

- What happened?
- Why does this matter?
- How do I fix it?
- Is publish blocked?
- What happens if ignored?

## Prompt and Menu Standards

- Include a persistent status section showing current editor, current field/mode, modification state, validation count, publish readiness, and unsaved-change state.
- Include contextual footers with common commands.
- Avoid `Invalid input`; report the exact input, why it was rejected, accepted alternatives, and how to discover values.
- `back` and `cancel` must be safe and non-destructive.
- Save output must clearly say whether the editor remains open.

## Consistency Rules

- Use title-case section names and consistent command casing.
- Put state before choices, choices before footer commands.
- Use one vocabulary across MEDIT, OEDIT, REDIT, ZEDIT, QUESTEDIT, and future editors.
- Prefer natural synonyms where they do not conflict with data entry.

## Future Builder Requirements

All future Builder editors must adopt the same contextual help, educational validation, safe cancellation, status bar, footer commands, searchable help, save clarity, and undo/redo change summaries before being considered feature complete.
