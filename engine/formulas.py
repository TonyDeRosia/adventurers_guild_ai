"""Deterministic Formula Engine and modifier pipeline for Smart MUD.

This module is architecture-only: formulas are registered and traced, but no
combat, class, skill, spell, equipment, or balancing math is hardcoded here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from time import perf_counter
import ast, math
from typing import Any
from uuid import uuid4


class FormulaOperation(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    OVERRIDE = "override"
    PERCENTAGE_INCREASE = "percentage_increase"
    PERCENTAGE_REDUCTION = "percentage_reduction"
    CLAMP = "clamp"
    CUSTOM = "custom"


class StackingRule(StrEnum):
    UNIQUE = "unique"
    REPLACE = "replace"
    REFRESH_DURATION = "refresh_duration"
    STACK = "stack"
    HIGHEST_ONLY = "highest_only"
    LOWEST_ONLY = "lowest_only"
    BUILDER_CUSTOM = "builder_custom"


SUPPORTED_STATS = {
    "attack_rating", "armor", "critical", "critical_chance", "critical_avoidance",
    "parry", "block", "dodge", "movement_speed", "cast_speed", "casting_speed",
    "threat", "carry_capacity", "carry_weight", "spell_power", "healing_power",
    "initiative", "mana_regeneration", "movement_regeneration", "defense_rating",
    "hit_bonus", "damage_bonus", "reach", "range", "accuracy", "attack_power", "weapon_damage", "magic_defense", "critical_damage", "armor_penetration", "resistances", "attack_speed", "recovery_speed",
}
RESERVED_FORMULA_IDS = {"formula", "modifier", "engine", "registry", "trace"}


@dataclass
class FormulaDefinition:
    id: str
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    dependencies: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    plugin_owner: str | None = None
    builder_owner: str | None = None
    world_overrides: dict[str, Any] = field(default_factory=dict)
    plugin_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.id.replace("_", " ").title()


@dataclass
class Modifier:
    id: str
    source: str
    category: str
    priority: int
    stacking_rule: str
    duration: Any
    target_stat: str
    operation: str
    value: Any
    conditions: dict[str, Any] = field(default_factory=dict)
    plugin_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, target_stat: str, operation: str, value: Any, source: str = "builder", **kw: Any) -> "Modifier":
        return cls(id=kw.pop("id", f"mod_{uuid4().hex}"), source=source, category=kw.pop("category", "custom"), priority=kw.pop("priority", 100), stacking_rule=kw.pop("stacking_rule", StackingRule.STACK.value), duration=kw.pop("duration", None), target_stat=target_stat, operation=operation, value=value, **kw)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool: return not self.errors


class FormulaRegistry:
    def __init__(self) -> None:
        self.formulas: dict[str, FormulaDefinition] = {}

    def register(self, formula: FormulaDefinition, replace: bool = False) -> None:
        if formula.id in self.formulas and not replace:
            raise ValueError(f"Duplicate formula ID: {formula.id}")
        self.formulas[formula.id] = formula

    def replace(self, formula: FormulaDefinition) -> None:
        self.register(formula, replace=True)

    def get(self, formula_id: str) -> FormulaDefinition | None:
        return self.formulas.get(formula_id)

    def metadata(self) -> list[dict[str, Any]]:
        return [asdict(v) for v in sorted(self.formulas.values(), key=lambda f: f.id)]

    @classmethod
    def default(cls) -> "FormulaRegistry":
        reg = cls()
        for stat in sorted(SUPPORTED_STATS):
            reg.register(FormulaDefinition(id=stat, description="Placeholder Builder-overridable formula; no gameplay math is hardcoded.", inputs=[], outputs=[stat], validation={"placeholder": True}))
        for fid in ["shop_buy_price_v1", "shop_sell_price_v1", "service_price_v1", "repair_price_v1", "currency_conversion_v1"]:
            reg.register(FormulaDefinition(id=fid, description="Phase 7B conservative economy formula placeholder; EconomyService records the input/output trace and never executes arbitrary Python.", inputs=["quantity", "item_base_value", "service_base_price"], outputs=["price"], validation={"phase7b": True}), replace=True)
        return reg

    def validate(self) -> ValidationResult:
        result = ValidationResult(); versions: dict[tuple[str, str | None], str] = {}
        for fid, formula in self.formulas.items():
            if fid in RESERVED_FORMULA_IDS: result.errors.append(f"reserved formula id: {fid}")
            for dep in formula.dependencies:
                if dep not in self.formulas: result.errors.append(f"formula {fid} missing dependency {dep}")
            key = (fid, formula.plugin_owner)
            if key in versions and versions[key] != formula.version: result.errors.append(f"version conflict for {fid}")
            versions[key] = formula.version
        for node in self.formulas:
            self._visit(node, [], result)
        return result

    def _visit(self, node: str, stack: list[str], result: ValidationResult) -> None:
        if node in stack:
            result.errors.append("circular formula dependency: " + " -> ".join(stack + [node])); return
        f = self.formulas.get(node)
        if f:
            for dep in f.dependencies: self._visit(dep, stack + [node], result)


class ModifierRegistry:
    def __init__(self) -> None:
        self.modifiers: dict[str, Modifier] = {}
        self.modifier_types = {op.value for op in FormulaOperation}

    def register(self, modifier: Modifier) -> None:
        self.modifiers[modifier.id] = modifier

    def for_stat(self, stat: str) -> list[Modifier]:
        return sorted([m for m in self.modifiers.values() if m.target_stat == stat], key=lambda m: (m.priority, m.id))

    def validate(self, known_stats: set[str] | None = None) -> ValidationResult:
        result = ValidationResult(); known = known_stats or SUPPORTED_STATS
        for m in self.modifiers.values():
            if m.operation not in self.modifier_types: result.errors.append(f"modifier {m.id} invalid operation {m.operation}")
            if m.target_stat not in known: result.warnings.append(f"modifier {m.id} unknown target stat {m.target_stat}")
            if m.stacking_rule not in {s.value for s in StackingRule}: result.errors.append(f"modifier {m.id} invalid stacking rule {m.stacking_rule}")
        return result

    def stacked_for_stat(self, stat: str) -> list[Modifier]:
        grouped: dict[tuple[str, str], list[Modifier]] = {}
        output: list[Modifier] = []
        for m in self.for_stat(stat):
            if m.stacking_rule == StackingRule.STACK.value: output.append(m)
            else: grouped.setdefault((m.source, m.category), []).append(m)
        for mods in grouped.values():
            rule = mods[-1].stacking_rule
            if rule in {StackingRule.UNIQUE.value, StackingRule.REPLACE.value, StackingRule.REFRESH_DURATION.value}: output.append(mods[-1])
            elif rule == StackingRule.HIGHEST_ONLY.value: output.append(max(mods, key=lambda x: x.value if isinstance(x.value, (int,float)) else 0))
            elif rule == StackingRule.LOWEST_ONLY.value: output.append(min(mods, key=lambda x: x.value if isinstance(x.value, (int,float)) else 0))
            elif rule == StackingRule.BUILDER_CUSTOM.value: output.append(mods[-1])
        return sorted(output, key=lambda m: (m.priority, m.id))


@dataclass
class FormulaResult:
    final_value: Any
    formula_name: str
    modifier_list: list[dict[str, Any]]
    calculation_trace: list[dict[str, Any]]
    execution_time: float
    diagnostic_metadata: dict[str, Any]


class FormulaEngine:
    def __init__(self, formulas: FormulaRegistry | None = None, modifiers: ModifierRegistry | None = None) -> None:
        self.formulas = formulas or FormulaRegistry.default(); self.modifiers = modifiers or ModifierRegistry()
        self.generation = 0

    def invalidate(self) -> None: self.generation += 1

    def calculate(self, actor: Any, stat: str, base_value: Any = 0, variables: dict[str, Any] | None = None) -> FormulaResult:
        start = perf_counter(); formula_id = self._formula_for(actor, stat); formula = self.formulas.get(formula_id)
        trace = [{"step": "formula_lookup", "stat": stat, "formula_id": formula_id, "found": bool(formula)}, {"step": "base_value", "value": base_value}]
        value = base_value
        applied = []
        for mod in self.modifiers.stacked_for_stat(stat):
            before = value; value = self._apply(value, mod); applied.append(asdict(mod)); trace.append({"step": "modifier", "modifier_id": mod.id, "operation": mod.operation, "value": mod.value, "before": before, "after": value})
        return FormulaResult(value, formula_id, applied, trace, perf_counter() - start, {"engine_generation": self.generation, "formula_metadata": asdict(formula) if formula else None, "variables": variables or {}})


    def evaluate_expression(self, formula_id: str, expression: str, variables: dict[str, Any] | None = None, *, base_value: Any = 0) -> FormulaResult:
        """Evaluate a Builder-authored arithmetic expression through FormulaEngine authority.

        This is the one safe expression path used by canonical character stats;
        it accepts numeric variables, arithmetic, comparisons, boolean operators,
        ternary expressions, and a tiny deterministic function set. Unknown
        variables resolve to 0 so older formula drafts remain forward compatible.
        """
        start = perf_counter(); vars = dict(variables or {}); vars.setdefault("base", base_value)
        trace = [{"step":"expression_lookup","formula_id":formula_id,"expression":expression},{"step":"variables","variables":dict(vars)}]
        value = self._safe_eval_expression(expression or "0", vars)
        return FormulaResult(value, formula_id, [], trace + [{"step":"expression_result","value":value}], perf_counter() - start, {"engine_generation": self.generation, "variables": vars})

    _EXPR_FUNCS = {"min": min, "max": max, "floor": math.floor, "ceil": math.ceil, "round": round, "abs": abs, "clamp": lambda x, a, b: max(a, min(x, b))}
    _EXPR_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.IfExp, ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.BoolOp, ast.And, ast.Or, ast.Call)

    def _safe_eval_expression(self, expression: str, variables: dict[str, Any]) -> float:
        tree = ast.parse(expression or "0", mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, self._EXPR_NODES): raise ValueError(f"unsafe formula node: {type(node).__name__}")
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in self._EXPR_FUNCS): raise ValueError("unsupported formula function")
            if isinstance(node, ast.Name) and node.id not in self._EXPR_FUNCS and node.id not in variables: variables[node.id] = 0
        return float(eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}, **self._EXPR_FUNCS}, variables))

    def _formula_for(self, actor: Any, stat: str) -> str:
        cache = getattr(actor, "derived_statistics_cache", {}) or {}
        entry = cache.get(stat) if isinstance(cache, dict) else None
        return getattr(entry, "formula_name", None) or (entry.get("formula_name") if isinstance(entry, dict) else None) or stat

    def _apply(self, current: Any, mod: Modifier) -> Any:
        if not isinstance(current, (int, float)) or not isinstance(mod.value, (int, float, list, tuple)): return current
        op = mod.operation; val = mod.value
        if op == "add": return current + val
        if op == "subtract": return current - val
        if op == "multiply": return current * val
        if op == "divide": return current / val if val else current
        if op == "minimum": return min(current, val)
        if op == "maximum": return max(current, val)
        if op == "override": return val
        if op == "percentage_increase": return current * (1 + val / 100)
        if op == "percentage_reduction": return current * (1 - val / 100)
        if op == "clamp" and isinstance(val, (list, tuple)) and len(val) == 2: return max(val[0], min(current, val[1]))
        return current
