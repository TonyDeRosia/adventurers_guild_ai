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
    identity: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    progression: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    combat: dict[str, Any] = field(default_factory=dict)
    carrying: dict[str, Any] = field(default_factory=dict)
    currency: dict[str, Any] = field(default_factory=dict)
    survival: dict[str, Any] = field(default_factory=dict)
    time: dict[str, Any] = field(default_factory=dict)
    effects: list[dict[str, Any]] = field(default_factory=list)
    abilities: list[dict[str, Any]] = field(default_factory=list)
    cooldowns: list[dict[str, Any]] = field(default_factory=list)
    equipment: list[dict[str, Any]] = field(default_factory=list)
    inventory: list[dict[str, Any]] = field(default_factory=list)
    quest_summary: dict[str, Any] = field(default_factory=dict)

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
    stats = _as_mapping(getattr(character, "calculated_stats", None)) or _as_mapping(getattr(character, "stats", None))
    attrs = _as_mapping(getattr(character, "attributes", None)) or _as_mapping(getattr(character, "ability_scores", None))
    attr_snapshot: dict[str, Any] = {}
    for key in ("strength","dexterity","constitution","intelligence","wisdom","charisma"):
        raw = attrs.get(key) if isinstance(attrs, dict) else None
        if isinstance(raw, dict):
            attr_snapshot[key] = {k: raw.get(k) for k in ("base","modifier","final") if raw.get(k) is not None}
        elif raw is not None:
            attr_snapshot[key] = {"final": raw}
        elif hasattr(character, key):
            attr_snapshot[key] = {"final": getattr(character, key)}
    currency = _as_mapping(getattr(character, "currency", None)).copy()
    for cur in ("gold", "silver", "copper"):
        if hasattr(character, cur) and getattr(character, cur) is not None:
            currency.setdefault(cur, getattr(character, cur))
    return CharacterDisplaySnapshot(
        identity={k:v for k,v in {"character_id":getattr(character,"id",None),"display_name":_char(character,"name",default=None),"title":getattr(character,"title",None),"race_name":_char(character,"race_name","race",default=None),"class_name":_char(character,"class_name","character_class","char_class",default=None),"level":getattr(character,"level",None),"age":getattr(character,"age",None),"alignment":getattr(character,"alignment",None),"birthday":getattr(character,"birthday",None)}.items() if v not in (None,"")},
        resources={k:getattr(character,k) for k in ("hp","max_hp","mana","max_mana","stamina","max_stamina","hp_regen","mana_regen","stamina_regen") if hasattr(character,k)},
        progression={k:v for k,v in {"xp":getattr(character,"xp",None),"xp_to_next_level":_canonical_tnl(character),"practice_points":getattr(character,"practice_points",None),"training_points":getattr(character,"training_points",None),"quest_points":getattr(character,"quest_points",None),"level_progress_percent":getattr(character,"level_progress_percent",None)}.items() if v is not None},
        attributes=attr_snapshot,
        combat={k:(stats.get(k) if k in stats else getattr(character,k)) for k in ("armor","evasion","accuracy","hit_bonus","damage_bonus","spell_saves","resistances","critical_melee","critical_spell","critical_heal","weapon_damage_summary","unarmed_damage_summary") if (k in stats or hasattr(character,k))},
        carrying={k:getattr(character,k) for k in ("current_weight","carry_weight","carry_capacity","encumbrance_key","encumbrance_text","encumbrance","item_count","max_item_count") if hasattr(character,k)},
        currency=currency,
        survival={k:getattr(character,k) for k in ("posture","hunger","thirst","fatigue","active_combat","status_conditions") if hasattr(character,k)},
        time={k:getattr(character,k) for k in ("played_time","play_time","age","last_login","birthday") if hasattr(character,k)},
        effects=list(getattr(character,"effects",[]) or getattr(character,"affects",[]) or []),
        inventory=list(getattr(character,"inventory",[]) or []),
    )

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

