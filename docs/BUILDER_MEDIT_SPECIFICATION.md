# Phase 15C.0 Builder MEDIT Specification

This specification is the canonical Smart MUD implementation roadmap for Mob Builder parity with Anthony's customized Adventurer's Lair Builder. Adventurer's Lair is a behavioral reference only: Smart MUD must implement equivalent authoring outcomes through Builder sessions, draft records, validation, history, audit, preview, publish, activation, and rollback. Do not port TBA C code, bitvectors, global arrays, menu code, file formats, or compatibility wrappers.

## Audit Scope and Evidence

Direct GitHub checkout of `TonyDeRosia/tbamud_adventurers_lair` was attempted for this phase, but the execution environment returned `CONNECT tunnel failed, response 403`. This document therefore records a conservative parity contract based on the requested Adventurer's Lair feature surface, established Circle/TBA Oasis MEDIT behavior, and existing Smart MUD Builder architecture. Any future local source review may add details, but must not weaken these Smart MUD architectural requirements.

Existing Smart MUD mobile Builder foundations already include session scratch records, dirty quit prompts, service-level save transactions, mobile validation, preview, testspawn/testclear, immutable publish generations, and rollback. Phase 15C work must extend that architecture rather than replacing it.

## Non-Negotiable Smart MUD Design Rules

- MEDIT edits must happen inside `BuilderEditSession` working records until explicitly saved.
- Saved edits must update Builder drafts only; live runtime content changes only through publish and activation.
- Validation must run before save and publish and must report errors, warnings, and info.
- Every mutation must produce Builder history and audit metadata.
- Runtime IDs are Smart MUD IDs; VNUMs are authoring/indexing metadata scoped by area and zone.
- Flags must be named capabilities/effects in JSON, never imported C bitvectors.
- Reference fields must resolve through canonical services and world-package collections.
- Builder previews must use the same projections that runtime spawning and combat consume.

## MEDIT Primary Workflow

### Entry, lookup, and creation

`medit <id|vnum>`, `mcreate <vnum> <name>`, `mstat <id|vnum>`, `mdelete <id|vnum>`, and future subcommands must resolve targets by Smart MUD ID first, then numeric VNUM when unambiguous in the current area or explicit search scope. Builders may search by keyword, alias, display name, VNUM range, area, zone, tag, flag, behavior profile, loot profile, or missing dependency.

Creating a mobile must require a selected or explicit area whose mob VNUM range contains the requested VNUM. The generated ID convention is `<area_id>_mob_<vnum>`, but Smart MUD may retain stable custom IDs when migration history requires it. Creation should initialize safe defaults, mark the session dirty, and keep the draft unpublished until save and publish.

### Session state, navigation, save, and cancel

A MEDIT session owns one working mobile record, a savepoint, a revision, lock metadata, current submenu path, and dirty state. Navigation accepts explicit commands rather than hardcoded menu state: `back`, `main`, `preview`, `validate`, `diff`, `save`, `discard`, `quit`, and `help`. `quit` on a dirty session must offer save, discard, or cancel. `discard` restores the savepoint. `save` validates and writes a draft transaction; it does not publish. There is no runtime mutation on cancel.

Undo should be implemented as Smart MUD history/snapshot revert, not as legacy menu memory. The minimum parity requirement is one-session discard plus post-save history inspection; future phases may add field-level undo.

### Ownership and permissions

Builders must have `builder`, `admin`, or `owner` authority and must be allowed to edit the target area or zone. Admin/owner can override normal ownership locks. Validation must reject VNUMs outside the area's mob range, duplicate VNUMs in the same area, and references to zones not owned by the selected area.

## General Information Fields

| Field | Adventurer's Lair behavior to preserve | Smart MUD field requirement | Validation |
|---|---|---|---|
| Sex | Builder chooses canonical sex/gender presentation for NPC text. | Store a normalized enum such as `neutral`, `male`, `female`, `nonbinary`, `unknown`, plus optional pronoun profile later. | Must be known value. |
| Keywords | Space-delimited nouns used by commands and lookup. | Store ordered keyword list. | Required; each token safe, lowercase display-normalizable; no empty tokens. |
| Aliases | Additional lookup aliases beyond canonical keywords. | Store ordered aliases separate from keywords. | Warn on duplicate keywords/aliases. |
| Short description | Room/combat display name. | `short_description` or `display_name`. | Required; length and punctuation checks. |
| Long description | Standing room line. | `long_description`. | Required for spawnable mobs; should end cleanly. |
| Detailed description | Examine/look-at text. | `description` rich text block. | Required; style warnings for empty/too short. |
| Position | Current/resting pose used at spawn or reset. | `initial_position`. | Must be compatible with body/lifecycle. |
| Default position | Pose to return to when idle. | `default_position`. | Cannot be more disabled than initial position unless intentional warning. |
| Attack type | Natural attack verb/damage type fallback. | Natural weapon profile or default attack profile. | Must resolve to damage taxonomy. |
| Pet price | Purchase cost for pet/shop-pet behavior. | Economy/service field or pet profile reference. | Requires pet/trainable flag or warns if orphaned. |

