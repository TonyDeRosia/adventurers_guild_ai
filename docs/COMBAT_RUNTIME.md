# Combat Runtime

`CombatRuntimeService` owns live encounters, participants, rounds, queued actions, room legality, targeting, and combat flow. The live server wires combat ticks from `MudRuntime.tick()` into `combat_runtime.process_due_rounds()`, so automatic rounds continue without the player re-entering `attack` each pulse.

## Canonical resolution order

1. Build typed `CombatResolutionContext` from `CombatActionRequest`.
2. Load resident attacker and defender actors.
3. Build `CombatStatService` snapshots.
4. Resolve hit projection: base 30 + attacker level + accuracy + hit bonus + strength + intelligence + wisdom - defender level - evasion + posture + range + concealment, clamped 5-95 unless automatic hit applies.
5. Resolve saving throw if declared.
6. Roll weapon/natural/unarmed damage from min/max profile with deterministic seed/action identity.
7. Apply `physical_damage_resolution` or spell/healing formula.
8. Apply armor scaling when `armor_applies` and damage is not true.
9. Apply typed resistance when `resistance_applies` and damage is not true.
10. Apply critical multiplier when allowed.
11. Apply partial-save remaining percent.
12. Mutate health/healing through `RuntimeResourceService`.
13. Hand zero health to lifecycle exactly once.
14. Persist round history, enqueue messages, update next action/round times, and end combat when no valid opponents remain.

## Windows manual acceptance checklist

1. In PowerShell, `cd "C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2"`.
2. Start Smart MUD with the project's normal command, for example `python -m engine.mud_runtime` if that is the configured entrypoint.
3. Log in/enter existing Kraevok (`char_shattered_realms_kraevok`); do not recreate the character.
4. Run `score` and record Armor, Evasion, Spell Saves, Hitroll, Damroll, Accuracy, critical fields, and unarmed damage.
5. Locate or spawn a safe test NPC using existing builder tools.
6. Use authorized combat diagnostics/trace output if available; otherwise inspect combat round history.
7. Attack unarmed and record hit chance trace and rolled damage.
8. Equip a weapon and confirm actual rolled damage changes.
9. Equip armor on the target and confirm physical mitigation changes.
10. Add Evasion to the target and confirm hit chance decreases.
11. Add Hitroll to Kraevok and confirm hit chance increases.
12. Add Damroll and confirm damage changes once.
13. Test melee criticals, spell saves, spell criticals, and healing criticals through existing ability definitions.
14. Kill the target and confirm combat ends, corpse creation/rewards/credit occur once.
15. Restart Smart MUD and confirm persistent results remain correct.

Windows testing was not executed by this agent.
