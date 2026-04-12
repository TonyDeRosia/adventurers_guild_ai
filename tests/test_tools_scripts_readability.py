from __future__ import annotations

from pathlib import Path


SCRIPT_EXPECTATIONS = {
    "tools/build_exe.bat": [
        "Adventurer Guild AI - EXE Build Script",
        "[1/6] Resolving Python",
        "[5/6] Running PyInstaller",
        "set \"LOG_DIR=%ROOT_DIR%\\logs\\tools\"",
        "Log file:",
    ],
    "tools/build_installer.bat": [
        "Adventurer Guild AI - Installer Build Script",
        "[1/5] Resolving Python",
        "[5/5] Building Windows installer",
        "set \"LOG_DIR=%ROOT_DIR%\\logs\\tools\"",
        "Log file:",
    ],
    "tools/setup_dev_env.bat": [
        "Adventurer Guild AI - Dev Environment Setup",
        "[1/3] Resolving Python",
        "[3/3] Installing requirements",
        "set \"LOG_DIR=%ROOT_DIR%\\logs\\tools\"",
        "Log file:",
    ],
    "release/create_release_package.bat": [
        "Adventurer Guild AI - Release Package Script",
        "[1/4] Resolving Python",
        "[4/4] Auditing source packaging layout",
        "set \"LOG_DIR=%ROOT_DIR%\\logs\\tools\"",
        "Log file:",
    ],
}


def test_scripts_include_user_facing_banner_steps_and_logging() -> None:
    for path, expected in SCRIPT_EXPECTATIONS.items():
        content = Path(path).read_text(encoding="utf-8")
        for phrase in expected:
            assert phrase in content, f"Missing '{phrase}' in {path}"


def test_scripts_include_failure_pause_behavior() -> None:
    for path in SCRIPT_EXPECTATIONS:
        content = Path(path).read_text(encoding="utf-8")
        assert "if \"%INTERACTIVE%\"==\"1\" pause" in content
        assert "Phase failed:" in content
