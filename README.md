# Adventurer's Guild AI

Adventurer's Guild AI is a local-first fantasy campaign application with a browser-first UI.

## Run from source

Double click `run.bat` at the repository root.

What should happen:
- The launcher detects Python (`py -3`, then `python`).
- If dependencies are not initialized yet, it runs `tools\setup_dev_env.bat` automatically.
- It starts `run.py` in browser mode by default.
- The app opens `http://127.0.0.1:8000` after the `/health` readiness check passes.
- If your browser does not open automatically, the launcher prints the local URL so you can open it manually.
- If startup fails, the window stays open and shows the error.

`run.bat` is the one primary source launcher.

## Packaged release / installer

End users should use the installed app, not repository scripts.

1. Build/download `AdventurerGuildAI-Setup.exe`.
2. Run the installer.
3. Launch from Start Menu or Desktop shortcut.

Repository `.bat` files are for source development and release maintenance only.

## Optional developer commands

### Terminal mode (developer/debug only)
```bat
run.bat --terminal
```

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

### Launch an already-built packaged exe (maintainers)
```bat
launch_packaged_exe.bat
```
