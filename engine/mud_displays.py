"""Smart MUD display rendering engine with semantic color roles."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from dataclasses import dataclass, field
from enum import Enum

class DisplayIntent(str, Enum):
    ROOM = "ROOM"; TARGET_LOOK = "TARGET_LOOK"; TARGET_EXAMINE = "TARGET_EXAMINE"; IDENTIFY = "IDENTIFY"; READ = "READ"; LOOK_INSIDE = "LOOK_INSIDE"; LOOK_DIRECTION = "LOOK_DIRECTION"; EXITS = "EXITS"
    INVENTORY = "INVENTORY"; EQUIPMENT = "EQUIPMENT"; SCORE = "SCORE"; WORTH = "WORTH"; ATTRIBUTES = "ATTRIBUTES"; AFFECTS = "AFFECTS"; SKILLS = "SKILLS"; SPELLS = "SPELLS"; COOLDOWNS = "COOLDOWNS"; PROMPT = "PROMPT"; COMBAT_STATUS = "COMBAT_STATUS"; QUEST_STATUS = "QUEST_STATUS"
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
class DisplayCell:
    text: str = ""
    role: str = "character_value"
    width: int | None = None
    align: str = "left"
    trusted_markup: bool = False
    segments: list[DisplaySegment] = field(default_factory=list)
    min_width: int = 4
    shrink_priority: int = 100
    wrap: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DisplayRow:
    cells: list[DisplayCell] = field(default_factory=list)
    role: str = "character_value"

@dataclass
class DisplayDivider:
    role: str = "character_frame"
    kind: str = "section"

@dataclass
class DisplayTable:
    rows: list[DisplayRow] = field(default_factory=list)
    role: str = "character_value"

@dataclass
class DisplayFrame:
    title: str = ""
    rows: list[Any] = field(default_factory=list)
    width: int = 79
    frame_role: str = "character_frame"
    title_role: str = "character_title"
    frame_style: str = "classic_double"
    title_alignment: str = "center"
    border_characters: dict[str, str] = field(default_factory=dict)
    divider_characters: dict[str, str] = field(default_factory=dict)

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


@dataclass(frozen=True)
class CharacterDisplaySnapshot:
    schema_version: str = "phase13c3-b.snapshot.v1"
    snapshot_version: str = "phase13c3-b.snapshot.v1"
    character_id: str = ""
    generated_at: str = ""
    identity: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    race: dict[str, Any] = field(default_factory=dict)
    character_class: dict[str, Any] = field(default_factory=dict)
    level: int = 1
    alignment: str = ""
    age: dict[str, Any] = field(default_factory=dict)
    location: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    progression: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    combat: dict[str, Any] = field(default_factory=dict)
    offense: dict[str, Any] = field(default_factory=dict)
    defense: dict[str, Any] = field(default_factory=dict)
    saves: dict[str, Any] = field(default_factory=dict)
    resistances: dict[str, Any] = field(default_factory=dict)
    criticals: dict[str, Any] = field(default_factory=dict)
    weapon_profile: dict[str, Any] = field(default_factory=dict)
    unarmed_profile: dict[str, Any] = field(default_factory=dict)
    speed: dict[str, Any] = field(default_factory=dict)
    carrying: dict[str, Any] = field(default_factory=dict)
    encumbrance: dict[str, Any] = field(default_factory=dict)
    currency: dict[str, Any] = field(default_factory=dict)
    survival: dict[str, Any] = field(default_factory=dict)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    time: dict[str, Any] = field(default_factory=dict)
    effects: list[dict[str, Any]] = field(default_factory=list)
    active_affects: list[dict[str, Any]] = field(default_factory=list)
    mechanics: dict[str, Any] = field(default_factory=dict)
    source_versions: dict[str, Any] = field(default_factory=dict)
    abilities: list[dict[str, Any]] = field(default_factory=list)
    cooldowns: list[dict[str, Any]] = field(default_factory=list)
    equipment: list[dict[str, Any]] = field(default_factory=list)
    inventory: list[dict[str, Any]] = field(default_factory=list)
    quest_summary: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DisplayStat:
    stat_id: str
    label: str
    value: Any = None
    formatted_value: str = ""
    unit: str = ""
    display_group: str = ""
    display_order: int = 0
    active: bool = True
    inactive_reason: str = ""
    visible: bool = True
    style_role: str = "character_value"
    tooltip: str = ""
    source_version: str = ""
    availability: str = "available"

@dataclass(frozen=True)
class ScoreViewModel:
    schema_version: str
    character_id: str
    generated_at: str = ""
    identity: tuple[DisplayStat, ...] = ()
    progression: tuple[DisplayStat, ...] = ()
    resources: tuple[DisplayStat, ...] = ()
    attributes: tuple[DisplayStat, ...] = ()
    offense: tuple[DisplayStat, ...] = ()
    defense: tuple[DisplayStat, ...] = ()
    damage: tuple[DisplayStat, ...] = ()
    criticals: tuple[DisplayStat, ...] = ()
    saves: tuple[DisplayStat, ...] = ()
    resistances: tuple[DisplayStat, ...] = ()
    speed: tuple[DisplayStat, ...] = ()
    carrying: tuple[DisplayStat, ...] = ()
    survival: tuple[DisplayStat, ...] = ()
    conditions: tuple[DisplayStat, ...] = ()
    effects: tuple[dict[str, Any], ...] = ()
    companions: tuple[DisplayStat, ...] = ()
    location: tuple[DisplayStat, ...] = ()
    currencies: tuple[DisplayStat, ...] = ()
    mechanics: tuple[DisplayStat, ...] = ()
    availability: dict[str, str] = field(default_factory=dict)
    source_versions: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class AbilityDisplaySnapshot:
    ability_id: str = ""
    display_name: str = "Ability"
    ability_kind: str = "ability"
    category: str = "General"
    rank: int = 1
    maximum_rank: int = 1
    description: str = ""
    resource_costs: tuple[dict[str, Any], ...] = ()
    cooldown_remaining: Any = None
    cooldown_duration: Any = None
    target_mode: str = "Self"
    range_summary: str = ""
    cast_time: str = ""
    availability: str = "unknown"
    availability_reason_code: str = "unknown"
    availability_text: str = "Availability unknown."
    passive: bool = False
    learned_source_display: str = ""
    usage_syntax: str = ""
    visible_tags: tuple[str, ...] = ()

def _as_mapping(obj: Any) -> dict[str, Any]:
    return obj if isinstance(obj, dict) else {}

def _canonical_tnl(character: Any) -> Any:
    for name in ("xp_to_next_level", "tnl", "experience_to_next_level"):
        if hasattr(character, name):
            value = getattr(character, name)
            if value is not None: return value
    prog = getattr(character, "progression", None)
    if isinstance(prog, dict):
        for name in ("xp_to_next_level", "tnl", "experience_to_next_level"):
            if prog.get(name) is not None: return prog.get(name)
    if hasattr(character, "next_level_xp") and hasattr(character, "xp"):
        return max(0, int(getattr(character, "next_level_xp") or 0) - int(getattr(character, "xp") or 0))
    return None

def build_character_display_snapshot(character: Any) -> CharacterDisplaySnapshot:
    """Compatibility adapter for tests and legacy callers.

    Live runtime commands use CharacterDisplaySnapshotService directly; this
    helper is intentionally only the single fallback boundary for older tests
    that pass ad-hoc SimpleNamespace character objects to builders.
    """
    from engine.display_services import CharacterDisplaySnapshotService
    return CharacterDisplaySnapshotService().build_snapshot(character)

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
    frames: list[DisplayFrame] = field(default_factory=list)

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


def _visible_width(text: Any) -> int:
    return len(strip_mud_color_markup(re.sub(r"\{/?[a-z_]+\}", "", html.unescape(str(text or "")))))

def _tokenize_markup(text: str) -> list[tuple[str, str]]:
    """Return (kind, token) pairs without splitting markup/control tokens."""
    out=[]; i=0; text=str(text or "")
    while i < len(text):
        if text[i] == "{" and (m:=re.match(r"\{/?[a-z_]+\}", text[i:])):
            out.append(("markup", m.group(0))); i += len(m.group(0)); continue
        if text[i] == "&" and i+1 < len(text) and re.match(r"[A-Za-z0-9]", text[i+1]):
            out.append(("markup", text[i:i+2])); i += 2; continue
        if text[i] == "&" and (m:=re.match(r"&(?:[A-Za-z]+|#[0-9]+|#x[0-9A-Fa-f]+);", text[i:])):
            out.append(("char", html.unescape(m.group(0)))); i += len(m.group(0)); continue
        out.append(("char", text[i])); i += 1
    return out

def _slice_visible(text: str, width: int) -> str:
    out=[]; visible=0
    for kind, token in _tokenize_markup(str(text or "")):
        if kind == "markup": out.append(token); continue
        if visible >= width: break
        out.append(token); visible += 1
    return "".join(out)

def _split_visible_once(text: str, width: int) -> tuple[str, str]:
    left=[]; right=[]; visible=0; into_right=False
    for kind, token in _tokenize_markup(str(text or "")):
        if kind == "markup":
            (right if into_right else left).append(token); continue
        if visible < width and not into_right:
            left.append(token); visible += 1
        else:
            into_right=True; right.append(token)
    return "".join(left), "".join(right)

def _pad_visible(text: str, width: int, align: str = "left") -> str:
    text = _slice_visible(str(text), max(0,width))
    missing = max(0, width - _visible_width(text))
    if align == "right": return " " * missing + text
    if align == "center":
        left = missing // 2; return " " * left + text + " " * (missing - left)
    return text + " " * missing

def _wrap_visible(text: str, width: int) -> list[str]:
    text=str(text or "")
    if width <= 0: return [""]
    if not text: return [_pad_visible("", width)]
    lines=[]; cur=""
    for word in text.split(" "):
        candidate = word if not cur else cur + " " + word
        if _visible_width(candidate) <= width:
            cur = candidate; continue
        if cur:
            lines.append(_pad_visible(cur, width)); cur=""
        while _visible_width(word) > width:
            piece, word = _split_visible_once(word, width)
            lines.append(_pad_visible(piece, width))
        cur = word
    if cur or not lines: lines.append(_pad_visible(cur, width))
    return lines


def _frame_chars(frame: DisplayFrame, kind: str) -> tuple[str,str,str]:
    chars=getattr(frame, "border_characters", None) or {}
    divs=getattr(frame, "divider_characters", None) or {}
    style=str(getattr(frame, "frame_style", "classic_double") or "classic_double").lower()
    if style in {"classic_single", "single"}:
        defaults={"top":("┌","─","┐"),"bottom":("└","─","┘"),"section":("├","─","┤"),"item":("├","─","┤"),"row":("│"," ","│")}
    else:
        defaults={"top":("╔","═","╗"),"bottom":("╚","═","╝"),"section":("╠",divs.get("section","═"),"╣"),"item":("╟",divs.get("item","─"),"╢"),"row":("║"," ","║")}
    if kind == "row":
        return (chars.get("side", defaults["row"][0]), " ", chars.get("side", defaults["row"][2]))
    names={"top":("top_left","top","top_right"),"bottom":("bottom_left","bottom","bottom_right"),"section":("section_left","section","section_right"),"item":("item_left","item","item_right")}.get(kind,())
    base=defaults.get(kind, defaults["row"])
    return (chars.get(names[0], base[0]) if names else base[0], chars.get(names[1], divs.get(kind, base[1])) if names else base[1], chars.get(names[2], base[2]) if names else base[2])

def _frame_line_plain(frame: DisplayFrame, content: str = "", *, kind: str = "row") -> str:
    width=max(32,int(frame.width or 79)); inner=width-2
    style=str(getattr(frame, "frame_style", "classic_double") or "classic_double").lower()
    if style == "none": return content
    if style == "minimal":
        if kind == "top": return _pad_visible(str(getattr(frame, "title", "") or ""), width, getattr(frame, "title_alignment", "left"))
        if kind in {"section", "bottom"}: return "─" * min(width, max(1, inner))
        if kind == "item": return "-" * min(width, max(1, inner))
        return _pad_visible(content, width)
    if kind != "row":
        l,ch,r=_frame_chars(frame, kind); return l + ch*inner + r
    l,_,r=_frame_chars(frame, "row"); return l + _pad_visible(content, inner) + r

def _cell_segments(cell: DisplayCell) -> list[DisplaySegment]:
    return list(cell.segments) if cell.segments else [DisplaySegment(str(cell.text), cell.role, cell.trusted_markup)]


def resolve_theme_role(theme: Any, canonical_role: str) -> str:
    default_role_aliases = {
        "skills.name_header_role": "ability_list_header",
        "skills.proficiency_header_role": "ability_list_header",
        "spells.name_header_role": "ability_list_header",
        "spells.proficiency_header_role": "ability_list_header",
        "abilities.name_header_role": "ability_list_header",
        "abilities.proficiency_header_role": "ability_list_header",
    }
    base_role = default_role_aliases.get(canonical_role, canonical_role)
    role = str(((getattr(theme, "semantic_roles", {}) or {}).get(canonical_role)) or base_role)
    if "high_contrast" in tuple(getattr(theme, "accessibility", ()) or ()):
        role = {"character_frame":"character_title","character_muted":"character_value","equipment_empty":"character_value"}.get(role, role)
    if "colorblind" in tuple(getattr(theme, "accessibility", ()) or ()):
        role = {"character_positive":"success","character_negative":"warning"}.get(role, role)
    return role if role in SEMANTIC_COLOR_ROLES else (base_role if base_role in SEMANTIC_COLOR_ROLES else "system")

def theme_label(theme: Any, key: str, default: str) -> str:
    labels = getattr(theme, "labels", {}) or {}
    aliases = {"hp": "health", "practice": "practice_points", "training": "training_points"}
    return str(labels.get(key, labels.get(aliases.get(key, ""), default)))

def _seg(text: Any, role: str, theme: Any = None, trusted: bool = False) -> DisplaySegment:
    return DisplaySegment(str(text), resolve_theme_role(theme, role), trusted)

def build_empty_display_rows(family: str, theme: Any, default_message: str) -> list[DisplayLine]:
    policy = str(getattr(theme, "empty_section_policy", "hide") if theme is not None else "hide")
    labels = getattr(theme, "labels", {}) or {}
    if policy == "show_muted":
        label = labels.get(f"{family}.title", family.replace("_", " ").title())
        msg = labels.get(f"{family}.muted_empty", f"{label}: none" if family != "inventory" else f"{label}: empty")
        return [DisplayLine(msg, role=resolve_theme_role(theme, "character_muted"), trusted_markup=True)]
    if policy == "show_empty_message":
        return [DisplayLine(labels.get(f"{family}.empty", default_message), role=resolve_theme_role(theme, "character_muted"), trusted_markup=True)]
    return []

def _frame_segments(frame: DisplayFrame, content: str = "", *, kind: str = "row", role: str = "character_value", segments: list[DisplaySegment] | None = None) -> DisplayLine:
    if kind != "row": return DisplayLine(_frame_line_plain(frame, kind=kind), role=frame.frame_role)
    style=str(getattr(frame, "frame_style", "classic_double") or "classic_double").lower()
    inner=max(30,int(frame.width or 79)-(0 if style in {"minimal","none"} else 2))
    if segments is None: segments=[DisplaySegment(_pad_visible(content, inner), role)]
    if style in {"minimal", "none"}:
        return DisplayLine(segments=segments)
    side=_frame_chars(frame, "row")[0]
    return DisplayLine(segments=[DisplaySegment(side, frame.frame_role), *segments, DisplaySegment(side, frame.frame_role)])

def _field_segments(label: str, value: Any, *, value_role: str = "character_value", theme: Any = None) -> list[DisplaySegment]:
    return [_seg(f"{label}: ", "character_label", theme, True), _seg(str(value), value_role, theme)]

def _field_text(label: str, value: Any) -> str:
    return f"{label}: {value}"

def build_character_frame_document(intent: DisplayIntent | str, title: str, rows: list[Any], *, width: int = 79, theme: Any = None, show_title: bool = True) -> DisplayDocument:
    width = int(getattr(theme, "width", width) if theme is not None else width)
    label = (getattr(theme, "labels", {}) or {}).get(f"{str(intent).split('.')[-1].lower()}.title") or title
    frame=DisplayFrame(title=label, width=width, frame_role=resolve_theme_role(theme, "character_frame"), title_role=resolve_theme_role(theme, "character_title"), frame_style=getattr(theme, "frame_style", "classic_double") if theme else "classic_double", title_alignment=getattr(theme, "title_alignment", "center") if theme else "center", border_characters=dict(getattr(theme, "border_characters", {}) or {}), divider_characters=dict(getattr(theme, "divider_characters", {}) or {}))
    doc=DisplayDocument(intent, semantic_role=resolve_theme_role(theme, "character_value"), title_role=frame.title_role, frames=[frame])
    lines=[_frame_segments(frame, kind="top")]
    if show_title:
        lines.extend([_frame_segments(frame, segments=[_seg(_pad_visible(label, width-2, frame.title_alignment), "character_title", theme, True)]), _frame_segments(frame, kind="section")])
    for row in rows:
        if isinstance(row, DisplayDivider): lines.append(_frame_segments(frame, kind=row.kind)); continue
        if isinstance(row, DisplayLine):
            for wrapped in _wrap_visible(_line_text(row), width-2): lines.append(_frame_segments(frame, segments=[DisplaySegment(wrapped, _line_role(row,"character_value"), _line_trusted(row))]));
            continue
        if isinstance(row, DisplayRow):
            gap = 3
            inner = width - 2
            fixed_total = gap * max(0, len(row.cells)-1)
            auto = max(1, len([c for c in row.cells if not c.width]))
            specified = sum(int(c.width or 0) for c in row.cells)
            remaining = max(0, inner - fixed_total - specified)
            widths = [max(c.min_width, int(c.width or remaining // auto or c.min_width)) for c in row.cells]
            overflow = max(0, sum(widths) + fixed_total - inner)
            if overflow:
                order = sorted(range(len(row.cells)), key=lambda i: row.cells[i].shrink_priority, reverse=True)
                for i in order:
                    take = min(overflow, max(0, widths[i] - row.cells[i].min_width))
                    widths[i] -= take; overflow -= take
                    if overflow <= 0: break
            wrapped_cells=[]
            for cell, cwidth in zip(row.cells, widths):
                text = "".join(seg.text for seg in _cell_segments(cell))
                base_role = (_cell_segments(cell)[0].role if _cell_segments(cell) else cell.role)
                physical = _wrap_visible(text, cwidth) if cell.wrap else [_pad_visible(text, cwidth, cell.align)]
                wrapped_cells.append((cell, cwidth, base_role, [_pad_visible(x.rstrip(), cwidth, cell.align) for x in physical]))
            height = max((len(x[3]) for x in wrapped_cells), default=1)
            for line_idx in range(height):
                raw=[]
                for idx,(cell,cwidth,base_role,physical) in enumerate(wrapped_cells):
                    if idx: raw.append(DisplaySegment(" "*gap, row.role))
                    segs=_cell_segments(cell)
                    if line_idx == 0 and len(physical) == 1 and sum(_visible_width(seg.text) for seg in segs) <= cwidth:
                        used=0
                        if cell.align == "right":
                            pad=max(0,cwidth-sum(_visible_width(seg.text) for seg in segs)); raw.append(DisplaySegment(" "*pad, row.role)); used += pad
                        elif cell.align == "center":
                            pad=max(0,cwidth-sum(_visible_width(seg.text) for seg in segs)); left=pad//2; raw.append(DisplaySegment(" "*left, row.role)); used += left
                        for seg in segs:
                            raw.append(seg); used += _visible_width(seg.text)
                        if used < cwidth: raw.append(DisplaySegment(" "*(cwidth-used), row.role))
                    else:
                        raw.append(DisplaySegment(physical[line_idx] if line_idx < len(physical) else " "*cwidth, base_role, cell.trusted_markup))
                visible=sum(_visible_width(seg.text) for seg in raw)
                if visible < inner: raw.append(DisplaySegment(" "*(inner-visible), row.role))
                lines.append(_frame_segments(frame, segments=raw))
            continue
        for wrapped in _wrap_visible(str(row), width-2): lines.append(_frame_segments(frame, segments=[DisplaySegment(wrapped,"character_value")]))
    lines.append(_frame_segments(frame, kind="bottom")); doc.lines=lines; return doc

def _char(character: Any, *names: str, default: Any = "") -> Any:
    for n in names:
        if hasattr(character,n):
            v=getattr(character,n)
            if v not in (None,""): return v
    return default

def _row_fields(*pairs: tuple[str, Any, str], theme: Any = None) -> DisplayRow:
    cells=[]
    for label,value,*role in pairs:
        cells.append(DisplayCell(width=34, segments=_field_segments(label, value, value_role=role[0] if role else "character_value", theme=theme)))
    return DisplayRow(cells)

def _fmt_attr(data: Any) -> str:
    if isinstance(data, dict):
        base=data.get("base"); mod=data.get("modifier"); final=data.get("final")
        if base is not None and mod not in (None,0) and final is not None: return f"{base} ({mod:+}) = {final}"
        if final is not None: return str(final)
        if base is not None: return str(base)
    return str(data)

def _empty_row(section_id: str, theme: Any) -> DisplayLine | None:
    policy = str(getattr(theme, "empty_section_policy", "hide") if theme is not None else "hide")
    labels = getattr(theme, "labels", {}) or {}
    if policy == "show_muted": return DisplayLine(labels.get(f"{section_id}.empty", f"{section_id.title()}: none"), role="character_muted", trusted_markup=True)
    if policy == "show_empty_message":
        return DisplayLine(
            labels.get(
                f"{section_id}.empty",
                f"No {section_id.replace('_', ' ')} to show.",
            ),
            role="character_muted",
            trusted_markup=True,
        )
    return None

def _ordered_sections(section_rows: dict[str, list[Any]], theme: Any, *, required: set[str] | None = None) -> list[Any]:
    required = required or set()
    canonical = list(section_rows.keys())
    visible = tuple(getattr(theme, "visible_sections", ()) or ()) if theme is not None else ()
    order = tuple(getattr(theme, "section_order", ()) or ()) if theme is not None else ()
    allowed = set(visible) if visible else set(canonical)
    allowed |= required
    seq = [x for x in order if x in section_rows] + [x for x in canonical if x not in order]
    rows=[]; first=True
    for sid in seq:
        if sid not in allowed: continue
        part=list(section_rows.get(sid) or [])
        if not part:
            er=_empty_row(sid, theme)
            if er is not None: part=[er]
        if not part: continue
        if not first: rows.append(DisplayDivider())
        first=False; rows.extend(part)
    return rows or [DisplayLine("Character information is unavailable.", role="character_muted")]

SCORE_SCHEMA_VERSION = "phase13c3-b.snapshot.v1"
SCORE_CONTENT_WIDTH = 77
SCORE_VISIBLE_WIDTH = 81
SCORE_SECTION_TITLES = {
    "identity": "Character Identity", "progression": "Progression", "resources": "Resources",
    "attributes": "Primary Attributes", "offense": "Offense", "defense": "Defense",
    "damage": "Damage", "criticals": "Criticals", "saves": "Saving Throws",
    "resistances": "Resistances", "speed": "Speed and Initiative",
    "carrying": "Carrying and Encumbrance", "survival": "Survival and Condition",
    "effects": "Active Effects", "mechanics": "Status and Mechanics",
    "location": "Location", "companions": "Companions", "currencies": "Currencies",
    "diagnostics": "Snapshot Diagnostics",
}
SCORE_MODES = {"score", "compact", "full", "detailed"}

def _availability_text(value: Any, availability: str = "available") -> str:
    if availability == "unsupported": return "Not implemented"
    if availability == "inactive": return "Inactive"
    if availability == "not_applicable": return "Not applicable"
    if availability == "hidden_by_world": return "Hidden by world"
    if availability == "unavailable": return "Unavailable"
    return str(value) if value not in (None, "") else "Not selected"

def _display_value(value: Any, unit: str = "", fmt: str = "") -> str:
    if isinstance(value, Mapping):
        if value.get("formatted_value") not in (None, ""): return str(value.get("formatted_value"))
        if value.get("display") not in (None, ""): return str(value.get("display"))
        if value.get("final") is not None: value = value.get("final")
        elif value.get("value") is not None: value = value.get("value")
    if value is None: return "—"
    if fmt in {"integer", "number", "thousands"}:
        try: return f"{int(value):,}"
        except Exception: pass
    if fmt in {"percent", "percentage"} or unit in {"%", "percent", "percentage"}:
        try: return f"{float(value):g}%"
        except Exception: return f"{value}%"
    if unit and unit not in {"", "number"} and str(value) != "—":
        return f"{value} {unit}"
    return str(value)

def _stat_from_entry(stat_id: str, entry: Any, fallback_label: str, *, group: str, order: int = 0) -> DisplayStat:
    if isinstance(entry, Mapping):
        active = bool(entry.get("active", True))
        availability = str(entry.get("availability") or ("available" if active else "inactive"))
        return DisplayStat(
            stat_id=str(entry.get("stat_id") or stat_id),
            label=str(entry.get("label") or entry.get("display_label") or fallback_label),
            value=entry.get("value", entry.get("final", entry.get("display"))),
            formatted_value=str(entry.get("formatted_value") or _availability_text(_display_value(entry, str(entry.get("unit") or ""), str(entry.get("display_format") or "")), availability)),
            unit=str(entry.get("unit") or ""),
            display_group=group,
            display_order=int(entry.get("display_order") or order),
            active=active,
            inactive_reason=str(entry.get("inactive_reason") or ""),
            visible=bool(entry.get("visible", True)),
            style_role=str(entry.get("style_role") or ("character_muted" if not active else "character_value")),
            tooltip=str(entry.get("description") or entry.get("tooltip") or ""),
            source_version=str(entry.get("source_version") or ""),
            availability=availability,
        )
    return DisplayStat(stat_id=stat_id, label=fallback_label, value=entry, formatted_value=_display_value(entry), display_group=group, display_order=order)

def _stats_from_mapping(data: Mapping[str, Any], *, group: str) -> tuple[DisplayStat, ...]:
    out=[]
    for i, (key, value) in enumerate(data.items()):
        if key.startswith("_"): continue
        out.append(_stat_from_entry(str(key), value, str(key).replace("_", " ").title(), group=group, order=i * 10))
    return tuple(sorted((s for s in out if s.visible), key=lambda s: (s.display_order, s.label)))

def _resource_stats(res: Mapping[str, Any]) -> tuple[DisplayStat, ...]:
    pairs=(("health","HP","hp","max_hp","resource_health"),("mana","Mana","mana","max_mana","resource_mana"),("stamina","Stamina","stamina","max_stamina","resource_stamina"),("movement","Movement","movement","max_movement","resource_movement"))
    out=[]
    for i,(sid,label,cur,mx,role) in enumerate(pairs):
        if cur in res or mx in res:
            out.append(DisplayStat(sid,label,formatted_value=f"{res.get(cur, '—')} / {res.get(mx, '—')}",display_group="resources",display_order=i*10,style_role=role))
    return tuple(out)

def _damage_stats(snap: CharacterDisplaySnapshot) -> tuple[DisplayStat, ...]:
    rows=[]
    for sid, label, prof in (("weapon","Weapon",snap.weapon_profile or {}),("unarmed","Unarmed",snap.unarmed_profile or {})):
        if not isinstance(prof, Mapping) or not prof: continue
        if prof.get("summary"):
            value=str(prof.get("summary"))
        else:
            name=prof.get("weapon_name") or prof.get("name")
            lo=prof.get("minimum_damage", prof.get("min_damage"))
            hi=prof.get("maximum_damage", prof.get("max_damage"))
            dtype=prof.get("damage_type") or ""
            value=" ".join(x for x in (f"{lo}–{hi}" if lo is not None and hi is not None else "", str(dtype), f"({name})" if name else "") if x)
        if value and value != "0–0":
            rows.append(DisplayStat(sid,label,formatted_value=value,display_group="damage",display_order=10 if sid=="weapon" else 20))
        for extra in ("attack_speed","reach","range"):
            if prof.get(extra) is not None:
                rows.append(DisplayStat(f"{sid}_{extra}", extra.replace("_"," ").title(), formatted_value=str(prof.get(extra)), display_group="damage", display_order=30))
    return tuple(rows)

def build_score_view_model(snapshot: CharacterDisplaySnapshot, *, mode: str = "score") -> ScoreViewModel:
    version = getattr(snapshot, "schema_version", getattr(snapshot, "snapshot_version", ""))
    if version != SCORE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported score snapshot version: {version}")
    ident=snapshot.identity or {}; prog=snapshot.progression or {}
    identity=[
        DisplayStat("name","Name",formatted_value=str(ident.get("display_name") or "Adventurer"),display_group="identity",display_order=10),
    ]
    if ident.get("title"): identity.append(DisplayStat("title","Title",formatted_value=str(ident.get("title")),display_group="identity",display_order=20))
    for sid, label, obj, fallback in (("race","Race",snapshot.race,"unavailable"),("class","Class",snapshot.character_class,"unsupported"),("deity","Deity",(snapshot.mechanics or {}).get("deity", {"availability":"unavailable"}),"unavailable"),("hometown","Hometown",(snapshot.mechanics or {}).get("hometown", {"availability":"unavailable"}),"unavailable")):
        avail=str((obj or {}).get("availability") or ("available" if (obj or {}).get("name") else fallback))
        identity.append(DisplayStat(sid,label,formatted_value=_availability_text((obj or {}).get("name"), avail),display_group="identity",display_order=30 + len(identity),availability=avail,active=avail=="available",style_role="character_muted" if avail!="available" else "character_value"))
    identity.extend([DisplayStat("level","Level",formatted_value=_display_value(snapshot.level),display_group="identity",display_order=70),
                     DisplayStat("alignment","Alignment",formatted_value=str(snapshot.alignment or "Neutral/unspecified"),display_group="identity",display_order=80)])
    if snapshot.age.get("display"): identity.append(DisplayStat("age","Age",formatted_value=str(snapshot.age.get("display")),display_group="identity",display_order=90))
    if snapshot.time.get("play_time"): identity.append(DisplayStat("played_time","Played",formatted_value=str(snapshot.time.get("play_time")),display_group="identity",display_order=100))
    if snapshot.survival.get("posture"): identity.append(DisplayStat("position","Position",formatted_value=str(snapshot.survival.get("posture")).title(),display_group="identity",display_order=110))
    
    # Normal SCORE uses concise progression fields and avoids the old wrapped
    # "XP Required Next Level"/"XP To Next Level" duplication.
    prog_normalized={}
    if "level" in prog: prog_normalized["level"]={"label":"Level","value":prog.get("level"),"display_order":10}
    if "xp" in prog: prog_normalized["xp"]={"label":"Experience","value":prog.get("xp"),"display_order":20,"display_format":"thousands"}
    tnl = prog.get("xp_to_next_level", prog.get("experience_to_next_level"))
    if tnl is not None: prog_normalized["to_next_level"]={"label":"To Next Level","value":tnl,"display_order":30,"display_format":"thousands"}
    if "practice_points" in prog: prog_normalized["practice_points"]={"label":"Practice","value":prog.get("practice_points"),"display_order":40}
    if "training_points" in prog: prog_normalized["training_points"]={"label":"Training","value":prog.get("training_points"),"display_order":50}
    if mode == "detailed":
        for k,v in prog.items(): prog_normalized.setdefault(k, v)
    progression=_stats_from_mapping(prog_normalized, group="progression")
    currencies=_stats_from_mapping(snapshot.currency or {}, group="currencies")
    carrying=list(_stats_from_mapping(snapshot.carrying or {}, group="carrying"))
    if snapshot.encumbrance:
        carrying.extend(_stats_from_mapping(snapshot.encumbrance, group="carrying"))
    return ScoreViewModel(
        schema_version=version, character_id=str(snapshot.character_id or ident.get("character_id") or ""), generated_at=str(snapshot.generated_at or ""),
        identity=tuple(sorted(identity,key=lambda s:s.display_order)), progression=progression, resources=(),
        attributes=_stats_from_mapping(snapshot.attributes or {}, group="attributes"), offense=_stats_from_mapping(snapshot.offense or {}, group="offense"),
        defense=_stats_from_mapping(snapshot.defense or {}, group="defense"), damage=_damage_stats(snapshot),
        criticals=_stats_from_mapping(snapshot.criticals or {}, group="criticals"), saves=_stats_from_mapping(snapshot.saves or {}, group="saves"),
        resistances=_stats_from_mapping(snapshot.resistances or {}, group="resistances"), speed=_stats_from_mapping(snapshot.speed or {}, group="speed"),
        carrying=tuple(carrying), survival=_stats_from_mapping(snapshot.survival or {}, group="survival"),
        conditions=tuple(DisplayStat(f"condition_{i}", "Condition", formatted_value=str(c.get("name") or c.get("label") or c), display_group="conditions", display_order=i) for i,c in enumerate(snapshot.conditions or [])),
        effects=tuple(snapshot.effects or ()), location=_stats_from_mapping(snapshot.location or {}, group="location"),
        currencies=currencies, mechanics=_stats_from_mapping(snapshot.mechanics or {}, group="mechanics"), source_versions=dict(snapshot.source_versions or {}),
    )

def render_display_field(stat: DisplayStat) -> DisplayCell:
    role = stat.style_role or ("character_muted" if not stat.active else "character_value")
    text = stat.formatted_value or _display_value(stat.value, stat.unit)
    if not stat.active and stat.inactive_reason:
        text = f"{text} ({stat.inactive_reason})"
    return DisplayCell(width=25, segments=_field_segments(stat.label, text, value_role=role), metadata={"stat_id": stat.stat_id, "tooltip": stat.tooltip, "availability": stat.availability})

def render_display_section(title: str, stats: tuple[DisplayStat, ...], *, columns: int = 2) -> list[Any]:
    visible=[s for s in stats if s.visible and (s.availability != "hidden_by_world")]
    if not visible: return []
    rows=[DisplayLine(title.upper(), role="character_title")]
    cells=[render_display_field(s) for s in visible]
    for i in range(0, len(cells), columns): rows.append(DisplayRow(cells[i:i+columns]))
    return rows

def render_resource_pair(stats: tuple[DisplayStat, ...]) -> list[Any]: return render_display_section("Resources", stats, columns=2)
def render_damage_profile(stats: tuple[DisplayStat, ...]) -> list[Any]: return render_display_section("Damage", stats, columns=2)
def render_resistance_grid(stats: tuple[DisplayStat, ...]) -> list[Any]: return render_display_section("Resistances", stats, columns=3)
def render_identity_summary(stats: tuple[DisplayStat, ...]) -> list[Any]: return render_display_section("Character Identity", stats, columns=2)
def render_location_summary(stats: tuple[DisplayStat, ...]) -> list[Any]: return render_display_section("Location", stats, columns=2)
def render_effect_list(effects: tuple[dict[str, Any], ...]) -> list[Any]:
    if not effects: return []
    rows=[DisplayLine("ACTIVE EFFECTS", role="character_title")]
    for e in effects:
        kind=str(e.get("classification") or e.get("category") or e.get("type") or "neutral").lower()
        role="character_positive" if kind in {"beneficial","positive","buff"} else "character_negative" if kind in {"harmful","negative","debuff"} else "character_value"
        bits=[str(e.get("display_name") or e.get("name") or "Effect")]
        if e.get("remaining") or e.get("duration"): bits.append(f"Duration: {e.get('remaining') or e.get('duration')}")
        if e.get("stacks") or e.get("stack_count"): bits.append(f"Stacks: {e.get('stacks') or e.get('stack_count')}")
        rows.append(DisplayLine(" — ".join(bits), role=role))
    return rows

def _al_stat_value(data: Mapping[str, Any], key: str, label: str | None = None) -> str | None:
    entry = data.get(key)
    if entry is None:
        return None
    return _display_value(entry, str(entry.get("unit") or "") if isinstance(entry, Mapping) else "", str(entry.get("display_format") or "") if isinstance(entry, Mapping) else "")

def _al_attr(snapshot: CharacterDisplaySnapshot, *keys: str) -> str:
    aliases = {"str": ("str", "strength"), "int": ("int", "intelligence"), "wis": ("wis", "wisdom"), "dex": ("dex", "dexterity"), "con": ("con", "constitution"), "cha": ("cha", "charisma")}
    for key in keys:
        for candidate in aliases.get(key, (key,)):
            if candidate in (snapshot.attributes or {}):
                entry = (snapshot.attributes or {})[candidate]
                if isinstance(entry, Mapping):
                    base = entry.get("base", entry.get("value", entry.get("final")))
                    final = entry.get("final", entry.get("value", base))
                    mod = entry.get("total_modifier", entry.get("modifier"))
                    if mod is None and base is not None and final is not None:
                        try: mod = int(final) - int(base)
                        except Exception: mod = None
                    shown = final if final is not None else base
                    if mod is not None:
                        try: return f"{int(shown)} ({int(mod):+d})"
                        except Exception: return f"{shown} ({mod})"
                    return _display_value(shown)
                return _display_value(entry)
    return "--"

def _al_raw_value(data: Mapping[str, Any], *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in data:
            value = data.get(key)
            if isinstance(value, Mapping):
                return value.get("value", value.get("final", value.get("display", default)))
            return value
    return default

def _al_int_text(value: Any) -> str:
    if isinstance(value, Mapping): value = value.get("value", value.get("final", value.get("display", 0)))
    try: return str(int(value))
    except Exception: return str(value if value not in (None, "") else 0)

def _al_line(text: str) -> DisplayLine:
    return DisplayLine(text, role="character_value")


def _score_row(content: str = "") -> DisplayLine:
    return DisplayLine(" " + _pad_visible(str(content), SCORE_CONTENT_WIDTH) + " ", role="character_value", trusted_markup=True)

def _score_divider() -> DisplayDivider:
    return DisplayDivider()

def _required_score_text(value: Any, field: str) -> str:
    if isinstance(value, Mapping):
        value = value.get("value", value.get("display", value.get("final")))
    if hasattr(value, "value"):
        value = getattr(value, "value")
    if value in (None, ""):
        raise ValueError(f"score_projection_incomplete field={field}")
    text = str(value)
    if text in {"--", "Unknown", "Unavailable", "Not implemented", "None"}:
        raise ValueError(f"score_projection_incomplete field={field}")
    return text

def _score_int(value: Any, field: str) -> int:
    if isinstance(value, Mapping):
        value = value.get("value", value.get("final", value.get("display")))
    if hasattr(value, "value"):
        value = getattr(value, "value")
    if value in (None, ""):
        raise ValueError(f"score_projection_incomplete field={field}")
    return int(value)

def _score_signed(value: Any, field: str) -> str:
    return f"{_score_int(value, field):+d}"

def _score_age_text(age: Mapping[str, Any]) -> str:
    display = age.get("display") if isinstance(age, Mapping) else None
    years = age.get("years") if isinstance(age, Mapping) else None
    if display not in (None, ""):
        if isinstance(display, int) or (isinstance(display, str) and display.isdigit()):
            n = int(display); return f"{n} year{'s' if n != 1 else ''} old"
        return _required_score_text(display, "age")
    n = _score_int(years, "age")
    return f"{n} year{'s' if n != 1 else ''} old"

def _score_play_time(time: Mapping[str, Any]) -> str:
    if isinstance(time, Mapping):
        if time.get("play_time"):
            text = str(time.get("play_time"))
            if re.fullmatch(r"\d+ hours?", text):
                hours = int(text.split()[0]); return f"{hours // 24} day{'s' if hours // 24 != 1 else ''}, {hours % 24} hour{'s' if hours % 24 != 1 else ''}"
            return text
        seconds = time.get("played_seconds", time.get("play_seconds"))
        if seconds is not None:
            total = max(0, int(float(seconds))); days, rem = divmod(total, 86400); hours = rem // 3600
            return f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
    return "0 days, 0 hours"

def _score_encumbrance(carry: Mapping[str, Any], enc: Mapping[str, Any]) -> str:
    raw = enc.get("encumbrance_state", enc.get("encumbrance_text", carry.get("encumbrance_state", carry.get("encumbrance_text"))))
    if isinstance(raw, Mapping): raw = raw.get("value", raw.get("display"))
    mapping = {"none":"None", "light":"Light", "moderate":"Moderate", "heavy":"Heavy", "overloaded":"Overloaded"}
    if raw not in (None, ""):
        key = str(raw).strip().lower()
        if key in mapping: return mapping[key]
    cap = _score_int(_al_raw_value(carry, "carry_capacity", "maximum_weight", default=None), "carrying.capacity")
    cur = _score_int(_al_raw_value(carry, "current_weight", "current_carry_weight", default=None), "carrying.current_weight")
    if cap <= 0: return "None"
    pct = cur * 100 / cap
    return "Light" if pct < 25 else "Moderate" if pct < 50 else "Heavy" if pct < 75 else "Overloaded"

def _score_currency_line(currencies: Mapping[str, Any]) -> str:
    return f"Gold: {_score_int(currencies.get('gold'), 'currency.gold'):>8} Diamonds: {_score_int(currencies.get('diamonds'), 'currency.diamonds'):>6} Glory: {_score_int(currencies.get('glory'), 'currency.glory'):>6} Bank: {_score_int(currencies.get('bank'), 'currency.bank'):>8}"

def _score_status(snap: CharacterDisplaySnapshot) -> str:
    surv = snap.survival or {}; ident = snap.identity or {}
    posture = str(surv.get("posture") or ident.get("position") or "standing").lower().replace("_", " ")
    target = surv.get("combat_target_name") or ident.get("combat_target_name") or ""
    sitting_on = surv.get("sitting_on") or surv.get("sitting_on_short_description")
    mapping = {"dead":"You are DEAD!", "mortally wounded":"Mortally wounded!", "incapacitated":"Incapacitated", "stunned":"Stunned", "sleeping":"Sleeping", "resting":"Resting", "sitting":"Sitting", "standing":"Standing"}
    if posture == "fighting": return f"Fighting {target}".rstrip()
    if posture == "sitting" and sitting_on: return f"Sitting on {sitting_on}"
    return mapping.get(posture, "Floating")

def build_score_document(character: Any = None, *, snapshot: CharacterDisplaySnapshot | None = None, theme: Any = None, mode: str = "score", detailed_allowed: bool = False) -> DisplayDocument:
    """Render normal SCORE in Adventurer's Lair order, minus prompt resources/alignment."""
    snap=snapshot or build_character_display_snapshot(character)
    mode=(mode or "score").lower()
    if mode not in SCORE_MODES: raise ValueError(f"Unsupported score display mode: {mode}")
    if mode == "detailed" and not detailed_allowed: raise PermissionError("Detailed SCORE is available to Builder/admin characters only.")
    version = getattr(snap, "schema_version", getattr(snap, "snapshot_version", ""))
    if version != SCORE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported score snapshot version: {version}")
    ident=snap.identity or {}; prog=snap.progression or {}; carry=snap.carrying or {}; enc=snap.encumbrance or {}; surv=snap.survival or {}
    name=_required_score_text(ident.get("display_name") or ident.get("name"), "identity.name")
    title=str(ident.get("title") if ident.get("title") is not None else snap.title or "")
    race=_required_score_text((snap.race or {}).get("name") or ident.get("race_name"), "identity.race")
    cls=_required_score_text((snap.character_class or {}).get("name") or ident.get("class_name"), "identity.class")
    age=_score_age_text(snap.age or {})
    level=_score_int(snap.level, "progression.level")
    xp=_score_int(prog.get("xp", prog.get("experience")), "progression.xp")
    tnl=_score_int(prog.get("xp_to_next_level", prog.get("experience_to_next_level")), "progression.tnl")
    curw=_score_int(_al_raw_value(carry, "current_weight", "current_carry_weight", default=None), "carrying.current_weight")
    maxw=_score_int(_al_raw_value(carry, "carry_capacity", "maximum_weight", default=None), "carrying.capacity")
    enc_text=_score_encumbrance(carry, enc)
    offense=snap.offense or {}; defense=snap.defense or {}; saves=snap.saves or {}; crit=snap.criticals or {}; combat=snap.combat or {}
    armor=_score_int(_al_raw_value(defense, "armor", default=_al_raw_value(combat, "armor", default=None)), "combat.armor")
    evasion=_score_int(_al_raw_value(defense, "evasion", default=_al_raw_value(combat, "evasion", default=None)), "combat.evasion")
    spell_save=_score_int(_al_raw_value(saves, "spell", "magic", "magic_save", "spell_saves", default=_al_raw_value(combat, "spell_saves", default=None)), "combat.spell_saves")
    hit=_score_int(_al_raw_value(offense, "hit_bonus", default=None), "combat.hitroll")
    dam=_score_int(_al_raw_value(offense, "damage_bonus", default=None), "combat.damroll")
    acc=_score_int(_al_raw_value(offense, "accuracy", default=_al_raw_value(combat, "accuracy", default=None)), "combat.accuracy")
    crit_melee=_score_int(_al_raw_value(crit, "critical_melee", "critical_hit", default=None), "combat.critical_melee")
    crit_spell=_score_int(_al_raw_value(crit, "critical_spell", default=None), "combat.critical_spell")
    crit_heal=_score_int(_al_raw_value(crit, "critical_heal", default=None), "combat.critical_heal")
    quest_summary=snap.quest_summary or ident.get("quest_summary") or {}
    completed=_score_int(quest_summary.get("completed_count", quest_summary.get("quests_completed", prog.get("quests_completed", 0))) if isinstance(quest_summary, Mapping) else 0, "quests.completed")
    qpoints=_score_int(prog.get("quest_points", quest_summary.get("quest_points", 0) if isinstance(quest_summary, Mapping) else 0), "quests.points")
    active = quest_summary.get("active") if isinstance(quest_summary, Mapping) else None
    active_name = active.get("name") if isinstance(active, Mapping) else (active[0].get("name") if isinstance(active, list) and active and isinstance(active[0], Mapping) else None)
    quest_line = f"Current quest: {active_name}" if active_name else "Not currently on a quest."
    quest_vnum = quest_summary.get("active_vnum") or (active.get("vnum") if isinstance(active, Mapping) else None) if isinstance(quest_summary, Mapping) else None
    played=_score_play_time(snap.time or {})
    immortal = bool(ident.get("immortal") or ident.get("is_immortal") or ident.get("level_role") == "immortal" or level >= int(ident.get("immortal_level", 1000) or 1000))
    status=_score_status(snap)
    hunger=_required_score_text(surv.get("hunger"), "survival.hunger"); thirst=_required_score_text(surv.get("thirst"), "survival.thirst")
    rows=[
        _score_row("CHARACTER STATUS"), _score_divider(),
        _score_row(f"Name: {name:<22} Title: {title}"),
        _score_row(f"Race: {race:<22} Class: {cls}"),
        _score_row(f"Level: {level:<21} Age: {age}"),
    ]
    if (snap.age or {}).get("is_birthday") or (snap.age or {}).get("birthday_today"):
        rows.append(_score_row("*** It's your birthday today! ***"))
    rows += [_score_divider(), _score_row(), _score_row(f"Exp: {xp:<31} TNL: {tnl}"), _score_row(), _score_row(f"Carry Capacity: {curw} / {maxw} ({enc_text})"), _score_divider()]
    rows += [_score_row(f"Base Stats: Str {_al_attr(snap,'str')} Dex {_al_attr(snap,'dex')} Con {_al_attr(snap,'con')}"), _score_row(f"            Int {_al_attr(snap,'int')} Wis {_al_attr(snap,'wis')} Cha {_al_attr(snap,'cha')}"), _score_row(), _score_row(f"Armor: {armor:<8} Evasion: {evasion:<5} Spell Saves: {spell_save}"), _score_row(), _score_row(f"Offense: Hitroll {hit:+d} Damroll {dam:+d} Accuracy: {acc}%")]
    unarmed=snap.unarmed_profile or {}; weapon=snap.weapon_profile or {}; weapon_active=bool(weapon and weapon.get("active") and (weapon.get("weapon_name") or weapon.get("name")) and str(weapon.get("name") or "").lower() != "unarmed")
    if not weapon_active and unarmed:
        dice_count=unarmed.get("dice_count"); die_size=unarmed.get("die_size"); bonus=unarmed.get("flat_bonus", unarmed.get("bonus", 0)); avg=unarmed.get("average_damage")
        if dice_count is not None and die_size is not None:
            if avg in (None, ""):
                avg=(int(dice_count)*(int(die_size)+1))/2 + int(bonus or 0)
            avg_text=str(int(avg)) if float(avg) == int(float(avg)) else f"{float(avg):.1f}"
            rows.append(_score_row(f"Unarmed Dice: {int(dice_count)}d{int(die_size)} + {int(bonus or 0)} (Avg {avg_text} per hit, before bonuses)"))
    rows += [_score_row(), _score_row(f"Critical hit: {crit_melee} Critical Spell: {crit_spell} Critical Heal: {crit_heal}"), _score_divider(), _score_row("Currencies"), _score_row(_score_currency_line(snap.currency or {})), _score_divider()]
    left=f"Quests completed: {completed}"; right=f"Quest Points: {qpoints}"; gap=max(2, SCORE_CONTENT_WIDTH-len(left)-len(right)); rows.append(_score_row(left + " "*gap + right))
    rows.append(_score_row(quest_line))
    show_vnums=bool((snap.identity or {}).get("show_vnums") or (snap.mechanics or {}).get("show_vnums"))
    if active_name and show_vnums and quest_vnum: rows.append(_score_row(f"[Quest VNUM: {quest_vnum}]"))
    rows += [_score_divider(), _score_row(f"Play time: {played}")]
    rows.append(_score_row(f"Status: {status}" if immortal else f"Status: {status} Hunger: {hunger} Thirst: {thirst}"))
    cond_names=[]
    for cond in snap.conditions or []:
        text=str(cond.get("label") or cond.get("name") or cond) if isinstance(cond, Mapping) else str(cond)
        cond_names.append(text.lower())
    if surv.get("intoxicated") or any("intox" in x for x in cond_names): rows.append(_score_row("You are intoxicated."))
    if surv.get("hungry") or any("hungry" in x for x in cond_names): rows.append(_score_row("You are hungry."))
    if surv.get("thirsty") or any("thirsty" in x for x in cond_names): rows.append(_score_row("You are thirsty."))
    if bool((snap.mechanics or {}).get("summonable") or ident.get("summonable")): rows.append(_score_row("You are summonable by other players."))
    if mode == "detailed" or immortal:
        rows.append(_score_divider())
        rows.append(_score_row("IMMORTAL INFORMATION"))
        rows.append(_score_row(f"POOFIN: {(ident.get('poofin') or f'{name} appears with an ear-splitting bang.')}"))
        rows.append(_score_row(f"POOFOUT: {(ident.get('poofout') or f'{name} disappears in a puff of smoke.')}"))
        zone=ident.get("builder_zone") or ident.get("current_zone_name") or ident.get("current_zone_id")
        if zone: rows.append(_score_row(f"Your current zone: {zone}"))
    frame=DisplayFrame(title="CHARACTER STATUS", width=SCORE_VISIBLE_WIDTH, frame_style="classic_double", title_alignment="left")
    doc=DisplayDocument(DisplayIntent.SCORE, semantic_role="character_value", title_role="character_title", frames=[frame])
    doc.lines=[_frame_segments(frame, kind="top"), *[_frame_segments(frame, kind=r.kind) if isinstance(r, DisplayDivider) else _frame_segments(frame, segments=[DisplaySegment(_line_text(r), r.role, True)]) for r in rows], _frame_segments(frame, kind="bottom")]
    doc.debug_metadata.update({"snapshot_version": version, "mode": mode, "reference": "Adventurer's Lair ACMD(do_score) parity without HP/Mana/Move/Alignment"})
    return doc

