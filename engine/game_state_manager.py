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

    def _load_sample_payload(self) -> dict:
        return json.loads(self.sample_campaign_path.read_text(encoding="utf-8"))

    def _apply_additive_defaults(self, payload: dict) -> dict:
        sample = self._load_sample_payload()

        payload.setdefault("active_dialogue", None)
        payload.setdefault("world_flags", {})

        payload.setdefault("locations", {})
        for location_id, location_data in sample.get("locations", {}).items():
            payload["locations"].setdefault(location_id, location_data)

        payload.setdefault("npcs", {})
        for npc_id, npc_data in sample.get("npcs", {}).items():
            payload["npcs"].setdefault(npc_id, npc_data)

        payload.setdefault("quests", {})
        for quest_id, quest_data in sample.get("quests", {}).items():
            payload["quests"].setdefault(quest_id, quest_data)

        for flag_key, flag_value in sample.get("world_flags", {}).items():
            payload["world_flags"].setdefault(flag_key, flag_value)

        player = payload.setdefault("player", {})
        player.setdefault("inventory", ["Worn Backpack", "Torch"])
        if "inventory_item_ids" not in player:
            player["inventory_item_ids"] = []
        player.setdefault("equipped_weapon_id", None)
        player.setdefault("equipped_trinket_id", None)

        payload.setdefault("event_log", ["Campaign initialized"])
        return payload

    def new_from_sample(self) -> CampaignState:
        payload = self._load_sample_payload()
        payload = self._apply_additive_defaults(payload)
        return CampaignState.from_dict(payload)

    def create_new_campaign(
        self,
        player_name: str,
        char_class: str,
        profile: str,
        mature_content_enabled: bool,
    ) -> CampaignState:
        payload = self._load_sample_payload()
        new_payload = deepcopy(payload)
        new_payload["campaign_id"] = f"{profile}_{player_name.lower().replace(' ', '_')}"
        new_payload["campaign_name"] = f"{player_name}'s {profile.replace('_', ' ').title()} Campaign"
        new_payload["player"]["name"] = player_name
        new_payload["player"]["char_class"] = char_class
        new_payload["player"]["inventory"] = ["Worn Backpack", "Torch"]
        new_payload["player"]["inventory_item_ids"] = ["worn_backpack", "torch"]
        new_payload["settings"]["profile"] = profile
        new_payload["settings"]["mature_content_enabled"] = mature_content_enabled
        new_payload["settings"]["narration_tone"] = "grim" if profile == "dark_fantasy" else "heroic"
        new_payload["event_log"] = [f"Campaign initialized for {player_name} ({char_class})"]
        return CampaignState.from_dict(self._apply_additive_defaults(new_payload))

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        return self.save_manager.save(state, slot)

    def load(self, slot: str = "autosave") -> CampaignState:
        loaded = self.save_manager.load(slot)
        upgraded_payload = self._apply_additive_defaults(loaded.to_dict())
        return CampaignState.from_dict(upgraded_payload)

    def can_load(self, slot: str = "autosave") -> bool:
        return self.save_manager.exists(slot)
