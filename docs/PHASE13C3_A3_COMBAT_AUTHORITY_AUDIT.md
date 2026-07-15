# Phase 13C3-A3 Combat Authority Audit

This audit records the current Smart MUD combat paths and the Phase 13C3-A3 migration target. Adventurer's Lair behavior was used only as a conceptual reference for conventional MUD hit/miss, mitigation, critical, save, defeat, and messaging flow; no C implementation, macros, structs, tables, formulas, or file formats were copied.

## Authoritative Runtime Pipeline

Final authority is: command/controller/ability request -> `CombatResolutionContext` -> `CombatResolutionService` -> `CombatStatService.get_combat_snapshot()` for attacker and defender -> world-authored formula stages -> canonical resource mutation helpers -> structured `CombatResolutionResult`.

Armor is applied before typed resistance. Armor is flat reduction after armor penetration. Resistance is a percentage reduction capped to safe runtime bounds. Damage is clamped at zero unless `true` damage bypasses mitigation. Core parry/block hooks are represented by events and diagnostics but are inactive until authored equipment/body requirements and formulas exist.

## Combat Paths

| Path | File / class / function | Current inputs | Prior formula/source | Bypassed CombatStatService? | Migration plan | Final authoritative service |
|---|---|---|---|---|---|---|
| Basic attack command/runtime | `engine.combat.CombatEngine.resolve_attack` | attacker Actor, defender Actor, room/time | legacy actor derived stats: `accuracy`, `defense_rating`, `attack_power`, direct equipment armor/resistance | Yes when no combat stat service was provided | Delegates to `CombatResolutionService` when a `CombatStatService` is injected; legacy path remains only as compatibility fallback | `CombatResolutionService.resolve` + `CombatStatService` |
| Attack profile selection | `engine.combat.CombatEngine.attack_profile` | Actor equipment/natural weapon profile | direct equipment/natural profile read | Partial | Kept only as profile selector; damage numbers are read from CombatStatSnapshot weapon/unarmed profiles in canonical resolution | `CombatStatService.get_damage_profile` and snapshot unarmed profile |
| Damage application | `engine.combat.apply_damage` | Actor resources, amount | direct health subtraction with clamp | Yes | Retained as canonical low-level resource helper called only by resolution/resource services | `CombatResolutionService` -> `apply_damage` |
| Healing application | `engine.combat.apply_healing` | Actor resources, amount | direct health addition with max clamp | Yes | Retained as canonical low-level resource helper; healing attack kind uses same result pipeline | `CombatResolutionService` -> `apply_healing` |
| NPC AI basic attack | `engine.combat_behavior.CombatBehaviorService.execute_action` | selected action candidate | `self.combat.resolve_attack(a,t)` | Previously inherited legacy CombatEngine behavior | Because `CombatEngine.resolve_attack` now delegates when configured, AI controllers request actions and cannot directly mutate health | `CombatResolutionService` through `CombatEngine` |
| Ability damage | `engine.abilities.AbilityExecutionService._apply_damage_component` | ability component base amount/damage type | temporary natural weapon then `CombatEngine.resolve_attack` | Partially | Still enters through `CombatEngine.resolve_attack`; the canonical delegate consumes snapshots and context rather than ability-specific damage math | `CombatResolutionService` |
| Ability healing | `engine.abilities.AbilityExecutionService.apply_healing` | source/target/amount | direct `actor_apply_healing` | Yes | Low-level clamp is safe; future ability healing can construct healing `CombatResolutionContext`. Current audit flags this as remaining direct resource helper use, not an independent formula authority | Canonical resource helper; target `CombatResolutionService` healing kind |
| Ability costs/cooldowns | `engine.abilities.AbilityExecutionService._pay_costs`, `_start_cooldown` | Actor resources, ability data | `modify_resource` and cooldown rows | No combat stat formula | Stays outside damage authority; resource costs do not calculate combat outcome | AbilityExecutionService + resource helper |
| Resource maximum sync | `engine.character_stats.CombatStatService.synchronize_resources` | character current resources, calculated maxima | derived stat formulas | No | Already canonical; combat snapshots clamp current to max and persist where possible | `CombatStatService` |
| Regeneration/resource display | display/runtime services | Character fields | mixed display fields | Partial | No combat formula work in display; CharacterDisplaySnapshot consumes prepared runtime fields | `CharacterDisplaySnapshotService` consuming snapshots |
| Death/defeat | `engine.combat.CombatEngine.resolve_attack` and lifecycle manager | defender health <= 0 | direct state set and optional lifecycle handoff | Partial | Canonical result marks `defender_defeated`; CombatEngine compatibility sets dead state once | `CombatResolutionService` + lifecycle manager integration |
| Builder diagnostics | `combatbreakdown` target/last/formula | last result/formula id | not complete before this phase | N/A | Structured diagnostics in `CombatResolutionResult.diagnostics` contain source versions, inputs, rolls, mitigation, and final result for command display | `CombatResolutionResult` diagnostics |

## Duplicate Authorities Identified and Removed or Constrained