def build_worth_document(character: Any = None, *, snapshot: CharacterDisplaySnapshot | None = None, worth_snapshot: Any = None, theme: Any = None) -> DisplayDocument:
    currency=(worth_snapshot.currencies if worth_snapshot is not None else (snapshot or build_character_display_snapshot(character)).currency)
    cells=[DisplayCell(width=18, segments=_field_segments(k.title(), v, value_role="gold" if k=="gold" else "character_value")) for k,v in currency.items() if v is not None]
    if not cells: cells=[DisplayCell("You are broke.", role="character_muted", width=30)]
    return build_character_frame_document(DisplayIntent.WORTH,"CURRENCIES",[DisplayRow(cells)],width=48, theme=theme)

def _ability_cost(row: dict[str, Any]) -> str:
    costs=row.get('costs') or []
    return ", ".join(f"{c.get('amount', c.get('percentage',0))} {str(c.get('resource_id','')).title()}" for c in costs) or "No cost"

def build_abilities_document(rows: list[dict[str, Any]], *, title: str="ABILITIES", empty: str="You have no abilities.", theme: Any = None) -> DisplayDocument:
    out=[]
    compact = title in {"SKILLS", "SPELLS", "ABILITIES"}
    family = title.lower()
    if compact:
        out.append(DisplayRow([
            DisplayCell(theme_label(theme, f"{family}.name_header", title), width=48, role=resolve_theme_role(theme, f"{family}.name_header_role"), min_width=min(len(title), 8), shrink_priority=10, wrap=False),
            DisplayCell(theme_label(theme, f"{family}.proficiency_header", "PROFICIENCY"), width=17, align='right', role=resolve_theme_role(theme, f"{family}.proficiency_header_role"), min_width=len("PROFICIENCY"), shrink_priority=1, wrap=False),
        ], role="character_label"))
    for r in rows:
        name=str(r.get('name') or r.get('id') or 'Ability').replace('_',' ').title()
        proficiency=max(1, min(100, int(r.get('proficiency') or r.get('rank') or 1)))
        rank = f"{proficiency}%"
        out.append(DisplayRow([DisplayCell(name,width=48, role="character_value"),DisplayCell(rank,width=17,align='right', role="character_value", wrap=False)], role="character_value"))
        if not compact:
            status=str(r.get('status_text') or r.get('availability_text') or ('Passive' if r.get('passive') else 'Availability unknown.'))
            out.append(DisplayLine(f"Status: {status}", role="character_positive" if status=='Ready' else "warning"))
            out.append(DisplayLine(str(r.get('description') or ''), role="character_value"))
    if len(out) == (1 if compact else 0): out=build_empty_display_rows(title.lower(), theme, empty) or [DisplayLine(empty, role=resolve_theme_role(theme, "character_muted"))]
    return build_character_frame_document(DisplayIntent.SKILLS if title=='SKILLS' else DisplayIntent.SPELLS if title=='SPELLS' else DisplayIntent.SYSTEM,title,out,width=70, theme=theme, show_title=not compact)

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
        if str(doc.intent) == "DisplayIntent.SCORE" or str(doc.intent) == "SCORE":
            blocks.append("\n".join(_line_text(x).rstrip() for x in doc.lines))
        else:
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

