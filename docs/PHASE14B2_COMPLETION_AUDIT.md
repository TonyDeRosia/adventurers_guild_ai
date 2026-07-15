# Phase 14B2 Completion Audit

This audit is based on the checked-out repository state at implementation time and records what is actually present in code, not what earlier roadmap text claimed.

## Status Key

- **Implemented and runtime-used**: invoked by normal runtime paths.
- **Implemented but isolated**: callable helper or primitive that is not fully wired into all lifecycle events.
- **Model only**: dataclass/schema exists without complete runtime ownership.
- **Compatibility path only**: legacy support retained but not the canonical authoring path.
- **Placeholder**: visible command/registry entry exists without full behavior.
- **Missing**: not implemented in this repository.
- **Incorrectly claimed complete**: documentation or tests implied completion beyond implementation.

## Audited Components

| Component | Files / Methods | Classification | Findings |
|---|---|---|---|
| AbilityDefinition | `engine/abilities.py` `AbilityDefinition`, `LegacyAbilityDefinitionAdapter.adapt` | Implemented and runtime-used | Phase 14B2 normalizes canonical operation authoring into `canonical_effects`, with deterministic load-time promotion from legacy `plugin_data.canonical_effects`. |
| AbilityEffectDefinition | `engine/abilities.py` `AbilityEffectDefinition` | Model only | Dataclass exists and is used as a schema contract; most runtime effects still pass dictionaries. |
| RuntimeEffectInstance | `engine/abilities.py` `RuntimeEffectInstance`, `AbilityExecutionService._persist_runtime_effect` | Implemented and runtime-used | Persistent actor effect rows are created and ticked; dataclass is not the sole storage object. |
| AuraDefinition | `engine/abilities.py` `AuraDefinition`, `create_aura`, `update_aura_membership`, `remove_aura_member`, `remove_aura` | Implemented but isolated | Auras create DB state and membership, but reconciliation still uses registered actors rather than authoritative room membership. |
| TransformationDefinition | `engine/abilities.py` `TransformationDefinition`, `start_transformation` | Implemented but isolated | Transformation changes actor combat profile and persists an effect; complete equipment policy and restart restoration remain incomplete. |
| SummonDefinition | `engine/abilities.py` `SummonDefinition`, `create_summons`, `dismiss_summon`, `process_summon_expirations` | Implemented but isolated | Summons are registered actors and persisted relationships, but full room membership/world controller integration is partial. |
| RoomEffectDefinition | `engine/abilities.py` `RoomEffectDefinition`, `create_room_effect`, `process_room_effect_ticks`, `remove_room_effect` | Implemented but isolated | Room effect persistence and tick claims exist; entry/exit resident cleanup is not fully movement-owned. |
| SummonProfile | `engine/abilities.py` `SummonProfile`, `save_summon_profile`, `restore_summon_profile`, `repair_summon_profile` | Implemented but isolated | Approved-field profile persistence exists; command/editor coverage is incomplete. |
| AbilityEffectOperationRegistry | `engine/abilities.py` `AbilityEffectOperationRegistry`, `AbilityEffectOperationSpec` | Implemented and runtime-used | One registry now exposes operation metadata, validates Phase 14A and executable Phase 14B operations, and no longer marks advanced operations reserved. |
| AbilityAvailabilityService | `engine/abilities.py` `AbilityAvailabilityService.resolve_actor_abilities`, `AbilityExecutionService.get_actor_abilities`, `_grants` | Implemented but isolated | Structured grants and duplicate suppression exist for DB/progression/plugin actor ability IDs; complete projection from every requested source remains partial. |
| AbilityExecutionService | `engine/abilities.py` `AbilityExecutionService` | Implemented and runtime-used | Gateway, validation, costs, cooldowns, effects, damage/healing, advanced operations and persistence are runtime-used. Normal runtime uses `combat_runtime` when injected; fallback `CombatEngine` remains for isolated use. |
| Runtime wiring | `engine/abilities.py` `_apply_damage_component`, `apply_healing`, `_pay_costs` | Implemented but isolated | Resource service and injected combat runtime are honored. Startup duplicate-authority assertions remain incomplete. |
| Command routing | `engine/command_registry.py`; runtime command handlers outside this audit scope | Placeholder / partial | Public command registry lists core ability commands, but some Phase 14B2 diagnostics are not fully implemented. |
| Persistence | `engine/abilities.py` `init_ability_schema` | Implemented and runtime-used | Ability grants, cooldowns, casts, effects, auras, summons, profiles, room effects, trigger claims, and tick claims have SQLite tables. |
| World definitions | repository content files | Implemented but isolated | Representative content exists in tests and package data, but not a complete Adventurer's Lair catalog. |
| Builder drafts/editors/publication/reload | `engine/builder_content_editor.py` plus builder command modules | Implemented but isolated | Existing content editor performs draft mutation primitives. Full Phase 14B2 advanced editor command surface and transactional publication are not complete. |
| Tests | `tests/test_phase14a_ability_foundation.py`, `tests/test_phase14b_advanced_abilities.py`, `tests/test_phase14b2_schema_registry.py` | Implemented and runtime-used for covered primitives | Tests cover schema adaptation, registry metadata, Phase 14A operations, and Phase 14B runtime primitives. Full Windows acceptance was not performed. |

