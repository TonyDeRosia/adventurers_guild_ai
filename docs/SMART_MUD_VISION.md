# Smart MUD Vision

Smart MUD is a reusable multiplayer MUD engine. It provides systems: startup, command processing, persistence, rendering, plugin discovery, hooks, validation, and package loading. Smart MUD is not a fantasy game, a campaign engine, an image-generation runtime, or a container for hardcoded lore.

## Engine and worlds

The engine is independent from content. All races, classes, rooms, NPCs, items, quests, spells, abilities, factions, dialogue, colors, lore, and intelligence files live in installable world packages under `worlds/`. A world package may describe fantasy, science fiction, modern Earth, cyberpunk, zombie survival, pirates, western, post-apocalyptic, or any other genre. The engine never branches on genre.

## Traditional MUD mechanics

Smart MUD preserves command-first play, rooms, exits, characters, inventories, prompts, scrollback, builders, and deterministic state transitions. AI may enrich presentation and assistance, but core game state must remain inspectable, testable, and deterministic.

## Determinism and AI

Rules and persistence are authoritative. AI is an extension layer and context consumer, not the source of truth for character state or world integrity. Generated text must not mutate installed packages directly.

## Builder philosophy

Builder data belongs to each world package in `builder/audit`, `builder/history`, `builder/snapshots`, `builder/exports`, `builder/imports`, and `builder/templates`. Future OLC tools should save auditable changes and support granular reloads of a room, NPC, area, quest, or item without rebooting the server.

## Multiplayer philosophy

The runtime treats players as concurrent sessions over one selected world package. SQLite stores live state, command history, scrollback, room runtime state, NPC runtime state, relationships, quests, audit logs, and deaths.

## Plugin philosophy

Plugins extend systems without modifying engine code. They may register commands, database tables, builder editors, runtime hooks, scheduled events, AI context providers, and render extensions. Worlds declare required and optional plugins in their manifests.

## Persistence philosophy

Installed packages are immutable source material at runtime. The engine loads a package, creates runtime objects, and persists live mutations to SQLite. Package updates should not corrupt live state.

## Renderer and commands

Renderers display state using semantic roles rather than world-specific assumptions. Commands operate through engine systems and hooks, with content resolved from the loaded package and live SQLite state.