def _slice_visible(text: str, width: int) -> str:
    out=[]; visible=0; i=0; text=str(text or "")
    while i < len(text) and visible < width:
        if text[i] == "{" and (m:=re.match(r"\{/?[a-z_]+\}", text[i:])):
            out.append(m.group(0)); i += len(m.group(0)); continue
        if text[i] == "&" and i+1 < len(text) and re.match(r"[A-Za-z0-9]", text[i+1]):
            out.append(text[i:i+2]); i += 2; continue
        out.append(text[i]); visible += 1; i += 1
    return "".join(out)

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
    words=text.split(" ")
    lines=[]; cur=""
    for word in words:
        candidate = word if not cur else cur + " " + word
        if _visible_width(candidate) <= width:
            cur = candidate; continue
        if cur: lines.append(_pad_visible(cur, width)); cur=""
        while _visible_width(word) > width:
            lines.append(_pad_visible(_slice_visible(word, width), width)); word = word[len(strip_mud_color_markup(_slice_visible(word, width))):]
        cur = word
    if cur or not lines: lines.append(_pad_visible(cur, width))
    return lines

def _frame_chars(frame: DisplayFrame, kind: str) -> tuple[str,str,str]:
    chars=getattr(frame, "border_characters", None) or {}
    defaults={"top":("╔","═","╗"),"bottom":("╚","═","╝"),"section":("╠","═","╣"),"item":("╟","─","╢")}
    return defaults.get(kind, ("║"," ","║"))

def _frame_line_plain(frame: DisplayFrame, content: str = "", *, kind: str = "row") -> str:
    width=max(32,int(frame.width or 79)); inner=width-2
    if kind != "row":
        l,ch,r=_frame_chars(frame, kind); return l + ch*inner + r
    l,_,r=_frame_chars(frame, "row"); return l + _pad_visible(content, inner) + r

def _cell_segments(cell: DisplayCell) -> list[DisplaySegment]:
    return list(cell.segments) if cell.segments else [DisplaySegment(str(cell.text), cell.role, cell.trusted_markup)]

def _frame_segments(frame: DisplayFrame, content: str = "", *, kind: str = "row", role: str = "character_value", segments: list[DisplaySegment] | None = None) -> DisplayLine:
    if kind != "row": return DisplayLine(_frame_line_plain(frame, kind=kind), role=frame.frame_role)
    inner=max(30,int(frame.width or 79)-2)
    if segments is None: segments=[DisplaySegment(_pad_visible(content, inner), role)]
    return DisplayLine(segments=[DisplaySegment("║", frame.frame_role), *segments, DisplaySegment("║", frame.frame_role)])

def _field_segments(label: str, value: Any, *, value_role: str = "character_value") -> list[DisplaySegment]:
    return [DisplaySegment(f"{label}: ", "character_label"), DisplaySegment(str(value), value_role)]

def _field_text(label: str, value: Any) -> str:
    return f"{label}: {value}"

