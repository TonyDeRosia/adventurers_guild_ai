"""Smart MUD display rendering engine with semantic color roles."""

from __future__ import annotations

from typing import Any, Optional

from dataclasses import dataclass, field
from enum import Enum

class DisplayIntent(str, Enum):
    ROOM = "ROOM"; TARGET_LOOK = "TARGET_LOOK"; TARGET_EXAMINE = "TARGET_EXAMINE"; IDENTIFY = "IDENTIFY"; READ = "READ"; LOOK_INSIDE = "LOOK_INSIDE"; LOOK_DIRECTION = "LOOK_DIRECTION"; EXITS = "EXITS"
    INVENTORY = "INVENTORY"; EQUIPMENT = "EQUIPMENT"; SCORE = "SCORE"; ATTRIBUTES = "ATTRIBUTES"; AFFECTS = "AFFECTS"; SKILLS = "SKILLS"; SPELLS = "SPELLS"; COOLDOWNS = "COOLDOWNS"; PROMPT = "PROMPT"; COMBAT_STATUS = "COMBAT_STATUS"; QUEST_STATUS = "QUEST_STATUS"
    ITEM_ACTION = "ITEM_ACTION"; MOVEMENT = "MOVEMENT"; POSTURE = "POSTURE"; COMMUNICATION = "COMMUNICATION"; SOCIAL = "SOCIAL"; SHOP = "SHOP"; BOARD = "BOARD"; QUEST = "QUEST"; TRAINER = "TRAINER"; CRAFTING = "CRAFTING"; GATHERING = "GATHERING"
    COMBAT = "COMBAT"; DEATH = "DEATH"; REWARD = "REWARD"; RESPAWN = "RESPAWN"; AMBIENT = "AMBIENT"
    HELP = "HELP"; WHO = "WHO"; WHERE = "WHERE"; SYSTEM = "SYSTEM"; SUCCESS = "SUCCESS"; WARNING = "WARNING"; ERROR = "ERROR"; ADMIN = "ADMIN"; BUILDER = "BUILDER"

@dataclass
class DisplayEntry:
    text: str
    role: str = "system"
    quantity: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DisplaySegment:
    text: str
    role: str = "content"
    trusted_markup: bool = False

@dataclass
class DisplayLine:
    text: str = ""
    role: str = "system"
    trusted_markup: bool = False
    segments: list[DisplaySegment] = field(default_factory=list)

@dataclass
class DisplayField:
    label: str
    value: Any
    label_role: str = "score_label"
    value_role: str = "score_value"
    trusted_markup: bool = False
    occupied: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DisplaySection:
    title: str = ""
    lines: list[Any] = field(default_factory=list)
    entries: list[DisplayEntry] = field(default_factory=list)
    fields: list[Any] = field(default_factory=list)
    role: str = "system"
    title_role: str = "system"

@dataclass
class DisplayDocument:
    intent: DisplayIntent | str
    title: str = ""
    semantic_role: str = "system"
    title_role: str = "system"
    subtitle: str = ""
    subtitle_role: str = "system"
    paragraphs: list[Any] = field(default_factory=list)
    lines: list[Any] = field(default_factory=list)
    sections: list[DisplaySection] = field(default_factory=list)
    footer: str = ""
    spacing: str = "major"
    renderer_hints: dict[str, Any] = field(default_factory=dict)
    debug_metadata: dict[str, Any] = field(default_factory=dict)

def normalize_sentence(text: Any) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return ""
    raw = re.sub(r"([.!?]){2,}$", r"\1", raw)
    if raw[-1] not in ".!?]>)\"\'":
        raw += "."
    return raw

def _line_text(line: Any) -> str:
    if isinstance(line, DisplayLine) and line.segments:
        return "".join(str(seg.text) for seg in line.segments)
    return str(getattr(line, "text", line))

def _line_role(line: Any, default: str = "system") -> str:
    return str(getattr(line, "role", default) or default)

def _line_trusted(line: Any) -> bool:
    return bool(getattr(line, "trusted_markup", False))

def _render_entry_plain(entry: DisplayEntry) -> str:
    if entry.metadata.get("room_group") and entry.quantity and entry.quantity > 1:
        return f"({entry.quantity}) {entry.text}"
    qty = f"{entry.quantity}x " if entry.quantity and entry.quantity > 1 else ""
    return qty + str(entry.text)

