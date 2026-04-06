# Adventurer's Guild AI

A local-first, modular fantasy campaign engine with:
- Existing terminal gameplay loop (preserved)
- New additive local web chat scaffold
- Optional image generation architecture via workflow templates
- Campaign memory + retrieval + analysis mode

## Install

```bash
python -m pip install -r requirements.txt
```

## Run terminal mode (existing flow)

```bash
python -m app.main
```

Alternative launcher:

```bash
python run.py
```

## Run web UI mode (new additive flow)

```bash
python -m app.web
```

Then open: <http://127.0.0.1:8000>

## Terminal mode and web mode coexistence

- Terminal mode remains unchanged and continues to use `app.main` + `CampaignEngine` directly.
- Web mode is a separate entrypoint (`app.web`) that reuses the same backend `CampaignEngine` and `GameStateManager`.
- No gameplay rules were moved into frontend files; UI is presentation/API only.
- Save files remain under `data/saves` and are shared across both modes.

## Web UI architecture scaffold

The web UI is intentionally lightweight and dependency-minimal:

- `app/web.py`
  - static file hosting
  - API routes
  - in-memory message presentation history for chat rendering
- `app/static/index.html`
  - left sidebar (campaign slots)
  - center chat panel
  - bottom input bar
  - right panel placeholder (state/image preview)
- `app/static/styles.css`
  - clean chat-style panel layout
- `app/static/app.js`
  - minimal frontend state/render loop for local API calls

### API routes

- `POST /api/campaign/input`
  - send player input to the campaign engine
- `GET /api/campaign/state`
  - fetch current campaign state summary
- `POST /api/campaign/start`
  - start a new campaign or load a save slot
- `GET /api/campaign/messages`
  - fetch current session message history
- `GET /api/campaign/saves`
  - list save slots
- `POST /api/images/generate`
  - request image generation for a selected workflow template

## Image generation scaffold

Image generation is kept separate from narration/rules systems.

### Core modules

- `images/base.py`
  - image adapter interface
  - request/response dataclasses
  - null adapter fallback
- `images/comfyui_adapter.py`
  - ComfyUI adapter scaffold (`/prompt` submission)
- `images/workflow_manager.py`
  - workflow template loader from files
  - prompt/token injection utilities
  - node input override support

### Workflow templates

Workflow JSON templates live in `data/workflows/`:

- `scene_image.json`
- `character_portrait.json`

Templates support token injection such as:

- `{{prompt}}`
- `{{negative_prompt}}`
- `{{seed}}`
- `{{steps}}`
- `{{cfg}}`

Runtime parameters can also patch node input fields via `node_updates`.

## Workflow template structure

Expected shape (simplified):

```json
{
  "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}"}},
  "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative_prompt}}"}},
  "meta": {"template_type": "scene_image"}
}
```

## Configure local image generation

By default, web mode uses a null image adapter (safe fallback).

To wire ComfyUI in later phases:

1. Run ComfyUI locally (default expected URL: `http://localhost:8188`)
2. Instantiate and set `ComfyUIAdapter` in `WebRuntime`.
3. Keep using workflow files in `data/workflows/` for template-driven prompts.

## Core campaign intelligence flow (local-first)

## NPC personality graph system (new)

NPC behavior now includes a modular, data-driven personality layer loaded from `data/npc_personalities.json`.

### NPC profile structure

Each profile contains:

- identity
- core_traits
- values
- fears
- desires
- speech_style
- faction_ties
- moral_tendencies
- state_defaults
- evolution_rules

Two current NPCs are refactored to use this profile system:

- `elder_thorne`
- `warden_elira`

### Dynamic state

Every NPC now persists additive state fields:

- `trust_toward_player`
- `fear_toward_player`
- `stress`
- `hope`
- `anger`
- `loyalty`
- `instability`

State is clamped and updated by dialogue effects, explicit personality events, and profile evolution rules.

### Memory flow (NPC-specific)

NPCs now track structured memory entries (`memory_log`) with:

- event_type
- summary
- turn
- world_event_id (optional)
- player_action (optional)
- impact map
- tags

Memories are appended as interactions occur and are used by behavior evaluation and evolution thresholds.

### Evolution rule flow

Evolution rules live in profile data and can trigger from events such as:

- quest completion
- player betrayal
- faction conflict
- village danger
- repeated kindness/cruelty

Rules can:

- modify dynamic state
- unlock behavior tags (used by dialogue conditions)
- record a milestone memory

### Behavior evaluation layer

Before dialogue output, NPC responses are evaluated from:

- profile moral tendencies + speech style
- current dynamic state
- recent memory signals (e.g., betrayal)
- scene context
- active world/quest context (via event-driven state updates)

Evaluation modifies tone framing, willingness to share, hostility/friendliness, and quest openness.

### Memory flow

The engine now tracks five additive memory layers in save-compatible state:

- `recent_memory`: short rolling context from the latest turns
- `long_term_memory`: structured entries (quest/NPC/world/summary categories)
- `session_summaries`: compact milestone summaries for reuse
- `unresolved_plot_threads`: open hooks to revisit
- `important_world_facts`: durable world truths for continuity

Memory is updated automatically after each turn, and save checkpoints are also recorded as summaries.

### Retrieval flow

Before narration generation, a retrieval pipeline ranks and gathers context by:

- current location
- active quests
- current NPC focus
- recent actions
- important world-state flags

The selected memory snippets are assembled into the prompt as a dedicated `[Memory Context]` layer.

### Summary flow

Summaries are generated for important actions (movement, combat, dialogue, quest changes) and save events.
Each summary is compact and structured with turn, trigger, location, related quest IDs, and optional NPC/world references.

### Analysis mode

Use terminal command `analyze <question>` for campaign intelligence queries, for example:

- `analyze summarize my campaign so far`
- `analyze what quests are active`
- `analyze what does this npc think of me`
- `analyze what happened recently`
- `analyze what choices are affecting the world`

Use `summarize` for a quick campaign state digest.

### Prompt assembly layers

Prompt construction is now explicitly layered:

1. system role
2. campaign tone
3. content settings (narration-only maturity/tone layer)
4. requested mode (`play`, `summarize`, `analyze`)
5. memory context
6. scene context
7. player state summary

## Updated terminal command flow

- Existing commands remain available (`look`, `move`, `talk`, `attack`, etc.)
- New commands:
  - `summarize`
  - `analyze <question>`
- Output now uses a lightweight chat-style presentation:
  - player (`🧭 You`)
  - narrator (`📜 Narrator`)
  - npc (`🗣️ NPC`)
  - quest updates (`📌 Quest`)
  - system (`⚙️ System`)

## Existing game systems (preserved)

- Save/load
- Dialogue trees + choice handling
- Quests
- Enemy encounters/combat
- Inventory/stats
- World state + faction/relationship tracking
- Model adapter scaffold
- Save compatibility with additive memory fields

## Run tests

```bash
python -m pytest -q
```
