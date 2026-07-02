"""Data-driven Core Game V1 loading, validation, and character helpers."""
from __future__ import annotations

import ast, json, operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CORE_GAME_DIR = Path(__file__).resolve().parents[1] / "data" / "core_game"

class CoreGameError(ValueError):
    """Raised when Core Game content is missing or invalid."""

@dataclass(frozen=True)
class ContentSpec:
    name: str
    path: str
    required: tuple[str, ...]

SPECS = {
    "stats": ContentSpec("Stats", "rules/stats.json", ("primary_stats", "derived_stats", "allocation", "formulas")),
    "races": ContentSpec("Race", "character/races.json", ("id", "name", "description", "stat_bonuses", "traits", "tags")),
    "classes": ContentSpec("Class", "character/classes.json", ("id", "name", "description", "primary_stats", "allowed_armor", "allowed_weapons", "resource_type", "starting_abilities", "starting_items", "level_1_choices", "tags")),
    "backgrounds": ContentSpec("Background", "character/backgrounds.json", ("id", "name", "description", "starting_items", "starting_abilities", "tags")),
    "spells": ContentSpec("Spell", "abilities/spells.json", ("id", "name", "type", "class_tags", "level_requirement", "resource_cost", "cooldown", "target_type", "range", "description", "mechanical_effect", "narrative_guidance", "scaling", "tags")),
    "skills": ContentSpec("Skill", "abilities/skills.json", ("id", "name", "type", "class_tags", "level_requirement", "resource_cost", "cooldown", "target_type", "range", "description", "mechanical_effect", "narrative_guidance", "scaling", "tags")),
    "passives": ContentSpec("Passive", "abilities/passives.json", ("id", "name", "type", "class_tags", "level_requirement", "resource_cost", "cooldown", "target_type", "range", "description", "mechanical_effect", "narrative_guidance", "scaling", "tags")),
    "weapons": ContentSpec("Item", "items/weapons.json", ("id", "name", "type", "slot", "rarity", "value", "weight", "requirements", "stats", "effects", "description", "tags")),
    "armor": ContentSpec("Item", "items/armor.json", ("id", "name", "type", "slot", "rarity", "value", "weight", "requirements", "stats", "effects", "description", "tags")),
    "consumables": ContentSpec("Item", "items/consumables.json", ("id", "name", "type", "slot", "rarity", "value", "weight", "requirements", "stats", "effects", "description", "tags")),
    "tools": ContentSpec("Item", "items/tools.json", ("id", "name", "type", "slot", "rarity", "value", "weight", "requirements", "stats", "effects", "description", "tags")),
    "misc": ContentSpec("Item", "items/misc.json", ("id", "name", "type", "slot", "rarity", "value", "weight", "requirements", "stats", "effects", "description", "tags")),
    "zones": ContentSpec("Zone", "world/zones.json", ("id", "name", "summary", "atmosphere", "npcs", "objects", "exits", "active_hooks", "tags")),
    "factions": ContentSpec("Faction", "world/factions.json", ("id", "name", "description", "tags")),
    "npcs": ContentSpec("NPC template", "world/npcs.json", ("id", "name", "kind", "description", "faction_id", "default_zone", "dialogue_seed", "tags")),
    "quests": ContentSpec("Quest template", "world/quests.json", ("id", "title", "description", "starting_zone", "objectives", "rewards", "tags")),
}

