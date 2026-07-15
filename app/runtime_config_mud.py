"""MUD-specific runtime configuration for Smart MUD application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MudColorConfig:
    """MUD terminal color mapping - all semantic roles."""
    # Room/area display
    room_name: str = "#ffff00"
    area_name: str = "#00ffff"
    room_description: str = "#ffffff"
    content: str = "#ffffff"
    contents_heading: str = "#00ff00"
    
    # Entities
    exit: str = "#00ff00"
    npc: str = "#ff00ff"
    mob: str = "#ff6600"
    player: str = "#ffff00"
    object: str = "#ff00ff"
    
    # Items by rarity
    item_common: str = "#cccccc"
    item_uncommon: str = "#00ff00"
    item_rare: str = "#0088ff"
    item_epic: str = "#ff00ff"
    item_legendary: str = "#ffff00"
    
    # Combat and effects
    command_echo: str = "#888888"
    system: str = "#00ff00"
    error: str = "#ff0000"
    warning: str = "#ffff00"
    success: str = "#00ff00"
    combat: str = "#ff0000"
    damage: str = "#ff0000"
    healing: str = "#00ff00"
    spell: str = "#0088ff"
    skill: str = "#00ff00"
    quest: str = "#ffff00"
    
    # Score/stats display
    score_label: str = "#00ffff"
    score_value: str = "#ffffff"
    ability_list_header: str = "#ffff55"
    equipment_slot: str = "#00ffff"
    equipment_item: str = "#ffffff"
    equipment_empty: str = "#777777"
    gold: str = "#ffd700"
    hp: str = "#ff5555"
    mp: str = "#5599ff"
    stamina: str = "#ffd166"
    
    # Dialogue
    dialogue: str = "#ffff00"
    prompt: str = "#d8dee9"
    input: str = "#ffffff"
    
    # Prompt components
    prompt_marker: str = "#00ff00"
    prompt_hp: str = "#ff0000"
    prompt_mana: str = "#0088ff"
    prompt_stamina: str = "#ffff00"
    prompt_xp: str = "#00ff00"
    prompt_gold: str = "#ffff00"
    prompt_mv: str = "#00ffff"
    prompt_alignment: str = "#ff00ff"
    prompt_position: str = "#00ffff"
    prompt_target: str = "#ff00ff"
    prompt_area: str = "#00ffff"
    prompt_time: str = "#888888"


@dataclass
class MudClientRuntimeConfig:
    """Client-side MUD preferences."""
    auto_scroll: bool = True
    pause_auto_scroll_when_scrolled_up: bool = True
    command_echo: bool = True
    command_history_size: int = 100
    scrollback_size: int = 1000
    compact_mode: bool = False
    wide_mode: bool = False
    font_size: int = 12


def get_default_mud_colors() -> dict[str, str]:
    """Get default MUD color configuration as dict."""
    config = MudColorConfig()
    result = {}
    for field_name in MudColorConfig.__dataclass_fields__:
        result[field_name] = getattr(config, field_name)
    return result

SUPPORTED_MUD_COLOR_ROLES = list(MudColorConfig.__dataclass_fields__)


def normalize_mud_color_overrides(colors: dict | None) -> dict[str, str]:
    """Return supported, non-blank custom MUD color overrides."""
    if not isinstance(colors, dict):
        return {}
    allowed = set(SUPPORTED_MUD_COLOR_ROLES)
    result: dict[str, str] = {}
    for key, value in colors.items():
        if key not in allowed:
            continue
        clean = str(value or "").strip()
        if not clean or clean == "-":
            continue
        result[key] = clean
    return result


def get_mud_color_presets() -> dict[str, dict[str, str]]:
    """Built-in MUD color presets keyed by display name."""
    dark_fantasy = get_default_mud_colors()
    return {
        "Dark Fantasy": dark_fantasy,
        "Classic MUD": {**dark_fantasy, **{role: "#d8dee9" for role in SUPPORTED_MUD_COLOR_ROLES}, "ability_list_header":"#ffff55", "exit": "#33ff66", "command_echo": "#b9c8dd", "error": "#ff6b6b", "warning": "#ffd166", "success": "#7ee787", "gold": "#ffd700", "hp": "#ff7777", "mp": "#7aa2ff", "stamina": "#ffd166"},
        "Green Terminal": {**{role: "#33ff66" for role in SUPPORTED_MUD_COLOR_ROLES}, "content":"#ffffff", "room_description":"#ffffff", "dialogue":"#ffffff", "equipment_slot":"#00ffff", "equipment_item":"#ffffff", "equipment_empty":"#777777", "prompt_hp":"#ff5555", "prompt_mana":"#5599ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
        "Amber Terminal": {**{role: "#ffbf00" for role in SUPPORTED_MUD_COLOR_ROLES}, "content":"#ffffff", "room_description":"#ffffff", "equipment_slot":"#00ffff", "equipment_item":"#ffffff", "equipment_empty":"#777777", "prompt_hp":"#ff5555", "prompt_mana":"#5599ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
        "High Contrast": {**dark_fantasy, "content":"#ffffff", "equipment_empty":"#aaaaaa", "room_description": "#ffffff", "exit": "#7cff7c", "error": "#ff5555", "warning": "#ffff55", "score_label": "#00ffff", "score_value": "#ffffff"},
        "Colorblind Friendly": {**dark_fantasy, "content":"#ffffff", "equipment_empty":"#999999", "prompt_stamina":"#f0e442", "exit": "#56b4e9", "spell": "#cc79a7", "gold": "#f0e442", "damage": "#d55e00", "healing": "#009e73", "hp": "#d55e00", "mp": "#56b4e9"},
    }


def resolve_mud_colors(selected_preset: str | None, custom_roles: dict | None) -> dict[str, str]:
    presets = get_mud_color_presets()
    preset_name = selected_preset if selected_preset in presets else "Dark Fantasy"
    return {**presets[preset_name], **normalize_mud_color_overrides(custom_roles)}

@dataclass
class MudRuntimeConfig:
    """Server-side Smart MUD runtime configuration."""
    default_world_id: str = ""
    ai_provider: str = "null"
    telnet_enabled: bool = False
    telnet_host: str = "127.0.0.1"
    telnet_port: int = 4000
    telnet_max_connections: int = 25


class MudRuntimeConfigStore:
    """JSON config store for Smart MUD startup settings."""

    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)

    def load(self) -> MudRuntimeConfig:
        import json
        if not self.path.exists():
            return MudRuntimeConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return MudRuntimeConfig()
        return MudRuntimeConfig(
            default_world_id=str(data.get("default_world_id", "")),
            ai_provider=str(data.get("ai_provider", "null")),
            telnet_enabled=bool(data.get("telnet_enabled", False)),
            telnet_host=str(data.get("telnet_host", "127.0.0.1")),
            telnet_port=int(data.get("telnet_port", 4000)),
            telnet_max_connections=int(data.get("telnet_max_connections", 25)),
        )

    def save(self, config: MudRuntimeConfig) -> None:
        import json
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.__dict__, indent=2), encoding="utf-8")
