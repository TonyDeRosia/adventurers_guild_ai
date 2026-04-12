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
    root = project_root()
    candidates = [root / "app" / "static", root / "static"]
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        candidates.extend([executable_root / "app" / "static", executable_root / "static"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def content_data_dir() -> Path:
    """Read-only authored game content bundled with the app."""
    return project_root() / "data"


def bundled_runtime_dir() -> Path:
    """Return the bundled third-party runtime root."""
    if getattr(sys, "frozen", False):
        candidates = [
            install_dir() / "runtime_bundle",
            project_root() / "runtime_bundle",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    return project_root() / "packaging" / "windows" / "runtime_bundle"


def bundled_comfyui_dir() -> Path:
    """Return the expected bundled portable ComfyUI runtime path."""
    return bundled_runtime_dir() / "comfyui"


def bundled_workflow_dir() -> Path:
    """Return bundled workflow template directory for ComfyUI mode."""
    bundled = bundled_runtime_dir() / "workflows"
    if bundled.exists():
        return bundled
    return content_data_dir() / "workflows"


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
    if src.is_file():
        _copy_if_missing(src, dst)
        return
    if not src.is_dir():
        return
    if dst.exists() and not dst.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.glob("**/*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            try:
                if target.exists() and not target.is_dir():
                    continue
                target.mkdir(parents=True, exist_ok=True)
            except (FileExistsError, NotADirectoryError):
                continue
            continue
        if not path.is_file():
            continue
        if target.parent.exists() and not target.parent.is_dir():
            continue
        if not target.exists():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except (FileExistsError, NotADirectoryError):
                continue
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
    _copy_if_missing(paths.content_data / "defaults" / "app_config.json", paths.config / "app_config.json")
    _copy_if_missing(legacy_root / "app_config.json", paths.config / "app_config.json")
    _copy_tree_missing(legacy_root / "saves", paths.saves)
    _copy_tree_missing(legacy_root / "generated_images", paths.generated_images)
    _copy_tree_missing(legacy_root / "logs", paths.logs)
    _copy_tree_missing(legacy_root / "campaign_memory", paths.campaign_memory)
    _copy_tree_missing(legacy_root / "cache", paths.cache)

    # Keep workflow templates available for user customization without mutating install files.
    _copy_tree_missing(paths.content_data / "workflows", paths.workflows)
    return paths
