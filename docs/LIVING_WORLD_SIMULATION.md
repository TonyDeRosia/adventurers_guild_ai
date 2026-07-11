# LIVING WORLD SIMULATION

Phase 5B adds deterministic living-entity infrastructure owned by SQLite and runtime APIs, not AI providers.

- Mutable world time, simulation state, needs, goals, relationships, and memories are persisted in SQLite.
- World JSON and Builder drafts provide authoring defaults and seeds only.
- Runtime APIs expose deterministic state for future AI plugins without letting AI become authoritative.
- Player-agency boundaries forbid invented player thoughts, feelings, private inventory knowledge, remote conversations, Builder metadata, and future events.

Manual acceptance commands include: `worldtime status`, `simulation status`, `eprofile harl`, `eschedule harl`, `eneeds harl`, `egoals harl`, `ememories harl`, and `econtext harl`.


## Phase 6D deterministic combat behavior

Phase 6D introduces canonical NPC combat behavior profiles, hostility evaluation, threat tables, deterministic action candidates, assist/protect/flee/surrender/call-for-help/pursuit hooks, pet modes, and Builder/Admin diagnostics. The system is a validator and selector only: AbilityExecutionService continues to own ability validation, costs, cooldowns, casts, healing, damage components, and effects; CombatEngine continues to own basic attack resolution and lifecycle handoff. Generative AI is not required for combat, and future AI suggestions cannot bypass deterministic validation.


## Phase 8A Quest Integration

Phase 8A introduces `engine.quests.QuestService`, `QuestEventRouter`, `ConversationService`, and `WorldStateService` as the canonical quest and authored narrative-state foundation. Quests are Builder/world-package data, consume canonical EventBus-style events idempotently, branch deterministically, persist runtime state in SQLite, and hand rewards to RewardService instead of mutating items, XP, currencies, abilities, progression, Actor stats, or world records directly. Future AI may propose text or actions, but QuestService validates all outcomes; unrestricted scripts remain forbidden.

## Phase 8B Organization Integration

Phase 8B adds the canonical `OrganizationService` for parties, guilds, clans, NPC organizations, roles, permissions, invitations, applications, shared quest context, group combat attribution, and organization audit history. These systems provide context only and call existing canonical services for combat, quests, rewards, economy, progression, crafting, and world state.


## Phase 11B Perception Integration

Phase 11B adds `engine.perception.PerceptionService` as the single sensory boundary for stealth, concealment, search, tracking, scent, sound, trails, and observer knowledge. It queries canonical services, especially `EnvironmentService`, and stores restart-safe sensory state in SQLite.

## Phase 11C2 Gathering Integration

Gathered outputs are canonical item/reward payloads; Crafting, Economy, Profession/Progression, Environment, Perception, Quest, Achievement, Property, Organization/Faction, Living World, Builder, and score surfaces integrate by consuming GatheringService data or EventBus events. GatheringService does not price resources, mutate quest state directly, create a shadow inventory, destroy terrain, implement farming, run autonomous workers, or bypass canonical services.
