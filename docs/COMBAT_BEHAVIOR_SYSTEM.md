# COMBAT BEHAVIOR SYSTEM

Phase 6D adds a deterministic, Builder-editable combat behavior layer for non-player Actors. The authoritative pipeline is Living World simulation, combat awareness, hostility evaluation, threat evaluation, behavior profile, tactical state, action candidates, deterministic selection, AbilityExecutionService or CombatEngine execution, and lifecycle handoff.

The behavior layer never calculates damage, directly changes Health, applies effects, creates corpses, respawns Actors, bypasses cooldowns/resources/targeting, bypasses formulas, or invents abilities. Future AI may propose actions, but this deterministic validator remains the fallback and authority.

Implemented foundations include combat behavior profiles, hostility traces, threat ownership by stable Actor IDs, action candidates with invalid reasons, basic attack fallback, assist/protect/flee/surrender/call-for-help/pursuit policy fields, pet modes, Builder diagnostics commands, and conservative Starter Guildlands pilot profiles.

Manual acceptance starts with: `builder on`, `behaviorlist`, `behaviorstat civilian_safe`, `behaviorstat town_guard_defender`, `actorbehavior <actor>`, `threatlist <actor>`, `combatcandidates <actor>`, and `combatdecision <actor>`.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7A reward boundary

Rewards are issued through `engine.rewards.RewardService` and persisted as reward packets. This document's subsystem remains the authority for its own domain; reward delivery calls canonical APIs rather than editing subsystem tables directly.

## Phase 8B Organization Integration

Phase 8B adds the canonical `OrganizationService` for parties, guilds, clans, NPC organizations, roles, permissions, invitations, applications, shared quest context, group combat attribution, and organization audit history. These systems provide context only and call existing canonical services for combat, quests, rewards, economy, progression, crafting, and world state.


## Phase 8C faction integration note

Phase 8C adds `FactionService` as the canonical owner of faction reputation, standing, diplomacy interpretation, access decisions, faction reward eligibility, and reputation history. Factions link to `OrganizationService` identities; organization membership, roles, permissions, group combat attribution, quests, rewards, economy, combat, and world state remain owned by their existing canonical services. Subsystems must call `FactionService` rather than mutating faction reputation directly. Faction warfare, laws, territory conquest, elections, autonomous politics, and PvP faction rules remain outside this foundation.
