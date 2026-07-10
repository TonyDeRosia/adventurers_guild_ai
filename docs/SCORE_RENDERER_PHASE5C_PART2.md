# Score Renderer Phase 5C Part 2

Smart MUD uses `engine/score_renderer.py` as the only permanent Actor score presentation layer.  The renderer recreates the classic Adventurer's-Lair-style character sheet as boxed, aligned, independently renderable sections while remaining presentation-only.

## Sections

`ActorScoreRenderer.order` composes identity, resources, primary attributes, derived placeholders, combat placeholders, equipment, conditions, resistances, affects, spellup, progression, currencies, relationships, simulation, Builder diagnostics, formula diagnostics, and raw Actor JSON.  Each section has a `render_<section>` function and can be called through `render_section`.

## ANSI and Semantic Color

The renderer emits Smart MUD semantic tags such as `score_label`, `score_value`, `hp`, `mp`, `stamina`, `equipment_item`, `gold`, `player`, and `system`.  Web, telnet, and plain-text transports can colorize or strip these tags, so ANSI/color enhances readability without being required.

## Builder Diagnostics

Builder/Admin-only sections are `diagnostics`, `formulas`, and `raw`.  Normal players receive a restricted message.  Diagnostics show Actor identity, metadata, validation warnings, renderer section registration, and formula placeholder registration without executing formulas.

## Actor Presentation and Extension Points

Future Builder-defined attributes, resources, currencies, resistances, effect groups, spellup groups, and derived statistics are displayed from Actor dictionaries without adding new renderer paths.  Combat, equipment bonuses, formula execution, spells, skills, and AI reasoning remain out of scope.

## Command Routing

Score-related commands route through the same renderer: `score`, `score <section>`, `score preview`, `score raw`, `score diagnostics`, `score formulas`, `worth`, `equipment`, `affects`, `saff`, `spellup`, and `resists`.
