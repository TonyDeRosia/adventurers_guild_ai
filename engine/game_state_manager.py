"""Campaign state lifecycle manager."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from engine.entities import CampaignState
from engine.save_manager import SaveManager


class GameStateManager:
    """Owns in-memory campaign state and persistence interactions."""

    def __init__(self, content_data_dir: Path, saves_dir: Path, user_data_dir: Path | None = None) -> None:
        self.content_data_dir = content_data_dir
        self.user_data_dir = user_data_dir
        self.sample_campaign_path = content_data_dir / "sample_campaign.json"
        self.save_manager = SaveManager(saves_dir)

    def new_from_sample(self) -> CampaignState:
        payload = json.loads(self.sample_campaign_path.read_text(encoding="utf-8"))
        return CampaignState.from_dict(payload)

    def create_new_campaign(
        self,
        player_name: str,
        char_class: str,
        profile: str,
        mature_content_enabled: bool,
        content_settings_enabled: bool = True,
        campaign_tone: str | None = None,
        maturity_level: str | None = None,
        thematic_flags: list[str] | None = None,
        campaign_name: str | None = None,
        world_name: str | None = None,
        world_theme: str | None = None,
        starting_location_name: str | None = None,
        premise: str | None = None,
        player_concept: str | None = None,
        suggested_moves_enabled: bool = True,
    ) -> CampaignState:
        payload = json.loads(self.sample_campaign_path.read_text(encoding="utf-8"))
        new_payload = deepcopy(payload)
        clean_player_name = player_name.strip() or "Aria"
        clean_char_class = char_class.strip() or "Ranger"
        clean_profile = profile.strip() or "classic_fantasy"
        clean_campaign_name = (campaign_name or "").strip() or f"{clean_player_name}'s {clean_profile.replace('_', ' ').title()} Campaign"
        clean_world_name = (world_name or "").strip() or "Moonfall"
        clean_world_theme = (world_theme or "").strip() or clean_profile.replace("_", " ")
        clean_starting_location = (starting_location_name or "").strip() or "Moonfall Town"
        clean_premise = (premise or "").strip()
        clean_player_concept = (player_concept or "").strip()

        new_payload["campaign_id"] = f"{clean_profile}_{clean_player_name.lower().replace(' ', '_')}"
        new_payload["campaign_name"] = clean_campaign_name
        new_payload["player"]["name"] = clean_player_name
        new_payload["player"]["char_class"] = clean_char_class
        new_payload["player"]["inventory"] = ["worn_backpack", "torch", "field_draught"]
        new_payload["settings"]["profile"] = clean_profile
        resolved_mature_enabled = mature_content_enabled if content_settings_enabled else False
        new_payload["settings"]["mature_content_enabled"] = resolved_mature_enabled
        default_tone = "grim" if clean_profile == "dark_fantasy" else "heroic"
        resolved_tone = campaign_tone or default_tone
        new_payload["settings"]["narration_tone"] = resolved_tone
        new_payload["settings"]["content_settings"] = {
            "tone": resolved_tone,
            "maturity_level": maturity_level or ("mature" if resolved_mature_enabled else "standard"),
            "thematic_flags": thematic_flags or ["adventure", "mystery"],
        }
        new_payload["settings"]["suggested_moves_enabled"] = bool(suggested_moves_enabled)
        new_payload["settings"]["player_suggested_moves_override"] = None
        if not content_settings_enabled:
            new_payload["settings"]["content_settings"] = {
                "tone": resolved_tone,
                "maturity_level": "standard",
                "thematic_flags": [],
            }
        new_payload["event_log"] = [f"Campaign initialized for {clean_player_name} ({clean_char_class})"]
        new_payload["locations"][new_payload["current_location_id"]]["name"] = clean_starting_location
        starting_description = (
            f"{clean_starting_location} in {clean_world_name}, a {clean_world_theme} setting."
            if not clean_premise
            else f"{clean_starting_location} in {clean_world_name}. {clean_premise}"
        )
        new_payload["locations"][new_payload["current_location_id"]]["description"] = starting_description
        new_payload["world_meta"] = {
            "world_name": clean_world_name,
            "world_theme": clean_world_theme,
            "starting_location_name": clean_starting_location,
            "tone": resolved_tone,
            "premise": clean_premise,
            "player_concept": clean_player_concept,
        }
        new_payload["faction_reputation"] = {"town": 0, "guild": 0, "unknown": 0}
        new_payload["quest_outcomes"] = {}
        new_payload["world_events"] = ["campaign_started"]
        new_payload["combat_effects"] = {}
        return CampaignState.from_dict(new_payload)

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        return self.save_manager.save(state, slot)

    def load(self, slot: str = "autosave") -> CampaignState:
        loaded = self.save_manager.load(slot)
        if loaded is not None:
            return loaded
        return self.create_new_campaign(
            player_name="Aria",
            char_class="Ranger",
            profile="classic_fantasy",
            mature_content_enabled=False,
            content_settings_enabled=True,
            campaign_tone="heroic",
            maturity_level="standard",
            thematic_flags=["adventure", "mystery"],
        )

    def can_load(self, slot: str = "autosave") -> bool:
        return self.save_manager.exists(slot)
