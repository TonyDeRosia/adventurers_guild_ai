"""Persistence manager for campaign save/load."""

from __future__ import annotations

import json
from pathlib import Path

from engine.entities import CampaignState


class SaveManager:
    """Reads and writes campaign state as JSON."""

    def __init__(self, save_dir: Path) -> None:
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _save_path(self, slot: str) -> Path:
        return self.save_dir / f"{slot}.json"

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        path = self._save_path(slot)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        return path

    def load(self, slot: str = "autosave") -> CampaignState:
        path = self._save_path(slot)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CampaignState.from_dict(payload)

    def exists(self, slot: str = "autosave") -> bool:
        return self._save_path(slot).exists()
