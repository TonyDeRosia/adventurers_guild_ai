# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application with a browser-first UI.

## Launch model (single clear paths)

- **Developer source path (root):** `dev_run.bat`
- **End-user installed path:** `AdventurerGuildAI-Setup.exe` installer → Start Menu/Desktop shortcut

`run.bat` has been removed to eliminate launch ambiguity.

---

## End User: install and run (no Python, no .bat scripts)

1. Download `AdventurerGuildAI-Setup.exe`.
2. Run installer.
3. Choose install location.
4. Launch app from Start Menu or Desktop shortcut.

End users should **not** run repository `.bat` scripts.

---

## Developer: run from source

### Prerequisites
- Windows
- Python 3.10+

### Source run (browser UI default)
```bat
dev_run.bat
```

### Optional terminal mode (developer-only)
```bat
dev_run.bat --terminal
```

`dev_run.bat` will:
- detect Python (`py -3` or `python`),
- install dependencies via `tools\setup_dev_env.bat` when needed,
- start backend in web mode by default,
- wait for health readiness before opening browser,
- keep the console window open on launch failure (pause-on-error).

---

## Packaged/release launch behavior

- Installer output: `installer\Output\AdventurerGuildAI-Setup.exe`
- User handoff package: `release\user\AdventurerGuildAI-Setup.exe`
- Maintenance-only packaged exe helper: `launch_packaged_exe.bat` (for repo maintainers validating local `AdventurerGuildAI.exe` or `dist\AdventurerGuildAI.exe`)

The release experience for end users remains: install and launch from Start Menu/Desktop.

---

## Browser readiness behavior

On web launch, browser auto-open waits for a **real HTTP readiness check**:
- Polls `http://<host>:<port>/health`
- Requires HTTP 200 and payload containing `{"status": "ok"}`
- Retries until timeout
- Opens browser only after readiness succeeds
- Prints failure reason if readiness does not succeed

This prevents opening the browser before the app can answer web requests.

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

## Files and data separation

- **Install files:** chosen install directory (e.g., `C:\Program Files\AdventurerGuildAI`)
- **User data:** `%LOCALAPPDATA%\AdventurerGuildAI`

User data includes saves/config/logs/generated images and remains separate from installed binaries.

---

## Script responsibilities

### Root
- `dev_run.bat` → **primary developer source launcher** (browser by default, pause-on-error).
- `launch_packaged_exe.bat` → maintenance helper to launch an existing packaged exe from the repo tree.

### tools/ (developer-only)
- `tools\dev_run.bat` → compatibility wrapper that forwards to root `dev_run.bat`.
- `tools\setup_dev_env.bat` → install/update Python dependencies for development.
- `tools\build_exe.bat` → build standalone exe with PyInstaller.
- `tools\build_installer.bat` → build installer with Inno Setup.

### release/
- `release\create_release_package.bat` → copy installer into `release\user\` for end-user handoff.
