from __future__ import annotations

from pathlib import Path


SCRIPT_EXPECTATIONS = {
    "run.bat": [
        "Adventurer's Guild AI (Source Run)",
        "Installing/updating dependencies from requirements.txt",
        "Launching application via run.py",
    ],
    "Build_AdventurersGuildAI.bat": [
        "Adventurer Guild AI - Packaged EXE Build",
        "[1/6] Resolve Python",
        "[5/6] Run PyInstaller spec build",
        "Final EXE path:",
        "Log file:",
    ],
}


def test_scripts_include_user_facing_banner_steps_and_logging() -> None:
    for path, expected in SCRIPT_EXPECTATIONS.items():
        content = Path(path).read_text(encoding="utf-8")
        for phrase in expected:
            assert phrase in content, f"Missing '{phrase}' in {path}"


def test_build_script_includes_failure_pause_behavior() -> None:
    content = Path("Build_AdventurersGuildAI.bat").read_text(encoding="utf-8")
    assert "if \"%INTERACTIVE%\"==\"1\" pause" in content
    assert "Step failed:" in content
