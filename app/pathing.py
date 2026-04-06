"""Runtime path helpers for source, portable, and installed executable modes."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "AdventurerGuildAI"
PORTABLE_ENV = "ADVENTURER_GUILD_AI_PORTABLE"
USER_DATA_ENV = "ADVENTURER_GUILD_AI_USER_DATA_DIR"


def project_root() -> Path:
    """Return the project root in source mode or bundle root in frozen mode."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def install_dir() -> Path:
    """Return the directory where the launcher executable/script lives."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()


def static_dir() -> Path:
    return project_root() / "app" / "static"


def content_data_dir() -> Path:
    """Read-only authored game content bundled with the app."""
    return project_root() / "data"


def _default_user_data_dir() -> Path:
    override = os.getenv(USER_DATA_ENV)
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.getenv("LOCALAPPDATA")
    roaming_app_data = os.getenv("APPDATA")

    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME
    if roaming_app_data:
        return Path(roaming_app_data) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def is_portable_mode() -> bool:
    if os.getenv(PORTABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return False


def user_data_dir() -> Path:
    """Writable runtime data root.

    Installed mode defaults to %LOCALAPPDATA%/AdventurerGuildAI.
    Portable mode can be enabled with ADVENTURER_GUILD_AI_PORTABLE=1.
    """
    if getattr(sys, "frozen", False) and is_portable_mode():
        return install_dir() / "portable_data"
    return _default_user_data_dir()


@dataclass(frozen=True)
class RuntimePaths:
    content_data: Path
    user_data: Path
    saves: Path
    config: Path
    campaign_memory: Path
    logs: Path
    generated_images: Path
    cache: Path
    workflows: Path


def runtime_paths() -> RuntimePaths:
    base = user_data_dir()
    return RuntimePaths(
        content_data=content_data_dir(),
        user_data=base,
        saves=base / "saves",
        config=base / "config",
        campaign_memory=base / "campaign_memory",
        logs=base / "logs",
        generated_images=base / "generated_images",
        cache=base / "cache",
        workflows=base / "workflows",
    )


def _copy_if_missing(src: Path, dst: Path) -> None:
    if src.is_file() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_tree_missing(src: Path, dst: Path) -> None:
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.glob("**/*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def initialize_user_data_paths() -> RuntimePaths:
    """Create runtime folders and migrate known mutable legacy data if present."""
    paths = runtime_paths()
    for folder in [
        paths.user_data,
        paths.saves,
        paths.config,
        paths.campaign_memory,
        paths.logs,
        paths.generated_images,
        paths.cache,
        paths.workflows,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    legacy_root = install_dir() / "data"
    _copy_if_missing(legacy_root / "app_config.json", paths.config / "app_config.json")
    _copy_tree_missing(legacy_root / "saves", paths.saves)
    _copy_tree_missing(legacy_root / "generated_images", paths.generated_images)
    _copy_tree_missing(legacy_root / "logs", paths.logs)
    _copy_tree_missing(legacy_root / "campaign_memory", paths.campaign_memory)
    _copy_tree_missing(legacy_root / "cache", paths.cache)

    # Keep workflow templates available for user customization without mutating install files.
    _copy_tree_missing(paths.content_data / "workflows", paths.workflows)
    return paths