## Stats Menu Audit

The Stats Menu is a first-class nested editor, not a flat collection of raw numbers. It must support manual edits, recommendations, quick build, validation, and preview.

### Editable fields

- Level.
- Hit points: fixed value or dice/profile expression.
- Mana or equivalent resource pool.
- Move/stamina or equivalent resource pool.
- Armor/defense rating.
- Hitroll/accuracy bonus.
- Damroll/damage bonus.
- Damage dice for default/natural attack.
- Experience reward.
- Gold/currency carried or generated.
- Attributes: strength, dexterity, constitution, intelligence, wisdom, charisma, and any Smart MUD canonical attributes.
- Saving throws: physical, mental, magic, and any configured save taxonomy.

### Generated, editable, and derived values

| Value | Classification | Requirement |
|---|---|---|
| Level | Editable seed | Drives recommendations and quick build. |
| HP/mana/move | Editable with generated defaults | Quick build fills from level/body/archetype; builder may override. |
| Armor/hitroll/damroll | Editable with generated defaults | Preview must show final resolved combat values. |
| Damage dice | Editable generated default | Must synchronize with default natural weapon when appropriate. |
| Experience/gold | Editable generated defaults | Formula helper recommends values; manual override remains visible. |
| Attributes | Editable generated defaults | Derived combat stats must be previewed separately. |
| Saving throws | Editable or profile-derived | Store explicit overrides and show profile baseline. |
| Combat snapshot | Derived | Never hand-edited; computed through canonical stat services. |

### Quick Build behavior

Quick Build asks for level, role/archetype, durability, offense style, defense style, resource style, and reward style. It writes suggested stats into the working record and marks fields as generated until the builder manually overrides them. It must present a before/after diff and allow apply/cancel. Recommended values must be generated by Smart MUD formula/profile data, not hardcoded TBA formulas.

### Validation and preview

Stats validation must catch missing level, invalid dice, negative resource pools, inconsistent default attack damage, rewards outside configured bounds, attributes outside legal ranges, and missing required body/combat profiles. Preview must show raw authored stats, generated recommendations, overrides, and final resolved runtime snapshot.

## NPC Flags Catalog

Flags are stored as named tags/capabilities with grouped display. Deprecated or custom flags are documented by name and must be preserved as inert metadata only when needed for migration notes.

| Group | Flags/concepts | Purpose and runtime behavior | Builder validation |
|---|---|---|---|
| Movement | sentinel, scavenger, stay_zone, wanderer, mount, aquatic, flying, no_track | Controls autonomous movement, zone boundaries, item pickup, mountability, and environmental mobility. | Requires movement/AI profile where runtime behavior is expected; warn if room terrain conflicts. |
| Combat | aggressive, aggressive_evil, aggressive_good, aggressive_neutral, wimpy, assist, guard, protector, no_summon, no_charm, no_sleep, no_bash, no_blind | Controls hostility, defenses, immunities, assist/protect behavior, and combat availability. | Requires hostility/combat behavior profile; incompatible flags warn. |
| Quest | questgiver, quest_target, quest_mob, bounty, kill_credit, no_kill_credit | Marks quest interaction and objective hooks. | Must reference quest/objective metadata when active. |
| Trainer | trainer, practice_trainer, guild_trainer, class_trainer, skill_trainer, spell_trainer | Allows training/practice interactions. | Requires trainer definition and offers. |
| Guild/shop/service | guildmaster, shopkeeper, banker, repairer, innkeeper, stablemaster, auctioneer | Service-provider behavior. | Requires matching service/shop/economy profile. |
| Aggression/social | helper, memory, hunter, police, hates, fears | Reactive AI, memory, pursuit, law behavior. | Requires behavior/event profile once implemented. |
| Summoning/control | pet, charmable, no_charm, summoned, tethered | Pet lifecycle, charm restrictions, summon restrictions. | Pet price requires pet profile; charm flags must not conflict. |
| AI | ai_actor, scripted, autonomous, conversation_agent | Identifies mobs driven by Smart MUD AI/event systems. | `ai_actor` must mean eligible for canonical AI observation/decision loop; it must not imply any copied TBA special procedure. Requires behavior/controller profile or explicit warning. |
| Utility | no_corpse, corpse_persistent, invisible_to_mortals, immortal_only, prototype, no_purge | Operational/runtime modifiers. | Staff-only flags require admin/owner; no-corpse warns if loot exists. |
| Special/custom | special_proc_reference, dg_triggered, custom tags | Legacy/custom behavior hooks. | Must map to a Smart MUD service, event reaction, ability, or script reference before publish. |