def render_display_mud(doc: DisplayDocument, *, color_enabled: bool = True) -> str:
    if not color_enabled:
        return render_display_plain(doc)

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

def render_display_ansi(doc: DisplayDocument, *, color_enabled: bool = True) -> str:
    mud = render_display_mud(doc, color_enabled=color_enabled)
    if not color_enabled:
        return render_display_plain(doc)
    ansi_roles = {"ability_list_header": "33"}
    def repl(match: re.Match[str]) -> str:
        closing, role = match.group(1), match.group(2)
        if role not in SEMANTIC_COLOR_ROLES:
            return ""
        code = ansi_roles.get(role)
        if not code:
            return ""
        return "\033[0m" if closing else f"\033[{code}m"
    return strip_mud_color_markup(TAG_RE.sub(repl, mud)) + "\033[0m"

def render_display_html(doc: DisplayDocument, *, color_enabled: bool = True) -> str:
    vm = (getattr(doc, "renderer_hints", {}) or {}).get("score_view_model")
    if vm is not None:
        section_names = ["identity","progression","resources","attributes","offense","defense","damage","criticals","saves","resistances","speed","carrying","survival","location"]
        parts = ['<section class="mud-score" role="region" aria-label="Character score">', f'<header><h2>{html.escape(str(doc.title or "Character Score"))}</h2></header>']
        for name in section_names:
            stats = tuple(getattr(vm, name, ()) or ())
            if name == "survival":
                stats = stats + tuple(getattr(vm, "conditions", ()) or ())
            if not stats: continue
            parts.append(f'<section class="score-section score-section-{html.escape(name)}"><h3>{html.escape(SCORE_SECTION_TITLES.get(name, name.title()))}</h3><dl>')
            for stat in stats:
                if not stat.visible or stat.availability == "hidden_by_world": continue
                value = stat.formatted_value or _display_value(stat.value, stat.unit)
                cls = re.sub(r"[^a-z0-9_-]+", "-", f"score-field {stat.style_role} {stat.availability}".lower())
                title = f' title="{html.escape(stat.tooltip)}"' if stat.tooltip else ""
                parts.append(f'<div class="{cls}" data-stat-id="{html.escape(stat.stat_id)}"{title}><dt>{html.escape(stat.label)}</dt><dd>{html.escape(value)}</dd></div>')
            parts.append("</dl></section>")
        effects = tuple(getattr(vm, "effects", ()) or ())
        if effects:
            parts.append('<section class="score-section score-section-effects"><h3>Active Effects</h3><ul>')
            for e in effects:
                name = str(e.get("display_name") or e.get("name") or "Effect")
                bits=[name]
                if e.get("remaining") or e.get("duration"): bits.append(f"Duration: {e.get('remaining') or e.get('duration')}")
                if e.get("stacks") or e.get("stack_count"): bits.append(f"Stacks: {e.get('stacks') or e.get('stack_count')}")
                parts.append(f'<li>{html.escape(" — ".join(bits))}</li>')
            parts.append("</ul></section>")
        parts.append("</section>")
        return "".join(parts)
    if not color_enabled:
        return html.escape(render_display_plain(doc))
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

