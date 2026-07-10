"""Single modular Adventurer's-Lair-style score sheet rendering for Actors.

The renderer is intentionally presentation-only: it does not execute combat,
formulas, spell, skill, equipment bonus, or AI logic.  All score-related
commands should call :class:`ActorScoreRenderer` so the Actor presentation layer
has one permanent render path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from engine.actors import Actor, FormulaRegistry
from engine.phase5f import BodyProfileRegistry
from engine.mud_displays import semantic

ADMIN_SECTIONS = {"diagnostics", "formulas", "raw"}

BOX_WIDTH = 78
EMPTY = "--"

REMOVED_GAMEPLAY_SLOTS = {"primary_weapon", "secondary_weapon", "shield", "quiver", "ranged", "ammo", "both_hands"}
RESOURCE_ROWS = [
    ("health", "Health", "hp"), ("mana", "Mana", "mp"), ("movement", "Movement", "score_value"),
    ("stamina", "Stamina", "stamina"), ("hunger", "Hunger", "score_value"), ("thirst", "Thirst", "score_value"),
    ("fatigue", "Fatigue", "score_value"), ("drunkenness", "Drunkenness", "score_value"),
    ("warmth", "Warmth", "score_value"), ("body_temperature", "Body Temperature", "score_value"),
    ("corruption", "Corruption", "score_value"), ("sanity", "Sanity", "score_value"), ("oxygen", "Oxygen", "score_value"),
]
DERIVED_KEYS = [
    "attack_rating", "defense_rating", "armor", "hit_bonus", "damage_bonus", "critical_chance",
    "critical_damage", "critical_avoidance", "parry", "block", "dodge", "initiative", "threat",
    "spell_power", "healing_power", "movement_regeneration", "mana_regeneration", "health_regeneration",
    "carry_weight", "carry_capacity", "reach", "range", "casting_speed", "attack_speed",
]
COMBAT_FIELDS = [
    "primary_weapon", "secondary_weapon", "attack_style", "combat_profile", "aggression_profile",
    "combat_stance", "target", "range", "attack_delay", "combat_flags", "natural_attacks",
    "shield_status", "dual_wield_status", "builder_combat_profile",
]
CONDITIONS = ["standing", "resting", "sleeping", "fighting", "flying", "swimming", "invisible", "hidden", "sneaking", "mounted"]
RESISTANCES = ["physical", "slash", "pierce", "blunt", "fire", "cold", "lightning", "poison", "disease", "holy", "shadow", "arcane", "mental", "bleeding"]
AFFECT_GROUPS = ["positive", "negative", "passive", "equipment", "temporary", "permanent", "future_ai"]
SPELLUP_GROUPS = ["permanent", "long", "medium", "short", "expiring"]
PROGRESSION_FIELDS = ["level", "experience", "experience_to_next", "practice_sessions", "training_sessions", "remorts", "builder_progression_data", "future_advancement_data"]
CURRENCY_FIELDS = ["gold", "silver", "copper", "premium"]
RELATIONSHIP_FIELDS = ["faction", "guild_standing", "clan_standing", "friends", "enemies", "followers", "pet", "mount", "mentor", "family", "marriage", "builder_relationship_data"]
SIMULATION_FIELDS = ["current_schedule", "current_goal", "current_activity", "current_need", "current_mood", "current_location", "current_simulation_tick", "current_world_time"]


def _human(key: str) -> str:
    return str(key).replace("_", " ").title()


def _value(value: Any) -> str:
    if value is None or value == "":
        return EMPTY
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_value(v) for v in value) if value else EMPTY
    if isinstance(value, dict):
        if "name" in value:
            return str(value["name"])
        return ", ".join(f"{_human(k)}={_value(v)}" for k, v in value.items()) if value else EMPTY
    return str(value)


def _line(left: str = "") -> str:
    return semantic("system", f"| {left:<{BOX_WIDTH - 4}} |")


def _rule(ch: str = "-") -> str:
    if ch == "=":
        return semantic("system", ch * (BOX_WIDTH - 2))
    return semantic("system", "+" + ch * (BOX_WIDTH - 2) + "+")


def _header(title: str) -> list[str]:
    text = f" {title} "
    fill = BOX_WIDTH - 2 - len(text)
    return [_rule("="), semantic("system", "|" + text + "-" * max(0, fill) + "|") + semantic("system", f"  [{title.title()}]"), _rule("-")]


def _field(label: str, value: Any, *, role: str = "score_value", width: int = 22) -> str:
    return f"{semantic('score_label', label + ':'):<0} {semantic(role, _value(value))}".ljust(width)


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)


class ActorScoreRenderer:
    """The one score renderer, with independently renderable sections."""

    order = [
        "identity", "resources", "primary_attributes", "derived_attributes", "combat", "equipment",
        "conditions", "resistances", "affects", "spellup", "progression", "currencies", "relationships",
        "simulation", "diagnostics", "formulas", "raw",
    ]
    aliases = {
        "score": "all", "preview": "all", "actor": "all", "attrs": "primary_attributes", "attributes": "primary_attributes",
        "derived": "derived_attributes", "resists": "resistances", "saff": "affects", "spellups": "spellup",
        "worth": "currencies", "currency": "currencies", "money": "currencies", "builder": "diagnostics",
        "builder_diagnostics": "diagnostics", "ai": "simulation", "ai_diagnostics": "simulation",
    }

    def __init__(self, formula_registry: FormulaRegistry | None = None, *, ansi: bool = False):
        self.formula_registry = formula_registry or FormulaRegistry.default()
        self.body_registry = BodyProfileRegistry()
        self.ansi = ansi
        self._renderers: dict[str, Callable[[Actor, bool], str]] = {name: getattr(self, f"render_{name}") for name in self.order}

    def render(self, actor: Actor, section: str = "all", *, admin: bool = False, ansi: bool | None = None) -> str:
        section = self.aliases.get((section or "all").lower(), (section or "all").lower())
        if section != "all":
            return self.render_section(actor, section, admin=admin, ansi=ansi)
        return "\n".join(self.render_section(actor, s, admin=admin, ansi=ansi) for s in self.order if admin or s not in ADMIN_SECTIONS)

    def render_section(self, actor: Actor, section: str, *, admin: bool = False, ansi: bool | None = None) -> str:
        section = self.aliases.get(section, section)
        if section not in self._renderers:
            return f"Unknown score section: {section}"
        if section in ADMIN_SECTIONS and not admin:
            return "That score section is restricted to administrators and Builders."
        return self._renderers[section](actor, admin)

    def _section(self, title: str, rows: list[str]) -> str:
        return "\n".join(_header(title) + (rows or [_line("None.")]) + [_rule("-")])

    def _two_col(self, pairs: list[tuple[str, Any, str]]) -> list[str]:
        rows = []
        for idx in range(0, len(pairs), 2):
            l_label, l_value, l_role = pairs[idx]
            left = _field(l_label, l_value, role=l_role)
            if idx + 1 < len(pairs):
                r_label, r_value, r_role = pairs[idx + 1]
                right = _field(r_label, r_value, role=r_role)
            else:
                right = ""
            rows.append(_line(f"{left:<36} {right}"))
        return rows

    def render_identity(self, actor: Actor, admin: bool = False) -> str:
        i = actor.identity
        pairs = [("Name", i.name, "player"), ("Title", i.title, "score_value"), ("Race", i.race, "score_value"), ("Class", i.class_placeholder, "score_value"), ("Profession", i.profession_placeholder, "score_value"), ("Guild", i.guild, "score_value"), ("Clan", i.clan, "score_value"), ("Religion", i.religion, "score_value"), ("Alignment", i.alignment, "score_value"), ("Gender", i.gender, "score_value"), ("Age", i.age, "score_value"), ("Height", i.height, "score_value"), ("Weight", i.weight, "score_value"), ("Languages Known", i.languages, "score_value"), ("Speaking Language", i.speaking_language, "score_value"), ("Current Position", i.position, "score_value"), ("World", i.current_world, "score_value"), ("Area", i.current_area, "score_value"), ("Zone", i.current_zone, "score_value"), ("Room", i.current_location, "score_value")]
        if admin:
            pairs.append(("Builder Actor ID", actor.actor_id, "score_value"))
        rows = self._two_col(pairs)
        rows.append(_line(_field("Description", i.description or "None", width=70)))
        return self._section("SCORE IDENTITY", rows)

    def render_resources(self, actor: Actor, admin: bool = False) -> str:
        r = actor.resources
        pairs = []
        for key, label, role in RESOURCE_ROWS:
            maxv = getattr(r, f"maximum_{key}", None)
            cur = getattr(r, key, None)
            val = f"{cur}/{maxv}  Regen: future  Mods: future" if maxv is not None else f"{_value(cur)}  Regen: future  Mods: future"
            pairs.append((label, val, role))
        for key, value in actor.plugin_data.get("resources", {}).items():
            pairs.append((_human(key), f"{_value(value)}  Regen: future  Mods: future", "score_value"))
        return self._section("RESOURCES", self._two_col(pairs))

    def render_primary_attributes(self, actor: Actor, admin: bool = False) -> str:
        return self._section("PRIMARY ATTRIBUTES", self._two_col([(_human(k), v, "score_value") for k, v in actor.attributes.items()]))

    def render_derived_attributes(self, actor: Actor, admin: bool = False) -> str:
        stats = dict(actor.derived_statistics_cache)
        for key in DERIVED_KEYS:
            stats.setdefault(key, None)
        pairs = []
        for key, stat in stats.items():
            formula = getattr(stat, "formula_name", key)
            value = getattr(stat, "value", None)
            label = getattr(stat, "label", _human(key))
            pairs.append((label, f"{_value(value)}  Formula: {formula}", "score_value"))
        return self._section("DERIVED ATTRIBUTES", self._two_col(pairs))

    def render_combat(self, actor: Actor, admin: bool = False) -> str:
        data = dict(actor.combat_profile or {})
        pairs = [(_human(k), data.get(k, "future"), "score_value") for k in COMBAT_FIELDS]
        return self._section("COMBAT PROFILE", self._two_col(pairs))

    def render_equipment(self, actor: Actor, admin: bool = False) -> str:
        eq = actor.equipment_profile.get("equipped", actor.equipment_profile) or {}
        profile = self.body_registry.get(getattr(actor, "body_profile_id", "humanoid"))
        rows = []
        if admin:
            rows.append(_line(_field("Body Profile", profile.id, width=70)))
        pairs = []
        for slot in profile.slots:
            if not slot.visible:
                continue
            item = eq.get(slot.id) or eq.get(slot.display_name) or "nothing"
            pairs.append((slot.display_name, item, "equipment_item"))
        rows.extend(self._two_col(pairs))
        return self._section("EQUIPMENT", rows)

    def render_conditions(self, actor: Actor, admin: bool = False) -> str:
        data = dict(actor.condition_profile or {})
        pairs = [(_human(k), data.get(k, "future"), "score_value") for k in CONDITIONS]
        for k, v in data.items():
            if k not in CONDITIONS:
                pairs.append((_human(k), v, "score_value"))
        return self._section("CONDITIONS", self._two_col(pairs))

    def render_resistances(self, actor: Actor, admin: bool = False) -> str:
        data = dict(actor.resistance_profile or {})
        keys = RESISTANCES + [k for k in data if k not in RESISTANCES]
        rows = [_line(f"{semantic('score_label','Type'):<22} {semantic('score_label','Base'):<10} {semantic('score_label','Equipment'):<12} {semantic('score_label','Effects'):<10} {semantic('score_label','Total')}")]
        for key in keys:
            val = data.get(key, {})
            if not isinstance(val, dict):
                val = {"base": val, "equipment": "future", "effects": "future", "total": val}
            rows.append(_line(f"{_human(key):<20} {_value(val.get('base','future')):<10} {_value(val.get('equipment','future')):<12} {_value(val.get('effects','future')):<10} {_value(val.get('total','future'))}"))
        return self._section("RESISTANCES", rows)

    def _grouped_effect_rows(self, effects: Any, groups: list[str]) -> list[str]:
        rows: list[str] = []
        source = effects if isinstance(effects, dict) else {}
        flat = source.get("affects", source)
        for group in groups + [g for g in flat if isinstance(flat.get(g), list) and g not in groups]:
            rows.append(_line(semantic("score_label", _human(group))))
            items = flat.get(group, []) if isinstance(flat, dict) else []
            if isinstance(items, dict):
                items = [dict(v, name=k) if isinstance(v, dict) else {"name": k, "source": v} for k, v in items.items()]
            if not items:
                rows.append(_line("  none")); continue
            rows.append(_line("  Name                 Source        Duration   Remaining  Stacks Category"))
            for item in items:
                if not isinstance(item, dict):
                    item = {"name": item}
                rows.append(_line(f"  {_value(item.get('name')):<20} {_value(item.get('source','future')):<13} {_value(item.get('duration','future')):<10} {_value(item.get('remaining','future')):<10} {_value(item.get('stacks', item.get('stack_count', 1))):<6} {_value(item.get('category', group))}"))
        return rows

    def render_affects(self, actor: Actor, admin: bool = False) -> str:
        return self._section("AFFECTS", self._grouped_effect_rows(actor.effect_container, AFFECT_GROUPS))

    def render_spellup(self, actor: Actor, admin: bool = False) -> str:
        return self._section("SPELLUP", self._grouped_effect_rows(actor.effect_container.get("spellup", {}), SPELLUP_GROUPS))

    def render_progression(self, actor: Actor, admin: bool = False) -> str:
        data = actor.progression_profile or {}
        return self._section("PROGRESSION", self._two_col([(_human(k), data.get(k, "future"), "score_value") for k in PROGRESSION_FIELDS]))

    def render_currencies(self, actor: Actor, admin: bool = False) -> str:
        data = actor.plugin_data.get("currencies", {})
        keys = CURRENCY_FIELDS + [k for k in data if k not in CURRENCY_FIELDS]
        return self._section("CURRENCIES", self._two_col([(_human(k), data.get(k, 0 if k in {"gold", "silver", "copper"} else "future"), "gold" if k in {"gold", "silver", "copper"} else "score_value") for k in keys]))

    def render_relationships(self, actor: Actor, admin: bool = False) -> str:
        data = actor.relationship_profile or {}
        return self._section("RELATIONSHIPS", self._two_col([(_human(k), data.get(k, "future"), "score_value") for k in RELATIONSHIP_FIELDS]))

    def render_simulation(self, actor: Actor, admin: bool = False) -> str:
        data = actor.simulation_profile or {}
        pairs = [(_human(k), data.get(k, "future"), "score_value") for k in SIMULATION_FIELDS]
        if admin:
            pairs.extend([("Need Profile", actor.need_profile or "future", "score_value"), ("Goal Profile", actor.goal_profile or "future", "score_value"), ("Memory Profile", actor.memory_profile or "future", "score_value")])
        return self._section("SIMULATION", self._two_col(pairs))

    def render_diagnostics(self, actor: Actor, admin: bool = False) -> str:
        warnings = []
        if not actor.identity.name or actor.identity.name == "Unnamed":
            warnings.append("Missing identity.name")
        missing = [k for k, v in actor.attributes.items() if v is None]
        if missing:
            warnings.append("Missing base attributes: " + ", ".join(missing))
        data = {"actor_id": actor.actor_id, "actor_type": actor.actor_type, "builder_metadata": actor.builder_metadata, "validation_warnings": warnings or ["none"], "renderer_sections": self.order, "single_renderer": "ActorScoreRenderer", "future_formula_names": {s.formula_name: self.formula_registry.has(s.formula_name) for s in actor.derived_statistics_cache.values()}, "derived_placeholders": list(actor.derived_statistics_cache)}
        return self._section("BUILDER DIAGNOSTICS", self._two_col([(_human(k), v, "score_value") for k, v in data.items()]))

    def render_formulas(self, actor: Actor, admin: bool = False) -> str:
        rows = [_line("Statistic             Formula                  Base       Modifiers       Final")]
        for key, stat in actor.derived_statistics_cache.items():
            formula = getattr(stat, "formula_name", key)
            label = getattr(stat, "label", _human(key))
            rows.append(_line(f"{label:<21} {formula:<24} placeholder placeholder    placeholder"))
        return self._section("FORMULA DEBUG", rows)

    def render_raw(self, actor: Actor, admin: bool = False) -> str:
        text = json.dumps(actor.to_dict(), indent=2, sort_keys=True, default=_json_default)
        return self._section("RAW ACTOR JSON", [_line(line[: BOX_WIDTH - 6]) for line in text.splitlines()])
