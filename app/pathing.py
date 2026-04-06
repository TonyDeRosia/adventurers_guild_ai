"""Runtime path helpers for source and bundled executable modes."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """Return the project root for both source and PyInstaller modes."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return project_root() / "data"


def static_dir() -> Path:
    return project_root() / "app" / "static"
