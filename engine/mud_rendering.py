"""Semantic MUD renderer: game state stores tags, presentation chooses colors."""
from __future__ import annotations
import html, re
from typing import Any

SEMANTIC_COLOR_ROLES = ["room_name","area_name","room_description","npc_friendly","npc_neutral","npc_hostile","monster","player","item_common","item_uncommon","item_rare","item_epic","item_legendary","exit","quest","magic","combat","damage","healing","system","warning","error","prompt_marker","prompt_hp","prompt_mana","prompt_stamina","prompt_xp","prompt_gold","dialogue"]
PRESETS = {
 "Classic MUD": {r: "#d8dee9" for r in SEMANTIC_COLOR_ROLES},
 "Green Terminal": {r: "#33ff66" for r in SEMANTIC_COLOR_ROLES},
 "Amber Terminal": {r: "#ffbf00" for r in SEMANTIC_COLOR_ROLES},
 "Dark Fantasy": {**{r: "#c9b79c" for r in SEMANTIC_COLOR_ROLES}, "room_name":"#f2d27c", "exit":"#87ceeb", "npc_friendly":"#9be28f", "npc_hostile":"#ff6b6b", "magic":"#b48cff", "prompt_hp":"#ff7777", "prompt_mana":"#7aa2ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
 "High Contrast": {r: "#ffffff" for r in SEMANTIC_COLOR_ROLES},
 "Colorblind Friendly": {**{r: "#e6e6e6" for r in SEMANTIC_COLOR_ROLES}, "exit":"#56b4e9", "magic":"#cc79a7", "prompt_gold":"#f0e442", "damage":"#d55e00", "healing":"#009e73"},
}
TAG_RE = re.compile(r"\{(/?)([a-z_]+)\}")

def semantic(role: str, text: Any) -> str:
    role = role if role in SEMANTIC_COLOR_ROLES else "system"
    return f"{{{role}}}{text}{{/{role}}}"

def render_semantic_html(text: str, colors: dict[str, str] | None = None) -> str:
    colors = colors or PRESETS["Dark Fantasy"]
    escaped = html.escape(text)
    def repl(m: re.Match[str]) -> str:
        closing, role = m.group(1), m.group(2)
        if role not in SEMANTIC_COLOR_ROLES: return ""
        return "</span>" if closing else f'<span class="mud-{role}" style="color:{html.escape(colors.get(role, "#ffffff"))}">' 
    return TAG_RE.sub(repl, escaped).replace("\n", "<br>")

def render_semantic_plain(text: str) -> str:
    return TAG_RE.sub("", text)

def render_room(room: dict[str, Any], world: dict[str, Any], player: dict[str, Any], *, npcs: list[dict[str, Any]] | None = None, objects: list[dict[str, Any]] | None = None, narrative: list[str] | None = None) -> str:
    npcs = npcs or []; objects = objects or []; narrative = narrative or []
    lines = [semantic("room_name", room.get("name", "Unknown Room")), semantic("area_name", world.get("name", "Unknown World")), "", semantic("room_description", room.get("long_description") or room.get("short_description", "")), "", "You see:"]
    for npc in npcs: lines.append(semantic(f"npc_{npc.get('disposition','neutral')}" if npc.get('disposition') in {'friendly','neutral','hostile'} else "npc_neutral", npc.get("name", npc.get("id", "NPC"))))
    for obj in objects: lines.append(semantic("item_common", obj.get("name", obj.get("id", "Object"))))
    lines += ["", "Exits:"] + [semantic("exit", e.get("direction", "")) for e in room.get("exits", []) if not e.get("hidden")]
    if narrative: lines += [""] + [semantic("dialogue", n) for n in narrative]
    hp, max_hp = player.get("hp", 0), player.get("max_hp", 0)
    mana = player.get("mana", player.get("energy_or_mana", 0)); max_mana = player.get("max_mana", mana)
    stm = player.get("stamina", player.get("Stamina", 0)); max_stm = player.get("max_stamina", stm)
    lines += ["", f"{semantic('prompt_hp', f'HP {hp}/{max_hp}')}  {semantic('prompt_mana', f'MP {mana}/{max_mana}')}  {semantic('prompt_stamina', f'STM {stm}/{max_stm}')}  LVL {player.get('level',1)}  {semantic('prompt_xp', f'XP {player.get('xp',0)}')}  {semantic('prompt_gold', f'Gold {player.get('gold',0)}')}", f"{player.get('race','Human')} {player.get('class', player.get('char_class','Adventurer'))}", str(room.get("name", "")), semantic("prompt_marker", ">")]
    return "\n".join(lines)