def render_display_plain(doc: DisplayDocument) -> str:
    blocks: list[str] = []
    if doc.title:
        blocks.append(str(doc.title).strip())
    if doc.subtitle:
        blocks.append(str(doc.subtitle).strip())
    para = [p.strip() for p in doc.paragraphs if str(p).strip()]
    if para:
        blocks.append("\n".join(para))
    if doc.lines:
        blocks.append("\n".join(_line_text(x).rstrip() for x in doc.lines if _line_text(x).strip()))
    for section in doc.sections:
        lines: list[str] = []
        if section.title:
            lines.append(str(section.title).strip())
        lines.extend(_line_text(x).rstrip() for x in section.lines if _line_text(x).strip())
        lines.extend(_render_entry_plain(e) for e in section.entries if str(e.text).strip())
        lines.extend(_render_field_plain(f) for f in section.fields)
        if lines:
            blocks.append("\n".join(lines))
    if doc.footer:
        blocks.append(str(doc.footer).strip())
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(b for b in blocks if b.strip())).strip()

def _role(role: str, default: str = "system") -> str:
    return role if role in SEMANTIC_COLOR_ROLES else default

def _mud(role: str, text: Any) -> str:
    return semantic(_role(role), str(text))

def _render_field_plain(field: Any) -> str:
    if isinstance(field, DisplayField):
        return f"{field.label}: {field.value}"
    if isinstance(field, (tuple, list)) and len(field) >= 2:
        return f"{field[0]}: {field[1]}"
    return str(field)

def _render_field_mud(field: Any, section: DisplaySection) -> str:
    if isinstance(field, DisplayField):
        value = strip_mud_color_markup(str(field.value)) if field.trusted_markup else str(field.value)
        return f"{_mud(field.label_role, field.label + ':')} {_mud(field.value_role, value)}"
    if isinstance(field, (tuple, list)) and len(field) >= 2:
        return f"{_mud('score_label', str(field[0]) + ':')} {_mud(section.role, field[1])}"
    return _mud(section.role, field)


def _render_line_mud(line: Any, default_role: str) -> str:
    if isinstance(line, DisplayLine) and line.segments:
        return "".join(_mud(seg.role, strip_mud_color_markup(seg.text) if seg.trusted_markup else seg.text) for seg in line.segments)
    text = strip_mud_color_markup(_line_text(line)) if _line_trusted(line) else _line_text(line)
    return _mud(_line_role(line, default_role), text)

def _render_line_html(line: Any, default_role: str) -> str:
    if isinstance(line, DisplayLine) and line.segments:
        return "".join(_render_role_html(seg.role, seg.text, trusted_markup=seg.trusted_markup) for seg in line.segments)
    return _render_role_html(_line_role(line, default_role), _line_text(line).rstrip(), trusted_markup=_line_trusted(line))

def _render_field_html(field: Any, section: DisplaySection) -> str:
    if isinstance(field, DisplayField):
        return f"{_render_role_html(field.label_role, field.label + ':')} {_render_role_html(field.value_role, field.value, trusted_markup=field.trusted_markup)}"
    return semantic_html(_render_field_mud(field, section))

def render_display_mud(doc: DisplayDocument) -> str:
    parts: list[str] = []
    if doc.title: parts.append(_mud(getattr(doc, 'title_role', '') or doc.semantic_role, str(doc.title).strip()))
    if doc.subtitle: parts.append(_mud(getattr(doc, 'subtitle_role', '') or doc.semantic_role, str(doc.subtitle).strip()))
    paras=[_mud(_line_role(p, doc.semantic_role), _line_text(p).strip()) for p in doc.paragraphs if _line_text(p).strip()]
    if paras: parts.append("\n".join(paras))
    line_block=[_render_line_mud(x, doc.semantic_role).rstrip() for x in doc.lines if _line_text(x).strip()]
    if line_block: parts.append("\n".join(line_block))
    for section in doc.sections:
        lines=[]
        if section.title: lines.append(_mud(section.title_role or section.role, str(section.title).strip()))
        lines.extend(_render_line_mud(x, section.role).rstrip() for x in section.lines if _line_text(x).strip())
        lines.extend(_mud(e.role or section.role, _render_entry_plain(e)) for e in section.entries if str(e.text).strip())
        lines.extend(_render_field_mud(f, section) for f in section.fields)
        if lines: parts.append("\n".join(lines))
    if doc.footer: parts.append(_mud(doc.semantic_role, str(doc.footer).strip()))
    text = re.sub(r"\n{3,}", "\n\n", "\n\n".join(p for p in parts if p.strip())).strip()
    return text or _mud(doc.semantic_role, "Nothing to show.")

