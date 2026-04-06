# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application with a browser-first UI.

## Launch model (single clear paths)

- **End-user path:** `AdventurerGuildAI-Setup.exe` installer → choose install folder → launch from Start Menu/Desktop → browser UI opens.
- **Developer path:** run from source with `tools\dev_run.bat`.

`run.bat` at repo root is **release-only** (it only launches an already-built `.exe` if present).

---

## End User: install and run (no Python)

1. Download `AdventurerGuildAI-Setup.exe`.
2. Run installer.
3. Choose install location.
4. Launch app from Start Menu or Desktop shortcut.

End users do **not** run `.bat` developer scripts and do **not** need Python.

---

## Developer: run from source

### Prerequisites
- Windows
- Python 3.10+

### Source run (browser UI default)
```bat
tools\dev_run.bat
```

### Optional terminal mode (developer-only)
```bat
tools\dev_run.bat --terminal
```

`tools\dev_run.bat` bootstraps dependencies through `tools\setup_dev_env.bat` when needed.

---

## Developer: build release artifacts

### Build standalone executable
```bat
tools\build_exe.bat
```
Output:
- `dist\AdventurerGuildAI.exe`

### Build Windows installer
```bat
tools\build_installer.bat
```
Output:
- `installer\Output\AdventurerGuildAI-Setup.exe`

### Prepare installer-only handoff package
```bat
release\create_release_package.bat
```
Output:
- `release\user\AdventurerGuildAI-Setup.exe`

---

## Browser readiness behavior

On web launch, browser auto-open waits for a **real HTTP readiness check**:
- Polls `http://<host>:<port>/health`
- Requires HTTP 200 and payload containing `{"status": "ok"}`
- Retries until timeout
- Opens browser only after readiness succeeds

This prevents launching the browser before the app can actually answer web requests.

---

## Files and data separation

- **Install files:** chosen install directory (e.g., `C:\Program Files\AdventurerGuildAI`)
- **User data:** `%LOCALAPPDATA%\AdventurerGuildAI`

User data includes saves/config/logs/generated images and remains separate from installed binaries.

---

## Script responsibilities

### Root
- `run.bat` → release-only launcher for existing built exe; not a source launcher.

### tools/ (developer-only)
- `tools\dev_run.bat` → run from source (browser UI default).
- `tools\setup_dev_env.bat` → install/update Python dependencies for development.
- `tools\build_exe.bat` → build standalone exe with PyInstaller.
- `tools\build_installer.bat` → build installer with Inno Setup.

### release/
- `release\create_release_package.bat` → copy installer into `release\user\` for end-user handoff.
