"""Typed performance counter reset/validation helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CounterDefinition:
    key: str
    value_type: type
    default_factory: Callable[[], Any]
    category: str = "runtime"
    reset_policy: str = "reset"  # reset|preserve|gauge
    classification: str = "cumulative"  # cumulative|gauge|mapping|history
    description: str = ""

def _default_zero() -> int: return 0
def _default_float() -> float: return 0.0
def _default_dict() -> dict: return {}
def _default_list() -> list: return []

COUNTER_DEFINITIONS: dict[str, CounterDefinition] = {}

def register_counter(key: str, value_type: type = int, *, default_factory: Callable[[], Any] | None = None, category: str = "runtime", reset_policy: str = "reset", classification: str = "cumulative", description: str = "") -> CounterDefinition:
    if default_factory is None:
        default_factory = _default_dict if value_type is dict else _default_list if value_type is list else _default_float if value_type is float else _default_zero
    definition = CounterDefinition(key, value_type, default_factory, category, reset_policy, classification, description)
    COUNTER_DEFINITIONS[key] = definition
    return definition

def ensure_counter_definitions(counters: dict[str, Any] | None = None) -> dict[str, CounterDefinition]:
    keys = set(counters or {}) | {
        "combat_sql_round_history_insert", "combat_sql_action_queue_insert", "combat_sql_action_queue_update",
        "combat_validation_rejection_by_reason", "violence_profile_sections", "violence_profile_last_sections",
    }
    for key in sorted(keys):
        if key in COUNTER_DEFINITIONS:
            continue
        val = (counters or {}).get(key, 0)
        category = key.split('_',1)[0] if '_' in key else 'runtime'
        if key in {"combat_sql_round_history_insert", "combat_sql_action_queue_insert", "combat_sql_action_queue_update"}:
            register_counter(key, int, category="combat_sql", classification="cumulative", description=f"Combat SQL write counter {key}.")
        elif key in PROFILE_MAP_COUNTERS:
            register_counter(key, dict, category="combat", classification="mapping", description=f"Violence profiler mapping counter {key}.")
        elif key in PRESERVED_KEYS or key.startswith(PRESERVED_PREFIXES):
            register_counter(key, type(val) if val is not None else object, default_factory=lambda v=val: v, category=category, reset_policy="preserve", classification="gauge", description=f"Preserved runtime object/configuration counter {key}.")
        elif key in REASON_MAP_COUNTERS or key.endswith('_by_reason') or isinstance(val, dict):
            register_counter(key, dict, category=category, classification="mapping", description=f"Mapping counter {key}.")
        elif 'history' in key or 'recent' in key or isinstance(val, (list,set,deque)):
            register_counter(key, type(val) if isinstance(val,(set,deque)) else list, default_factory=(lambda v=val: deque(maxlen=v.maxlen) if isinstance(v, deque) else set() if isinstance(v,set) else []), category=category, classification="history", description=f"History counter {key}.")
        elif isinstance(val, float) or key.endswith(('_seconds','_duration','_duration_s')):
            register_counter(key, float, category=category, description=f"Floating point counter {key}.")
        else:
            register_counter(key, int, category=category, classification="gauge" if key.endswith('_active') or key.endswith('_backlog') or key.startswith('last_') else "cumulative", description=f"Integer counter {key}.")
    return COUNTER_DEFINITIONS

def make_initial_counters(keys: list[str]) -> dict[str, Any]:
    counters = {k: 0 for k in keys}
    ensure_counter_definitions(counters)
    for k, d in COUNTER_DEFINITIONS.items():
        counters.setdefault(k, d.default_factory())
    return counters

def increment_counter(counters: dict[str, Any], key: str, amount: int = 1) -> None:
    ensure_counter_definitions(counters)
    if key not in COUNTER_DEFINITIONS:
        raise KeyError(f"Unregistered performance counter: {key}")
    counters[key] = counters.get(key, COUNTER_DEFINITIONS[key].default_factory()) + amount

def schema_rows(counters: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_counter_definitions(counters)
    rows=[]
    for k,d in sorted(COUNTER_DEFINITIONS.items()):
        v=counters.get(k, d.default_factory())
        rows.append({"key":k,"type":d.value_type.__name__,"category":d.category,"reset_policy":d.reset_policy,"classification":d.classification,"current_type":type(v).__name__,"valid":isinstance(v,d.value_type) if d.value_type is not object else True})
    return rows

def validate_all_performance_counter_schema(counters: dict[str, Any]) -> list[str]:
    ensure_counter_definitions(counters)
    errors=[]
    for k in counters:
        if k not in COUNTER_DEFINITIONS:
            errors.append(f"{k}: unregistered")
    for k,d in COUNTER_DEFINITIONS.items():
        v=counters.get(k, d.default_factory())
        if d.value_type is not object and not isinstance(v, d.value_type):
            errors.append(f"{k}: expected {d.value_type.__name__}, got {type(v).__name__}")
    return errors

REASON_MAP_COUNTERS = {"combat_validation_rejection_by_reason"}
PROFILE_MAP_COUNTERS = {"violence_profile_sections", "violence_profile_last_sections"}
PRESERVED_PREFIXES = ("scheduler_",)
PRESERVED_KEYS = {"pulse_config", "runtime_scheduler_task", "runtime_scheduler_thread"}


def _typed_default_for(key: str, current: Any) -> Any:
    if key in PRESERVED_KEYS or key.startswith(PRESERVED_PREFIXES):
        return current
    if key in REASON_MAP_COUNTERS or key.endswith("_by_reason"):
        return {}
    if key in PROFILE_MAP_COUNTERS or "profile" in key and isinstance(current, dict):
        return {}
    if "history" in key or "recent" in key:
        if isinstance(current, deque):
            return deque(maxlen=current.maxlen)
        if isinstance(current, list):
            return []
        if isinstance(current, set):
            return set()
    if key.endswith("_seconds") or key.endswith("_duration") or key.endswith("_duration_s"):
        return 0.0
    if key.endswith("_ms") or key.endswith("_max_ms") or key.startswith("max_") or "_max_" in key:
        return 0
    if isinstance(current, float):
        return 0.0
    if isinstance(current, int) and not isinstance(current, bool):
        return 0
    if isinstance(current, dict):
        return {}
    if isinstance(current, list):
        return []
    if isinstance(current, set):
        return set()
    if isinstance(current, deque):
        return deque(maxlen=current.maxlen)
    return current


def validate_performance_counter_schema(counters: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, invalid_key) without mutating counters."""
    errors = validate_all_performance_counter_schema(counters)
    if errors:
        return False, errors[0].split(":", 1)[0]
    return True, ""


def reset_performance_counters(runtime: Any) -> tuple[bool, str]:
    """Reset counters with typed defaults and recompute live gauges atomically."""
    counters = getattr(runtime, "performance_counters", None)
    if not isinstance(counters, dict):
        return False, "performance_counters"
    ensure_counter_definitions(counters)
    ok, invalid = validate_performance_counter_schema(counters)
    if not ok:
        return False, invalid
    new_values = {}
    for key, definition in COUNTER_DEFINITIONS.items():
        current = counters.get(key, definition.default_factory())
        new_values[key] = current if definition.reset_policy == "preserve" else _typed_default_for(key, current)
    for key in sorted(REASON_MAP_COUNTERS | PROFILE_MAP_COUNTERS):
        new_values.setdefault(key, {})
    cr = getattr(runtime, "combat_runtime", None)
    if cr is not None:
        active = [e for e in getattr(cr, "resident_encounters", {}).values() if getattr(e, "status", "") == "active"]
        new_values["combat_encounters_active"] = len(active)
    ok, invalid = validate_performance_counter_schema(new_values)
    if not ok:
        return False, invalid
    counters.clear()
    counters.update(new_values)
    return True, ""
