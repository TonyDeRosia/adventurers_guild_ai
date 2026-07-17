# Runtime Parity Roadmap — Phase 16A.1 Verified Baseline

This roadmap removes the Phase 16A template language. Each phase names the runtime owner, files, commands, persistence, tests, and Builder implications that must be inspected before implementation.

## Phase 16B — Persistent exit and door state parity
- Runtime owner: `MudRuntime` movement path plus a narrow exit-state owner if `MudRuntime` cannot persist state without duplication.
- Smart MUD source files: `engine/mud_runtime.py`, `engine/mud_commands.py`, `engine/world_registry.py`, `engine/zone_resets.py`, `engine/mud_state_store.py`, `worlds/shattered_realms/rooms/rooms.json`, `worlds/shattered_realms/resets/resets.json`.
- Adventurer's Lair evidence to verify: `src/act.movement.c` door/movement commands, `src/act.item.c` key interactions, `src/db.c` exit loading/reset data, `src/structs.h` room-direction structures, and zone reset door commands.
- Commands: directional movement, `open`, `close`, `lock`, `unlock`, `pick`, `look`, and any hidden-exit discovery command already routed through Smart MUD.
- Persistence: canonical per-exit state keyed by world/room/direction with reset defaults, lock state, key reference, hidden/discovered state, and restart survival.
- Tests: focused movement/door command tests, reset replay tests, persistence restart tests, event publication tests, and negative tests for missing keys/one-way exits.
- Builder implication: document existing room/exit draft fields and validation blockers only; do not build broad Builder UI in 16B.
- Dependency verdict: remains the correct next phase.

## Phase 16C — Container runtime parity
- Runtime owner: inventory/item-instance APIs and `MudRuntime` item command adapter.
- Smart MUD source files: `engine/inventory.py`, `engine/mud_runtime.py`, `engine/mud_commands.py`, `engine/runtime_resources.py`, `engine/mud_state_store.py`, `worlds/shattered_realms/items/items.json`, `worlds/shattered_realms/item_templates/item_templates.json`.
- Adventurer's Lair evidence to verify: `src/act.item.c` get/put/drop/give/container handling, `src/structs.h` object values/flags, `src/db.c` object loading, and object save/rent paths.
- Commands: `get`, `put`, `drop`, `give`, `inventory`, `look in`, `open`, `close`, `lock`, `unlock` for containers only.
- Persistence: nested item location, capacity, closed/locked state, key id, corpse/container contents, and restart survival.
- Tests: nested capacity, locked container, room/inventory movement, restart, and Builder data validation tests.
- Builder implication: expose validation requirements for item type/value fields after runtime semantics are canonical.

## Phase 16D — Object consumption and lights
- Runtime owner: object-use dispatcher backed by SurvivalNeeds and item-instance state.
- Smart MUD source files: `engine/survival_needs.py`, `engine/inventory.py`, `engine/mud_runtime.py`, `engine/abilities.py`, `worlds/shattered_realms/consumable_profiles/consumable_profiles.json`, `worlds/shattered_realms/light_source_profiles/light_source_profiles.json`.
- Adventurer's Lair evidence to verify: `src/act.item.c` eat/drink/quaff/fill/pour/recite/use paths, object value fields in `src/structs.h`, and affect/poison interactions in `src/magic.c`.
- Commands: `eat`, `drink`, `sip`, `taste`, `fill`, `pour`, `light`, `extinguish`, and relevant `use` aliases.
- Persistence: remaining portions, light fuel/timer, poison/condition effects, and consumed object removal.
- Tests: command success/failure, resource changes, room dark/light rendering hooks, persistence, and no duplicate item state.
- Builder implication: validate consumable/light profiles against command-visible object types.

## Phase 16E — Object magic dispatcher
- Runtime owner: AbilityService plus item-use dispatcher.
- Smart MUD source files: `engine/abilities.py`, `engine/spellbook.py`, `engine/inventory.py`, `engine/mud_runtime.py`, `worlds/shattered_realms/spells/spells.json`, `worlds/shattered_realms/casting_profiles/casting_profiles.json`.
- Adventurer's Lair evidence to verify: `src/spell_parser.c`, `src/magic.c`, `src/act.item.c`, and object spell value definitions in `src/structs.h`.
- Commands: `quaff`, `recite`, `use`, `zap`, `brandish`, target parsing, charge depletion.
- Persistence: item charges, cooldown if Smart MUD profile requires it, consumed scroll/potion removal.
- Tests: target resolution, charge exhaustion, effect application, failures outside combat/inside combat, and restart state.
- Builder implication: spell references on magic items must validate against canonical spell ids.

