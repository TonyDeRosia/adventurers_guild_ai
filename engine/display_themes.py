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


def preview_display_theme(raw: dict[str, Any], family: str = "score") -> dict[str, str]:
    """Render a realistic theme preview through the runtime display builders."""
    errors = validate_display_theme(raw)
    if errors:
        return {"ok": "false", "errors": "\n".join(errors)}
    from types import SimpleNamespace
    from engine.mud_displays import (
        build_score_document, build_worth_document, build_abilities_document,
        build_inventory_document, build_equipment_document, build_prompt_document,
        render_display_plain, render_display_mud, render_display_html,
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
    if family == "worth": doc = build_worth_document(sample)
    elif family in {"skills","spells","abilities","cooldowns"}: doc = build_abilities_document(abilities, title=family.upper())
    elif family == "inventory": doc = build_inventory_document([{"name":"a polished lantern"}])
    elif family == "equipment": doc = build_equipment_document([{"equipped_slot":"main_hand","name":"iron sword"}], ["main_hand","off_hand"])
    elif family == "prompt": doc = build_prompt_document(sample)
    else: doc = build_score_document(sample)
    width = int(raw.get("width") or 0)
    if width and getattr(doc, "frames", None):
        for frame in doc.frames: frame.width = width
    return {"ok": "true", "plain": render_display_plain(doc), "mud": render_display_mud(doc), "html": render_display_html(doc)}