## AFF Flags Catalog

Permanent affects on mobiles are authored as named permanent effect references or canonical affect names, never bit positions. They are applied when a mobile instance is spawned and removed with that instance unless a script/service adds separate runtime effects.

| Affect | Runtime intent | Restrictions/interactions |
|---|---|---|
| blind/infravision/detect_invisible/detect_magic/sense_life | Perception modifiers. | Perception affects require sensory support; warn if runtime consumer absent. |
| invisible/hide/sneak | Visibility and stealth. | Must integrate with visibility service and command discovery. |
| sanctuary/protection/barrier | Defensive mitigation. | Requires effect definition with stacking policy. |
| haste/slow | Speed/round timing. | Cannot both be permanent unless explicit custom rule. |
| flying/water_breathing | Movement/environment access. | Must align with movement capability. |
| poison/disease/curse | Persistent negative conditions. | Spawn-with-negative-affect must be intentional; warnings for vendors/questgivers. |
| charm/sleep/paralysis/stun | Control/disabling states. | Usually invalid as default permanent affects unless scripted statue/sleeping mob. |
| strength/dexterity/constitution/intelligence/wisdom/charisma modifiers | Attribute changes. | Prefer stat profile modifiers; stacking must be explicit. |
| resist/immunity/vulnerability effects | Damage or school mitigation. | Must resolve to canonical resistance taxonomy. |

## Loadout and Loot Audit

Adventurer's Lair-style mobs may have equipment, inventory, guaranteed drops, random drops, chances, and wear locations. Smart MUD must model these through equipment/loadout profiles, inventory seed profiles, reward definitions, loot tables, treasure groups, death-loot profiles, and corpse-decay profiles.

Equipment entries require item reference, wear location, chance or guarantee, quantity, condition/quality seed, visibility, droppable policy, and copy/delete behavior. Inventory entries require item reference, quantity, chance, generated ownership, and whether the item is carried, usable, stealable, or corpse-transferable. Guaranteed drops belong in reward/death-loot entries. Random drops belong in loot-table rows with chance, weight, quantity range, eligibility, and seed policy.

Validation must detect missing objects, invalid wear locations for item/body, duplicate exclusive wear slots, impossible chances, orphan loot tables, no-corpse mobs with corpse loot, and cyclic reward references. Preview must show equipped view, inventory view, corpse contents projection, guaranteed drops, random roll table, missing dependency warnings, and copy/delete impact.

## Combat Abilities Audit

Combat abilities should use Smart MUD `AbilityExecutionService` and ability loadouts. The MEDIT nested editor must list assigned abilities in deterministic order and support add, clone, set, delete, enable/disable, reorder, validate, and preview.

Each entry requires ability ID, trigger mode, target selector, priority/order, chance/weight, cooldown, resource cost policy, range, timing/round phase, conditions, usage limits per fight/spawn/day, status flags, and failure messaging. Trigger modes include opener, every round, below health threshold, target casting, ally injured, fleeing, death throes, and scripted event. Target selectors include current target, highest threat, lowest health enemy, random enemy, self, ally, room, owner/master, and quest actor where supported.

Validation must prove ability existence, legal target profile, actor resource compatibility, cooldown group, required flags, and no impossible conditions. Preview must simulate candidate selection with reasons and sample combat output.

## Event Reactions Audit

Event reactions are Smart MUD's canonical replacement for ad hoc special procedures. MEDIT must support reactions as data records attached to a mobile or behavior profile.

