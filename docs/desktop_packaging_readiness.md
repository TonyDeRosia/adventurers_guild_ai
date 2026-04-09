# Desktop Packaging Readiness Audit (Phase: Runtime Orchestration)

## Scope
This document covers setup/runtime/desktop integration only. Gameplay systems are intentionally out of scope.

## Startup flow audit
- Launcher initializes user-writable paths under user data and starts web runtime (`run.py`, `app/pathing.py`).
- Web runtime now reports desktop capabilities explicitly (`/api/desktop/capabilities`).
- Setup readiness now includes a first-run status model for packaged onboarding.

## Packaging-ready behaviors implemented
- **App launch**
  - Detects source vs frozen desktop runtime mode using a dedicated desktop capability layer.
- **Config storage**
  - Uses app-controlled writable user data roots (`config`, `saves`, `logs`, `generated_images`) via `initialize_user_data_paths`.
- **Bundled ComfyUI runtime detection**
  - Uses bundled runtime directory resolution and first-run status surfacing.
- **Start/stop bundled image engine from app**
  - Start path now resolves through validated/app-controlled configuration with explicit launch target logging.
  - Stop endpoint is exposed to shutdown managed ComfyUI from setup UI flows.
- **Native file/folder pickers**
  - Routed through desktop capability layer with environment-aware availability checks.
- **Open official download pages**
  - Routed through backend desktop integration (`/api/setup/open-external-url`) with browser fallback in frontend.

## First-run status model
The runtime now emits first-run state buckets:
- app installed (packaged desktop detected / source mode)
- text AI ready/not ready
- image bundle ready/missing
- model folder selected/missing
- text-only mode active/inactive

## Installer work still required outside the app
- Place bundled ComfyUI runtime under `<install_root>/runtime_bundle/comfyui`.
- Place bundled workflow templates under `<install_root>/runtime_bundle/workflows`.
- Ensure launcher executable and static assets are co-located per runtime expectations.
- Optionally include embedded Python runtime adjacent to ComfyUI (`python_embeded/python.exe`) for robust no-PATH launch.

## Future installer disk layout requirements
- `<install_root>/AdventurerGuildAI(.exe)`
- `<install_root>/runtime_bundle/comfyui/...`
- `<install_root>/runtime_bundle/workflows/scene_image.json`
- `<install_root>/runtime_bundle/workflows/character_portrait.json`
- User data root created at first run (or pre-created):
  - `<user_data>/config/app_config.json`
  - `<user_data>/saves/`
  - `<user_data>/logs/`
  - `<user_data>/generated_images/`

## Non-goals honored
- No gameplay logic changes.
- No image prompt generation logic changes.
- No automatic third-party model downloads were introduced.
