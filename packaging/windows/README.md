# Windows desktop packaging path (v1 packaged-build baseline)

This document is the build/distribution contract for the first real Windows packaged desktop output.

## Build pipeline

1. Run a packaging audit against `packaging/windows/runtime_bundle`.
2. Build a PyInstaller **onedir** package from `packaging/windows/AdventurerGuildAI.spec`.
3. Run a post-build distribution audit against `dist/AdventurerGuildAI`.
4. Wrap `dist/AdventurerGuildAI` with Inno Setup.

### Exact commands (from repo root)

```bat
tools\build_exe.bat
tools\build_installer.bat
```

Equivalent direct PyInstaller invocation (when debugging spec edits):

```bat
py -3 -m PyInstaller --noconfirm --clean packaging\windows\AdventurerGuildAI.spec
```

The spec resolves the repo root from PyInstaller's execution context (`SPEC`/working directory), so it does not depend on `__file__` being defined.


## One-click launcher (recommended for non-technical packaging)

Use the repository-root GUI launcher:

```bat
Build_AdventurersGuildAI.py
```

Optional compatibility launcher:

```bat
Build_AdventurersGuildAI.bat
```

What the GUI launcher does:

1. Uses a native folder picker to choose the output folder.
2. Exposes point-and-click actions for **Build EXE**, **Build Installer**, and **Build Everything**.
3. Reuses `tools\build_exe.bat` and `tools\build_installer.bat` without replacing their packaging logic.
4. Enforces build-mode prerequisites: EXE mode does not require Inno Setup, Installer/Everything do.
5. Streams build output into a live scrolling GUI log and writes the same output to a persistent log file.
6. Copies resulting build artifacts into the selected output folder and prints the final installer path clearly when produced.
7. Shows clear success/error status in the app window and enables an **Open output folder** action after successful builds.

## PyInstaller bundle inputs

The spec includes these required runtime/application assets:

- `data/` (authored game/runtime content)
- `app/static/` (frontend assets)
- `packaging/windows/runtime_bundle/` (installer-aware runtime scaffolding)

The spec intentionally does **not** include model checkpoints. `tools/audit_distribution.py` blocks checkpoint/model artifacts from packaged paths.

## Expected `dist` output layout

After `tools\build_exe.bat`, expect:

- `dist/AdventurerGuildAI/AdventurerGuildAI.exe`
- `dist/AdventurerGuildAI/app/static/*`
- `dist/AdventurerGuildAI/data/*`
- `dist/AdventurerGuildAI/runtime_bundle/README.txt`
- `dist/AdventurerGuildAI/runtime_bundle/comfyui/README.txt`
- `dist/AdventurerGuildAI/runtime_bundle/workflows/scene_image.json`
- `dist/AdventurerGuildAI/runtime_bundle/workflows/character_portrait.json`
- `dist/AdventurerGuildAI/runtime_bundle/THIRD_PARTY_NOTICES.txt`
- `dist/AdventurerGuildAI/runtime_bundle/licenses/ComfyUI-LICENSE-MIT.txt`

## Runtime pathing contract (source vs frozen)

- Source mode resolves bundled runtime scaffolding at `packaging/windows/runtime_bundle`.
- Frozen mode first resolves bundled runtime scaffolding at `<install_dir>/runtime_bundle`.
- Frozen fallback allows `_MEIPASS/runtime_bundle` when running directly from raw PyInstaller output.
- Bundled workflows resolve from bundled runtime first, then fall back to `data/workflows`.

## Local packaged-mode verification before installer stage

1. Build executable output:
   - `tools\build_exe.bat`
2. Launch packaged executable:
   - `dist\AdventurerGuildAI\AdventurerGuildAI.exe`
3. Verify startup log prints runtime root/user data and server starts.
4. Open setup status (in app UI) and confirm installer-layout checks see:
   - `runtime_bundle`
   - `runtime_bundle/comfyui`
   - both bundled workflow JSON files

Optional portable-data smoke test:

```bat
set ADVENTURER_GUILD_AI_PORTABLE=1
dist\AdventurerGuildAI\AdventurerGuildAI.exe
```

## Installer handoff prep (Inno Setup)

Installer must copy the full `dist/AdventurerGuildAI/*` tree into:

- `C:\Program Files\AdventurerGuildAI\`

### Required files/folders to copy

- `AdventurerGuildAI.exe`
- `app/static/*`
- `data/*`
- `runtime_bundle/comfyui/*` (runtime scaffold; actual runtime payload may be populated during release prep)
- `runtime_bundle/workflows/scene_image.json`
- `runtime_bundle/workflows/character_portrait.json`
- `runtime_bundle/THIRD_PARTY_NOTICES.txt`
- `runtime_bundle/licenses/ComfyUI-LICENSE-MIT.txt`

### Desktop/start-menu expectations

Installer should create:

- Start Menu shortcut to `AdventurerGuildAI.exe`
- Optional desktop shortcut to `AdventurerGuildAI.exe`

On launch, app should start web backend and open the native PyWebView desktop window automatically.

## What remains for installer-wrapper step

- Finalize product metadata/versioning in `installer/AdventurerGuildAI.iss`.
- Sign installer + executable (release policy dependent).
- Package/ship any legally distributable external runtime payloads under `runtime_bundle/comfyui`.
- Publish installer artifact from `installer/Output/AdventurerGuildAI_Setup.exe`.
