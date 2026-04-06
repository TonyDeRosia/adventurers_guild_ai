"""Combat and damage resolution logic.

Rules are isolated from narration so they can be swapped independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from rules.dice import roll_d20, roll_die


@dataclass
class Enemy:
    """Simple enemy stat block for phase 1 combat."""

    name: str
    hp: int
    armor_class: int
    attack_bonus: int
    damage_die: int = 6


@dataclass
class AttackResult:
    attacker: str
    defender: str
    hit: bool
    raw_roll: int
    total_roll: int
    damage: int
    remaining_hp: int


class CombatEngine:
    """Roll-based combat helpers."""

    def resolve_attack(
        self,
        attacker_name: str,
        attack_bonus: int,
        defender_name: str,
        defender_armor_class: int,
        defender_hp: int,
        damage_die: int = 8,
    ) -> AttackResult:
        raw, total = roll_d20(attack_bonus)
        hit = total >= defender_armor_class
        damage = roll_die(damage_die) if hit else 0
        remaining_hp = max(0, defender_hp - damage)
        return AttackResult(
            attacker=attacker_name,
            defender=defender_name,
            hit=hit,
            raw_roll=raw,
            total_roll=total,
            damage=damage,
            remaining_hp=remaining_hp,
        )