## Phase 16F — Corpse loot and decay parity
- Runtime owner: combat death lifecycle, inventory, and runtime resource decay.
- Smart MUD source files: `engine/combat_runtime.py`, `engine/character_state.py`, `engine/inventory.py`, `engine/runtime_resources.py`, `engine/mud_runtime.py`.
- Adventurer's Lair evidence to verify: `src/fight.c` death/corpse creation, `src/act.item.c` corpse get/loot/sacrifice, object decay/extract paths.
- Commands: `get all corpse`, `look corpse`, `sacrifice` if present, and ordinary container commands against corpse objects.
- Persistence: corpse contents, ownership/loot restrictions, decay timers, extraction events.
- Tests: NPC death, player death policy, loot transfer, decay, restart, and event idempotency.
- Builder implication: none beyond profile docs; corpse behavior is runtime-owned.

## Phase 16G — Reset dependency executor
- Runtime owner: `ZoneResetService` and world-state resolver.
- Smart MUD source files: `engine/zone_resets.py`, `engine/world_registry.py`, `engine/content_registry.py`, `engine/mud_runtime.py`, `worlds/shattered_realms/resets/resets.json`.
- Adventurer's Lair evidence to verify: `src/db.c` zone reset interpreter and reset command order semantics.
- Commands: admin reset/reload commands if registered; player-visible effects through spawned mobs/items/doors.
- Persistence: reset history, max-count guards, dependency success/failure, and door/container/corpse interactions.
- Tests: ordered reset dependencies, missing references, idempotency, restart, and content validation.
- Builder implication: publish blockers for invalid reset references.

## Phase 16H — Mobile aggression and scavenging
- Runtime owner: combat behavior/living-world tick services.
- Smart MUD source files: `engine/combat_behavior.py`, `engine/living_world.py`, `engine/perception.py`, `engine/factions.py`, `worlds/shattered_realms/aggression_profiles/aggression_profiles.json`, `worlds/shattered_realms/controller_profiles/controller_profiles.json`.
- Adventurer's Lair evidence to verify: custom `ai_actor*` files if accessible, `src/mobact.c`, `src/fight.c`, and special procedure hooks.
- Commands: no new player command required; visible behavior through room entry, combat starts, assistance, flee/pursuit, scavenging.
- Persistence: active targets, cooldowns, aggression memory if Smart MUD profile requires it.
- Tests: aggression triggers, faction/visibility gates, scavenging, assist, pursuit, and no offline tick duplication.
- Builder implication: profile validation only after runtime semantics are fixed.

## Phase 16I — Special procedure adapter
- Runtime owner: declarative behavior adapter, not direct C special procedure cloning.
- Smart MUD source files: `engine/event_bus` equivalent call sites through runtime services, `engine/quests.py`, `engine/dialogue_service.py`, `engine/combat_behavior.py`, `engine/mud_runtime.py`.
- Adventurer's Lair evidence to verify: `src/spec_procs.c`, shop/guild/quest special hooks, and assignment data in world files.
- Commands: command interception points named by each migrated special.
- Persistence: adapter-local state only when behavior is stateful.
- Tests: one migrated special per behavior class plus command interception regressions.
- Builder implication: data model for assigning safe declarative specials.

## Phase 16J — Practice and skill improvement
- Runtime owner: training/progression services.
- Smart MUD source files: `engine/training.py`, `engine/progression.py`, `engine/spellbook.py`, `worlds/shattered_realms/trainer_definitions/trainer_definitions.json`, `worlds/shattered_realms/class_tracks/class_tracks.json`.
- Adventurer's Lair evidence to verify: `src/class.c`, `src/spec_procs.c` guildmasters, `src/spell_parser.c`, and player skill storage.
- Commands: `practice`, `train`, `skills`, `spells`, and trainer interaction commands.
- Persistence: learned skill percentages/ranks, practice sessions, refunds/respec if enabled.
- Tests: class/race gates, costs, skill gains, trainer availability, persistence.
- Builder implication: trainer definitions must validate skill/class refs.

## Phase 16K — DG trigger foundation
- Runtime owner: safe Smart MUD trigger service over EventBus.
- Smart MUD source files: `engine/quests.py`, `engine/dialogue_service.py`, `engine/mud_runtime.py`, `engine/content_registry.py`, and a new isolated trigger module only after design approval.
- Adventurer's Lair evidence to verify: `src/dg_*.c`, trigger script storage, attach points for rooms/mobs/objects.
- Commands: trigger-visible commands only; no arbitrary script execution.
- Persistence: trigger variables, cooldowns, script state, audit logs.
- Tests: room/mobile/object trigger attach, conditions, effects, persistence, security rejection.
- Builder implication: script authoring must wait for safe runtime contract.