def build_character_frame_document(intent: DisplayIntent | str, title: str, rows: list[Any], *, width: int = 79) -> DisplayDocument:
    frame=DisplayFrame(title=title, width=width)
    doc=DisplayDocument(intent, semantic_role="character_value", title_role="character_title", frames=[frame])
    lines=[_frame_segments(frame, kind="top"), _frame_segments(frame, segments=[DisplaySegment(_pad_visible(title, width-2, "center"), "character_title")]), _frame_segments(frame, kind="section")]
    for row in rows:
        if isinstance(row, DisplayDivider): lines.append(_frame_segments(frame, kind=row.kind)); continue
        if isinstance(row, DisplayLine):
            for wrapped in _wrap_visible(_line_text(row), width-2): lines.append(_frame_segments(frame, segments=[DisplaySegment(wrapped, _line_role(row,"character_value"), _line_trusted(row))]));
            continue
        if isinstance(row, DisplayRow):
            raw=[]
            for idx,cell in enumerate(row.cells):
                if idx: raw.append(DisplaySegment("   ", row.role))
                cwidth = cell.width or max(cell.min_width, (width-2)//max(1,len(row.cells))-3)
                segs=_cell_segments(cell)
                # keep individual segment roles, place padding on last segment role
                used=0
                for seg in segs:
                    raw.append(seg); used += _visible_width(seg.text)
                if cwidth > used: raw.append(DisplaySegment(" "*(cwidth-used), segs[-1].role if segs else cell.role))
            visible=sum(_visible_width(seg.text) for seg in raw)
            if visible < width-2: raw.append(DisplaySegment(" "*((width-2)-visible), row.role))
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

def _row_fields(*pairs: tuple[str, Any, str]) -> DisplayRow:
    cells=[]
    for label,value,*role in pairs:
        cells.append(DisplayCell(width=34, segments=_field_segments(label, value, value_role=role[0] if role else "character_value")))
    return DisplayRow(cells)

def _fmt_attr(data: Any) -> str:
    if isinstance(data, dict):
        base=data.get("base"); mod=data.get("modifier"); final=data.get("final")
        if base is not None and mod not in (None,0) and final is not None: return f"{base} ({mod:+}) = {final}"
        if final is not None: return str(final)
        if base is not None: return str(base)
    return str(data)

def build_score_document(character: Any, *, snapshot: CharacterDisplaySnapshot | None = None) -> DisplayDocument:
    snap=snapshot or build_character_display_snapshot(character)
    ident,res,prog,attrs,combat,carry,currency,surv,time=snap.identity,snap.resources,snap.progression,snap.attributes,snap.combat,snap.carrying,snap.currency,snap.survival,snap.time
    rows=[]
    rows.append(_row_fields(("Name", ident.get("display_name","Adventurer")), ("Title", ident.get("title","—"))))
    rows.append(_row_fields(("Race", ident.get("race_name","—")), ("Class", ident.get("class_name","—"))))
    rows.append(_row_fields(("Level", ident.get("level","—")), ("Alignment", ident.get("alignment","—"))))
    if ident.get("age") or ident.get("birthday"): rows.append(_row_fields(("Age", ident.get("age","—")), ("Birthday", ident.get("birthday","—"))))
    rows.append(DisplayDivider())
    resource_parts=[]
    for label,a,b in (("HP","hp","max_hp"),("Mana","mana","max_mana"),("Stamina","stamina","max_stamina")):
        if a in res or b in res: resource_parts.append(f"{label}: {res.get(a,'—')}/{res.get(b,'—')}")
    if resource_parts: rows.append(DisplayLine("   ".join(resource_parts)))
    if prog: rows.append(_row_fields(("Experience", prog.get("xp","—")), ("TNL", prog.get("xp_to_next_level","—"))))
    pts=[(k.replace("_"," ").title(),v) for k,v in prog.items() if k in {"practice_points","training_points","quest_points","level_progress_percent"}]
    if pts: rows.append(_row_fields(*pts[:2]))
    if carry:
        rows.append(DisplayLine(f"Carry Capacity: {carry.get('current_weight', carry.get('carry_weight','—'))} / {carry.get('carry_capacity','—')} — {carry.get('encumbrance_text', carry.get('encumbrance','—'))}"))
    rows.append(DisplayDivider())
    labels=[("Str","strength"),("Dex","dexterity"),("Con","constitution"),("Int","intelligence"),("Wis","wisdom"),("Cha","charisma")]
    attr_cells=[DisplayCell(width=22, segments=_field_segments(lab, _fmt_attr(attrs[key]))) for lab,key in labels if key in attrs]
    for i in range(0,len(attr_cells),3): rows.append(DisplayRow(attr_cells[i:i+3]))
    if combat:
        rows.append(DisplayDivider())
        for chunk in (("Armor","armor","Evasion","evasion"),("Spell Saves","spell_saves","Accuracy","accuracy"),("Hit Bonus","hit_bonus","Damage Bonus","damage_bonus"),("Critical Melee","critical_melee","Critical Spell","critical_spell"),("Critical Heal","critical_heal","Weapon","weapon_damage_summary"),("Unarmed","unarmed_damage_summary","Resistances","resistances")):
            pairs=[]
            for lab,key in zip(chunk[::2], chunk[1::2]):
                if key in combat: pairs.append((lab, combat[key]))
            if pairs: rows.append(_row_fields(*pairs[:2]))
    if currency:
        rows.append(DisplayDivider()); rows.append(DisplayRow([DisplayCell(width=22, segments=_field_segments(k.title(), v, value_role="gold" if k=="gold" else "character_value")) for k,v in currency.items() if v is not None]))
    st=[(k.replace('_',' ').title(),v) for k,v in surv.items() if v not in (None,"")]
    if st: rows.append(DisplayDivider()); rows.append(_row_fields(*st[:2]))
    tt=[(k.replace('_',' ').title(),v) for k,v in time.items() if v not in (None,"")]
    if tt: rows.append(DisplayDivider()); rows.append(_row_fields(*tt[:2]))
    return build_character_frame_document(DisplayIntent.SCORE,"CHARACTER STATUS",rows,width=79)

def build_worth_document(character: Any, *, snapshot: CharacterDisplaySnapshot | None = None) -> DisplayDocument:
    currency=(snapshot or build_character_display_snapshot(character)).currency
    cells=[DisplayCell(width=18, segments=_field_segments(k.title(), v, value_role="gold" if k=="gold" else "character_value")) for k,v in currency.items() if v is not None]
    if not cells: cells=[DisplayCell("You are broke.", role="character_muted", width=30)]
    return build_character_frame_document(DisplayIntent.SCORE,"CURRENCIES",[DisplayRow(cells)],width=48)

def _ability_cost(row: dict[str, Any]) -> str:
    costs=row.get('costs') or []
    return ", ".join(f"{c.get('amount', c.get('percentage',0))} {str(c.get('resource_id','')).title()}" for c in costs) or "No cost"

def build_abilities_document(rows: list[dict[str, Any]], *, title: str="ABILITIES", empty: str="You have no abilities.") -> DisplayDocument:
    out=[]
    for i,r in enumerate(rows):
        if i: out.append(DisplayDivider(kind="item"))
        rank=f"Rank: {int(r.get('rank') or 1)}/{int(r.get('maximum_rank') or 100)}"
        out.append(DisplayRow([DisplayCell(str(r.get('name') or r.get('id') or 'Ability').replace('_',' ').title(),width=48),DisplayCell(rank,width=17,align='right')], role="character_title"))
        status=str(r.get('status_text') or r.get('availability_text') or ('Passive' if r.get('passive') else 'Availability unknown.'))
        out.append(DisplayLine(f"Status: {status}", role="character_positive" if status=='Ready' else "warning"))
        meta=[]
        if title == 'SPELLS':
            meta=[DisplayCell(f"Mana: {next((c.get('amount') for c in (r.get('costs') or []) if c.get('resource_id') in {'mana','mp'}), 0)}",width=18),DisplayCell(f"Cooldown: {r.get('cooldown_remaining') or r.get('cooldown') or '—'}",width=22),DisplayCell(f"Target: {((r.get('targeting') or {}).get('mode') or 'Self').title()}",width=20)]
        else:
            cat=str(r.get('category') or r.get('ability_type') or 'General').replace('_',' ').title(); meta=[DisplayCell(f"Category: {cat}",width=34),DisplayCell(f"Cost: {_ability_cost(r)}",width=28)]
        out.append(DisplayRow(meta));
        if r.get('description'): out.append(DisplayLine(str(r.get('description')), role="character_value"))
    if not out: out=[DisplayLine(empty, role="character_muted")]
    return build_character_frame_document(DisplayIntent.SKILLS if title=='SKILLS' else DisplayIntent.SPELLS if title=='SPELLS' else DisplayIntent.SYSTEM,title,out,width=70)

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

def build_prompt_document(character: Any) -> DisplayDocument:
    prefs = getattr(character, "preferences", {}) or {}
    if not getattr(character, "prompt_template", None) and not getattr(character, "prompt_preset", None) and not prefs.get("prompt_template") and not prefs.get("prompt_preset"):
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
    }
    template=_prompt_template(character)
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