def _render_role_html(role: str, text: Any, *, trusted_markup: bool = False) -> str:
    role = _role(role)
    inner = render_mud_color_html(str(text)) if trusted_markup else html.escape(str(text))
    return f'<span role="{html.escape(role)}">{inner}</span>'

def render_display_html(doc: DisplayDocument) -> str:
    # Render each field independently. Trusted Builder markup is parsed only for
    # the specific authored line, avoiding global post-render string replacement
    # that can corrupt spans when the same text appears in multiple places.
    parts: list[str] = []
    if doc.title:
        parts.append(_render_role_html(getattr(doc, 'title_role', '') or doc.semantic_role, str(doc.title).strip()))
    if doc.subtitle:
        parts.append(_render_role_html(getattr(doc, 'subtitle_role', '') or doc.semantic_role, str(doc.subtitle).strip()))
    paras=[_render_role_html(_line_role(p, doc.semantic_role), _line_text(p).strip(), trusted_markup=_line_trusted(p)) for p in doc.paragraphs if _line_text(p).strip()]
    if paras: parts.append("<br>".join(paras))
    line_block=[_render_line_html(x, doc.semantic_role) for x in doc.lines if _line_text(x).strip()]
    if line_block: parts.append("<br>".join(line_block))
    for section in doc.sections:
        lines=[]
        if section.title: lines.append(_render_role_html(section.title_role or section.role, str(section.title).strip()))
        lines.extend(_render_line_html(x, section.role) for x in section.lines if _line_text(x).strip())
        lines.extend(_render_role_html(e.role or section.role, _render_entry_plain(e)) for e in section.entries if str(e.text).strip())
        lines.extend(_render_field_html(f, section) for f in section.fields)
        if lines: parts.append("<br>".join(lines))
    if doc.footer: parts.append(_render_role_html(doc.semantic_role, str(doc.footer).strip()))
    return re.sub(r"(?:\n\n){2,}", "\n\n", "\n\n".join(p for p in parts if p.strip())).strip() or _render_role_html(doc.semantic_role, "Nothing to show.")

def group_display_entries(items: list[dict[str, Any]], *, key_fields: tuple[str, ...] = ("name", "equipped_slot", "condition", "status")) -> list[DisplayEntry]:
    grouped: OrderedDict[tuple[Any, ...], DisplayEntry] = OrderedDict()
    for item in items:
        name = str(item.get("short_description") or item.get("name") or "something").strip()
        key = tuple(item.get(k) for k in key_fields) + (name,)
        if key not in grouped:
            grouped[key] = DisplayEntry(name, role=str(item.get("role") or "content"), quantity=0, metadata={"instance_ids": []})
        grouped[key].quantity += int(item.get("stack_count") or 1)
        if item.get("instance_id"):
            grouped[key].metadata.setdefault("instance_ids", []).append(item.get("instance_id"))
    return list(grouped.values())

def build_inventory_document(items: list[dict[str, Any]], *, carrying: str = "") -> DisplayDocument:
    doc = DisplayDocument(DisplayIntent.INVENTORY, title="Inventory", semantic_role="system")
    if items:
        doc.sections.append(DisplaySection(lines=[DisplayLine("You are carrying:")], entries=group_display_entries(items)))
    else:
        doc.paragraphs.append("You are not carrying anything.")
    if carrying:
        doc.sections.append(DisplaySection(title="Carrying", lines=[carrying]))
    return doc

