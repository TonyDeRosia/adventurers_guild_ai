# Adventurer's Guild AI (Expanded Terminal Foundation)

A local-first, modular AI campaign engine for D&D-style fantasy play.

## Quick Start

```bash
python -m pip install -r requirements.txt
python -m app.main
```

Alternative launcher:

```bash
python run.py
```

## What this phase adds

This update extends the existing terminal MVP loop without replacing startup flow or core architecture.

- Data-driven **NPC dialogue trees** with branching player choices.
- Data-driven **enemy definitions** (Bone Warden now loaded from `data/enemies.json`).
- Expanded **item + inventory system** with consumables, quest items, and equipable trinkets.
- Lightweight **player stats layer** (`strength`, `agility`, `intellect`, `vitality`) integrated into combat and item modifiers.
- Expanded **combat actions**: `defend`, `ability`, and `flee` alongside the existing `attack`.
- **Faction reputation** tracking (`town`, `guild`, `unknown`) with dialogue and quest availability hooks.
- **Relationship tiers** (`hostile`, `neutral`, `friendly`, `loyal`) derived from disposition and used in branching logic.
- **Branching quest outcomes** (`combat`, `dialogue`, `item`) persisted in state for future consequences.
- Simple **world event/consequence log** for triggered aftermath states.
- Lightweight enemy behavior types (`aggressive`, `defensive`, `reckless`) driving turn-to-turn AI flavor.
- A second location (`whispering_woods`) and a second quest (`q_moonlantern_oath`) with a new NPC (`warden_elira`).
- **World flags** that carry consequences into later interactions.
- Lightweight **model provider scaffold** for future local backends, while still working fully offline.
- Cleaner narration prompt organization separating system tone, campaign tone, scene context, and player state summary.
- Campaign-level `content_settings` for local narration controls (tone, maturity level, thematic flags).

## Folder structure

```text
app/
  main.py
engine/
  campaign_engine.py
  game_state_manager.py
  save_manager.py
  entities.py
  character_sheet.py
  inventory.py
  content_registry.py      # Data loader for dialogues/enemies/items
  dialogue_service.py      # Dialogue node/choice runner
memory/
  npc_memory.py
  world_state.py
  quest_tracker.py
rules/
  dice.py
  combat.py
models/
  base.py
  provider.py              # Future-facing narration provider scaffold
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
  saves/
tests/
  test_rules_and_save.py
  test_campaign_extensions.py
```

## Current playable content

- Locations: `moonfall_town`, `moonfall_catacombs`, `whispering_woods`
- NPCs: `elder_thorne`, `warden_elira`
- Quests:
  - `q_catacomb_blight` (Silence Beneath Moonfall)
  - `q_moonlantern_oath` (Moonlantern Oath)
- Enemy: `bone_warden` (data-driven)

## Commands

- `help`
- `look`
- `move <location_id>`
- `talk <npc_id>`
- `choose <number>` (dialogue response)
- `attack`
- `defend`
- `ability`
- `flee`
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

## Save format notes

Save compatibility is preserved with additive fields. Older saves still load.

New additive fields include:

- `player.equipped_item_id`
- `player.strength`
- `player.agility`
- `player.intellect`
- `player.vitality`
- `active_dialogue_npc_id`
- `active_dialogue_node_id`
- `faction_reputation`
- `quest_outcomes`
- `world_events`
- `combat_effects`
- additional `world_flags` keys for branching outcomes
- `npc.relationship_tier`
- `quest.availability`
- `settings.content_settings`:
  - `tone` (narrative style such as `heroic`, `grim`, `noir`, etc.)
  - `maturity_level` (`standard` or `mature`)
  - `thematic_flags` (list of active narrative themes)

## Content settings (local-only configuration)

Content behavior is controlled entirely by each campaign's local configuration. No external service, policy endpoint, or remote moderation toggle is required for this feature.

### Where it applies

- **Applies to:** narration, dialogue framing, and scene description prompt layering.
- **Does not apply to:** combat calculations, stats, inventory effects, leveling/progression, or other rules logic.

### Campaign creation flow

When starting a new campaign, you can:

1. Enable or disable custom content settings.
2. Select campaign tone.
3. Set maturity level (`standard` or `mature`).
4. Provide thematic flags (comma-separated).

If custom content settings are disabled, the campaign falls back to a neutral defaults layer (`standard` + no thematic flags).

### Adult content support

For adult (18+) campaigns, set `maturity_level` to `mature` and add any desired thematic flags. This project keeps content handling as a configurable narration layer rather than hardcoded gameplay restrictions.

## Design principles

- Rules/math remain separated from narration and prompt construction.
- Mature/adult themes remain a tone/config layer only.
- New systems are modular and data-driven for future content growth.

## Gameplay depth systems (phase)

- **Combat math additions (deterministic):**
  - Attack hit bonus now includes strength scaling.
  - Damage receives a small strength bonus on successful hits.
  - Defend reduces incoming damage using vitality.
  - Ability attacks use intellect for improved hit/damage.
  - Flee attempts use agility as their escape modifier.
- **Quest consequences:**
  - Quest completion now stores explicit outcome mode in `quest_outcomes`.
  - Outcome flags are reused for later NPC reaction lines and world events.

## Run tests

```bash
python -m pytest -q
```
