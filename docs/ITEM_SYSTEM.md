# Smart MUD Item System (Phase 2E)

## Objective

Phase 2E replaces placeholder inventory and equipment behavior with a persistent runtime object system. Characters and rooms own persistent item instances, equipment persists across sessions, and every object interaction passes through `MudRuntime`.

Combat, AI behavior, Builder Mode gameplay, crafting, shops, quests, spells, skills, banking, and NPC AI remain intentionally out of scope.

## Runtime Authority

The runtime is the only authority over gameplay state.

The following systems may never directly manipulate item ownership or equipment state:

- Web UI
- Telnet transport
- Plugins
- Builder Mode
- World packages
- SQLite helpers

Every item interaction must execute through `MudRuntime`. World packages define immutable templates only. SQLite persists runtime state only. Transports request runtime operations and display runtime responses. Plugins observe or extend runtime behavior but never replace runtime ownership. No duplicate inventory logic may exist anywhere else in the project.

## Item Model

Smart MUD uses one canonical runtime item model with immutable templates and mutable instances.

Do not create separate runtime classes such as `Weapon`, `Armor`, `Food`, `Container`, or `QuestItem` unless the existing architecture already requires them. Use a single canonical runtime `Item` model with behavior determined by template data and registered handlers. Future plugins may extend behavior without requiring inheritance trees.

### Item Templates

Item templates are loaded from world packages and are read-only at runtime. They describe immutable reference data such as:

- `id`
- `name`
- `keywords`
- `short_description`
- `long_description`
- `item_type`
- `weight`
- `value`
- `wear_slots`
- `weapon_flags`
- `armor_values`
- `stackable`
- `max_stack`
- `rarity`
- `level_requirement`
- `lore`
- `plugin_data`

Template data must never be modified at runtime.

### Item Instances

Item instances are runtime records persisted to SQLite. Each spawned item has:

- `instance_id`
- `template_id`
- `owner_type`
- `owner_id`
- `room_id`
- `equipped_slot`
- `stack_count`
- `condition`
- `durability`
- `created_at`
- `updated_at`
- `custom_flags`
- `plugin_data`

Instances reference templates. Runtime objects must not duplicate template information except where short-lived caching is necessary.

## Item Lifecycle

Every runtime item follows one lifecycle:

```text
Template
↓
Spawn Runtime Instance
↓
Room Inventory
↓
Character Inventory
↓
Equipment
↓
Character Inventory
↓
Room Inventory
↓
Future Container
↓
Future Corpse
↓
Destroyed
↓
Archived (future)
```

Items must never duplicate themselves during ownership transfers. Every item instance always has exactly one owner. Equipment is not a duplicate copy of an inventory item; it is another ownership state of the same runtime instance.

## SQLite Persistence

SQLite stores mutable runtime state. World packages remain immutable content sources.

Persistent storage must support:

- `item_templates`
- `item_instances`
- `character_inventory`
- `room_inventory`
- `equipment`

The schema should reuse existing tables where possible and avoid duplicating state already represented elsewhere.

## Canonical Runtime API

`MudRuntime` exposes the authoritative item API. Commands, plugins, Builder Mode, transports, and future systems must use runtime functions instead of manipulating SQLite directly.

Minimum runtime API:

- `spawn_item()`
- `destroy_item()`
- `transfer_item()`
- `pickup_item()`
- `drop_item()`
- `equip_item()`
- `unequip_item()`
- `move_item()`
- `find_item()`
- `find_room_items()`
- `find_inventory_items()`
- `find_equipped_items()`
- `resolve_item_keywords()`
- `get_visible_room_items()`
- `validate_equipment()`

Future gameplay systems should build on these APIs rather than creating new inventory logic.

## Ownership Model

Objects may belong to a room, character, future NPC, future corpse, future container, or plugin-defined owner type. Ownership transfers must always execute through `transfer_item()`. Commands must never update SQLite ownership directly.

The following systems must all call the same runtime transfer path:

- `get`
- `take`
- `drop`
- `loot`
- `wear`
- `remove`
- `wield`
- future shops
- future trading
- future banking
- future crafting
- future AI
- future Builder Mode
- future plugins

This guarantees identical behavior everywhere.

## Equipment System

Minimum equipment slots are:

- `head`
- `neck`
- `body`
- `back`
- `arms`
- `hands`
- `finger_left`
- `finger_right`
- `waist`
- `legs`
- `feet`
- `main_hand`
- `off_hand`
- `both_hands`
- `ranged`
- `ammo`
- `light`

Templates determine where items may be equipped. The runtime must not hardcode specific item identities.

Equipment rules:

- Only one item may occupy a slot unless explicitly defined otherwise.
- Finger slots are independent.
- Main hand and off hand are independent.
- Two-handed weapons occupy both hands.
- Equipping a conflicting item automatically unequips the existing item.
- Removing a two-handed weapon frees both hands.
- Items may never exist simultaneously in equipment and inventory.
- Equipment persists across logout.
- Equipment persists across reboot.
- Equipment changes always publish EventBus events.

