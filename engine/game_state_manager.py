"""Campaign state lifecycle manager."""

from __future__ import annotations

import json
from pathlib import Path

from engine.character_sheets import CharacterSheet
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
        suggested_moves_enabled: bool = False,
        display_mode: str = "story",
        character_sheets: list[dict[str, object]] | None = None,
        character_sheet_guidance_strength: str = "light",
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
            "structured_state": {},
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
        clean_display_mode = str(display_mode or "story").strip().lower()
        new_payload["settings"]["display_mode"] = clean_display_mode if clean_display_mode in {"story", "mud", "rpg"} else "story"
        new_payload["settings"]["image_generation_enabled"] = True
        new_payload["settings"]["campaign_auto_visuals_enabled"] = True
        new_payload["settings"]["player_suggested_moves_override"] = None
        new_payload["settings"]["play_style"] = {
            "allow_freeform_powers": True,
            "auto_update_character_sheet_from_actions": True,
            "strict_sheet_enforcement": False,
            "auto_sync_player_declared_identity": True,
            "auto_generate_npc_personalities": True,
            "auto_evolve_npc_personalities": True,
            "reactive_world_persistence": True,
            "narration_format_mode": "book",
            "scene_visual_mode": "after_narration",
        }
        print(
            "[settings-defaults] new_campaign_defaults "
            "manual=true auto=true timing=after_narration suggested_moves=false"
        )
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
        parsed_sheets: list[CharacterSheet] = []
        new_payload["character_sheets"] = []
        for raw_sheet in character_sheets or []:
            if not isinstance(raw_sheet, dict):
                continue
            sheet = CharacterSheet.from_payload(raw_sheet)
            parsed_sheets.append(sheet)
            new_payload["character_sheets"].append(
                {
                    "id": sheet.id,
                    "name": sheet.name,
                    "sheet_type": sheet.sheet_type,
                    "role": sheet.role,
                    "archetype": sheet.archetype,
                    "level_or_rank": sheet.level_or_rank,
                    "faction": sheet.faction,
                    "description": sheet.description,
                    "stats": sheet.stats.__dict__,
                    "classic_attributes": sheet.classic_attributes.__dict__,
                    "traits": list(sheet.traits),
                    "abilities": list(sheet.abilities),
                    "guaranteed_abilities": [
                        {
                            "name": entry.name,
                            "type": entry.type,
                            "description": entry.description,
                            "cost_or_resource": entry.cost_or_resource,
                            "cooldown": entry.cooldown,
                            "tags": list(entry.tags),
                            "notes": entry.notes,
                        }
                        for entry in sheet.guaranteed_abilities
                    ],
                    "equipment": list(sheet.equipment),
                    "weaknesses": list(sheet.weaknesses),
                    "temperament": sheet.temperament,
                    "loyalty": sheet.loyalty,
                    "fear": sheet.fear,
                    "desire": sheet.desire,
                    "social_style": sheet.social_style,
                    "speech_style": sheet.speech_style,
                    "notes": sheet.notes,
                    "state": sheet.state.__dict__,
                    "guidance_strength": sheet.guidance_strength,
                }
            )
        self._apply_main_character_sheet_to_payload(new_payload, parsed_sheets, source="campaign_create")
        strength = str(character_sheet_guidance_strength or "light").strip().lower()
        new_payload["character_sheet_guidance_strength"] = strength if strength in {"light", "strong"} else "light"
        new_payload["world_events"] = ["campaign_started"]
        print("[campaign-create] mode=custom")
        print("[campaign-create] using_sample_template=False")
        print(f"[campaign-create] world_name={clean_world_name}")
        print(f"[campaign-create] starting_location={clean_starting_location}")
        print("[campaign-create] seeded_named_npcs=[]")
        print("[campaign-create] seeded_quests=[]")
        print(f"[campaign-create] display_mode={new_payload['settings']['display_mode']}")
        return CampaignState.from_dict(new_payload)

    def _apply_main_character_sheet_to_payload(
        self,
        payload: dict[str, object],
        sheets: list[CharacterSheet],
        source: str,
    ) -> None:
        main_sheet = next((sheet for sheet in sheets if sheet.sheet_type == "main_character"), None)
        print(f"[character-sheets] attached_main_sheet_found={str(main_sheet is not None).lower()} source={source}")
        if main_sheet is None:
            return

        player_payload = payload.get("player")
        if not isinstance(player_payload, dict):
            return

        world_flags = payload.get("world_flags")
        if not isinstance(world_flags, dict):
            world_flags = {}
            payload["world_flags"] = world_flags

        print("[character-sheets] applying_main_sheet_to_runtime=true")
        player_payload["name"] = main_sheet.name or player_payload.get("name", "")
        if main_sheet.role.strip():
            player_payload["char_class"] = main_sheet.role.strip()
        player_payload["role"] = main_sheet.role
        player_payload["archetype"] = main_sheet.archetype
        player_payload["hp"] = int(main_sheet.stats.health)
        player_payload["max_hp"] = int(main_sheet.stats.health)
        player_payload["energy_or_mana"] = int(main_sheet.stats.energy_or_mana)
        player_payload["attack_bonus"] = int(main_sheet.stats.attack)
        player_payload["defense"] = int(main_sheet.stats.defense)
        player_payload["speed"] = int(main_sheet.stats.speed)
        player_payload["magic"] = int(main_sheet.stats.magic)
        player_payload["willpower"] = int(main_sheet.stats.willpower)
        player_payload["presence"] = int(main_sheet.stats.presence)
        player_payload["classic_attributes"] = {
            "strength": main_sheet.classic_attributes.strength,
            "dexterity": main_sheet.classic_attributes.dexterity,
            "constitution": main_sheet.classic_attributes.constitution,
            "intelligence": main_sheet.classic_attributes.intelligence,
            "wisdom": main_sheet.classic_attributes.wisdom,
            "charisma": main_sheet.classic_attributes.charisma,
        }
        world_flags["main_character_sheet_applied"] = True
        structured_payload = payload.get("structured_state")
        if not isinstance(structured_payload, dict):
            structured_payload = {}
            payload["structured_state"] = structured_payload
        runtime_payload = structured_payload.get("runtime")
        if not isinstance(runtime_payload, dict):
            runtime_payload = {}
            structured_payload["runtime"] = runtime_payload
        spellbook_payload = runtime_payload.get("spellbook")
        if not isinstance(spellbook_payload, list) or not spellbook_payload:
            runtime_payload["spellbook"] = [
                {
                    "id": f"main_{index}_{entry.name.lower().replace(' ', '_')}",
                    "name": entry.name,
                    "type": entry.type,
                    "description": entry.description,
                    "cost_or_resource": entry.cost_or_resource,
                    "cooldown": entry.cooldown,
                    "tags": list(entry.tags),
                    "notes": entry.notes,
                }
                for index, entry in enumerate(main_sheet.guaranteed_abilities)
                if entry.name.strip()
            ]
            print(
                f"[spellbook] initialized_from_main_sheet={str(bool(runtime_payload['spellbook'])).lower()} "
                f"entry_count={len(runtime_payload['spellbook'])}"
            )
        print(f"[character-sheets] applied_health={main_sheet.stats.health}")

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        return self.save_manager.save(state, slot)

    def load(self, slot: str = "autosave") -> CampaignState:
        loaded = self.save_manager.load(slot)
        if loaded is not None:
            has_sheets = bool(loaded.character_sheets)
            print(f"[character-sheets] campaign_loaded_with_sheets=count:{len(loaded.character_sheets)}")
            if has_sheets:
                payload = loaded.to_dict()
                self._apply_main_character_sheet_to_payload(payload, loaded.character_sheets, source="campaign_load_runtime_sync")
                return CampaignState.from_dict(payload)
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
