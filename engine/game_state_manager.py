"""Campaign state lifecycle manager."""

from __future__ import annotations

import json
from pathlib import Path

from engine.entities import CampaignState
from engine.save_manager import SaveManager


class GameStateManager:
    """Owns in-memory campaign state and persistence interactions."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.sample_campaign_path = data_dir / "sample_campaign.json"
        self.save_manager = SaveManager(data_dir / "saves")

    def new_from_sample(self) -> CampaignState:
        payload = json.loads(self.sample_campaign_path.read_text(encoding="utf-8"))
        return CampaignState.from_dict(payload)

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        return self.save_manager.save(state, slot)

    def load(self, slot: str = "autosave") -> CampaignState:
        return self.save_manager.load(slot)

    def can_load(self, slot: str = "autosave") -> bool:
        return self.save_manager.exists(slot)