## Starter Items

World packages may define starter items. When a new character is created, the runtime spawns starter item instances, places them into inventory, and does not auto-equip them unless the package explicitly configures auto-equip behavior.

## Room Objects and Rendering

Room rendering must use runtime room inventory instead of placeholder objects. Room rendering order must always be:

1. Room title
2. Room description
3. Exits
4. Visible NPCs
5. Visible players
6. Visible objects
7. Prompt

Never interleave these sections. Never duplicate objects. Never render equipped items or inventory items as room objects.

## Inventory and Equipment Commands

The command router must support these aliases through the same runtime command path:

- `inventory`, `inv`, `i`
- `equipment`, `eq`
- `take`, `get`
- `remove`, `rem`
- `look`, `l`

Inventory output should list carried runtime item instances and display “You are carrying nothing.” when empty. Equipment output should list each canonical slot and its equipped item or “Nothing.”

## Object Interaction

The runtime must implement:

- `get`
- `take`
- `drop`
- `wear`
- `remove`
- `wield`
- `unwield`
- `hold`
- `look <object>`
- `examine`

Unknown objects should return classic MUD-style responses. Keyword resolution is case-insensitive, supports multi-word matches, prefers exact matches, and gracefully reports ambiguity.

## Item Transfer Pipeline

Every object interaction follows this order:

```text
Validate ownership
↓
Resolve keywords
↓
Permission validation
↓
Transfer runtime ownership
↓
Update SQLite
↓
Publish EventBus events
↓
Render output
↓
Return transport response
```

No command should bypass this pipeline.

## EventBus Events

The item system publishes deterministic runtime events, including:

- `item_spawned`
- `item_destroyed`
- `item_picked_up`
- `item_dropped`
- `item_equipped`
- `item_removed`
- `inventory_changed`
- `equipment_changed`
- `room_inventory_changed`

Payloads should include `account_id`, `session_id`, `character_id`, `room_id`, `template_id`, `instance_id`, and `transport_type` when available.

Event ordering must be deterministic. Example pickup flow:

```text
before_item_pickup
↓
item_picked_up
↓
inventory_changed
↓
room_inventory_changed
↓
after_item_pickup
↓
room_rendered
↓
prompt_rendered
↓
transport_response_sent
```

Future plugins should be able to subscribe at predictable stages.

## Plugin Compatibility

Plugins may:

- register item types
- add metadata
- observe inventory events
- add equip restrictions
- modify descriptions
- register new wearable slots
- register new item behaviors

Plugins may not:

- replace runtime ownership
- modify SQLite directly
- duplicate runtime item logic
- bypass `transfer_item()`
- replace `MudRuntime` inventory management

## Future Compatibility

The object system must support future implementation of containers, NPC inventory, shops, crafting, banking, mail, player trading, auction houses, corpses, loot, housing storage, vehicle storage, kingdom storage, quest items, builder spawning, AI inventories, and plugin-defined inventory owners without redesigning the runtime ownership model or SQLite schema.

## Acceptance Criteria

Phase 2E is complete when:

- Characters own persistent inventory.
- Rooms own persistent item instances.
- Equipment persists across sessions.
- `inventory`, `inv`, and `i` work.
- `equipment` and `eq` work.
- `get`, `take`, `drop`, `wear`, `remove`, `wield`, `unwield`, `hold`, `look <object>`, and `examine` work.
- Room rendering displays real runtime objects.
- Starter items are supported.
- SQLite stores runtime item instances.
- EventBus publishes item events.
- Web and telnet both use the same runtime object system.
- Focused Smart MUD tests pass.
- The runtime is the sole owner of item state.
- Every ownership transfer passes through `transfer_item()`.
- Every object command uses the canonical runtime API.
- Plugins cannot bypass runtime ownership.
- Builder Mode remains compatible with runtime ownership.
- Room rendering follows the documented render order.
- Equipment rules enforce slot conflicts correctly.
- Future systems can reuse this architecture without schema redesign.

Combat, AI, Builder Mode gameplay, crafting, shops, quests, and spells remain intentionally unimplemented.

## Phase 2E Implementation Notes

The initial Phase 2E runtime implementation keeps item ownership in `MudRuntime` and persists mutable runtime item instances in SQLite `item_instances`. Compatibility tables from earlier phases may still exist, but item commands use the canonical runtime item API rather than writing ownership rows directly.

World package item records are normalized at load time into immutable template mappings. Legacy Shattered Realms fields such as `type`, `slot`, and `description` are normalized to `item_type`, `wear_slots`, and `long_description` without mutating package records during command execution.

Plugins may observe EventBus item events in this phase. A full plugin item-behavior API is intentionally deferred, and plugins must not bypass `MudRuntime` ownership APIs.

## Item rendering note

Item behavior and ownership remain unchanged by semantic color rendering. Web displays should wrap inventory, equipment, and room-object names in semantic item roles (`object`, `equipment_item`, or rarity roles such as `item_common`, `item_uncommon`, `item_rare`, and `item_epic`) so CSS presets can style them. Telnet/plain clients receive stripped or ANSI-rendered text and must not receive HTML spans.