def build_affects_document(effects: list[dict[str, Any]], *, theme: Any = None) -> DisplayDocument:
    rows=[]
    visible=[e for e in effects if not e.get("hidden") and not e.get("secret") and not e.get("admin_only")]
    for i,e in enumerate(visible):
        if i: rows.append(DisplayDivider(kind="item"))
        kind=str(e.get("classification") or e.get("type") or e.get("kind") or "neutral").lower()
        role="character_positive" if kind in {"beneficial","positive","buff"} else "character_negative" if kind in {"harmful","negative","debuff"} else "character_value"
        name=str(e.get("display_name") or e.get("name") or "Effect").replace("_"," ").title()
        rows.append(DisplayRow([DisplayCell(name, width=42, role=role), DisplayCell(kind.title(), width=18, align="right", role=role)]))
        meta=[]
        if e.get("remaining") or e.get("duration"): meta.append(f"Duration: {e.get('remaining') or e.get('duration')}")
        if e.get("stacks") or e.get("stack_count"): meta.append(f"Stacks: {e.get('stacks') or e.get('stack_count')}")
        if e.get("source") or e.get("natural_source"): meta.append(f"Source: {e.get('natural_source') or e.get('source')}")
        if meta: rows.append(DisplayLine("   ".join(meta), role="character_muted"))
        mods=e.get("visible_modifiers") or e.get("modifiers") or []
        if mods: rows.append(DisplayLine("Modifiers: " + ", ".join(str(m) for m in mods), role="character_value"))
        if e.get("description"): rows.append(DisplayLine(str(e.get("description")), role="character_value"))
    if not rows:
        rows = build_empty_display_rows("affects", theme, "You have no active affects.")
    return build_character_frame_document(DisplayIntent.AFFECTS, (getattr(theme, "labels", {}) or {}).get("affects.title", "AFFECTS"), rows, width=60, theme=theme)

