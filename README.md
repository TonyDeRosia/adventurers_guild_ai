# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application with a browser-first UI.

## Run from source (normal path)

1. Double click `run.bat` from the repository root.
2. The script checks for Python (`py -3` first, then `python`).
3. The script installs dependencies from `requirements.txt`.
4. The script runs `python run.py`.
5. `run.py` starts the backend once, waits for `/health`, and opens the browser UI.

If startup fails, keep the console open and read the printed error details.

### Source startup behavior

- Browser UI is the default interface.
- Terminal mode remains available only for fallback/debug usage.
- If port `8000` is already in use, `run.py` prints a clear error and exits.
- If browser auto-open fails, the launcher prints the manual URL.

## Packaging and build workflows (developer-only)

These scripts are for packaging/distribution work and are **not** part of normal source running:

- Build standalone executable (PyInstaller):
  ```bat
  tools\build_exe.bat
  ```
- Build Windows installer (Inno Setup):
  ```bat
  tools\build_installer.bat
  ```
- Optional release handoff package:
  ```bat
  release\create_release_package.bat
  ```

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

## Troubleshooting

- If browser did not open, use the printed URL manually (default `http://127.0.0.1:8000`).
- If a port conflict is reported, stop the other process or launch with a different port in developer mode.
