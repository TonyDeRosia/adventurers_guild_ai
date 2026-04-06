# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application with a browser-first UI.

## End User Install

1. Download **`AdventurerGuildAI_Setup.exe`**.
2. Run the installer.
3. Choose your install folder in the installer wizard.
4. (Optional) Enable desktop shortcut creation.
5. Finish installation and launch the app from Start Menu/Desktop.

End users do **not** need Python, source files, or repository batch scripts.

## Installed App Launch Behavior

- The installed executable starts the local backend service.
- It waits for the `/health` endpoint to report ready.
- It opens the browser UI automatically at `http://127.0.0.1:8000` by default.
- If auto-open is blocked, the app prints a clear manual URL.
- Terminal mode is disabled in standard frozen/end-user builds unless explicitly enabled for debugging.

## Where User Data Is Stored

The install directory is treated as program files (read-only app payload).

Writable data is stored in the user profile:
- Primary location: `%LOCALAPPDATA%\AdventurerGuildAI`
- Fallback: `%APPDATA%\AdventurerGuildAI`

Mutable folders created there:
- `saves/`
- `config/`
- `campaign_memory/`
- `logs/`
- `generated_images/`
- `cache/`
- `workflows/`

The app seeds default configuration/workflow templates into the user-data area on first run.

## Developer Build

Developer scripts are in `tools\` and are not part of the end-user path.

### Build standalone executable (PyInstaller)
```bat
tools\build_exe.bat
```
Produces:
- `dist\AdventurerGuildAI.exe`

### Build Windows installer (Inno Setup)
```bat
tools\build_installer.bat
```
Produces:
- `installer\Output\AdventurerGuildAI_Setup.exe`

### Optional release handoff package
```bat
release\create_release_package.bat
```
Produces:
- `release\user\AdventurerGuildAI_Setup.exe`

### Guided install + build from source tree
```bat
run.bat
```
Prompts for an install folder, copies project files there, builds `AdventurerGuildAI.exe`, then launches the browser-ready launcher.

### Browser launcher (exe-first fallback)
```bat
launch_browser_window.bat
```
Starts `AdventurerGuildAI.exe` when present (or source mode fallback) and opens the browser UI window at `http://127.0.0.1:8000`.

## Troubleshooting

- If browser did not open, use the printed URL manually (default `http://127.0.0.1:8000`).
- If the port is already in use, relaunch with a different port in developer mode.
- If building fails, verify Python 3.10+ and Inno Setup 6 are installed for developer workflows.
