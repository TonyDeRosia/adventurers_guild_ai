# Guildlands Runtime Acceptance Guide

Phase 11F Part 4 certifies the Guildlands starter vertical slice through the real Smart MUD runtime rather than a parallel harness. The acceptance path is intentionally conservative: command routing enters `MudRuntime`, command metadata comes from the canonical `CommandRegistry`, content is loaded from the Builder/world-package JSON collections, runtime state is SQLite-authoritative, and gameplay side effects are emitted on the shared `EventBus`.

## Complete Guildlands Walkthrough

1. Launch Smart MUD and select `shattered_realms`.
2. Create a new player character; the manifest starting room is `guildhall_crossing_square`.
3. Use normal commands only: `look`, movement, `inventory`, `equipment`, `score`, `quests`, `journal`, `talk`/`greet`, `accept`, `progress`, `gather`/`harvest`, `turnin`, `kill`/`attack`, `loot`, `skin`, `butcher`, `cook`, `eat`, `drink`, `shop`, `sell`, `rent`/`property rent`, `sleep`, `wake`, `home`, `property`, `storage`, and `save`.
4. Complete the Emberleaf quest, then the wolf-pelts trail, then cook and consume food, sell surplus materials, rent an inn room, sleep, save, restart, reconnect, and verify the same character, room, inventory, currencies, quest state, needs, rental state, and audit history remain present.

## Vertical Slice Certification

Certification requires these canonical services to participate without replacement logic: Actor architecture, Formula Engine, Combat, Abilities, Combat Behavior, Progression, Rewards, Economy, Crafting, Gathering, Survival Needs, Cooking, Property, Environment, Perception, Training, Quest System, Conversation System, Faction System, Organization System, Builder, World Packages, SQLite runtime authority, and EventBus.

## Restart Validation

After `save`, shut down the runtime and instantiate it again against the same user-data directory. Re-enter the same character and validate SQLite-restored state for character location, carried and equipped items, currency ledger, quest journal/objective progress, gathered/depleted nodes, corpse extraction rows, cooked food freshness/servings, survival needs, rented room/property access, reward history, and command scrollback.

## EventBus Gameplay Flow

The expected once-only event chain is conversation -> quest accepted -> gathering completed -> quest updated -> combat completed -> corpse generated -> corpse extracted -> cooking completed -> consumption completed -> reward delivered -> economy transaction -> property rental -> sleep -> restart -> state restored. Idempotency belongs to the canonical service that owns each state table, not to command adapters.

## Builder Runtime Checklist

All rooms, NPCs, dialogue, quests, objectives, reward packets, items, recipes, loot, gathering nodes, corpse extraction profiles, campfires, shops, properties, journal text, and descriptions must remain Builder/world-package authored. Runtime commands may resolve, validate, and execute those records but must not hardcode starter content.

## Persistent Gameplay Checklist

SQLite is the runtime authority. Acceptance checks must inspect the service-owned tables for quest instances/objectives/history, resource node instances/sessions/results/extractions, crafting and cooking jobs/results, survival consumption/rest state, economy quotes/transactions/ledger, property instances/leases/access/storage, reward claims/history, and character/inventory/equipment rows.
