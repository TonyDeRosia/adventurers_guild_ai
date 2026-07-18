# Current Class/Ability Repair Audit

Phase 18E traced the production paths used by Smart MUD runtime class and ability behavior.

## Findings

- Character creation validates `race_id`/`class_id` against the loaded world package and persists them in `MudCharacter.actor_data` before calling starter progression repair (`engine/mud_runtime.py`, `MudRuntime.create_character`).
- SQLite character persistence stores the dataclass JSON in `characters.data`; canonical progression identity is stored separately in `actor_progression_state.primary_class_id` (`engine/mud_runtime.py`, `MUDStateStore.save_character`; `engine/progression.py`, `ProgressionService.initialize_actor_progression`).
- Runtime projection hydrates `primary_class_id` and `class_name` from `ProgressionService.progression_identity_snapshot` in `MudRuntime._ensure_starter_progression`.
- SCORE renders class display text from the display snapshot (`engine/mud_displays.py`, `build_score_document`). Extra `_score_row()` calls caused blank rows before `Name` and before `Alignment`.
- Ability definitions are loaded by `AbilityRegistry` from world `abilities`, `skills`, `spells`, and related collections (`engine/abilities.py`).
- Known abilities are projected by `AbilityExecutionService.get_actor_abilities`, which merges `actor_ability_grants`, `actor_ability_progression`, and live actor plugin grants.
- `skills`, `spells`, and `abilities` already call `AbilityDisplaySnapshotService` when available; fallback display paths still use `_ability_rows` and therefore must stay secondary only (`engine/mud_commands.py`).
- `cast`, direct skill commands, and normal ability use route through `MudCommandEngine._cmd_use_ability` and `AbilityRuntimeGateway`.
- Practice uses `ProgressionService.list_known_practice_abilities` and `resolve_practice_ability`, so it depends on the same `actor_ability_progression` rows but had a separate resolver.
- `spellup` used `AbilityExecutionService.get_actor_abilities` and `execute_instant_ability`, but class contamination in known ability rows could make its candidate set wrong.
- `aff`/`saff` display persisted runtime effects from `actor_effect_instances` and live actor effect containers through existing score/display services.
- Builder/NPC references validate ability IDs through world package registries and do not imply player progression.

## Root causes

1. `MudRuntime._ensure_starter_progression` granted a universal starter list to every non-Scholar character. That list included Warrior skills, Mage spells, Cleric spells, travel spells, and utility spells, which made Warriors know and display caster abilities.
2. Those universal starter rows used `source_type=starter_character`; without reconciliation they persisted across reloads and polluted `skills`, `spells`, `cast`, `practice`, and `spellup`.
3. Ability execution resolution only searched learned abilities. A known definition that was not learned and a truly unknown ability both collapsed to `Unknown ability.`
4. Direct commands (`kick`, `bandage`, `bash`) delegated to the ability command but inherited the same resolver failure modes.
5. SCORE had explicit blank row calls immediately before the identity and alignment rows.

## Repair strategy

- Preserve `actor_progression_state.primary_class_id` as the canonical persisted class ID.
- Hydrate runtime `MudCharacter.primary_class_id`/`class_name` from `ProgressionService.progression_identity_snapshot`.
- Replace the universal starter grant with class-specific starter/progression reconciliation.
- Retire only legacy `starter_character` ability rows that are not in the current class progression set; preserve unknown, awarded, admin, and trained rows.
- Extend `AbilityRuntimeGateway` so it resolves definitions independently of known abilities and reports `unknown_ability`, `not_known`, `wrong_category`, or `handler_not_implemented` honestly.
- Keep `spellup`, `cast`, direct commands, `skills`, and `spells` on `AbilityExecutionService.get_actor_abilities` / `AbilityRuntimeGateway`.
