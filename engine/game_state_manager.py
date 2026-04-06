"""Campaign state lifecycle manager."""

from __future__ import annotations

import json
from copy import deepcopy
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

    def create_new_campaign(
        self,
        player_name: str,
        char_class: str,
        profile: str,
        mature_content_enabled: bool,
    ) -> CampaignState:
        payload = json.loads(self.sample_campaign_path.read_text(encoding="utf-8"))
        new_payload = deepcopy(payload)
        new_payload["campaign_id"] = f"{profile}_{player_name.lower().replace(' ', '_')}"
        new_payload["campaign_name"] = f"{player_name}'s {profile.replace('_', ' ').title()} Campaign"
        new_payload["player"]["name"] = player_name
        new_payload["player"]["char_class"] = char_class
        new_payload["player"]["inventory"] = ["worn_backpack", "torch", "field_draught"]
        new_payload["settings"]["profile"] = profile
        new_payload["settings"]["mature_content_enabled"] = mature_content_enabled
        new_payload["settings"]["narration_tone"] = "grim" if profile == "dark_fantasy" else "heroic"
        new_payload["event_log"] = [f"Campaign initialized for {player_name} ({char_class})"]
        return CampaignState.from_dict(new_payload)

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        return self.save_manager.save(state, slot)

    def load(self, slot: str = "autosave") -> CampaignState:
        return self.save_manager.load(slot)

    def can_load(self, slot: str = "autosave") -> bool:
        return self.save_manager.exists(slot)
