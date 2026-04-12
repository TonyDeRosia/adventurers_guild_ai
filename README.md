# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application with a desktop-window web UI.

## Run from source (normal path)

1. Double click `run.bat` from the repository root.
2. The script checks for Python (`py -3` first, then `python`).
3. The script installs dependencies from `requirements.txt`.
4. The script runs `python run.py`.
5. `run.py` is the only runtime owner: it starts the backend once, waits for `/health`, and opens the native desktop window (PyWebView) for the local UI.

If startup fails, keep the console open and read the printed error details.

### Source startup behavior

- Native desktop window UI is the default interface.
- Terminal mode remains available only for fallback/debug usage.
- If port `8000` is already in use, `run.py` prints a clear error and exits.
- If desktop window startup fails, the launcher prints a clear error and exits.
- `app/web.py` is not a user launcher and is not part of the normal source startup path.

## Packaged EXE build workflow (Windows)

For normal packaged EXE builds, use exactly one root script:

```bat
Build_AdventurersGuildAI.bat
```

What to click from repo root:
- `run.bat` = run from source
- `Build_AdventurersGuildAI.bat` = build packaged EXE

Internal/developer scripts still exist for advanced packaging tasks and automation, but they are not the normal human entry point:
- `tools\build_exe.bat` (internal worker called by `Build_AdventurersGuildAI.bat`)
- `tools\build_installer.bat` (installer build)
- `release\create_release_package.bat` (release handoff helper)
- `tools\setup_dev_env.bat` (developer environment setup)

## Where user data is stored

Writable user data is stored in the user profile:
- Primary location: `%LOCALAPPDATA%\AdventurerGuildAI`
- Fallback: `%APPDATA%\AdventurerGuildAI`

Typical folders:
- `saves/`
- `config/`
- `campaign_memory/`
- `logs/`
- `generated_images/`
- `cache/`
- `workflows/`

## Managed image backend behavior (desktop mode)

- If image provider is configured to `comfyui`, the app can auto-start ComfyUI when startup checks pass.
- The app detects already-running ComfyUI and avoids duplicate launch.
- If the app launched ComfyUI as a managed child process, it is stopped when the app exits.
- If setup is incomplete (missing ComfyUI/workflow/checkpoint), the app keeps running in text mode and surfaces guided setup actions.

## Troubleshooting

- If the desktop window does not open, verify `pywebview` is installed and rerun `pip install -r requirements.txt`.
- If a port conflict is reported, stop the other process or launch with a different port in developer mode.