def build_inventory_document(items: list[dict[str, Any]], *, carrying: str = "", theme: Any = None) -> DisplayDocument:
    label=theme_label(theme, "inventory.empty", "You are not carrying anything.")
    rows=[]
    if items:
        rows.append(DisplayLine((getattr(theme, "labels", {}) or {}).get("inventory.heading", "You are carrying:"), role="character_label"))
        for entry in group_display_entries(items):
            rows.append(DisplayLine(_render_entry_plain(entry), role=entry.role, trusted_markup=True))
    else:
        rows.extend(build_empty_display_rows("inventory", theme, label) or [DisplayLine(label, role=resolve_theme_role(theme, "character_muted"), trusted_markup=True)])
    if carrying:
        rows.append(DisplayDivider()); rows.append(DisplayLine(carrying, role="character_value"))
    return build_character_frame_document(DisplayIntent.INVENTORY, (getattr(theme, "labels", {}) or {}).get("inventory.title", "INVENTORY"), rows, width=60, theme=theme)

def build_equipment_document(items: list[dict[str, Any]], slots: list[str], *, theme: Any = None) -> DisplayDocument:
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
    rows=[DisplayRow([DisplayCell(f.label, width=22, role="equipment_slot"), DisplayCell(str(f.value), width=34, role=f.value_role, trusted_markup=f.trusted_markup)]) for f in fields]
    if not items:
        rows = (build_empty_display_rows("equipment", theme, theme_label(theme, "equipment.empty", "You are not wearing anything.")) or [DisplayLine(theme_label(theme, "equipment.empty", "You are not wearing anything."), role=resolve_theme_role(theme, "equipment_empty"))]) + rows
    return build_character_frame_document(DisplayIntent.EQUIPMENT, (getattr(theme, "labels", {}) or {}).get("equipment.title", "EQUIPMENT"), rows, width=60, theme=theme)

