# COMBAT FLEE AND SURRENDER

Phase 6D adds a deterministic, Builder-editable combat behavior layer for non-player Actors. The authoritative pipeline is Living World simulation, combat awareness, hostility evaluation, threat evaluation, behavior profile, tactical state, action candidates, deterministic selection, AbilityExecutionService or CombatEngine execution, and lifecycle handoff.

The behavior layer never calculates damage, directly changes Health, applies effects, creates corpses, respawns Actors, bypasses cooldowns/resources/targeting, bypasses formulas, or invents abilities. Future AI may propose actions, but this deterministic validator remains the fallback and authority.

Implemented foundations include combat behavior profiles, hostility traces, threat ownership by stable Actor IDs, action candidates with invalid reasons, basic attack fallback, assist/protect/flee/surrender/call-for-help/pursuit policy fields, pet modes, Builder diagnostics commands, and conservative Starter Guildlands pilot profiles.

Manual acceptance starts with: `builder on`, `behaviorlist`, `behaviorstat civilian_safe`, `behaviorstat town_guard_defender`, `actorbehavior <actor>`, `threatlist <actor>`, `combatcandidates <actor>`, and `combatdecision <actor>`.
