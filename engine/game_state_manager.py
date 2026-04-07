"""Campaign state lifecycle manager."""

from __future__ import annotations

import json
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
        if not payload.get("world_meta"):
            payload["world_meta"] = {
                "world_name": "Moonfall",
                "world_theme": "classic fantasy",
                "starting_location_name": "Moonfall Town",
                "tone": payload.get("settings", {}).get("narration_tone", "heroic"),
                "premise": "",
                "player_concept": "",
            }
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
        new_payload: dict[str, object] = {
            "campaign_id": "",
            "campaign_name": "",
            "turn_count": 0,
            "current_location_id": "starting_location",
            "player": {
                "id": "player_1",
                "name": "",
                "char_class": "",
                "level": 1,
                "hp": 20,
                "max_hp": 20,
                "armor_class": 12,
                "attack_bonus": 3,
                "strength": 2,
                "agility": 2,
                "intellect": 2,
                "vitality": 2,
                "inventory": [],
                "xp": 0,
                "equipped_item_id": None,
            },
            "npcs": {},
            "locations": {
                "starting_location": {
                    "id": "starting_location",
                    "name": "",
                    "description": "",
                    "connections": [],
                }
            },
            "quests": {},
            "world_flags": {},
            "faction_reputation": {"town": 0, "guild": 0, "unknown": 0},
            "quest_outcomes": {},
            "world_events": [],
            "combat_effects": {},
            "active_enemy_id": None,
            "active_enemy_hp": None,
            "active_dialogue_npc_id": None,
            "active_dialogue_node_id": None,
            "event_log": [],
            "recent_memory": [],
            "long_term_memory": [],
            "session_summaries": [],
            "unresolved_plot_threads": [],
            "important_world_facts": [],
            "conversation_turns": [],
            "settings": {},
            "world_meta": {},
        }
        clean_player_name = player_name.strip() or "Aria"
        clean_char_class = char_class.strip() or "Ranger"
        clean_profile = profile.strip() or "classic_fantasy"
        clean_campaign_name = (campaign_name or "").strip() or f"{clean_player_name}'s {clean_profile.replace('_', ' ').title()} Campaign"
        clean_world_name = (world_name or "").strip() or "Untitled World"
        clean_world_theme = (world_theme or "").strip() or clean_profile.replace("_", " ")
        clean_starting_location = (starting_location_name or "").strip() or "Starting Area"
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
        new_payload["settings"]["image_generation_enabled"] = True
        new_payload["settings"]["campaign_auto_visuals_enabled"] = False
        new_payload["settings"]["player_suggested_moves_override"] = None
        if not content_settings_enabled:
            new_payload["settings"]["content_settings"] = {
                "tone": resolved_tone,
                "maturity_level": "standard",
                "thematic_flags": [],
            }
        new_payload["event_log"] = [
            f"Campaign initialized for {clean_player_name} ({clean_char_class})",
            f"World setup: {clean_world_name} / {clean_world_theme} / {clean_starting_location}",
        ]
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
        new_payload["world_events"] = ["campaign_started"]
        print("[campaign-create] mode=custom")
        print("[campaign-create] using_sample_template=False")
        print(f"[campaign-create] world_name={clean_world_name}")
        print(f"[campaign-create] starting_location={clean_starting_location}")
        print("[campaign-create] seeded_named_npcs=[]")
        print("[campaign-create] seeded_quests=[]")
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
