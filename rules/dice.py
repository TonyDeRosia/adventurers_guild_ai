"""Dice utility functions for rules subsystems."""

from __future__ import annotations

import random


def roll_die(sides: int) -> int:
    """Roll a single die with `sides` sides."""

    if sides <= 1:
        raise ValueError("sides must be greater than 1")
    return random.randint(1, sides)


def roll_d20(modifier: int = 0) -> tuple[int, int]:
    """Return raw d20 roll and total with modifier."""

    raw = roll_die(20)
    return raw, raw + modifier