## Capability Classification

| Capability | Classification | Notes |
|---|---|---|
| Typed targeting/cost/cooldown/material/effect schema | Implemented and runtime-used | Canonical top-level fields are loaded and consumed; legacy plugin storage adapts deterministically. |
| Cross-document dependency validation | Missing | No complete graph across abilities/effects/aura/stance/transformation/summon/room/item documents was found. |
| Transactional ability publication | Missing / partial | Existing builder framework is present, but full ability publication unit with failure injection is not complete. |
| Auras | Implemented but isolated | Membership reconciliation exists but is actor-registry based. |
| Stances | Implemented and runtime-used | Stance activation persists effects and enforces exclusive groups by tag removal. |
| Transformations | Implemented but isolated | Actor projection changes occur; equipment policies are partial. |
| Summons/followers | Implemented but isolated | Summon actors and relationships exist; world movement/controller integration is partial. |
| Persistent summon profiles | Implemented but isolated | Save/restore/repair methods exist; command surface incomplete. |
| Passive triggers | Placeholder / partial | Trigger claims table exists; full bounded trigger chain executor is not complete. |
| Item abilities and item operations | Implemented but isolated | Create/destroy/alter use item instance table; full canonical inventory ownership semantics are partial. |
| Room effects | Implemented but isolated | Creation/tick/removal exists; movement and resident reconciliation partial. |
| Builder editors | Missing / partial | Basic content editor exists; all requested `abilityedit` and advanced editors are not fully implemented. |
| Runtime acceptance | Incorrectly claimed complete if asserted elsewhere | Linux automated tests were run; Windows manual acceptance was not performed. |

## Phase 14B3 Runtime Matrix

This matrix records the runtime state of the checked-out repository after the Phase 14B3 service-wiring/grant-projection patch. It is intentionally conservative: broad lifecycle systems that still lack movement-owned reconciliation, restart proof, or command parity remain **incomplete**.