def build_equipment_document(items: list[dict[str, Any]], slots: list[str]) -> DisplayDocument:
    by: dict[str, dict[str, Any]] = {}
    for item in items:
        for slot in str(item.get("equipped_slot") or "").split(","):
            slot = slot.strip()
            if slot == "both_hands":
                by["main_hand"] = item; by["off_hand"] = item
            elif slot:
                by[slot] = item
    fields: list[DisplayField] = []
    for slot in slots:
        item = by.get(slot)
        fields.append(DisplayField(
            slot.replace("_", " ").capitalize(),
            item.get("short_description") or item.get("name", "something") if item else "nothing",
            label_role="equipment_slot",
            value_role="equipment_item" if item else "equipment_empty",
            trusted_markup=bool(item and (item.get("trusted_markup") or item.get("safe_authored_markup", True))),
            occupied=bool(item),
            metadata={"instance_id": item.get("instance_id"), "template_id": item.get("template_id")} if item else {},
        ))
    return DisplayDocument(DisplayIntent.EQUIPMENT, title="Equipment", semantic_role="system", title_role="system", paragraphs=[] if items else [DisplayLine("You are not wearing anything.", role="equipment_empty")], sections=[DisplaySection(fields=fields)])

def build_prompt_document(character: Any) -> DisplayDocument:
    segments = [DisplaySegment("[", "prompt_marker"), DisplaySegment(f"{character.hp}/{character.max_hp} HP", "prompt_hp")]
    if getattr(character, "max_mana", 0): segments += [DisplaySegment(" ", "prompt"), DisplaySegment(f"{character.mana}/{character.max_mana} MP", "prompt_mana")]
    if getattr(character, "max_stamina", 0): segments += [DisplaySegment(" ", "prompt"), DisplaySegment(f"{character.stamina}/{character.max_stamina} ST", "prompt_stamina")]
    if getattr(character, "xp", None) is not None and getattr(character, "show_xp_in_prompt", False): segments += [DisplaySegment(" ", "prompt"), DisplaySegment(f"{character.xp} XP", "prompt_xp")]
    if getattr(character, "gold", None) is not None and getattr(character, "show_gold_in_prompt", False): segments += [DisplaySegment(" ", "prompt"), DisplaySegment(f"{character.gold} Gold", "prompt_gold")]
    segments.append(DisplaySegment("]", "prompt_marker"))
    return DisplayDocument(DisplayIntent.PROMPT, semantic_role="prompt", lines=[DisplayLine(segments=segments)])

import html
import re

from engine.mud_rendering import SEMANTIC_COLOR_ROLES, render_mud_color_html, strip_mud_color_markup
from engine.conditions import condition_label
from collections import OrderedDict

_SEMANTIC_TAG_RE = re.compile(r"\{(/?)([a-z_]+)\}")

def semantic_html(text: str) -> str:
    """Convert trusted semantic role tags to safe HTML spans."""
    escaped = html.escape(str(text or ""))
    def repl(match: re.Match[str]) -> str:
        closing, role = match.group(1), match.group(2)
        if role not in SEMANTIC_COLOR_ROLES:
            return ""
        return "</span>" if closing else f'<span role="{html.escape(role)}">'
    return _SEMANTIC_TAG_RE.sub(repl, escaped).replace("\n", "<br>")

def semantic(role: str, text: Any) -> str:
    role = role if role in SEMANTIC_COLOR_ROLES else "system"
    return f"{{{role}}}{text}{{/{role}}}"


def _display_name(value: Any) -> str:
    """Return a player-facing title, never an internal id fallback unless unavoidable."""
    text = str(value or "").strip()
    if not text:
        return "Unknown Room"
    if "_" in text or text.islower():
        return text.replace("_", " ").title()
    return text


def _entity_text(entity: Any, *, compact: bool = True) -> tuple[str, str]:
    if isinstance(entity, dict):
        name = entity.get("name") or entity.get("title") or entity.get("id") or ""
        room_text = entity.get("room_description") or entity.get("short_description") or ""
        if compact and entity.get("entity_type") in {"npc", "mob", "player"}:
            state = str(entity.get("current_state") or (entity.get("state") or {}).get("current_state") or entity.get("movement_state") or "standing").lower()
            target = entity.get("combat_target_name") or (entity.get("state") or {}).get("combat_target_name")
            if target:
                text = f"{name} is here, fighting {target}."
            elif state in {"sleeping", "resting", "sitting"}:
                text = f"{name} is {state} here."
            elif state in {"stunned", "incapacitated", "unconscious"}:
                text = f"{name} is {state}."
            elif condition_label(entity) not in {"unharmed", "dead"}:
                text = f"{name} is here, {condition_label(entity)}."
            else:
                text = str(room_text or name)
        elif compact and entity.get("entity_type") == "corpse":
            text = entity.get("room_description") or entity.get("short_description") or name
        else:
            text = name if compact else (room_text or name)
        desc = entity.get("long_description") or entity.get("description") or ""
        return str(text).strip(), str(desc).strip()
    return str(entity).strip(), ""


