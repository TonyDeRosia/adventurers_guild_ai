"""Safe Builder-authored display theme contracts for character displays."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from engine.mud_rendering import SEMANTIC_COLOR_ROLES, validate_mud_color_markup

SUPPORTED_FAMILIES = {"score","worth","inventory","equipment","affects","skills","spells","abilities","cooldowns","quest_log","shop","board","trainer","help"}
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
    templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_display_theme(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    families = set((raw.get("templates") or {}).keys()) | set((raw.get("section_order") or {}).keys())
    for fam in families:
        if fam not in SUPPORTED_FAMILIES:
            errors.append(f"unsupported display family: {fam}")
    for role in (raw.get("semantic_roles") or {}).values():
        if role not in SEMANTIC_COLOR_ROLES:
            errors.append(f"unsupported semantic role: {role}")
    for label, text in (raw.get("labels") or {}).items():
        errors.extend(f"labels.{label}: {e}" for e in validate_mud_color_markup(str(text)))
    for name, template in (raw.get("prompt_presets") or {}).items():
        errors.extend(f"prompt_presets.{name}: {e}" for e in validate_mud_color_markup(str(template)))
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


def preview_display_theme(raw: dict[str, Any]) -> dict[str, str]:
    errors = validate_display_theme(raw)
    if errors:
        return {"ok": "false", "errors": "\n".join(errors)}
    title = ((raw.get("labels") or {}).get("score.title") or "CHARACTER STATUS")
    return {"ok": "true", "plain": title.replace("&Y", "").replace("&n", ""), "ansi": title, "html": title}
