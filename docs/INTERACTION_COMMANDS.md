# Interaction Commands

Phase 3C adds a runtime-owned, non-combat interaction command layer. Transports send player input to `MudRuntime`; they do not implement gameplay logic.

## Command Flow

```text
Transport -> MudRuntime parser -> alias/filler normalization -> deterministic target resolution -> runtime interaction API -> EventBus -> renderer -> transport
```

## Supported Non-Combat Commands

The parser recognizes common room, item, feature, entity, and equipment commands:

- Inspection: `look`, `look at`, `look in`, `glance`, `scan`, `search`, `listen`, `smell`
- Object/environment: `enter`, `leave`, `drink`, `eat`, `open`, `close`, `lock`, `unlock`, `pick`
- Pickup aliases: `get`, `take`, `pickup`, `pick up`
- Movement helpers: `run <direction>`, `walk <direction>`
- Dialogue: `talk`, `greet`, `hello`
- Containers foundation: `open chest`, `close chest`, `look in chest`, `put sword chest`, `get sword chest`
- Posture: `sit`, `stand`, `rest`, `sleep`, `wake`
- Equipment: `wear`, `wear all`, `remove`, `remove all`, `wield`, `hold`, `mainhand`, `offhand`, `dual`, `unwield`, `unequip`

Commands are case-insensitive and ignore extra whitespace. Optional filler words are normalized, so `look at sword` and `look sword`, `drink from fountain` and `drink fountain`, and `pick up sword` and `pickup sword` route identically where appropriate. `pick lock` remains an interaction command and does not route to pickup.

## Target Resolution Priority

Target resolution is deterministic:

1. Equipped items
2. Inventory
3. Room objects
4. Visible NPCs
5. Visible mobs
6. Exits
7. Canonical room features

Ambiguous matches require clarification instead of choosing randomly.

## Canonical Room Features

Room features are not inventory objects and cannot be picked up. Phase 3C includes canonical feature names such as `gate`, `door`, `fountain`, `altar`, `statue`, `portal`, `stairs`, `bridge`, `campfire`, `lever`, `switch`, `tree`, and `water`. Future Builder Mode can attach feature definitions and interaction hooks without transport changes.

## EventBus Events

The interaction layer publishes:

- `interaction_attempted`
- `interaction_succeeded`
- `interaction_failed`
- `environment_inspected`
- `entity_interaction`
- `object_interaction`
- `container_interaction`
- `command_alias_resolved`

## Non-Goals

Phase 3C does not implement combat, damage, spell casting, AI decision making, shops, quests, crafting, nested containers, pathfinding, stealth, lockpicking mechanics, traps, or Builder Mode.

## Phase 3C Hotfix: core non-combat commands

Targeted `look`, `l`, and `examine` now resolve a named target and display the target name plus its long description when one is available. `look at <target>` is normalized to the same targeted lookup. Runtime target resolution checks equipped items, inventory, portable room items, room features, visible NPCs, visible mobs, and exits.

Room features are fixed scenery unless explicitly marked `portable: true`. World data may describe features with optional fields such as `keywords`, `short_description`, `long_description`, `portable`, `drinkable`, `enterable`, `readable`, `usable`, `openable`, `locked`, `locked_message`, and `default_interactions`. Nonportable features such as fountains, gates, doors, altars, statues, campfires, stairs, and portals can be inspected and interacted with, but `get <feature>` returns clean MUD text instead of adding scenery to inventory.

`get all` and `take all` only collect portable room items. `drop all` drops carried inventory items only; equipped items must be removed first. Clean fallback handling is provided for `identify`/`id`, `use`, `read`, `pray`, `touch`, `push`, `pull`, `climb`, `enter`, `leave`, `drink`, `eat`, `search`, `listen`, `smell`, `scan`, and `glance`.

## Phase 3D command registry note

Smart MUD now tracks player, placeholder, future builder/admin, future combat, future magic, future economy, and future quest commands through a canonical command registry. The `commands` and `help` commands use registry metadata so classic MUD command coverage is deliberate without adding combat, AI, Builder Mode, shops, quests, spellcasting, or world expansion.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.