- Hardcoded legacy hit formula (`50 + acc - defense`) remains only in the non-injected compatibility branch. Injected runtime combat uses `attack_hit_resolution` from world formula content.
- Hardcoded legacy damage (`attack.base_damage + attack_power`) remains only in the compatibility branch. Canonical resolution uses snapshot weapon/unarmed profile, attack power, damage bonus, critical, armor, and resistance.
- Direct equipment armor reads are no longer used by canonical resolution; armor comes from defender CombatStatSnapshot.
- Direct resistance reads are no longer used by canonical resolution; typed resistance comes from defender CombatStatSnapshot.
- AI/controller code does not subtract health; it calls `CombatEngine.resolve_attack`.
- Ability damage does not own a separate damage application formula; it routes through `CombatEngine.resolve_attack`.
- FormulaEngine calls for combat stages are centralized in `CombatResolutionService._formula`; stat formulas remain centralized in `CombatStatService`.
- `Actor.derived_statistics_cache` is not used by canonical injected combat snapshots.

## Stable Snapshot Contract for Phase 13C3-B SCORE

`CombatStatSnapshot` exposes identity key, attributes, resources, offense, defense, saves, resistances, criticals, weapon profile, unarmed profile, speed, carrying, context, and source version. `CharacterDisplaySnapshotService` must format only already-prepared values and must not perform formula or modifier resolution.

## Manual Windows Acceptance (Not Run)

Manual acceptance was not run in this Linux CI/container session. Suggested Windows steps:

1. Start backend with the project launcher.
2. Log in and enter a test character.
3. Run `attributes`, `combatstats`, `equipment`, and `affects`.
4. Spawn or select a test target with the actual local builder/admin fixture commands.
5. Run `attack <target>` unarmed and record hit/damage.
6. Equip a weapon and run `attack <target>` again; verify weapon profile and damage changed.
7. Equip armor on defender and confirm mitigation changes.
8. Apply an accuracy/evasion/resistance affect and confirm `combatstats` and attack outcomes change.
9. Run `combatbreakdown last` to inspect source versions, formula IDs, rolls, mitigation, and final amount.
10. Remove equipment/effect and confirm reversion.
11. Restart and confirm persistence.
12. Run `set camp`, `set camp`, `build campfire`, and `recall` to verify noncombat regressions.

## Phase 13C3-A3E stale resource-state audit

Generic `MudCharacter` persistence now treats identity, location, progression, builder/editor state, inventory/equipment compatibility data, and other non-resource JSON as its ownership boundary.  Canonical current and maximum combat resources are owned by `RuntimeResourceService` through `actor_resource_versions` plus its mutation request ledger.

Audited reload/save paths and stale-write exposure:

| Path | Reload/save behavior | Stale resource risk | Phase 13C3-A3E control |
| --- | --- | --- | --- |
| `MudRuntime.enter_world` | Loads `MudCharacter`, ensures starter progression, registers a live Actor, then saves. | A pre-combat JSON blob could restore hp/mana/stamina during login. | The loaded character is hydrated from `RuntimeResourceService.hydrate_character()` before Actor registration or save. |
| `MudRuntime.handle_input` | Reloads the command-facing character for every command and saves at command completion. | A normal noncombat command after combat could save old hp/mana/stamina. | The command-facing object is hydrated before dispatch, and `MudStateStore.save_character()` overlays canonical resource rows before writing JSON/stats. |
| `MudRuntime.play_view` | Reloads character for room/prompt rendering. | Prompt/resource display could render stale values. | The character projection is hydrated before rendering. |
| Command completion saves | All ordinary command completion flows call `save_character`. | Any handler retaining an older object could persist stale resources. | `save_character` is now guarded at the persistence boundary and cannot blindly write stale current resources when canonical rows exist. |
| Movement | Movement mutates room/location and then uses command completion save. | Location save could carry stale resource fields. | Resource overlay runs inside the generic save. |
| Inventory/equipment commands | Item ownership/equipment state can trigger command completion save. | Equipment changes could carry stale hp/mana/stamina from the character JSON. | Resource overlay runs inside the generic save; equipment remains generic/runtime item ownership, not resource ownership. |
| Ability commands | Ability execution may mutate resources and then command completion saves. | Ability costs/damage/healing could be overwritten by the older command object. | Resource mutations route through `RuntimeResourceService`; final generic save hydrates from canonical rows. |
| Combat rounds | Combat runtime persists actor state and may reload character records. | Combat and command paths could race over health. | Resource mutation versions are the resource authority; stale expected versions are denied with `stale_resource_version`. |
| Controller actions / NPC actions | Controllers create combat work while player command objects may still exist. | Direct controller payloads with final state could overwrite health. | Controllers must submit canonical requests; resource writes are protected by `actor_resource_versions`. |
| Logout/session refresh/world reload | These paths reload characters and refresh runtime projections. | Reloaded JSON could contain older resource values. | Loading and saving now overlay canonical rows wherever the runtime persistence boundary is used. |
| Persistence helpers | `MudStateStore.load_character` and `save_character` are shared by many systems. | They were the largest stale-write chokepoint. | Both now consult `actor_resource_versions`; generic character persistence does not own current resources after canonical rows exist. |

Optimistic write rule: a resource mutation may include an expected version.  If the caller's expected version is older than the current `actor_resource_versions.version`, the mutation returns a structured denial with reason `stale_resource_version`, reloads the persisted current value into the Actor projection, and does not overwrite the newer value.
