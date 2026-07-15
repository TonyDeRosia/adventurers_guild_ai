"""Canonical player-facing health condition bands for Smart MUD."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ConditionBand:
    key: str
    label: str
    transition: str

BANDS = (
    (0.00, ConditionBand("dead", "dead", "is dead.")),
    (0.10, ConditionBand("incapacitated", "incapacitated", "collapses.")),
    (0.20, ConditionBand("near_collapse", "near collapse", "is barely standing.")),
    (0.35, ConditionBand("seriously_injured", "seriously injured", "is seriously injured.")),
    (0.50, ConditionBand("badly_wounded", "badly wounded", "is badly injured.")),
    (0.70, ConditionBand("wounded", "wounded", "looks wounded.")),
    (0.85, ConditionBand("lightly_wounded", "lightly wounded", "is lightly wounded.")),
    (0.95, ConditionBand("barely_scratched", "barely scratched", "is barely scratched.")),
    (1.01, ConditionBand("unharmed", "unharmed", "looks unharmed.")),
)

def _num(value: Any, default: int = 0) -> int:
    try: return int(float(value))
    except (TypeError, ValueError): return default

def health_values(subject: Any) -> tuple[int, int]:
    if subject is None: return (0, 1)
    if isinstance(subject, dict):
        st = subject.get("state") if isinstance(subject.get("state"), dict) else {}
        hp = subject.get("current_health", st.get("current_health", st.get("health")))
        maxhp = subject.get("maximum_health", st.get("maximum_health", st.get("max_health")))
    else:
        res = getattr(subject, "resources", subject)
        hp = getattr(res, "health", getattr(subject, "hp", 0))
        maxhp = getattr(res, "maximum_health", getattr(subject, "max_hp", hp or 1))
    return max(0, _num(hp, 0)), max(1, _num(maxhp, hp or 1))

def condition_band(subject: Any) -> ConditionBand:
    hp, maxhp = health_values(subject)
    if hp <= 0: return BANDS[0][1]
    pct = hp / maxhp
    for limit, band in BANDS[1:]:
        if pct < limit: return band
    return BANDS[-1][1]

def condition_label(subject: Any) -> str:
    return condition_band(subject).label

def condition_key(subject: Any) -> str:
    return condition_band(subject).key

def transition_text(name: str, subject: Any) -> str:
    band = condition_band(subject)
    return f"{name} {band.transition}"