Entry schema: event name, condition expression/profile, action type, target selector, parameters, cooldown, chance, priority, usage limit, enabled flag, tags, audit notes. Supported events should include spawn, despawn, reset, enter room, leave room, speech heard, command seen, attacked, damaged, health threshold, ally attacked, enemy killed, item given, item shown, timer tick, quest state changed, and death.

Supported actions include say/emote, move, attack, assist, flee, call for help, give/take item through services, start dialogue, start quest interaction, cast/use ability, set memory/faction signal, enqueue script, and emit event. Validation must restrict actions to canonical services and reject direct state mutation.

## Script Audit

Legacy script attachment behavior maps to Smart MUD future unified scripting references. A mobile may reference script packages/triggers, but MEDIT must store script IDs, trigger metadata, local variables/configuration, enabled state, order, and dependency notes. Scripts must validate against the script registry, required trigger types, permissions, and declared inputs/outputs. Scripts may be previewed through dry-run traces only. They must not bypass services, drafts, validation, publish, economy, inventory, combat, or event systems.

## Copy, Delete, and Dependency Checks

Copy must duplicate the working mobile into a new ID/VNUM, preserve field values, deep-copy nested editor data, and rewrite self-references where necessary. It must not duplicate runtime instances. Delete must be soft/staged in drafts, show all dependencies before confirmation, and block publish if active spawns, quests, shops, scripts, resets, or tests still require the mobile. Builders need `mdeps`, `mwhere`, and publish-time dependency reports.

## Smart MUD MEDIT Gap Analysis

| Feature | Adventurer's Lair | Smart MUD today | Gap | Phase | Priority |
|---|---|---|---|---|---|
| Session scratch, dirty quit, save/discard | Yes | Partial/implemented foundation | Extend to full MEDIT | 15C.1 | Critical |
| General identity fields | Yes | Partial | Complete field schema/editors | 15C.1 | Critical |
| Area/zone/VNUM ownership | Yes | Partial | Mob range enforcement | 15C.1 | Critical |
| Stats menu/quick build | Yes | Partial stats services | Nested editor and recommendations | 15C.2 | Critical |
| NPC flags | Yes | Missing as canonical catalog | Named capability schema | 15C.3 | High |
| AFF flags | Yes | Partial effect system | Permanent affect authoring | 15C.4 | High |
| Loadout/equipment/inventory | Yes | Partial profiles/services | Mob-specific nested editor | 15C.5 | High |
| Loot/death drops | Yes | Partial reward services | Builder integration/deps | 15C.5 | High |
| Combat abilities | Yes/custom | Partial ability loadouts | Mob ability editor | 15C.6 | High |
| Event reactions | Yes/custom | Partial event bus | Canonical reaction records | 15C.7 | High |
| Scripts | Yes/DG-style | Future | Unified script attachment spec | 15C.8 | Medium |
| Copy/delete | Yes | Partial | Dependency-aware operations | 15C.9 | High |
| Publish/runtime generation | No equivalent draft pipeline | Implemented foundation | Add all fields to package generation | 15C.9 | Critical |

## Recommended MEDIT Implementation Phases

- 15C.1: MEDIT Core: schema, commands, lookup, ownership, sessions, validation shell, preview shell.
- 15C.2: Stats Menu: quick build, formulas, recommendations, final stat preview.
- 15C.3: NPC Flags: named catalog, dependencies, runtime projections.
- 15C.4: AFF Flags: permanent effect authoring and spawn application.
- 15C.5: Loadout and Loot: equipment, inventory, reward/death-loot integration.
- 15C.6: Combat Abilities: ability loadout nested editor and combat preview.
- 15C.7: Event Reactions: canonical event reaction schema and service dispatch.
- 15C.8: Scripts: future unified scripting references and dry-run validation.
- 15C.9: Copy/Delete/Validation/Publish hardening: dependency graph, deletion workflow, publish coverage, rollback coverage.

## Future Smart MUD Extensions After Parity

After parity, Smart MUD should add equipment profiles, loot profiles, behavior profiles, dialogue packages, schedules, relationships, personalities, memory templates, AI archetypes, profession templates, spawn profiles, faction packages, and encounter templates. These belong after 15C.9 and must be profile-driven so many mobiles can share balanced behavior without duplicated records.

## Phase 15C.1 Implementation Clarification

Phase 15C.1 establishes the functional Smart MUD MEDIT foundation on the existing BuilderEditSession and draft workflow. The implemented foundation keeps mobile edits in canonical entity templates and normalizes legacy-compatible mobile fields into named schema sections for identity, keywords, descriptions, traits, attributes/resources, combat profile data, body/natural attacks, positions, flags, affects, economy, loadout, inventory, and loot/corpse configuration.

