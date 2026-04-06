# Adventurer's Guild AI (Phase 2 Foundation)

A local-first, modular AI campaign engine for terminal-first fantasy play.

## Design principles

- **Modular first:** every major subsystem is isolated and replaceable.
- **Rules separate from narration:** combat math and dice logic live in `rules/`, while storytelling prompts live in `prompts/` and model adapters in `models/`.
- **Data-driven content:** enemies, items, dialogue trees, and world hooks live under `data/` instead of being hardcoded into the engine.
- **Save-safe evolution:** state schema changes are additive and old saves are upgraded at load time.
- **Local model ready:** mock/null narration path works without external dependencies.

## Folder structure

```text
app/
  main.py
engine/
  campaign_engine.py
  content_repository.py
  dialogue_service.py
  world_content_service.py
  game_state_manager.py
  save_manager.py
  entities.py
  character_sheet.py
  inventory.py
memory/
  npc_memory.py
  world_state.py
  quest_tracker.py
rules/
  dice.py
  combat.py
models/
  base.py
  provider.py
  registry.py
  ollama_adapter.py
  gpt4all_adapter.py
prompts/
  templates.py
  renderer.py
data/
  sample_campaign.json
  dialogues.json
  enemies.json
  items.json
  world_content.json
  saves/
tests/
  test_rules_and_save.py
  test_campaign_features.py
```

## Quick start

### Requirements

- Python 3.10+

### Run (exact commands)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip pytest
python -m app.main
```

## Terminal commands

- `help`
- `look`
- `move <location_id>`
- `talk <npc_id>`
- `choose <number>`
- `attack`
- `rest`
- `status`
- `inventory`
- `use <item>`
- `equip <item>`
- `take <item>` / `drop <item>`
- `quests`
- `sheet`
- `save` / `load`
- `exit`

## Phase 2 foundation additions

### Dialogue choices

- NPC dialogue graphs with multiple choice responses via `data/dialogues.json`.
- Choices can update quest status, relationships, world flags, and grant item rewards.
- `talk <npc_id>` remains the entry point; `choose <number>` layers branching choices on top.

### Enemy definitions

- Enemy stats and encounter text are in `data/enemies.json`.
- The Bone Warden encounter now uses the structured enemy definition and reward metadata.

### Inventory + equipment (minimal slots)

- Items are defined in `data/items.json` with stable IDs and display names.
- Character inventory now persists both:
  - `inventory` (display names, compatibility)
  - `inventory_item_ids` (stable internal IDs)
- Equipment is intentionally minimal:
  - one `weapon` slot
  - one `trinket` slot

### Expanded world + second quest

- Added location: `brindlewatch_outpost`.
- Added NPC: `captain_mirel`.
- Added quest: `q_supply_line` (recover and return a sealed supply crate).

### World flags + consequences

- Generic scalable flag map in `world_flags`.
- Example branching consequence:
  - Elder Thorne dialogue choices set trust/approach flags.
  - Later status and interactions reflect those earlier flags.

### Model adapter scaffold

- Added `models/provider.py` with:
  - `NarrationRequest`
  - `NarrationProvider` protocol
  - deterministic `MockNarrationProvider`
- Engine now has a clean provider-backed call path while still working entirely offline.

### Prompt organization

Prompt rendering is lightweight and split into:

- system tone
- profile tone
- scene context
- player state summary

## Save format changes (additive)

The following fields were added without removing legacy fields:

- `player.inventory_item_ids: list[str]`
- `player.equipped_weapon_id: str | null`
- `player.equipped_trinket_id: str | null`
- `active_dialogue: { npc_id, node_id } | null`
- `world_flags` expanded to a generic key/value store (not just booleans)

### Backward compatibility behavior

When loading older saves, `GameStateManager` applies additive defaults for:

- missing new player fields
- missing quests/NPCs/locations introduced in this phase
- missing default world flags

Legacy inventories with only display names remain valid and are mapped into stable item IDs at runtime.

## Tests

Run all tests:

```bash
python -m pytest -q
```

Includes deterministic checks for:

- dialogue branching effects
- inventory use/equip behavior
- second quest progression
- save/load compatibility with new fields
- combat + persistence roundtrip