PRIMARY_STATS = ("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv}

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CoreGameError(f"Core Game file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CoreGameError(f"Invalid JSON in {path}: {exc}") from exc

def validate_records(records: Any, spec: ContentSpec) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise CoreGameError(f"{spec.name} content must be a list in {spec.path}.")
    seen, out = set(), []
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise CoreGameError(f"{spec.name} record #{idx} must be an object.")
        missing = [f for f in spec.required if f not in rec]
        if missing:
            raise CoreGameError(f"{spec.name} record #{idx} missing required field(s): {', '.join(missing)}")
        rid = str(rec.get("id") or "").strip()
        if not rid:
            raise CoreGameError(f"{spec.name} record #{idx} has blank id.")
        if rid in seen:
            raise CoreGameError(f"Duplicate {spec.name} id: {rid}")
        seen.add(rid); out.append(rec)
    return out

def load_collection(name: str, base_dir: Path = CORE_GAME_DIR) -> list[dict[str, Any]]:
    spec = SPECS[name]
    return validate_records(_read_json(base_dir / spec.path), spec)

def load_stats(base_dir: Path = CORE_GAME_DIR) -> dict[str, Any]:
    data = _read_json(base_dir / SPECS["stats"].path)
    missing = [f for f in SPECS["stats"].required if f not in data]
    if missing: raise CoreGameError(f"Stats missing required field(s): {', '.join(missing)}")
    return data

def load_core_game(base_dir: Path = CORE_GAME_DIR) -> dict[str, Any]:
    data = {"manifest": _read_json(base_dir / "manifest.json"), "stats": load_stats(base_dir)}
    for name in SPECS:
        if name != "stats": data[name] = load_collection(name, base_dir)
    data["abilities"] = data["spells"] + data["skills"] + data["passives"]
    data["items"] = data["weapons"] + data["armor"] + data["consumables"] + data["tools"] + data["misc"]
    data["world_bible"] = (base_dir / "world" / "world_bible.md").read_text(encoding="utf-8")
    return data

def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in records}

def _eval_expr(expr: str, stats: dict[str, int]) -> int:
    def ev(node):
        if isinstance(node, ast.Expression): return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.Name): return stats.get(node.id, 0)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS: return _OPS[type(node.op)](ev(node.left), ev(node.right))
        raise CoreGameError(f"Unsupported stat formula: {expr}")
    return int(ev(ast.parse(expr, mode="eval")))

def validate_point_allocation(stats: dict[str, int], rules: dict[str, Any] | None = None) -> None:
    rules = rules or load_stats()
    alloc = rules.get("allocation", {})
    total, minv, maxv = int(alloc.get("total_points", 30)), int(alloc.get("min", 3)), int(alloc.get("max_level_1", 10))
    missing = [s for s in PRIMARY_STATS if s not in stats]
    if missing: raise CoreGameError(f"Missing primary stat(s): {', '.join(missing)}")
    for s in PRIMARY_STATS:
        v = int(stats[s])
        if v < minv or v > maxv: raise CoreGameError(f"{s} must be between {minv} and {maxv} at level 1.")
    if sum(int(stats[s]) for s in PRIMARY_STATS) != total: raise CoreGameError(f"Primary stats must total {total} points.")

def calculate_derived_stats(stats: dict[str, int], equipped_armor: int = 0, armor_allows_dex: bool = True, rules: dict[str, Any] | None = None) -> dict[str, int]:
    rules = rules or load_stats(); validate_point_allocation(stats, rules)
    derived = {}
    formulas = rules.get("formulas", {})
    for key in ("HP", "Mana", "Stamina", "Initiative", "Carry Capacity"):
        derived[key] = _eval_expr(str(formulas[key]), stats)
    dex_mod = max(0, (int(stats["Dexterity"]) - 10) // 2) if armor_allows_dex else 0
    derived["Armor"] = int(equipped_armor) + dex_mod
    return derived

def auto_allocate_stats(class_id: str, classes: list[dict[str, Any]] | None = None) -> dict[str, int]:
    stats = dict.fromkeys(PRIMARY_STATS, 3); remaining = 30 - 18
    cls = by_id(classes or load_collection("classes")).get(class_id, {})
    priorities = list(cls.get("primary_stats", [])) + list(PRIMARY_STATS)
    i = 0
    while remaining > 0:
        stat = priorities[i % len(priorities)]
        if stat in stats and stats[stat] < 10: stats[stat] += 1; remaining -= 1
        i += 1
    return stats
