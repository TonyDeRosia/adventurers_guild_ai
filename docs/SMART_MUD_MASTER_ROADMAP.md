# Smart MUD Master Roadmap

## Phase 1: Runtime foundation
- Goal: Establish one Smart MUD startup lifecycle, registry, plugin scan, SQLite runtime, and project identity.
- Completed work: Smart MUD web/terminal startup exists; SQLite runtime schema initializes; canonical world registry selected; Builder workspace is auto-created; docs identify ownership.
- Remaining work: Continue retiring legacy campaign UI references outside normal startup.
- Dependencies: None.
- Acceptance criteria: Startup reaches Ready using Smart MUD systems only and loads `shattered_realms`.
- Suggested version target: `0.1.0`.

## Phase 2: SQLite persistent world foundation
- Goal: Persist authoritative mutable world/runtime state in SQLite.
- Completed work: Character, command history, scrollback, room/NPC runtime, quests, death log, and builder audit tables initialize.
- Remaining work: Normalize migrations, add world state mutation APIs, backup/export flows.
- Dependencies: Phase 1.
- Acceptance criteria: Runtime state survives restart without mutating package source files.
- Suggested version target: `0.2.0`.

## Phase 3: Account and character system
- Goal: Add accounts, authentication boundaries, character slots, and character lifecycle.
- Completed work: Basic character creation exists without accounts.
- Remaining work: Accounts, permissions, character selection, deletion, recovery, admin controls.
- Dependencies: Phase 2.
- Acceptance criteria: Multiple accounts can own isolated character sets safely.
- Suggested version target: `0.3.0`.

## Phase 4: Builder framework
- Goal: Provide safe Builder infrastructure and audited editing workflows.
- Completed work: Builder workspace folders and audit table exist.
- Remaining work: Builder permissions, editors, validation previews, import/export, snapshots.
- Dependencies: Phases 2-3.
- Acceptance criteria: Builders can edit draft content without corrupting runtime packages.
- Suggested version target: `0.4.0`.

## Phase 5: tbaMUD command and display parity
- Goal: Match expected MUD command surfaces and display conventions.
- Completed work: Initial command catalog and room/score rendering exist.
- Remaining work: Complete command parity audit, prompts, help, socials, admin displays.
- Dependencies: Phases 1-3.
- Acceptance criteria: Core navigation, communication, inventory, stats, help, and admin surfaces behave predictably.
- Suggested version target: `0.5.0`.

## Phase 6: Deterministic gameplay systems
- Goal: Implement deterministic combat, skills, spells, quests, shops, trainers, factions, and economy.
- Completed work: Package directories and some data structures exist.
- Remaining work: Actual gameplay mechanics and test coverage.
- Dependencies: Phases 2, 3, and 5.
- Acceptance criteria: Gameplay can run without AI and produces reproducible state transitions.
- Suggested version target: `0.6.0`.

## Phase 7: AI layer
- Goal: Add AI as an extension layer over deterministic state, not as source of truth.
- Completed work: Plugin registration has AI context provider slots.
- Remaining work: Context policies, safety boundaries, NPC narration hooks, deterministic fallbacks.
- Dependencies: Phase 6.
- Acceptance criteria: Disabling AI leaves gameplay fully playable.
- Suggested version target: `0.7.0`.

## Phase 8: Shattered Realms reference world
- Goal: Ship a complete reference world package.
- Completed work: `worlds/shattered_realms` package exists and loads.
- Remaining work: Expand content depth after deterministic systems are ready.
- Dependencies: Phases 5-7.
- Acceptance criteria: Reference world demonstrates major runtime features.
- Suggested version target: `0.8.0`.

## Phase 9: Multiplayer server maturity
- Goal: Harden concurrent sessions, networking, permissions, and operational behavior.
- Completed work: Session model exists in-process.
- Remaining work: Multi-user concurrency, locks, websockets/telnet strategy, observability, moderation.
- Dependencies: Phases 2-6.
- Acceptance criteria: Multiple players can connect and interact safely.
- Suggested version target: `0.9.0`.

## Phase 10: Packaging, releases, and polish
- Goal: Produce reliable releases with docs, installers, migration tools, and UX polish.
- Completed work: Launcher and packaging artifacts exist from earlier app history.
- Remaining work: Rebrand packaging, release automation, migration docs, final UI polish.
- Dependencies: Phases 1-9.
- Acceptance criteria: Users can install, run, update, and diagnose Smart MUD confidently.
- Suggested version target: `1.0.0`.
