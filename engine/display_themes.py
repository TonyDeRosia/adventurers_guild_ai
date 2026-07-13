"""Safe Builder-authored display theme contracts for character displays."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from engine.mud_rendering import SEMANTIC_COLOR_ROLES, validate_mud_color_markup

SUPPORTED_FAMILIES = {"score","worth","inventory","equipment","affects","skills","spells","abilities","cooldowns","prompt","quest_log","shop","board","trainer","help"}
FRAMED_FAMILIES = {"score","worth","inventory","equipment","affects","skills","spells","abilities","cooldowns"}
SUPPORTED_FRAME_STYLES = {"classic_double", "classic_single", "minimal", "none"}
SUPPORTED_TITLE_ALIGNMENTS = {"left", "center", "right"}
SUPPORTED_EMPTY_POLICIES = {"hide", "show_muted", "show_empty_message"}

class ThemeResolutionMode(str, Enum):
    PUBLISHED = "published"
    BUILDER_DRAFT_PREVIEW = "builder_draft_preview"

THEME_FIELD_SUPPORT = {
    fam: {
        "frame_style": True, "width": True, "title_alignment": True,
        "section_order": fam == "score", "visible_sections": fam == "score",
        "empty_section_policy": fam in FRAMED_FAMILIES if "FRAMED_FAMILIES" in globals() else True,
        "labels": True, "semantic_roles": True, "border_characters": True,
        "divider_characters": True, "templates": False, "prompt_presets": fam == "prompt",
    } for fam in SUPPORTED_FAMILIES
}
SCORE_SECTIONS = {"identity","resources","progression","carrying","attributes","combat","currency","survival","effects","time"}
BORDER_PARTS = {"top_left","top","top_right","side","bottom_left","bottom","bottom_right","section_left","section","section_right","item_left","item","item_right"}
ALLOWED_TEMPLATE_FIELDS = {"name","title","race","class_name","level","age","alignment","hp","max_hp","mana","max_mana","stamina","max_stamina","xp","tnl","gold","silver","copper","posture","hunger","thirst","played","last_login","rows","label","value","description","rank","status","category","cost","target","cooldown"}
_EXPR_RE = re.compile(r"[{][^{}]*([.()]|__|import|open|eval|exec|select\s|from\s|<\s*/?\w+)[^{}]*[}]", re.I)

@dataclass
class DisplayTheme:
    theme_id: str
    name: str
    description: str = ""
    frame_style: str = "classic_double"
    width: int = 79
    title_alignment: str = "center"
    section_order: dict[str, list[str]] = field(default_factory=dict)
    visible_sections: dict[str, list[str]] = field(default_factory=dict)
    empty_section_policy: str = "hide"
    labels: dict[str, str] = field(default_factory=dict)
    semantic_roles: dict[str, str] = field(default_factory=dict)
    border_characters: dict[str, str] = field(default_factory=dict)
    divider_characters: dict[str, str] = field(default_factory=dict)
    prompt_presets: dict[str, str] = field(default_factory=dict)
    player_selectable: bool = False
    accessibility: tuple[str, ...] = ()
    templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_display_theme(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(raw.get("frame_style") or "classic_double").lower() not in SUPPORTED_FRAME_STYLES:
        errors.append("unsupported frame_style")
    if str(raw.get("title_alignment") or "center").lower() not in SUPPORTED_TITLE_ALIGNMENTS:
        errors.append("unsupported title_alignment")
    if str(raw.get("empty_section_policy") or "hide").lower() not in SUPPORTED_EMPTY_POLICIES:
        errors.append("unsupported empty_section_policy")
    try:
        w=int(raw.get("width") or 79)
        if w < 36 or w > 160: errors.append("width must be 36-160")
    except Exception: errors.append("width must be an integer")
    families = set((raw.get("templates") or {}).keys()) | set((raw.get("section_order") or {}).keys()) | set((raw.get("visible_sections") or {}).keys())
    for fam in families:
        if fam not in SUPPORTED_FAMILIES:
            errors.append(f"unsupported display family: {fam}")
    for fam, sections in dict(raw.get("section_order") or {}, **(raw.get("visible_sections") or {})).items():
        allowed = SCORE_SECTIONS if fam == "score" else set()
        if allowed:
            for sec in sections or []:
                if sec not in allowed: errors.append(f"unsupported section for {fam}: {sec}")
    def _safe_one_char(path: str, value: Any) -> None:
        text=str(value or "")
        if _EXPR_RE.search("{"+text+"}") or "\x1b" in text or any(ord(c)<32 for c in text) or "<" in text or ">" in text or text.startswith("&") or len(text) != 1:
            errors.append(f"{path}: must be one safe visible character")
    for part, ch in (raw.get("border_characters") or {}).items():
        if part not in BORDER_PARTS: errors.append(f"unsupported border part: {part}")
        _safe_one_char(f"border_characters.{part}", ch)
    for part, ch in (raw.get("divider_characters") or {}).items():
        _safe_one_char(f"divider_characters.{part}", ch)
    for role in (raw.get("semantic_roles") or {}).values():
        if role not in SEMANTIC_COLOR_ROLES:
            errors.append(f"unsupported semantic role: {role}")
    for label, text in (raw.get("labels") or {}).items():
        errors.extend(f"labels.{label}: {e}" for e in validate_mud_color_markup(str(text)))
    for name, template in (raw.get("prompt_presets") or {}).items():
        errors.extend(f"prompt_presets.{name}: {e}" for e in validate_mud_color_markup(str(template)))
    for fam, template in (raw.get("templates") or {}).items():
        if template:
            errors.append(f"Templates are not currently supported for display family: {fam}.")
    def walk(obj: Any, path: str = "templates") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items(): walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj): walk(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            errors.extend(f"{path}: {e}" for e in validate_mud_color_markup(obj))
            if _EXPR_RE.search(obj): errors.append(f"{path}: arbitrary expressions, HTML, and attribute traversal are not allowed")
            for field_name in re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", obj):
                if field_name not in ALLOWED_TEMPLATE_FIELDS:
                    errors.append(f"{path}: unsupported template field {field_name}")
    walk(raw.get("templates") or {})
    return errors


def preview_display_theme(raw: dict[str, Any], family: str = "score") -> dict[str, str]:
    """Render a realistic theme preview through the runtime display builders."""
    errors = validate_display_theme(raw)
    if errors:
        return {"ok": "false", "errors": "\n".join(errors)}
    from types import SimpleNamespace
    from engine.mud_displays import (
        build_score_document, build_worth_document, build_abilities_document,
        build_inventory_document, build_equipment_document, build_prompt_document,
        render_display_plain, render_display_mud, render_display_ansi, render_display_html,
    )
    sample = SimpleNamespace(
        id="preview", name="Kraevok", title="Adventurer", race="Human", character_class="Ranger",
        level=12, age=31, alignment="Neutral Good", hp=84, max_hp=100, mana=32, max_mana=45,
        stamina=51, max_stamina=60, xp=4242, xp_to_next_level=758, gold=25, silver=3,
        posture="standing", hunger="sated", thirst="quenched", played_time="2 days", last_login="today",
        attributes={"strength":{"base":10,"modifier":2,"final":12},"dexterity":{"base":14,"modifier":1,"final":15},"constitution":{"final":11}},
        calculated_stats={"armor":18,"evasion":12,"accuracy":7,"hit_bonus":4,"damage_bonus":3,"critical_melee":"5%"},
        carry_weight=22, carry_capacity=80, encumbrance="light", prompt_preset="classic",
    )
    abilities=[{"name":"Build Campfire","rank":1,"maximum_rank":1,"status_text":"Requires an established campsite.","category":"Survival","description":"Builds a safe campfire when camp conditions permit."}]
    theme = _theme_from_raw(raw, family)
    if family == "worth": doc = build_worth_document(sample, theme=theme)
    elif family in {"skills","spells","abilities","cooldowns"}: doc = build_abilities_document(abilities, title=family.upper(), theme=theme)
    elif family == "inventory": doc = build_inventory_document([{"name":"a polished lantern"}], theme=theme)
    elif family == "equipment": doc = build_equipment_document([{"equipped_slot":"main_hand","name":"iron sword"}], ["main_hand","off_hand"], theme=theme)
    elif family == "prompt": doc = build_prompt_document(sample, theme=theme)
    else: doc = build_score_document(sample, theme=theme)
    width = int(raw.get("width") or 0)
    return {"ok": "true", "plain": render_display_plain(doc), "mud": render_display_mud(doc, color_enabled=getattr(theme, "color_enabled", True)), "ansi": render_display_ansi(doc, color_enabled=getattr(theme, "color_enabled", True)), "html": render_display_html(doc, color_enabled=getattr(theme, "color_enabled", True))}

def _theme_from_raw(raw: dict[str, Any], family: str) -> "ResolvedDisplayTheme":
    return ResolvedDisplayTheme(theme_id=str(raw.get("theme_id") or raw.get("id") or "draft"), family=family, width=max(36,min(160,int(raw.get("width") or 79))), frame_style=str(raw.get("frame_style") or "classic_double").lower(), title_alignment=str(raw.get("title_alignment") or "center").lower(), section_order=tuple((raw.get("section_order") or {}).get(family, ())), visible_sections=tuple((raw.get("visible_sections") or {}).get(family, ())), empty_section_policy=str(raw.get("empty_section_policy") or "hide").lower(), labels=dict(raw.get("labels") or {}), semantic_roles=dict(raw.get("semantic_roles") or {}), border_characters=dict(raw.get("border_characters") or {}), divider_characters=dict(raw.get("divider_characters") or {}), templates=dict((raw.get("templates") or {}).get(family, {})), prompt_presets=dict(raw.get("prompt_presets") or {}), player_selectable=bool((raw.get("metadata") or {}).get("player_selectable", False)))

@dataclass(frozen=True)
class DisplayThemeResolutionContext:
    world_id: str = "shattered_realms"
    zone_id: str = ""
    area_id: str = ""
    room_id: str = ""
    family: str = "score"
    world_default_theme: str = ""
    zone_theme_id: str = ""
    zone_family_theme_id: str = ""
    area_theme_id: str = ""
    area_family_theme_id: str = ""
    player_theme_id: str = ""
    player_display_width: str = ""
    accessibility: tuple[str, ...] = ()
    resolution_mode: ThemeResolutionMode = ThemeResolutionMode.PUBLISHED


@dataclass(frozen=True)
class ResolvedDisplayTheme:
    source_scope: str = "engine"
    theme_id: str = "engine_default"
    family: str = "score"
    width: int = 79
    frame_style: str = "classic_double"
    title_alignment: str = "center"
    section_order: tuple[str, ...] = ()
    visible_sections: tuple[str, ...] = ()
    empty_section_policy: str = "hide"
    labels: dict[str, str] = field(default_factory=dict)
    semantic_roles: dict[str, str] = field(default_factory=dict)
    border_characters: dict[str, str] = field(default_factory=dict)
    divider_characters: dict[str, str] = field(default_factory=dict)
    templates: dict[str, Any] = field(default_factory=dict)
    prompt_presets: dict[str, str] = field(default_factory=dict)
    player_selectable: bool = False
    accessibility: tuple[str, ...] = ()
    context: DisplayThemeResolutionContext | None = None
    color_enabled: bool = True
    palette: str = "default"
    resolution_mode: ThemeResolutionMode = ThemeResolutionMode.PUBLISHED


def load_display_themes(world_root: str | Any = "worlds/shattered_realms") -> dict[str, DisplayTheme]:
    import json
    from pathlib import Path
    root = Path(world_root)
    path = root / "display_themes" / "display_themes.json"
    if not path.exists(): return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("display_themes", raw) if isinstance(raw, dict) else raw
    out={}
    for item in items if isinstance(items, list) else []:
        errs = validate_display_theme(item)
        if errs: continue
        tid = str(item.get("theme_id") or item.get("id") or "")
        if tid: out[tid] = DisplayTheme(theme_id=tid, name=str(item.get("name") or tid), description=str(item.get("description") or ""), frame_style=str(item.get("frame_style") or "classic_double"), width=int(item.get("width") or 79), title_alignment=str(item.get("title_alignment") or "center"), section_order=dict(item.get("section_order") or {}), visible_sections=dict(item.get("visible_sections") or {}), empty_section_policy=str(item.get("empty_section_policy") or "hide"), labels=dict(item.get("labels") or {}), semantic_roles=dict(item.get("semantic_roles") or {}), border_characters=dict(item.get("border_characters") or {}), divider_characters=dict(item.get("divider_characters") or {}), prompt_presets=dict(item.get("prompt_presets") or {}), templates=dict(item.get("templates") or {}), metadata=dict(item.get("metadata") or {}))
    return out

def load_builder_draft_display_themes(world_root: str | Any = "worlds/shattered_realms") -> dict[str, DisplayTheme]:
    root = Path(world_root)
    path = root / "builder" / "display_themes.json"
    if not path.exists():
        return {}
    raw = _load_json(path, {})
    items = raw.get("display_themes", raw) if isinstance(raw, dict) else raw
    if isinstance(items, dict):
        seq = list(items.values())
    else:
        seq = items if isinstance(items, list) else []
    out: dict[str, DisplayTheme] = {}
    for item in seq:
        if not isinstance(item, dict) or validate_display_theme(item):
            continue
        tid = str(item.get("theme_id") or item.get("id") or "")
        if tid:
            out[tid] = DisplayTheme(theme_id=tid, name=str(item.get("name") or tid), description=str(item.get("description") or ""), frame_style=str(item.get("frame_style") or "classic_double"), width=int(item.get("width") or 79), title_alignment=str(item.get("title_alignment") or "center"), section_order=dict(item.get("section_order") or {}), visible_sections=dict(item.get("visible_sections") or {}), empty_section_policy=str(item.get("empty_section_policy") or "hide"), labels=dict(item.get("labels") or {}), semantic_roles=dict(item.get("semantic_roles") or {}), border_characters=dict(item.get("border_characters") or {}), divider_characters=dict(item.get("divider_characters") or {}), prompt_presets=dict(item.get("prompt_presets") or {}), templates=dict(item.get("templates") or {}), metadata=dict(item.get("metadata") or {}))
    return out


def _load_json(path: Path, default: Any) -> Any:
    import json
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception: return default

def _byid(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict): return raw
    if isinstance(raw, list): return {str(x.get("id")): x for x in raw if isinstance(x, dict) and x.get("id")}
    return {}

def _world_meta(raw: Any, wid: str) -> dict[str, Any]:
    if isinstance(raw, dict) and wid in raw and isinstance(raw[wid], dict): return raw[wid]
    return raw if isinstance(raw, dict) else {}

def load_published_theme_assignments(world_root: str | Path = "worlds/shattered_realms") -> dict[str, Any]:
    root = Path(world_root); wid = root.name
    return {
        "world": _world_meta(_load_json(root / "world" / "world.json", {}), wid),
        "areas": _byid(_load_json(root / "areas" / "areas.json", [])),
        "zones": _byid(_load_json(root / "zones" / "zones.json", [])),
    }

def load_builder_draft_theme_assignments(world_root: str | Path = "worlds/shattered_realms") -> dict[str, Any]:
    root = Path(world_root); wid = root.name
    return {
        "world": _world_meta(_load_json(root / "builder" / "world.json", {}), wid),
        "areas": _byid(_load_json(root / "builder" / "areas.json", {})),
        "zones": _byid(_load_json(root / "builder" / "zones.json", {})),
    }

def load_effective_builder_preview_assignments(world_root: str | Path = "worlds/shattered_realms") -> dict[str, Any]:
    pub=load_published_theme_assignments(world_root); draft=load_builder_draft_theme_assignments(world_root)
    return {"world": {**pub.get("world",{}), **draft.get("world",{})}, "areas": {**pub.get("areas",{}), **draft.get("areas",{})}, "zones": {**pub.get("zones",{}), **draft.get("zones",{})}}

def load_theme_assignments(world_root: str | Path = "worlds/shattered_realms") -> dict[str, Any]:
    return load_published_theme_assignments(world_root)

def _room_scope(character: Any, assignments: dict[str, Any]) -> tuple[str, str, str]:
    room_id = str(getattr(character, "room_id", "") or "") if character is not None else ""
    area_id = str(getattr(character, "area_id", "") or getattr(character, "current_area_id", "") or "") if character is not None else ""
    zone_id = str(getattr(character, "zone_id", "") or getattr(character, "current_zone_id", "") or "") if character is not None else ""
    if room_id and (not area_id or not zone_id):
        for z_id, z in (assignments.get("zones") or {}).items():
            if room_id in (z.get("room_ids") or []): zone_id = zone_id or str(z_id); area_id = area_id or str(z.get("area_id") or ""); break
    if zone_id and not area_id: area_id = str(((assignments.get("zones") or {}).get(zone_id) or {}).get("area_id") or "")
    return room_id, zone_id, area_id

def _assignment_theme(scope: dict[str, Any], family: str) -> tuple[str, str]:
    fams = scope.get("display_theme_ids") if isinstance(scope, dict) else None
    if isinstance(fams, dict) and fams.get(family): return str(fams[family]), "family"
    if isinstance(scope, dict) and scope.get("display_theme_id"): return str(scope["display_theme_id"]), "general"
    return "", ""

def resolve_effective_display_theme(character: Any = None, world_id: str = "shattered_realms", zone_id: str = "", area_id: str = "", family: str = "score", themes: dict[str, DisplayTheme] | None = None, world_root: str | Path | None = None, resolution_mode: ThemeResolutionMode | str = ThemeResolutionMode.PUBLISHED) -> ResolvedDisplayTheme:
    root = Path(world_root) if world_root else Path("worlds") / (world_id or "shattered_realms")
    mode = ThemeResolutionMode(resolution_mode)
    themes = themes or load_display_themes(root)
    if mode is ThemeResolutionMode.BUILDER_DRAFT_PREVIEW:
        themes = {**themes, **load_builder_draft_display_themes(root)}
    if not themes:
        themes = {"classic_adventurer": DisplayTheme("classic_adventurer", "Classic Adventurer"), "minimal_modern": DisplayTheme("minimal_modern", "Minimal Modern", frame_style="minimal", width=60, title_alignment="left")}
    assignments = load_effective_builder_preview_assignments(root) if mode is ThemeResolutionMode.BUILDER_DRAFT_PREVIEW else load_published_theme_assignments(root)
    if character is not None:
        room_id, z2, a2 = _room_scope(character, assignments); zone_id = zone_id or z2; area_id = area_id or a2
    else: room_id = ""
    prefs = getattr(character, "preferences", {}) or {} if character is not None else {}
    world_meta = assignments.get("world") or {}
    world_default = str(world_meta.get("default_display_theme_id") or "classic_adventurer")
    zone_theme, zkind = _assignment_theme((assignments.get("zones") or {}).get(zone_id) or {}, family)
    area_theme, akind = _assignment_theme((assignments.get("areas") or {}).get(area_id) or {}, family)
    candidates = [("player", prefs.get("display_theme")), ("area_family" if akind=="family" else "area", area_theme), ("zone_family" if zkind=="family" else "zone", zone_theme), ("world", world_default), ("engine", "classic_adventurer")]
    source, selected = next(((s,t) for s,t in candidates if t and str(t) in themes), ("engine", "classic_adventurer"))
    theme = themes.get(str(selected)) or DisplayTheme("engine_default", "Engine Default")
    width_pref = str(prefs.get("display_width") or theme.width or "79")
    width = {"wide":79,"medium":60,"narrow":44,"auto":int(theme.width or 79)}.get(width_pref, None)
    if width is None:
        try: width=max(36, min(160, int(width_pref)))
        except Exception: width=int(theme.width or 79)
    roles=dict(theme.semantic_roles); access=[]; palette="default"; color_enabled=True
    for key in ("no_color","high_contrast","colorblind","reduced_decoration"):
        if prefs.get(key): access.append(key)
    if prefs.get("no_color"): color_enabled=False
    if prefs.get("high_contrast"): palette="high_contrast"; roles.update({"character_muted":"character_value","character_label":"character_title"})
    if prefs.get("colorblind"): palette="colorblind"; roles.update({"character_positive":"success","character_negative":"warning"})
    frame_style=theme.frame_style
    if prefs.get("reduced_decoration") and frame_style in {"classic_double", "classic_single"}: frame_style="minimal"
    ctx=DisplayThemeResolutionContext(world_id=world_id, zone_id=zone_id, area_id=area_id, room_id=room_id, family=family, world_default_theme=world_default, zone_theme_id=zone_theme if zkind=="general" else "", zone_family_theme_id=zone_theme if zkind=="family" else "", area_theme_id=area_theme if akind=="general" else "", area_family_theme_id=area_theme if akind=="family" else "", player_theme_id=str(prefs.get("display_theme") or ""), player_display_width=str(prefs.get("display_width") or ""), accessibility=tuple(access), resolution_mode=mode)
    return ResolvedDisplayTheme(source_scope=source, theme_id=theme.theme_id, family=family, width=width, frame_style=frame_style, title_alignment=theme.title_alignment, section_order=tuple((theme.section_order or {}).get(family, ())), visible_sections=tuple((theme.visible_sections or {}).get(family, ())), empty_section_policy=theme.empty_section_policy, labels=dict(theme.labels), semantic_roles=roles, border_characters=dict(theme.border_characters), divider_characters=dict(theme.divider_characters), templates=dict((theme.templates or {}).get(family, {})), prompt_presets=dict(theme.prompt_presets), player_selectable=bool(theme.metadata.get("player_selectable", False)), accessibility=tuple(access), context=ctx, color_enabled=color_enabled, palette=palette, resolution_mode=mode)
