"""Phase 20B reward formulae and the canonical XP mutation boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

MAX_EXP_GAIN = 1_000_000
MAX_EXP_LOSS = 1_000_000
RARE_KILL_MAX_COUNT = 10
PVP_GLORY_COOLDOWN_SECONDS = 600


def trunc0(value: int | float) -> int:
    """Integer division/conversion that is explicitly toward zero."""
    return int(value)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def npc_base_xp(delta: int) -> int:
    if delta <= -15: return 1
    if delta <= -10: return 3
    if delta <= -8: return 5
    if delta <= -5: return 15
    if delta <= -3: return 40
    return {-2: 60, -1: 90, 0: 120, 1: 150, 2: 180, 3: 220, 4: 260, 5: 300}.get(delta, 350)


def npc_normal_xp(victim_level: int, recipient_level: int, authored_bonus_xp: int, max_gain: int = MAX_EXP_GAIN) -> int:
    return clamp(npc_base_xp(victim_level - recipient_level) + int(authored_bonus_xp), 0, max_gain)


def rare_kill_bonus(normal_xp: int, live_count: int) -> int:
    return max(1, trunc0(normal_xp / 4)) if 1 <= live_count <= RARE_KILL_MAX_COUNT else 0


def pvp_group_xp(victim_exp: int, member_count: int, max_loss: int = MAX_EXP_LOSS) -> tuple[int, int]:
    if member_count < 1: return 0, 0
    total = min(trunc0(victim_exp / 3) + member_count - 1, trunc0(max_loss * 2 / 3))
    return total, max(1, trunc0(total / member_count))


def alignment_after(current: int, victim: int) -> int:
    return current + trunc0((-victim - current) / 16)


def pve_glory(base: int, difference: int) -> int:
    return base if difference <= 3 else max(0, trunc0(base * max(0, 8 - difference) / 5))


def pvp_glory(base: int, difference: int) -> int:
    return base if difference <= 3 else max(0, trunc0(base * max(0, 10 - difference) / 7))


def death_penalty(current_exp: int, level: int, next_threshold: int, max_mortal_level: int, max_loss: int = MAX_EXP_LOSS) -> dict[str, int]:
    tnl = max(0, next_threshold - current_exp)
    if level <= 1 or max_mortal_level <= 1:
        percentage = 1
    else:
        numerator, denominator = level - 1, max_mortal_level - 1
        squared = denominator * denominator
        percentage = clamp(1 + trunc0((9 * numerator * numerator + trunc0(squared / 2)) / squared), 1, 10)
    loss = trunc0((tnl * percentage + 99) / 100)
    return {"tnl": tnl, "percentage": percentage, "loss": min(max_loss, loss)}


class CharacterXPService:
    """The sole XP mutation boundary; multiplier is intentionally applied here once."""
    def __init__(self, *, global_multiplier: float = 1.0, max_gain: int = MAX_EXP_GAIN, max_loss: int = MAX_EXP_LOSS,
                 threshold: Callable[[Any, int], int] | None = None, level_up: Callable[[Any], None] | None = None):
        self.global_multiplier, self.max_gain, self.max_loss = global_multiplier, max_gain, max_loss
        self.threshold, self.level_up = threshold, level_up
    def apply(self, actor: Any, amount: int) -> dict[str, int]:
        before = int(_get(actor, "current_exp", _get(actor, "exp", 0)))
        adjusted = min(self.max_gain, trunc0(amount * self.global_multiplier)) if amount >= 0 else -min(self.max_loss, abs(amount))
        after = max(0, before + adjusted); _set(actor, "current_exp", after); _set(actor, "exp", after)
        gained = 0
        if adjusted > 0 and self.threshold:
            level = int(_get(actor, "level", 1))
            while after >= self.threshold(actor, level + 1):
                level += 1; gained += 1; _set(actor, "level", level)
                if self.level_up: self.level_up(actor)
        return {"before": before, "after": after, "requested": amount, "applied": adjusted, "levels_gained": gained}


def _get(actor: Any, key: str, default: Any = None) -> Any:
    return actor.get(key, default) if isinstance(actor, dict) else getattr(actor, key, default)
def _set(actor: Any, key: str, value: Any) -> None:
    if isinstance(actor, dict): actor[key] = value
    else: setattr(actor, key, value)
