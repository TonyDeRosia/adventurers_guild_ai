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

    def resolve_player_attack(
        self,
        attacker_name: str,
        defender_name: str,
        defender_armor_class: int,
        defender_hp: int,
        base_attack_bonus: int,
        strength: int,
        damage_die: int = 8,
    ) -> AttackResult:
        hit_bonus = base_attack_bonus + (strength // 2)
        base = self.resolve_attack(
            attacker_name=attacker_name,
            attack_bonus=hit_bonus,
            defender_name=defender_name,
            defender_armor_class=defender_armor_class,
            defender_hp=defender_hp,
            damage_die=damage_die,
        )
        if not base.hit:
            return base
        bonus_damage = max(0, strength // 3)
        final_damage = base.damage + bonus_damage
        return AttackResult(
            attacker=base.attacker,
            defender=base.defender,
            hit=base.hit,
            raw_roll=base.raw_roll,
            total_roll=base.total_roll,
            damage=final_damage,
            remaining_hp=max(0, defender_hp - final_damage),
        )

    def resolve_special_ability(
        self,
        attacker_name: str,
        defender_name: str,
        defender_armor_class: int,
        defender_hp: int,
        base_attack_bonus: int,
        intellect: int,
    ) -> AttackResult:
        hit_bonus = base_attack_bonus + intellect
        base = self.resolve_attack(
            attacker_name=attacker_name,
            attack_bonus=hit_bonus,
            defender_name=defender_name,
            defender_armor_class=defender_armor_class,
            defender_hp=defender_hp,
            damage_die=6,
        )
        if not base.hit:
            return base
        ability_damage = base.damage + max(1, intellect // 2)
        return AttackResult(
            attacker=base.attacker,
            defender=base.defender,
            hit=base.hit,
            raw_roll=base.raw_roll,
            total_roll=base.total_roll,
            damage=ability_damage,
            remaining_hp=max(0, defender_hp - ability_damage),
        )

    def resolve_enemy_turn(
        self,
        enemy_name: str,
        enemy_behavior: str,
        enemy_attack_bonus: int,
        enemy_damage_die: int,
        enemy_hp: int,
        enemy_max_hp: int,
        defender_name: str,
        defender_armor_class: int,
        defender_hp: int,
        defender_vitality: int,
        defender_is_defending: bool = False,
    ) -> tuple[AttackResult, dict[str, int | bool]]:
        metadata: dict[str, int | bool] = {"guarded": False, "recoil_damage": 0}
        behavior = enemy_behavior.lower()
        attack_bonus = enemy_attack_bonus
        damage_die = enemy_damage_die

        if behavior == "aggressive":
            attack_bonus += 1
        elif behavior == "reckless":
            attack_bonus += 2
        elif behavior == "defensive" and enemy_hp <= max(1, enemy_max_hp // 2):
            metadata["guarded"] = True
            attack_bonus -= 1

        result = self.resolve_attack(
            attacker_name=enemy_name,
            attack_bonus=attack_bonus,
            defender_name=defender_name,
            defender_armor_class=defender_armor_class,
            defender_hp=defender_hp,
            damage_die=damage_die,
        )

        reduction = 0
        if result.hit and defender_is_defending:
            reduction += 2 + (defender_vitality // 2)
        elif result.hit:
            reduction += defender_vitality // 4

        final_damage = max(0, result.damage - reduction)
        adjusted = AttackResult(
            attacker=result.attacker,
            defender=result.defender,
            hit=result.hit,
            raw_roll=result.raw_roll,
            total_roll=result.total_roll,
            damage=final_damage,
            remaining_hp=max(0, defender_hp - final_damage),
        )

        if behavior == "reckless" and not result.hit:
            metadata["recoil_damage"] = 1

        return adjusted, metadata

    def resolve_flee_attempt(self, agility: int, difficulty: int = 14) -> tuple[bool, int]:
        raw, total = roll_d20(agility)
        return total >= difficulty, raw
