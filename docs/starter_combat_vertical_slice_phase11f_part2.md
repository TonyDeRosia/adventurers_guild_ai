# Phase 11F Part 2: Guildlands Starter Combat Vertical Slice

This slice extends the Guildlands starter path from the Emberleaf gathering errand into a complete first combat loop without adding replacement gameplay systems.

## Starter Combat Flow

1. Complete `guildlands_emberleaf_errand` for Guild Registrar Maren.
2. Accept `guildlands_wolf_pelts` from the same Builder-authored Maren conversation.
3. Travel north from `old_gate_road` to `emberwood_hunting_trail`.
4. Use the existing player commands (`consider`, `attack`/`kill`, `score`, `loot`, `get`, `inventory`, `equipment`, `quests`, `journal`, `talk`, `turnin`) against the runtime actor and command services.
5. Defeat `forest_wolf` using the canonical Combat and Combat Behavior foundations.
6. Let canonical death, corpse, RewardService loot, quest EventBus routing, turn-in, and reward delivery complete the loop.

## Combat Quest Integration

`guildlands_wolf_pelts` is Builder-authored content. Its objectives are data records:

- `guildlands_wolf_pelts_kill_one` listens for a `kill_template` objective matched by the `enemy_killed` EventBus alias and `target_actor_template_id=forest_wolf`.
- `guildlands_wolf_pelts_obtain_pelt` listens for a `collect_item` objective matched by `quest_item_obtained`, `item_collected`, or `corpse_looted` and `item_template_id=wolf_pelt`.

Quest progress remains automatic through `QuestEventRouter` and `QuestService.process_quest_event`.

## Corpse and Loot Flow

`forest_wolf` references `starter_wolf_death_loot`, `starter_wolf_treasure`, `wolf_common_loot`, and `standard_mob_corpse`. Loot resolution remains in RewardService and includes:

- guaranteed quest item: `wolf_pelt`
- guaranteed crafting material: `torn_hide`
- currency: `copper`
- rare equipment roll: `training_dagger`

Corpse persistence continues to use the existing SQLite corpse tables and decay fields. Duplicate event and reward delivery protection is provided by the existing unique quest-event and reward claim records.

## Combat EventBus Integration

Phase 11F Part 2 adds EventBus aliases to the existing quest objective family rather than adding a new quest system:

- `enemy_killed` → kill objectives
- `corpse_looted` → collect/custom objectives
- `item_collected` → collect/possess objectives
- `quest_item_obtained` → collect/possess objectives

## Guildlands Combat Vertical Slice Content

The slice adds only one room and one enemy:

- Room: `emberwood_hunting_trail`
- Enemy: `forest_wolf`
- Combat behavior: `wolf_pack`
- Ability loadout: `wolf_basic`
- Natural weapon: `wolf_bite`

The route is intentionally small: Guildhall Crossing → Old Gate Road → Emberwood Hunting Trail → return to Maren.

## Restart Persistence

The regression coverage verifies quest progress, consumed events, corpse records, loot packet resolution, and turn-in state after service re-instantiation against the same SQLite database. Runtime restart behavior remains SQLite-authoritative.

## Builder Combat Authoring

Builder owns the vertical-slice records: enemy definition, spawn/room placement, behavior references, loot/death/corpse profiles, quest definitions, quest objectives, reward references, and dialogue branches. Future edits should alter Builder JSON data, not add code paths.