The editor intentionally distinguishes fully editable foundation sections from advanced references. Ability loadouts, behavior/AI profiles, factions, and scripts are preserved, previewed, and validated as references where current runtime support exists; full advanced editors remain later MEDIT phases. Pet/economy data is stored, validated, and previewed, but runtime purchasing remains limited unless a world supplies the corresponding shop/service flow.

Normalization is deterministic and backward-compatible: legacy `natural_attacks` and top-level `natural_weapons` migrate into `combat_profile.natural_weapons`; aliases can seed keywords; resources can be represented as explicit named resource objects; mobile flags and permanent affects use named lists rather than integer bitvectors. Normalization must not infer a creature species from body, combat, behavior, faction, or loot profile names.

## Phase 15C.2A Core Parity Clarification

Phase 15C.2A completes the core, non-advanced MEDIT parity layer while preserving the Phase 15C.1 architecture. Combat Abilities, Event Reactions, and full Script Attachment editing remain deferred to Phase 15C.2B.

### Main menu honesty

The MEDIT main menu must identify the draft as a Builder-authored mobile, display VNUM, revision, world, area, zone, lock owner, validation counts, dirty status, builder completeness, publish status, and runtime activation status. Menu summaries must distinguish editable Builder systems from profile references and deferred runtime behavior. Resource summaries must display resolved named resource values rather than raw empty dictionaries.

### Stats Menu and Quick Build

The Stats Menu is the canonical nested editor for level, archetype, attributes, health, mana, stamina/movement, armor/defense, accuracy/hitroll, damage bonus/damroll, base damage dice, attack type, attacks per round, experience reward, and currency reward. It displays authored override, recommendation source, and resolved runtime value when those layers exist.

Quick Build recommendations are produced by `MobileRecommendationService` version `smartmud-medit-quick-build/v1`. The service is deterministic and separate from runtime materialization. It accepts level, archetype, durability, offense, defense, resource style, attack style, reward style, and difficulty rank inputs, can render a diff without mutating the draft, and applies accepted values as one undo checkpoint.

### Balance and reward validation

Validation includes non-destructive balance warnings using the same recommendation source/version. Warnings are publish-allowed unless paired with a separate blocking schema error. Current warnings cover unusually low/high health, excessive/insufficient XP, caster/support archetypes without mana or equivalent resources, contradictory mobile flags, contradictory permanent affects, and pet price without pet eligibility.

### Flags, affects, pet data, loadout, loot, attacks, and positions

Mobile flags and permanent affects remain named lists and preserve unknown compatible names through normalization. The grouped flag editor supports numeric and named toggles, clear/none, all, validate, undo, redo, and back. Runtime behavior is only claimed where a runtime consumer observes the projected field; otherwise the field is authoring-only or runtime-deferred.

Pet price remains canonical Builder data with validation. Runtime purchasing is deferred unless the world supplies a matching shop/service handler.

Equipment loadout, starting inventory, loot, corpse settings, attack type, natural attacks, spawn position, and default position are normalized into canonical mobile records and included in preview/runtime projections. Chance-based and service-dependent behaviors are preserved and labeled as authored/runtime-deferred when no runtime consumer exists.

### Preview and runtime projection

The consolidated preview covers identity, traits, stats, combat, item content, sample natural attack text, and death/corpse summary. Preview is deterministic and must not mutate the draft. Runtime projection includes keywords, descriptions, positions, flags, permanent affects, attributes, resources, combat profile, equipment loadout, starting inventory, and loot/corpse data so tests can prove fields advertised as runtime-supported are observable.

### Session consistency

Nested Stats, flag, equipment, spawn, list, reference, and multiline editors must honor back, save, discard/quit, validate, preview where applicable, undo, redo, and help. No-op field writes do not create checkpoints.

## Phase 15C.2B Advanced Parity and Lifecycle Hardening Clarification

Phase 15C.2B adds canonical, draft-backed advanced MEDIT sections for `combat_abilities`, `event_reactions`, and `script_attachments`. These records are normalized from compatible legacy forms such as explicit ability arrays, reaction arrays, script ID lists, and trigger arrays. Normalization is deterministic: missing nested IDs are generated from stable parent/entry seeds, missing priorities are filled from list order, chance strings such as `50%` become integer percentages, and legacy target/trigger names are lowercased with spaces converted to underscores. Unknown authored fields are preserved on the nested record rather than silently converted into scripts or reactions.