def presence_group_key(entity: Any) -> tuple[Any, ...] | None:
    """Return a conservative room-presence grouping key, or None for unique lines."""
    if not isinstance(entity, dict) or entity.get("entity_type") == "player":
        return None
    state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
    etype = entity.get("entity_type") or ("item" if entity.get("instance_id") else "")
    health = condition_label(entity)
    combat = state.get("combat_target_id") or state.get("combat_target_name")
    position = entity.get("current_state") or state.get("current_state") or entity.get("movement_state")
    owner = entity.get("owner_id") or entity.get("owner_type")
    lit = entity.get("status") or state.get("status") or state.get("lit")
    corpse_source = state.get("source_template_id") or state.get("source_entity_id") if etype == "corpse" else ""
    if combat or etype in {"corpse", "campfire", "campsite"}:
        return None
    return (etype, entity.get("template_id") or entity.get("id"), entity.get("name"), health, position, owner, lit, corpse_source)


CANONICAL_EXIT_ORDER = ["north", "west", "south", "east", "up", "down", "northeast", "northwest", "southeast", "southwest", "in", "out"]


def _room_description_paragraphs(room: Any, title: str) -> list[DisplayLine]:
    desc = str(getattr(room, "description", "") or "").strip()
    if desc.lower().startswith(title.lower()):
        desc = desc[len(title):].lstrip(" -:,.	")
        if desc and desc[0].islower(): desc = desc[0].upper() + desc[1:]
    return [DisplayLine(p.strip(), role="room_description", trusted_markup=True) for p in re.split(r"\n\s*\n", desc) if p.strip()]


def _exit_names(exits: Any) -> list[str]:
    names=[]
    if isinstance(exits, list):
        def key(ex: Any) -> int:
            d = str((ex.get("direction") or ex.get("dir")) if isinstance(ex, dict) else ex).lower()
            return CANONICAL_EXIT_ORDER.index(d) if d in CANONICAL_EXIT_ORDER else 999
        for exit_def in sorted(exits, key=key):
            direction = exit_def.get("direction") or exit_def.get("dir") if isinstance(exit_def, dict) else str(exit_def)
            if direction:
                closed = isinstance(exit_def, dict) and (exit_def.get("closed") or exit_def.get("locked"))
                names.append(f"({direction})" if closed else str(direction))
    return names


def build_room_document(room: Any, viewer: Any = None) -> DisplayDocument:
    title = _display_name(getattr(room, "title", "Unknown Room"))
    doc = DisplayDocument(DisplayIntent.ROOM, title=title, semantic_role="system", title_role="room_name")
    doc.paragraphs.extend(_room_description_paragraphs(room, title))
    visible_entries: list[DisplayEntry] = []
    for player in getattr(room, "players", []) or []:
        text, _ = _entity_text(player)
        if text and (viewer is None or text != getattr(viewer, "name", "")):
            visible_entries.append(DisplayEntry(text, role="content"))
    grouped: "OrderedDict[tuple[Any, ...], list[str]]" = OrderedDict()
    unique: list[str] = []
    for _role_name, seq in (("npc", getattr(room, "npcs", []) or []), ("mob", getattr(room, "mobs", []) or []), ("object", getattr(room, "objects", []) or [])):
        for ent in seq:
            text, _ = _entity_text(ent)
            if not text: continue
            key = presence_group_key(ent)
            if key is None: unique.append(text)
            else: grouped.setdefault(key, []).append(text)
    for entries in grouped.values():
        text=entries[0]
        visible_entries.append(DisplayEntry(text, role="content", quantity=len(entries), metadata={"grouped_count": len(entries), "room_group": True}))
    for text in unique: visible_entries.append(DisplayEntry(text, role="content"))
    if visible_entries:
        doc.sections.append(DisplaySection(title="You see:", entries=visible_entries, role="content", title_role="contents_heading"))
    exits = _exit_names(getattr(room, "exits", []) or [])
    doc.sections.append(DisplaySection(lines=[DisplayLine(f"[ Exits: {' '.join(exits) if exits else 'none'} ]", role="exit")], role="exit"))
    return doc


