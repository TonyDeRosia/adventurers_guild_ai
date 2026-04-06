# Adventurer's Guild AI

A local-first, modular fantasy campaign engine with:
- Existing terminal gameplay loop (preserved)
- New additive local web chat scaffold
- Optional image generation architecture via workflow templates

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

## Existing game systems (preserved)

- Save/load
- Dialogue trees + choice handling
- Quests
- Enemy encounters/combat
- Inventory/stats
- World state + faction/relationship tracking
- Model adapter scaffold

## Run tests

```bash
python -m pytest -q
```
