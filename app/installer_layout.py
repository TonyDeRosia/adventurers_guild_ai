"""Installer-aware packaged runtime layout validation helpers.

This module validates the expected runtime bundle layout used by desktop
installers so setup/onboarding can provide clear status messaging.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pathing import bundled_comfyui_dir, bundled_runtime_dir, bundled_workflow_dir


@dataclass(frozen=True)
class LayoutCheck:
    id: str
    required: bool
    present: bool
    path: str
    message: str

    @property
    def state(self) -> str:
        return "ready" if self.present else "missing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "required": self.required,
            "present": self.present,
            "state": self.state,
            "path": self.path,
            "message": self.message,
        }


class InstallerLayoutValidator:
    """Validate expected packaged runtime-bundle file/folder layout."""

    def __init__(self) -> None:
        runtime_root = bundled_runtime_dir()
        workflow_root = bundled_workflow_dir()
        self._checks = [
            ("runtime_bundle", True, runtime_root, True, "Packaged runtime bundle folder is present."),
            ("bundled_image_runtime", True, bundled_comfyui_dir(), True, "Bundled ComfyUI runtime folder is present."),
            (
                "workflow_scene_image",
                True,
                workflow_root / "scene_image.json",
                False,
                "Bundled scene workflow template is present.",
            ),
            (
                "workflow_character_portrait",
                True,
                workflow_root / "character_portrait.json",
                False,
                "Bundled character portrait workflow template is present.",
            ),
            (
                "embedded_python",
                False,
                runtime_root / "python_embeded" / "python.exe",
                False,
                "Embedded Python runtime detected for bundled launch.",
            ),
        ]

    def validate(self) -> dict[str, Any]:
        checks: list[LayoutCheck] = []
        missing_required: list[str] = []
        for check_id, required, path, expect_dir, ok_message in self._checks:
            exists = path.is_dir() if expect_dir else path.is_file()
            if exists:
                message = ok_message
            elif required:
                message = self._required_missing_message(check_id)
                missing_required.append(check_id)
            else:
                message = "Embedded Python runtime is optional and was not found. System Python fallback may be required."
            checks.append(
                LayoutCheck(
                    id=check_id,
                    required=required,
                    present=exists,
                    path=str(path),
                    message=message,
                )
            )

        by_id = {item.id: item.to_dict() for item in checks}
        valid = not missing_required
        summary = (
            "Installer layout is valid. Required packaged runtime files are present."
            if valid
            else "Installer layout is invalid. Required packaged runtime files are missing."
        )
        return {
            "valid": valid,
            "state": "valid" if valid else "invalid",
            "summary": summary,
            "missing_required": missing_required,
            "checks": by_id,
            "packaged_app_files_present": by_id["runtime_bundle"]["present"],
            "bundled_image_runtime_present": by_id["bundled_image_runtime"]["present"],
            "bundled_workflows_present": bool(
                by_id["workflow_scene_image"]["present"] and by_id["workflow_character_portrait"]["present"]
            ),
            "embedded_python_present": by_id["embedded_python"]["present"],
        }

    def _required_missing_message(self, check_id: str) -> str:
        messages = {
            "runtime_bundle": "Missing required packaged folder: runtime_bundle.",
            "bundled_image_runtime": "Missing required packaged folder: runtime_bundle/comfyui.",
            "workflow_scene_image": "Missing required packaged workflow: runtime_bundle/workflows/scene_image.json.",
            "workflow_character_portrait": "Missing required packaged workflow: runtime_bundle/workflows/character_portrait.json.",
        }
        return messages.get(check_id, "Required packaged asset is missing.")