### Item semantic color roles

Item names shown in rooms, inventory, and equipment should use semantic roles rather than fixed colors. Room objects use `object` or rarity roles (`item_common`, `item_uncommon`, `item_rare`, `item_epic`, `item_legendary`), and equipped names use `equipment_item`; telnet output must remain HTML-free.

## Phase 4A Builder Foundation

Smart MUD supports an in-game Builder foundation for authorized `builder`, `admin`, and `owner` roles. Builder commands are registered in the command registry and are hidden from normal players. Draft edits are persisted under `worlds/<world_id>/builder/` rather than being written directly to live world package files.

The Builder workspace uses `audit`, `history`, `snapshots`, `exports`, `imports`, and `templates` folders. Room, exit, feature, item template, entity template, and spawn edits go through Builder services so runtime validation and permission checks remain authoritative. `builder validate` checks draft consistency; `builder save` creates a safe export; `builder reload` reloads drafts where safe; `builder snapshot` captures the current draft state; and `builder history` reads audit records.

Future work may add a richer semantic web Builder UI and AI-assisted Builder tools, but Phase 4A intentionally does not add AI Builder, combat, quests, shops, or spellcasting.

## Bulk Item Commands

`get all`, `take all`, `get everything`, and `take everything` resolve the current room's visible portable item instances and move each eligible instance once through the runtime item-transfer path. NPCs, mobs, exits, and nonportable Builder scenery are ignored. Duplicate names are separate instances: `get iron` takes one deterministic matching Iron Sword, while `get all` takes every portable Iron Sword and other portable item in room order with stable instance ordering.

`drop all` and `drop everything` move carried, unequipped inventory items to the current room without changing item instance IDs. Equipped items are skipped and reported so bulk drop cannot silently delete, duplicate, or unequip gear. `get all` does not disturb equipped items.

Seeded room objects are created once per world/room/template seed key. Looking, moving away and back, saving, or reloading must not reseed collected items or multiply dropped items. Explicit zone or room reset behavior remains a future system.

## Phase 5A runtime content synchronization

Phase 5A establishes one canonical runtime truth. Item templates and entity templates are definitions only; `item_placements` and `spawns` are declarations; SQLite item/entity rows are live instances. Room rendering, look/examine, get/take, diagnostics, and future perception use canonical runtime room contents. Shared `feature_refs` resolve nonportable scenery alongside local room `features`. Blacksmith Stall now uses an anvil feature, two materialized Iron Sword item instances, one materialized Training Sword item instance, and one materialized Blacksmith Harl entity instance.

## Phase 5E equipment modifier bridge

Item templates may declare immutable `modifiers`. Only SQLite item instances whose runtime owner is `equipment` activate those declarations. The runtime modifier source includes the item instance ID and template ID; inventory and room items do not contribute.

## Phase 7A reward item delivery

Reward item delivery is centralized in `engine.rewards.RewardService`. Item rewards resolve as `RewardEntry` rows and create canonical runtime item instances through `MudRuntime.spawn_item()` when a runtime is available, or through the store item-instance API in legacy contexts. Reward packet and entry ids are stored with item metadata/custom flags so retries can detect already-created instances instead of duplicating items. Templates remain immutable.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.

## Phase 7C crafting integration

Phase 7C adds `engine.crafting.CraftingService` as the single canonical crafting and production service. Recipes are Builder/world-package data; exact runtime item instances are selected and reserved; jobs persist in SQLite and advance by world time; costs use EconomyService; outputs use RewardService; profession rewards use canonical profession/progression state; and crafted item instances retain quality and provenance without mutating item templates. Salvaging and refining are normal recipe types, while quests, final trainers, autonomous AI production, random affixes, auction houses, and final enchantment remain outside this phase.


## Phase 10A Written Content Integration

Written communication and readable content now route through `engine.written_content.WrittenContentService`. The canonical model is document instance -> immutable content version -> owner/placement/access -> delivery or publication -> read state -> audit. Integrations should call the service instead of writing mail, board, book, note, journal, or sign rows directly. Postage and service fees are quoted/settled through `EconomyService`; organization and faction decisions remain delegated to their canonical services; quest and achievement progress consumes written-content events.

Builder/world packages may include written document, content, access, retention, render, sanitization, mail service, board, posting, moderation, readable item, book, and journal profile collections. External messaging, unrestricted markup, executable links, arbitrary file attachments, AI-generated authoritative mail, and cross-server messaging remain forbidden.

## Phase 10B Property Integration

Smart MUD now includes the canonical `PropertyService` (`engine.property`) for Builder-authored property definitions, SQLite property instances, leases, access grants, property storage containers, actor home locations, and immutable property audit events. Related systems should integrate by service boundary: EconomyService for money, OrganizationService/FactionService for membership and reputation checks, WrittenContentService for notices, Quest/Achievement systems via property events, and canonical item instances for storage.