| System | Model only | Operation handler exists | Persistence exists | Runtime event wiring exists | Command routing exists | Gameplay verified | Restart verified | Complete / incomplete | Exact files and methods |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Ability service wiring | No | Yes | N/A | Partial | Yes | Focused | No | Incomplete | `engine/abilities.py` `AbilityExecutionService.__init__`, `assert_runtime_combat_authority`, `_apply_damage_component`, `apply_healing`; `engine/mud_runtime.py` `MudRuntime.load_world`. |
| Grant projection | No | Yes | Yes | Partial | Display only | Focused | Partial | Incomplete | `engine/abilities.py` `AbilityGrantProjection`, `project_ability_grants`, `_legacy_npc_ability_grants`, `_grants`, `get_actor_abilities`. |
| Auras | No | Yes | Yes | Partial | Via ability use | Focused primitive | No | Incomplete | `engine/abilities.py` `create_aura`, `update_aura_membership`, `remove_aura_member`, `remove_aura`. |
| Stances | No | Yes | Yes | Partial | Partial | Focused primitive | Partial | Incomplete | `engine/abilities.py` `activate_stance`, `remove_effects`; command surface in `engine/mud_commands.py`. |
| Transformations | No | Yes | Yes | Partial | Via ability use | Focused primitive | No | Incomplete | `engine/abilities.py` `start_transformation`, `process_effect_expirations`; stats read through combat profile but equipment policy is partial. |
| Summons | No | Yes | Yes | Partial | Partial | Focused primitive | No | Incomplete | `engine/abilities.py` `create_summons`, `dismiss_summon`, `process_summon_expirations`. |
| Summon profiles | No | Yes | Yes | No | Diagnostics partial | Focused primitive | Partial | Incomplete | `engine/abilities.py` `save_summon_profile`, `restore_summon_profile`, `repair_summon_profile`. |
| Passives | Partial | Partial | Trigger claims only | Partial | Listing partial | No broad proof | No | Incomplete | `engine/abilities.py` passive validation path, `trigger_claims` schema. |
| Triggers | Partial | Placeholder | Yes | No | Diagnostics partial | No | No | Incomplete | `engine/abilities.py` `trigger_claims` schema; no complete bounded trigger-chain executor. |
| Item abilities | Partial | Partial | Yes | Partial | `use` gateway partial | Focused legacy | Partial | Incomplete | `engine/abilities.py` grant projection from DB/effects, item activation through canonical ability gateway where commands call it. |
| Item creation/alteration | No | Yes | Yes | Partial | Via ability op | Focused primitive | Partial | Incomplete | `engine/abilities.py` `create_item`, `destroy_item`, `alter_item`, `_ensure_item_instance_material_columns`. |
| Room effects | No | Yes | Yes | Partial | Via ability op | Focused primitive | No | Incomplete | `engine/abilities.py` `create_room_effect`, `process_room_effect_ticks`, `remove_room_effect`. |
| Set Camp | No | Yes | Existing campsite tables | Runtime ability validation | Yes | Existing tests | Partial | Incomplete | `engine/abilities.py` `validate_ability_use`, `_apply_registered_effect`; survival service methods invoked by ability effects. |
| Build Campfire | No | Yes | Existing campfire tables | Runtime ability validation | Yes | Existing tests | Partial | Incomplete | `engine/abilities.py` `validate_ability_use`, `_apply_registered_effect`. |
| Recall | No | Yes | Character room state | Runtime ability validation | Yes | Existing tests | Partial | Incomplete | `engine/abilities.py` `validate_ability_use`, `_apply_registered_effect`. |

### Phase 14B3 audit notes

- Normal `MudRuntime.load_world` now injects the runtime-owned `CombatRuntimeService`, `CombatStatService`, state store, registries, and related canonical services into `AbilityExecutionService`, then calls `assert_runtime_combat_authority()` to fail startup if the ability service owns a duplicate normal-runtime `CombatEngine`.
- Isolated tests may still instantiate `AbilityExecutionService` without a `CombatRuntimeService`; only that mode creates the fallback `CombatEngine`.
- `project_ability_grants()` is now the named grant projection API. It records source type, source IDs, source instance IDs, proficiency, temporary/active/suppressed/visible state, source version, and de-duplicates by ability/source/source-instance. The legacy `actor.plugin_data.npc_ability_ids` path is retained only through `_legacy_npc_ability_grants()`.
- The remaining Phase 14B3 completion requirements are not all satisfied by this patch; movement-owned aura reconciliation, full room-effect resident behavior, full passive trigger chains, complete summon world-controller parity, and Windows manual acceptance remain open.