### Combat Abilities

Combat Abilities are structured data, not arbitrary JSON and not scripts. Each entry stores a stable `id`, `ability_type`, `ability_id`, enabled state, priority, optional builder label, target selector, trigger, chance, cooldowns, round bounds, resource costs, status/tag conditions, use limits, and classification flags. The editor supports add, edit, delete, copy, move, move up/down, toggle, inspect, preview, validate, dependency report, undo, redo, save, and back. Preview prints a deterministic decision trace with trigger, target, cooldown, use-limit, and runtime-support status. Runtime projection includes the canonical ability records, but runtime execution is only claimed for supported trigger mappings; unsupported mappings are warnings and remain editor-complete/runtime-deferred.

### Event Reactions

Event Reactions are canonical event/action records mapped to Smart MUD EventBus concepts. Each entry stores stable identity, event type, filters, action type, action data, target selector, chance, cooldowns, use limits, conditions/tags, priority, enabled state, and stop-processing behavior. The editor supports add, edit, delete, copy, reorder, toggle, inspect, validate, preview, dependency report, undo, redo, save, and back. Preview is simulated and must not publish live EventBus events. Runtime support is explicitly labeled per event/action mapping; deferred mappings remain publish-visible warnings rather than hidden behavior.

### Script Attachments

Script Attachments store approved script/trigger references, not a MEDIT-only scripting language. Each attachment stores a stable attachment ID, script reference, enabled state, priority, trigger/event binding, parameters, conditions, and execution policy. The editor supports list/add/remove/copy/reorder/toggle/inspect/validate/preview/dependency/back with undo/redo and draft save. Preview is a dry-run dependency trace only and never executes destructive script behavior. Runtime execution depends on the canonical script host, so script attachments are classified as editor complete/runtime host required unless that host validates the script.

### Diagnostics, Validation, Preview, and Lifecycle

Advanced nested sections participate in MobileTemplate validation and runtime projection. Validation now catches duplicate nested IDs, duplicate priorities, invalid chance/cooldown/limits, invalid targets, invalid ability types, invalid triggers/events/actions, missing ability/script references, contradictory required/forbidden statuses, contradictory required/forbidden tags, and event-loop risk. Warnings distinguish runtime-deferred ability triggers, runtime-deferred reaction mappings, and script attachments that require a canonical script host.

The consolidated MEDIT preview now includes ability decision order, event reaction summaries, script attachment summaries, runtime-support labeling, and simulated-only language. Preview remains deterministic, non-mutating, and side-effect free: it does not persist runtime instances, publish EventBus events, or run destructive scripts.

Draft save still writes Builder drafts only. Publish continues to validate drafts and create immutable generation snapshots through the canonical Builder lifecycle. Activation continues through generation activation rather than direct MEDIT mutation. Rollback remains generation-based and does not introduce a MEDIT-only rollback path. Copying entity templates normalizes advanced sections for the destination ID, refreshes nested IDs where needed, preserves intentional external references, resets publish/runtime/deletion metadata, and creates only a draft. Deletion remains dependency-protected with staged soft deletion when references exist and hard deletion only when no blocking references remain.

### Runtime Consumption Classification After 15C.2B

- Identity, keywords, descriptions, positions, flags, permanent affects, attributes, resources, combat profile, natural weapons, equipment, inventory, and loot are consumed or projected through existing Builder/runtime materialization paths.
- Combat Abilities are fully authored and projected; runtime behavior is supported only for explicitly supported trigger mappings and remains deferred for unsupported triggers until canonical combat services cover them behaviorally.
- Event Reactions are fully authored and projected; runtime behavior is supported only for explicitly supported EventBus/action mappings and remains deferred for unsupported mappings until canonical handlers exist.
- Script Attachments are fully authored and projected; runtime execution requires the canonical script host and security validation.

### Updated Roadmap

Customized Adventurer's Lair MEDIT parity is now substantially complete at the Builder/editor, validation, dependency, preview, copy/delete, and lifecycle-integration layers. Remaining gaps are runtime execution depth for advanced Combat Ability triggers, Event Reaction action handlers, and script-host-backed execution. Those gaps should be finished with behaviorally tested canonical runtime services, not with MEDIT-only substitutes. Full OEDIT parity remains outside this phase and should proceed separately after the final advanced-runtime MEDIT gaps are accepted or closed.
