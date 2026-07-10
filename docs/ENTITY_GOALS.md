# ENTITY GOALS

Phase 5B adds deterministic living-entity infrastructure owned by SQLite and runtime APIs, not AI providers.

- Mutable world time, simulation state, needs, goals, relationships, and memories are persisted in SQLite.
- World JSON and Builder drafts provide authoring defaults and seeds only.
- Runtime APIs expose deterministic state for future AI plugins without letting AI become authoritative.
- Player-agency boundaries forbid invented player thoughts, feelings, private inventory knowledge, remote conversations, Builder metadata, and future events.

Manual acceptance commands include: `worldtime status`, `simulation status`, `eprofile harl`, `eschedule harl`, `eneeds harl`, `egoals harl`, `ememories harl`, and `econtext harl`.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.
