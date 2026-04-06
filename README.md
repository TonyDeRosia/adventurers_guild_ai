# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application.

This repository now has a **clean split** between:
- **Developer workflows** (Python required for building/running from source)
- **End-user workflows** (installer + executable, no Python required)

---

## Developer Setup

> Developer machines need Python 3.10+.

1. Install Python 3.10+
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run in developer mode (default browser UI):

```bat
dev_run.bat
```

4. Optional: run terminal mode for debugging only:

```bat
dev_run.bat --terminal
```

---

## Build Executable (Developer)

Build a standalone Windows executable with PyInstaller:

```bat
dev_build_exe.bat
```

Output artifact:
- `dist/AdventurerGuildAI.exe`

Notes:
- The executable bundles Python runtime + app code.
- The build uses `--windowed` so end users do not see a Python/console window by default.
- End users do **not** need Python installed to run the built executable.

---

## Build Installer (Developer)

Build an installer with Inno Setup:

```bat
dev_build_installer.bat
```

Output artifact:
- `installer/Output/AdventurerGuildAI-Setup.exe`

Installer behavior:
- lets user choose install location
- creates Start Menu entry
- offers optional Desktop shortcut
- supports uninstall via standard Windows uninstall flow

Create a clean **end-user release package** (installer only):

```bat
release\create_release_package.bat
```

Release output:
- `release/user/AdventurerGuildAI-Setup.exe`

---

## End User Install

1. Download `AdventurerGuildAI-Setup.exe`
2. Run installer
3. Choose install location
4. (Optional) select desktop shortcut task
5. Finish install
6. Launch from Start Menu/Desktop shortcut

Default launch behavior for end users:
- App starts local backend
- App opens browser UI at `http://127.0.0.1:8000`
- Terminal mode is **not** the default user experience
- End users do not run Python scripts or batch build scripts

---

## Where User Data Is Stored

Install files and user data are intentionally separate.

### Install directory (read-only app files)
Selected by the user in installer, e.g.:
- `C:\Program Files\AdventurerGuildAI`

### User data directory (writable runtime data)
Stored under:
- `%LOCALAPPDATA%\AdventurerGuildAI`

Subfolders include:
- `saves/`
- `config/`
- `campaign_memory/`
- `logs/`
- `generated_images/`
- `cache/`
- `workflows/`

On first run, workflow templates are copied from bundled defaults into the user-data `workflows/` folder.

---

## Script and Artifact Map

### Developer-only scripts
- `dev_run.bat` - run from source (web UI default)
- `dev_build_exe.bat` - build standalone EXE with PyInstaller
- `dev_build_installer.bat` - build installer with Inno Setup
- `setup.bat` - install/update Python dependencies for development
- `release/create_release_package.bat` - prepare installer-only user release folder

### Compatibility wrappers (developer convenience)
- `build_exe.bat` -> forwards to `dev_build_exe.bat`
- `build_installer.bat` -> forwards to `dev_build_installer.bat`

### End-user launcher helper in repo
- `run.bat` launches existing `AdventurerGuildAI.exe` if present and does **not** require Python.

### End-user artifacts
- `dist/AdventurerGuildAI.exe`
- `installer/Output/AdventurerGuildAI-Setup.exe`
- `release/user/AdventurerGuildAI-Setup.exe`

---

## Browser UI Default Launch Behavior

`run.py` defaults to web mode (`--mode web`) and opens a browser unless `--no-browser` is specified.

Terminal mode is only entered through explicit developer action (`--terminal` or `--mode terminal`) and is blocked in standard frozen end-user builds unless `ADVENTURER_GUILD_AI_ENABLE_TERMINAL=1` is intentionally set.

---

## Browser Gameplay (Fully Wired)

The browser experience is now the primary, fully operational flow:

- Chat input sends turns to the backend campaign engine.
- Structured turn output is returned and rendered as narrator/NPC/quest/system messages.
- Turn history is persisted per campaign slot and restored after load/switch.
- Autosave/write-on-turn is enabled through slot persistence APIs.

### Campaign management in browser

- **New campaign:** creates a fresh campaign state and save slot.
- **Load/switch campaign:** loads any save slot and restores message history.
- **Save campaign:** saves active state to current/new slot.
- **Rename campaign:** renames the in-game campaign display name.
- **Delete campaign:** removes non-active save slots safely.

### Settings behavior

Global settings (persisted in `config/app_config.json`):
- model provider (`null`, `ollama`, `gpt4all`, `local_template`)
- model name / base URL / timeout
- image backend provider (`local`, `comfyui`, `null`)
- image backend enabled flag

Campaign settings (persisted in each save):
- narration tone, profile, mature-content toggle
- content settings (tone/maturity/thematic flags)
- campaign-level image-generation enabled toggle

Both global and campaign settings are wired to runtime behavior.

### Model configuration and runtime behavior

- Prompt assembly includes current scene, memory retrieval context, recent conversation, world state, and nearby NPC disposition context.
- `ollama` is called via `/api/chat` with system prompt + rolling history.
- If the primary model is unavailable at runtime, the engine gracefully falls back to local template narration for that turn and logs a readable system message.

### Image generation behavior

- Image generation flow: `request -> workflow template load/injection -> adapter call -> result metadata -> UI`.
- With `comfyui`, requests go to the configured ComfyUI server.
- If ComfyUI is unavailable, a graceful fallback generates a local placeholder SVG and marks fallback metadata.
- Campaign-level image toggle can disable generation safely with readable API errors.

### Reliability and error handling

- Corrupt saves are detected and quarantined as `.corrupt.<timestamp>.json`.
- API surfaces validation errors as readable JSON messages for UI display.
- Missing slots, invalid settings, unavailable model/image backends are handled without crashing the campaign runtime.

---

## Exact Flows

### Exact developer build flow

1. `setup.bat` (once, or when dependencies change)
2. `dev_build_exe.bat`
3. `dev_build_installer.bat`
4. `release\create_release_package.bat` (optional, for handoff folder)

### Exact end-user install flow

1. User receives `AdventurerGuildAI-Setup.exe` from `release/user/`
2. User runs installer and chooses install location
3. Installer places app files in chosen install path and creates shortcuts
4. User launches from Start Menu/Desktop
5. App starts backend + opens browser UI automatically