def render_room(room: Any, colors: dict[str, str] | None = None, character: Any = None) -> str:
    """Compatibility wrapper around the canonical room DisplayDocument."""
    return render_display_html(build_room_document(room, character))


def render_object(obj: Any) -> str:
    """Render an object for look/examine target output."""
    name, desc = _entity_text(obj, compact=False)
    if isinstance(obj, dict):
        name = str(obj.get("name") or obj.get("title") or name).strip()
    desc = desc or name
    return f'<span role="object">{render_mud_color_html(name)}</span>\n\n<span role="room_description">{render_mud_color_html(desc)}</span>'

def render_prompt(character: Any, colors: dict[str, str]) -> str:
    """Render the canonical configurable-style prompt as safe browser HTML."""
    return render_display_html(build_prompt_document(character))


def render_scrollback_line(output: str, role: str = "default", colors: dict[str, str] = None) -> str:
    """Render a single scrollback line with semantic role."""
    if colors is None:
        colors = {}
    
    return f'<span role="{html.escape(role)}">{html.escape(output)}</span>'


def render_command_echo(command: str, colors: dict[str, str]) -> str:
    """Render echoed command input."""
    return f'<span role="command_echo">&gt; {html.escape(command)}</span>'


def render_system_message(message: str, message_type: str = "system") -> str:
    """Render system message with appropriate role."""
    roles = {
        "system": "system",
        "error": "error",
        "warning": "warning",
        "combat": "combat",
        "quest": "quest",
    }
    role = roles.get(message_type, "system")
    return f'<span role="{role}">{html.escape(message)}</span>'


def render_combat_output(attacker: str, action: str, target: str, damage: int = 0, 
                        hit: bool = True, colors: dict[str, str] = None) -> str:
    """Render combat action output."""
    if colors is None:
        colors = {}
    
    if hit:
        return (
            f'<span role="combat">{html.escape(attacker)}</span> '
            f'<span role="combat">{html.escape(action)}</span> '
            f'<span role="combat">{html.escape(target)}</span> '
            f'<span role="damage">for {damage} damage</span>.'
        )
    else:
        return (
            f'<span role="combat">{html.escape(attacker)}</span> '
            f'<span role="combat">{html.escape(action)}</span> '
            f'<span role="warning">but misses</span> '
            f'<span role="combat">{html.escape(target)}</span>.'
        )


def render_dialogue(speaker: str, text: str, speaker_role: str = "npc") -> str:
    """Render dialogue with speaker color role."""
    role_colors = {
        "npc": "npc",
        "mob": "mob",
        "player": "player",
    }
    role = role_colors.get(speaker_role, "dialogue")
    
    return (
        f'<span role="{role}">{html.escape(speaker)}</span> '
        f'<span role="dialogue">says: "{render_mud_color_html(text)}"</span>'
    )


def render_inventory_list(character: Any, colors: dict[str, str]) -> str:
    """Render inventory display."""
    if not character.inventory:
        return '<span role="system">You are not carrying anything.</span>'
    
    lines = ['<span role="system">You are carrying:</span>']
    for item in character.inventory:
        item_name = item.get('name', 'unknown')
        qty = item.get('quantity', 1)
        rarity = item.get('rarity', 'common')
        role = f"item_{rarity}"
        
        qty_str = f" x{qty}" if qty > 1 else ""
        lines.append(f'  <span role="{role}">{html.escape(item_name)}</span>{qty_str}')
    
    return '\n'.join(lines)


def render_equipment_list(character: Any, colors: dict[str, str]) -> str:
    """Render equipment display."""
    if not character.equipment:
        return '<span role="system">You are not wearing anything.</span>'
    
    lines = ['<span role="system">You are wearing:</span>']
    for slot, item in character.equipment.items():
        item_name = item.get('name', 'empty') if item else 'empty'
        lines.append(
            f'  <span role="equipment_slot">{html.escape(slot)}</span>: '
            f'<span role="equipment_item">{html.escape(item_name)}</span>'
        )
    
    return '\n'.join(lines)


def apply_css_variables(colors: dict[str, str]) -> dict[str, str]:
    """Convert color roles to CSS variables for frontend application."""
    css_vars = {}
    for role, hex_color in colors.items():
        css_var_name = f"--mud-{role}"
        css_vars[css_var_name] = hex_color
    
    print(f"[mud-render] Generated {len(css_vars)} CSS variables")
    return css_vars
