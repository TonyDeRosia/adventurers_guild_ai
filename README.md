# Adventurer's Guild AI (Phase 1 MVP)

A local-first, modular AI campaign engine for Dungeons & Dragons style fantasy play.

## Quick Start (Windows)

### Step 1: Install Python

1. Download Python 3.10+ from: https://www.python.org/downloads/windows/
2. During install, enable **"Add Python to PATH"**.

### Step 2: Download this repository

- Click **Code → Download ZIP** and extract it, or clone with Git.

### Step 3: Double-click `run.bat`

- `run.bat` checks Python.
- On first run, it launches `setup.bat` to install dependencies.
- Then it starts the game.

That is the main path for non-technical users.

## Manual Run (all platforms)

If you prefer terminal commands:

```bash
python -m pip install -r requirements.txt
python -m app.main
```

Alternative root launcher:

```bash
python run.py
```

## Troubleshooting

- **"Python is not installed or not available in PATH"**
  - Install Python 3.10+ and re-run `run.bat`.
  - If already installed, restart terminal/Windows and try again.
- **Dependency install fails**
  - Check internet connection.
  - Run `python -m pip install --upgrade pip` then `python -m pip install -r requirements.txt`.
- **Window closes immediately after an error**
  - Run `run.bat` from Command Prompt to read full output.

## Optional: build a one-file executable

This is optional and not required for normal play.

```bash
python -m pip install pyinstaller
pyinstaller --onefile run.py
```

The executable appears in `dist/`.

## Design principles

- **Modular first:** every major subsystem is isolated and replaceable.
- **Rules separate from narration:** combat math and dice logic live in `rules/`, while storytelling prompts live in `prompts/` and model adapters in `models/`.
- **Memory separate from prompts:** campaign state and memory trackers are not mixed with prompt templates.
- **Local model ready:** null adapter included by default, with Ollama/GPT4All adapter hooks.
- **Desktop-friendly MVP:** terminal playable loop now; web UI can be added later without reworking engine core.

## Phase 1 folder structure

```text
app/
  main.py                    # Terminal entry point with minimal playable loop
engine/
  campaign_engine.py         # Turn orchestration across subsystems
  game_state_manager.py      # State lifecycle and save integration
  save_manager.py            # JSON save/load implementation
  entities.py                # Dataclasses for campaign state
  character_sheet.py         # Character progression and summary helpers
  inventory.py               # Inventory mutation service
memory/
  npc_memory.py              # NPC notes/disposition tracking
  world_state.py             # Location movement and world flag updates
  quest_tracker.py           # Quest listing/status updates/event log helpers
rules/
  dice.py                    # Dice rolling utilities
  combat.py                  # Combat resolution engine
models/
  base.py                    # Narration model adapter interface + fallback
  registry.py                # Provider factory
  ollama_adapter.py          # Ollama HTTP adapter hook
  gpt4all_adapter.py         # GPT4All integration placeholder adapter
prompts/
  templates.py               # Prompt templates
  renderer.py                # Prompt rendering from campaign state
images/
  base.py                    # Image adapter interface
  comfyui_adapter.py         # Optional ComfyUI HTTP hook
data/
  sample_campaign.json       # Starter campaign state
  saves/                     # Save slot JSON files (created/updated at runtime)
tests/
  test_rules_and_save.py     # Unit tests for combat + persistence roundtrip
```

## Useful in-game commands

- `help`
- `look`
- `move <location_id>`
- `talk <npc_id>`
- `attack`
- `rest`
- `status`
- `inventory`
- `take <item>` / `drop <item>`
- `quests`
- `sheet`
- `save` / `load`
- `exit`

## Campaign start flow

On launch, the game walks through:

1. Load autosave or start a new campaign
2. Character creation (name + class)
3. Campaign profile selection:
   - `classic fantasy`
   - `dark fantasy`
4. Mature themes toggle (tone/config only)

The mature setting changes narration style only; combat/math/state rules remain unchanged.

## Phase 1 playable content

- **Town:** `moonfall_town`
- **Questgiver:** `elder_thorne`
- **Dungeon encounter:** `moonfall_catacombs`
- **Enemy:** `Bone Warden`
- **Quest:** `Silence Beneath Moonfall`

## Run tests

```bash
python -m pytest -q
```

## Save format

- JSON persistence via `engine/save_manager.py`.
- Sample campaign schema mirrors the `CampaignState` dataclass in `engine/entities.py`.

## Model provider strategy

- Provider abstraction: `NarrationModelAdapter`.
- Current providers:
  - `null` (default deterministic fallback)
  - `ollama` (HTTP endpoint hook)
  - `gpt4all` (non-network placeholder for future SDK integration)

Switching adapters only changes engine wiring, not game state/rules code.

## Content settings

Campaign profile settings include:

- `mature_content_enabled`
- `narration_tone`
- `image_generation_enabled`

These are persisted in campaign JSON and referenced by prompt rendering.

## Roadmap

### Phase 2 – Better gameplay depth

- Multi-enemy combat encounters and turn order.
- Item stats/equipment slots and consumables.
- Skill checks and non-combat challenge resolution.
- Richer NPC relationship arcs and faction standing.
- Expanded quest state machine (branching objectives and fail states).

### Phase 3 – Local model + UI expansion

- FastAPI API layer with lightweight local web UI.
- Streaming narration responses and context windows.
- Robust Ollama/GPT4All runtime integration and adapter configuration.
- Campaign profile manager (multiple campaigns with settings UI).
- Optional scene image generation panel via ComfyUI hook.

### Phase 4 – Production hardening and ecosystem

- SQLite backend option with migration tooling.
- Plugin system for custom rulesets, worlds, and model providers.
- Deterministic replay/debug logs for balancing.
- Automated balancing tools and encounter simulation tests.
- Packaging for desktop distributions and save import/export.

## Notes for contributors

- Keep systems decoupled and additive.
- Avoid mixing rule math into prompt templates or model adapters.
- Prefer interface-driven extensions over direct cross-module coupling.
