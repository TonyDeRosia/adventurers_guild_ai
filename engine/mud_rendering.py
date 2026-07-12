"""Semantic MUD renderer: game state stores tags, presentation chooses colors."""
from __future__ import annotations
import html, re
from typing import Any

SEMANTIC_COLOR_ROLES = ["object_title","object_description","object_interaction","usage","placeholder","feature","entity_title","entity_description","direction","room_name","area_name","room_description","content","contents_heading","exit","npc","mob","npc_friendly","npc_neutral","npc_hostile","monster","player","object","item_common","item_uncommon","item_rare","item_epic","item_legendary","command_echo","system","error","warning","success","combat","damage","healing","spell","skill","magic","quest","score_label","score_value","equipment_slot","equipment_item","equipment_empty","gold","hp","mp","stamina","dialogue","prompt","input","prompt_marker","prompt_hp","prompt_mana","prompt_stamina","prompt_xp","prompt_gold"]
PRESETS = {
 "Classic MUD": {**{r: "#d8dee9" for r in SEMANTIC_COLOR_ROLES}, "room_name":"#ffff00", "room_description":"#ffffff", "content":"#ffffff", "contents_heading":"#00ff00", "exit":"#00ff00", "equipment_slot":"#00ffff", "equipment_item":"#ffffff", "equipment_empty":"#777777", "prompt_hp":"#ff0000", "prompt_mana":"#0088ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
 "Green Terminal": {**{r: "#33ff66" for r in SEMANTIC_COLOR_ROLES}, "content":"#ffffff", "room_description":"#ffffff", "dialogue":"#ffffff", "equipment_slot":"#00ffff", "equipment_item":"#ffffff", "equipment_empty":"#777777", "prompt_hp":"#ff5555", "prompt_mana":"#5599ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
 "Amber Terminal": {**{r: "#ffbf00" for r in SEMANTIC_COLOR_ROLES}, "content":"#ffffff", "room_description":"#ffffff", "equipment_slot":"#00ffff", "equipment_item":"#ffffff", "equipment_empty":"#777777", "prompt_hp":"#ff5555", "prompt_mana":"#5599ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
 "Dark Fantasy": {**{r: "#c9b79c" for r in SEMANTIC_COLOR_ROLES}, "content":"#ffffff", "contents_heading":"#7ee787", "equipment_slot":"#00ffff", "equipment_item":"#ffffff", "equipment_empty":"#777777", "room_name":"#f2d27c", "exit":"#87ceeb", "npc_friendly":"#9be28f", "npc_hostile":"#ff6b6b", "magic":"#b48cff", "dialogue":"#ffffff", "prompt_hp":"#ff7777", "prompt_mana":"#7aa2ff", "prompt_stamina":"#ffd166", "prompt_gold":"#ffd700"},
 "High Contrast": {**{r: "#ffffff" for r in SEMANTIC_COLOR_ROLES}, "contents_heading":"#00ff00", "exit":"#00ff00", "equipment_slot":"#00ffff", "equipment_empty":"#aaaaaa", "prompt_hp":"#ff5555", "prompt_mana":"#5599ff", "prompt_stamina":"#ffff55"},
 "Colorblind Friendly": {**{r: "#e6e6e6" for r in SEMANTIC_COLOR_ROLES}, "content":"#ffffff", "equipment_slot":"#56b4e9", "equipment_item":"#ffffff", "equipment_empty":"#999999", "prompt_hp":"#d55e00", "prompt_mana":"#56b4e9", "prompt_stamina":"#f0e442", "exit":"#56b4e9", "magic":"#cc79a7", "prompt_gold":"#f0e442", "damage":"#d55e00", "healing":"#009e73"},
}
TAG_RE = re.compile(r"\{(/?)([a-z_]+)\}")
PROMPT_TAG_RE = re.compile(r"\{/?prompt_[a-z_]+\}")

MUD_COLOR_CODES = {"w":"white","W":"white","r":"red","R":"red","g":"green","G":"green","y":"yellow","Y":"yellow","b":"blue","B":"blue","m":"magenta","M":"magenta","c":"cyan","C":"cyan"}
MUD_COLOR_TO_ANSI = {"white":"37","red":"31","green":"32","yellow":"33","blue":"34","magenta":"35","cyan":"36"}
MUD_COLOR_RE = re.compile(r"&([wWrRgGyYbBmMcCnN])")
UNSAFE_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

def validate_mud_color_markup(text: str) -> list[str]:
    raw=str(text or ""); errors=[]
    if UNSAFE_ANSI_RE.search(raw): errors.append("unsafe raw ANSI escape sequence")
    if re.search(r"<\s*/?\s*(script|style|span|div|br|html|body)\b", raw, re.I): errors.append("embedded HTML is not allowed")
    for bad in re.findall(r"&([^wWrRgGyYbBmMcCnN\s])", raw): errors.append(f"unsupported color token &{bad}")
    if any((ord(ch)<32 and ch not in "\n\r\t") for ch in raw): errors.append("invalid control character")
    return errors

def strip_mud_color_markup(text: str) -> str:
    return MUD_COLOR_RE.sub("", str(text or ""))

def render_mud_color_html(text: str) -> str:
    raw=UNSAFE_ANSI_RE.sub("", str(text or ""))
    parts=[]; pos=0; open_span=False
    for m in MUD_COLOR_RE.finditer(raw):
        parts.append(html.escape(raw[pos:m.start()]))
        code=m.group(1)
        if open_span:
            parts.append("</span>"); open_span=False
        if code not in {"n","N"}:
            color=MUD_COLOR_CODES[code]; parts.append(f'<span class="mud-color-{color}" data-mud-color="{color}">'); open_span=True
        pos=m.end()
    parts.append(html.escape(raw[pos:]))
    if open_span: parts.append("</span>")
    return "".join(parts).replace("\n","<br>")

def render_mud_color_ansi(text: str) -> str:
    raw=UNSAFE_ANSI_RE.sub("", str(text or ""))
    def repl(m):
        code=m.group(1)
        return "\033[0m" if code in {"n","N"} else f"\033[{MUD_COLOR_TO_ANSI[MUD_COLOR_CODES[code]]}m"
    return MUD_COLOR_RE.sub(repl, raw) + "\033[0m"

def semantic(role: str, text: Any) -> str:
    role = role if role in SEMANTIC_COLOR_ROLES else "system"
    return f"{{{role}}}{text}{{/{role}}}"

def strip_prompt_block(text: str) -> str:
    text = str(text or "")
    text = re.split(r"\n(?=\{prompt_(?:hp|mana|stamina|xp|gold|marker)\})", text, maxsplit=1)[0]
    return PROMPT_TAG_RE.sub("", text).rstrip()

def render_semantic_html(text: str, colors: dict[str, str] | None = None) -> str:
    colors = colors or PRESETS["Dark Fantasy"]
    escaped = html.escape(strip_prompt_block(text))
    def repl(m: re.Match[str]) -> str:
        closing, role = m.group(1), m.group(2)
        if role not in SEMANTIC_COLOR_ROLES: return ""
        return "</span>" if closing else f'<span class="mud-{html.escape(role)}" role="{html.escape(role)}">'
    return TAG_RE.sub(repl, escaped).replace("\n", "<br>")

def render_semantic_plain(text: str) -> str:
    return strip_mud_color_markup(TAG_RE.sub("", strip_prompt_block(text)))

def render_legacy_mud_room(room: dict[str, Any], world: dict[str, Any], player: dict[str, Any], *, npcs: list[dict[str, Any]] | None = None, objects: list[dict[str, Any]] | None = None, narrative: list[str] | None = None, corpses: list[dict[str, Any]] | None = None) -> str:
    npcs = [n for n in (npcs or []) if str(n.get("status", "alive")) == "alive"]; objects = objects or []; narrative = narrative or []; corpses = corpses or []
    lines = [semantic("room_name", room.get("name", "Unknown Room")), semantic("area_name", world.get("name", "Unknown World")), "", semantic("room_description", room.get("long_description") or room.get("short_description", "")), "", "You see:"]
    for npc in npcs: lines.append(semantic(f"npc_{npc.get('disposition','neutral')}" if npc.get('disposition') in {'friendly','neutral','hostile'} else "npc_neutral", npc.get("name", npc.get("id", "NPC"))))
    for obj in objects: lines.append(semantic("item_common", obj.get("name", obj.get("id", "Object"))))
    for corpse in corpses: lines.append(semantic("combat", corpse.get("name") or f"corpse of {corpse.get('npc_id', 'mob')}"))
    lines += ["", "Exits:"] + [semantic("exit", e.get("direction", "")) for e in room.get("exits", []) if not e.get("hidden")]
    if narrative: lines += [""] + [semantic("dialogue", n) for n in narrative]
    hp, max_hp = player.get("hp", 0), player.get("max_hp", 0)
    mana = player.get("mana", player.get("energy_or_mana", 0)); max_mana = player.get("max_mana", mana)
    stm = player.get("stamina", player.get("Stamina", 0)); max_stm = player.get("max_stamina", stm)
    level = player.get("level", 1)
    xp = player.get("xp", 0)
    gold = player.get("gold", 0)
    race = player.get("race", "Human")
    char_class = player.get("class", player.get("char_class", "Adventurer"))
    prompt = (
        f"{semantic('prompt_hp', f'HP {hp}/{max_hp}')}  "
        f"{semantic('prompt_mana', f'MP {mana}/{max_mana}')}  "
        f"{semantic('prompt_stamina', f'STM {stm}/{max_stm}')}  "
        f"LVL {level}  "
        f"{semantic('prompt_xp', f'XP {xp}')}  "
        f"{semantic('prompt_gold', f'Gold {gold}')}"
    )
    lines += ["", prompt, f"{race} {char_class}", str(room.get("name", "")), semantic("prompt_marker", ">")]
    return "\n".join(lines)