PROMPT_PRESETS = {
    "compact": "[%h/%H HP %m/%M MP %s/%S ST]",
    "classic": "[%h/%H HP %m/%M MP %s/%S ST %X TNL %g Gold]",
    "combat": "[%h/%H HP %m/%M MP | %t: %c]",
    "explorer": "[%h/%H HP %s/%S ST | %r | %T]",
    "minimal": ">",
}
PROMPT_MAX_LENGTH = 160

def _prompt_template(character: Any) -> str:
    prefs = getattr(character, "preferences", {}) or {}
    custom = getattr(character, "prompt_template", None) or prefs.get("prompt_template")
    preset = str(getattr(character, "prompt_preset", None) or prefs.get("prompt_preset") or "compact").lower()
    return str(custom or PROMPT_PRESETS.get(preset, PROMPT_PRESETS["compact"]))[:PROMPT_MAX_LENGTH]

def resolve_prompt_template(character: Any, theme: Any = None, preferences: dict[str, Any] | None = None, *, world_default: str | None = None) -> str:
    prefs = preferences if preferences is not None else (getattr(character, "preferences", {}) or {})
    custom = getattr(character, "prompt_template", None) or prefs.get("prompt_template")
    if custom: return str(custom)[:PROMPT_MAX_LENGTH]
    preset = getattr(character, "prompt_preset", None) or prefs.get("prompt_preset")
    if preset: return str(PROMPT_PRESETS.get(str(preset).lower(), PROMPT_PRESETS["compact"]))[:PROMPT_MAX_LENGTH]
    presets=getattr(theme, "prompt_presets", {}) or {}
    if presets: return str(presets.get("default") or presets.get("classic") or next(iter(presets.values()), ""))[:PROMPT_MAX_LENGTH]
    if world_default: return str(world_default)[:PROMPT_MAX_LENGTH]
    return PROMPT_PRESETS["compact"]

