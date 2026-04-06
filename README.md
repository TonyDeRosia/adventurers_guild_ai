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

### Compatibility wrappers (developer convenience)
- `build_exe.bat` -> forwards to `dev_build_exe.bat`
- `build_installer.bat` -> forwards to `dev_build_installer.bat`

### End-user launcher helper in repo
- `run.bat` launches existing `AdventurerGuildAI.exe` if present and does **not** require Python.

### End-user artifacts
- `dist/AdventurerGuildAI.exe`
- `installer/Output/AdventurerGuildAI-Setup.exe`

---

## Browser UI Default Launch Behavior

`run.py` defaults to web mode (`--mode web`) and opens a browser unless `--no-browser` is specified.

Terminal mode is only entered through explicit developer action (`--terminal` or `--mode terminal`).
