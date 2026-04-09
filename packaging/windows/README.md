# Windows desktop packaging path (v1)

This project now ships as a **single desktop application experience**:

1. Build an onedir executable package with PyInstaller.
2. Build an installer with Inno Setup.
3. Install to `Program Files\AdventurerGuildAI`.
4. Launch one executable (`AdventurerGuildAI.exe`) from Start Menu/Desktop.

## Architecture choices

- **Freezing route:** PyInstaller `--onedir`.
  - Chosen over `--onefile` because desktop-runtime dependencies and optional support files are easier to manage and update in-place.
  - Enables bundling of app data/static assets and additional runtime scaffolding folders.
- **Installer route:** Inno Setup.
  - Already present in repo and practical for Windows end-user distribution with start menu + desktop shortcut support.

## Runtime orchestration path

`run.py` launches the web runtime. Inside `WebRuntime`:

- A dedicated `ComfyProcessManager` owns any ComfyUI process started by the app.
- Startup auto-check attempts managed ComfyUI auto-start **only when**:
  - image provider is `comfyui`
  - image features are enabled
  - path/workflow/checkpoint pipeline checks pass
- Existing running ComfyUI is detected through readiness checks; duplicate launch is avoided.
- On app shutdown, managed ComfyUI child process is terminated.

## First-run dependency flow (in-app)

Dependency readiness APIs surface specific setup states:

- ComfyUI missing / invalid path
- workflow JSON missing / invalid path
- checkpoint folder missing / invalid path
- backend not reachable
- image provider disabled (`null`) fallback

The app remains usable in text mode even when image setup is incomplete.

## What gets bundled

Bundled in PyInstaller output:

- app runtime executable + Python runtime dependencies
- `data/` authored game content
- `app/static/` frontend assets
- `runtime_bundle/` scaffold folder (optional managed assets area)

Not bundled by default:

- large checkpoint/model files (size + license constraints)
- full ComfyUI runtime payload (user may connect existing install or run guided setup)

Compliance assets bundled:

- `runtime_bundle/THIRD_PARTY_NOTICES.txt`
- `runtime_bundle/licenses/ComfyUI-LICENSE-MIT.txt`

Packaging guardrails:

- `tools/audit_distribution.py` blocks known model/checkpoint artifacts from packaging paths.
- Build scripts run audits before and/or after packaging steps.
- Audit also verifies required third-party notice/license files are present.

## Build commands

From repository root on Windows:

```bat
tools\build_exe.bat
tools\build_installer.bat
```

Installer output:

- `installer\Output\AdventurerGuildAI_Setup.exe`

## Validation checklist

1. Fresh Windows machine / VM
   - Run installer.
   - Launch app from Start Menu.
   - Confirm browser UI opens without terminal actions.
2. ComfyUI auto-start path
   - Configure image provider = `comfyui` and valid paths.
   - Relaunch app and verify image backend is automatically started or detected.
3. Text-only fallback
   - Leave image backend unconfigured.
   - Confirm campaign play remains usable and setup guidance appears in-app.

## Known limitations

- Checkpoint/model files are intentionally out-of-band (download or locate existing models).
- ComfyUI bootstrap may still require runtime dependencies and driver-specific setup on end-user machines.
- Automatic model downloads must respect third-party licenses/terms per source.