def build_prompt_document(character: Any, theme: Any = None, template: str | None = None) -> DisplayDocument:
    prefs = getattr(character, "preferences", {}) or {}
    if template is None and not getattr(character, "prompt_template", None) and not getattr(character, "prompt_preset", None) and not prefs.get("prompt_template") and not prefs.get("prompt_preset"):
        if theme is not None and getattr(theme, "prompt_presets", None):
            presets=getattr(theme, "prompt_presets", {}) or {}; default=(presets.get("default") or presets.get("classic") or next(iter(presets.values()), ""))
            if default:
                return build_prompt_document(character, None, template=default)
        segments = [DisplaySegment("[", "prompt_marker"), DisplaySegment(f"{character.hp}/{character.max_hp} HP", "prompt_hp")]
        if getattr(character, "max_mana", 0): segments += [DisplaySegment(" ", "prompt"), DisplaySegment(f"{character.mana}/{character.max_mana} MP", "prompt_mana")]
        if getattr(character, "max_stamina", 0): segments += [DisplaySegment(" ", "prompt"), DisplaySegment(f"{character.stamina}/{character.max_stamina} ST", "prompt_stamina")]
        segments.append(DisplaySegment("]", "prompt_marker"))
        return DisplayDocument(DisplayIntent.PROMPT, semantic_role="prompt", lines=[DisplayLine(segments=segments)])
    xp=int(getattr(character,"xp",0) or 0); lvl=int(getattr(character,"level",1) or 1)
    tokens={
        "%h": (str(getattr(character,"hp",0)), "prompt_hp"), "%H": (str(getattr(character,"max_hp",0)), "prompt_hp"),
        "%m": (str(getattr(character,"mana",0)), "prompt_mana"), "%M": (str(getattr(character,"max_mana",0)), "prompt_mana"),
        "%s": (str(getattr(character,"stamina",0)), "prompt_stamina"), "%S": (str(getattr(character,"max_stamina",0)), "prompt_stamina"),
        "%x": (str(xp), "prompt_xp"), "%X": (str(_canonical_tnl(character) if _canonical_tnl(character) is not None else "—"), "prompt_xp"), "%g": (str(int(getattr(character,"gold",0) or 0)), "prompt_gold"),
        "%l": (str(lvl), "prompt"), "%a": (str(getattr(character,"alignment","neutral")), "prompt_alignment"), "%p": (str(getattr(character,"posture","standing")), "prompt_position"),
        "%t": (str(getattr(character,"combat_target","none") or "none"), "prompt_target"), "%c": (str(getattr(character,"target_condition","unknown") or "unknown"), "prompt_target"),
        "%r": (str(getattr(character,"room_name", getattr(character,"room_id", "unknown")) or "unknown"), "prompt_area"), "%z": (str(getattr(character,"area_name", getattr(character,"zone_name", "")) or ""), "prompt_area"),
        "%q": (str(getattr(character,"quest_timer", "--") or "--"), "prompt_time"), "%T": (str(getattr(character,"world_time", "--") or "--"), "prompt_time"),
        "%n": (str(getattr(character,"name", "Adventurer") or "Adventurer"), "prompt"), "%A": (str(getattr(character,"age", "--") or "--"), "prompt_time"),
        "%P": (str(getattr(character,"played_time", getattr(character,"play_time", "--")) or "--"), "prompt_time"), "%e": (str(getattr(character,"encumbrance_text", getattr(character,"encumbrance", "normal")) or "normal"), "prompt"),
        "%w": (str(getattr(character,"current_weapon", getattr(character,"weapon_damage_summary", "unarmed")) or "unarmed"), "prompt"), "%b": (str(getattr(character,"combat_state", "peaceful") or "peaceful"), "prompt"),
    }
    template=template if template is not None else resolve_prompt_template(character, theme, prefs)
    segments=[]; i=0
    while i < len(template):
        if template[i] == "%" and i+1 < len(template):
            token=template[i:i+2]
            if token == "%%": segments.append(DisplaySegment("%", "prompt")); i+=2; continue
            if token in tokens:
                text, role=tokens[token]; segments.append(DisplaySegment(text, role)); i+=2; continue
            segments.append(DisplaySegment(token, "warning")); i+=2; continue
        j=template.find("%", i)
        if j < 0: j=len(template)
        txt=template[i:j]
        role="prompt_marker" if set(txt) <= set("[]<>|: /-") else "prompt"
        segments.append(DisplaySegment(txt, role)); i=j
    return DisplayDocument(DisplayIntent.PROMPT, semantic_role="prompt", lines=[DisplayLine(segments=segments)])

import html
import re

from engine.mud_rendering import SEMANTIC_COLOR_ROLES, TAG_RE, render_mud_color_html, render_mud_color_ansi, strip_mud_color_markup
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
    return render_display_html(build_room_document(room, character), color_enabled=not bool(getattr(character, "preferences", {}).get("no_color")))


def render_object(obj: Any) -> str:
    """Render an object for look/examine target output."""
    name, desc = _entity_text(obj, compact=False)
    if isinstance(obj, dict):
        name = str(obj.get("name") or obj.get("title") or name).strip()
    desc = desc or name
    return f'<span role="object">{render_mud_color_html(name)}</span>\n\n<span role="room_description">{render_mud_color_html(desc)}</span>'

def render_prompt(character: Any, colors: dict[str, str]) -> str:
    """Render the canonical configurable-style prompt as safe browser HTML."""
    return render_display_html(build_prompt_document(character), color_enabled=not bool(getattr(character, "preferences", {}).get("no_color")))


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
