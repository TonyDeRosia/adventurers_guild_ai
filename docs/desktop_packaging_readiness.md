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
- **Installer-layout validation**
  - Runtime now validates packaged layout requirements for:
    - `runtime_bundle/comfyui`
    - `runtime_bundle/workflows/scene_image.json`
    - `runtime_bundle/workflows/character_portrait.json`
  - Runtime reports optional embedded Python (`runtime_bundle/python_embeded/python.exe`) as present/missing without marking layout invalid.
- **Start/stop bundled image engine from app**
  - Bundled launch now performs packaged-layout validation before process spawn.
  - Launch fails early with actionable setup messages when required packaged assets are missing.
  - Start path still resolves through validated/app-controlled configuration with explicit launch target logging.
  - Stop endpoint is exposed to shutdown managed ComfyUI from setup UI flows.
- **Native file/folder pickers**
  - Routed through desktop capability layer with environment-aware availability checks.
- **Open official download pages**
  - Routed through backend desktop integration (`/api/setup/open-external-url`) with browser fallback in frontend.

## First-run status model
The runtime now emits first-run state buckets:
- app installed (packaged desktop detected / source mode)
- text AI ready/not ready
- packaged app files present/missing (`runtime_bundle`)
- image bundle ready/missing (`runtime_bundle/comfyui`)
- bundled workflows present/missing (scene + character workflow templates)
- embedded Python present/missing (optional)
- installer layout valid/invalid/not_packaged
- model folder selected/missing
- text-only mode active/inactive

## Installer work still required outside the app
- Place bundled ComfyUI runtime under `<install_root>/runtime_bundle/comfyui` (**required**).
- Place bundled workflow templates under `<install_root>/runtime_bundle/workflows` (**required**):
  - `scene_image.json`
  - `character_portrait.json`
- Ensure launcher executable and static assets are co-located per runtime expectations.
- Optionally include embedded Python runtime under `<install_root>/runtime_bundle/python_embeded/python.exe` (**optional but recommended** for no-PATH launch).

## Future installer disk layout requirements
- `<install_root>/AdventurerGuildAI(.exe)`
- `<install_root>/runtime_bundle/comfyui/...`
- `<install_root>/runtime_bundle/workflows/scene_image.json`
- `<install_root>/runtime_bundle/workflows/character_portrait.json`
- `<install_root>/runtime_bundle/python_embeded/python.exe` (optional)
- User data root created at first run (or pre-created):
  - `<user_data>/config/app_config.json`
  - `<user_data>/saves/`
  - `<user_data>/logs/`
  - `<user_data>/generated_images/`

## Non-goals honored
- No gameplay logic changes.
- No image prompt generation logic changes.
- No automatic third-party model downloads were introduced.

## Packaged build implementation status
- PyInstaller onedir build now uses a checked-in spec at `packaging/windows/AdventurerGuildAI.spec`.
- Spec bundles `data/`, `app/static/`, and `packaging/windows/runtime_bundle/` into the desktop payload.
- Build script now invokes the spec directly and keeps pre/post distribution audits in place.
- Runtime bundled-path resolution in frozen mode now supports both `<install_dir>/runtime_bundle` and `_MEIPASS/runtime_bundle` fallback.
- Added tests for packaged runtime path resolution behavior (`tests/test_pathing_packaged.py`).
