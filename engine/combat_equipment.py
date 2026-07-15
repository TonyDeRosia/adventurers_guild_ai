"""Canonical Builder-driven combat equipment data for Phase 6B."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _num(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class CriticalProfile:
    id: str
    name: str
    multiplier: float = 2.0
    style: str = "normal"
    placeholders: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DamageProfile:
    id: str
    name: str
    damage_types: tuple[str, ...] = ("physical",)
    base_damage: int = 1
    category: str = "physical"
    placeholders: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BuilderAttackProfile:
    id: str
    name: str
    damage_category: str = "physical"
    critical_style: str = "normal"
    verbs: dict[str, str] = field(default_factory=dict)
    attack_messages: dict[str, str] = field(default_factory=dict)
    default_recovery: int = 1
    animation: str = "future"
    future_sound_ids: list[str] = field(default_factory=list)
    future_visual_ids: list[str] = field(default_factory=list)


class CombatContentRegistry:
    """Immutable lookup facade over world-package combat equipment collections."""

    def __init__(self, package: Any | None = None, *, records: dict[str, list[dict[str, Any]]] | None = None) -> None:
        records = records or {}
        get = lambda name: list(records.get(name) or getattr(package, name, []) or [])
        self.weapon_classes = self._index(get("weapon_classes"))
        self.weapon_templates = self._index(get("weapon_templates"))
        self.armor_classes = self._index(get("armor_classes"))
        self.armor_templates = self._index(get("armor_templates"))
        self.attack_profiles = self._index(get("attack_profiles"))
        self.critical_profiles = self._index(get("critical_profiles"))
        self.damage_profiles = self._index(get("damage_profiles"))
        self.natural_weapon_profiles = self._index(get("natural_weapon_profiles"))
        self.material_profiles = self._index(get("material_profiles"))
        self.equipment_sets = self._index(get("equipment_sets"))

    @staticmethod
    def _index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(r.get("id")): dict(r) for r in records if isinstance(r, dict) and r.get("id")}

    def validate(self) -> list[str]:
        errors: list[str] = []
        for wid, weapon in self.weapon_templates.items():
            self._require(wid, weapon, ["weapon_type", "weapon_class", "damage_profile", "attack_profile", "critical_profile", "occupies_slots"], errors, "Weapon")
            self._ref(wid, "weapon_class", weapon.get("weapon_class"), self.weapon_classes, errors)
            self._ref(wid, "damage_profile", weapon.get("damage_profile"), self.damage_profiles, errors)
            self._ref(wid, "attack_profile", weapon.get("attack_profile"), self.attack_profiles, errors)
            self._ref(wid, "critical_profile", weapon.get("critical_profile"), self.critical_profiles, errors)
        for aid, armor in self.armor_templates.items():
            self._require(aid, armor, ["armor_class", "armor_value", "coverage", "material", "occupies_slots"], errors, "Armor")
            self._ref(aid, "armor_class", armor.get("armor_class"), self.armor_classes, errors)
        for nid, natural in self.natural_weapon_profiles.items():
            self._require(nid, natural, ["attack_profile", "damage_profile", "critical_profile", "body_profiles"], errors, "Natural weapon")
            self._ref(nid, "attack_profile", natural.get("attack_profile"), self.attack_profiles, errors)
            self._ref(nid, "damage_profile", natural.get("damage_profile"), self.damage_profiles, errors)
        return errors

    @staticmethod
    def _require(rid: str, rec: dict[str, Any], keys: list[str], errors: list[str], label: str) -> None:
        for key in keys:
            if key not in rec:
                errors.append(f"{label} {rid} missing required field: {key}")

    @staticmethod
    def _ref(rid: str, field: str, value: Any, table: dict[str, dict[str, Any]], errors: list[str]) -> None:
        if value and str(value) not in table:
            errors.append(f"Combat equipment {rid} references missing {field}: {value}")

    def weapon_attack_data(self, weapon: dict[str, Any]) -> dict[str, Any]:
        template = self.weapon_templates.get(str(weapon.get("template_id") or weapon.get("id")), {}) | weapon
        damage = self.damage_profiles.get(str(template.get("damage_profile")), {})
        critical = self.critical_profiles.get(str(template.get("critical_profile")), {})
        attack = self.attack_profiles.get(str(template.get("attack_profile")), {})
        damage_types = template.get("damage_types") or damage.get("damage_types") or [damage.get("damage_type", "physical")]
        return {
            "id": str(attack.get("id") or template.get("attack_profile") or template.get("id", "weapon")),
            "name": str(attack.get("name") or template.get("name", "weapon")),
            "damage_type": str((damage_types or ["physical"])[0]),
            "base_damage": _num(template.get("base_damage", damage.get("base_damage", 1)), 1),
            "speed": max(1, _num(template.get("attack_speed", attack.get("default_recovery", 1)), 1)),
            "reach": _num(template.get("reach", 1), 1),
            "critical_multiplier": float(critical.get("multiplier", template.get("critical_multiplier", 2.0))),
            "weapon": template,
            "attack_profile_record": attack,
            "damage_profile_record": damage,
            "critical_profile_record": critical,
        }

    def natural_attack_data(self, actor: Any) -> dict[str, Any] | None:
        natural_ids = (actor.combat_profile or {}).get("natural_weapon_profile_ids") or []
        body_id = getattr(actor, "body_profile_id", "")
        candidates = [self.natural_weapon_profiles.get(str(i), {}) for i in natural_ids]
        if not candidates:
            candidates = [n for n in self.natural_weapon_profiles.values() if body_id in (n.get("body_profiles") or [])]
        for natural in candidates:
            if natural:
                data = self.weapon_attack_data(natural)
                data["weapon"] = natural
                return data
        # Authored starter-creature fallback: never silently use fists for known non-humanoid creatures.
        name = str(getattr(getattr(actor, "identity", None), "name", "") or "").lower()
        table = {"giant wood spider": ("spider_fangs", "fangs", "poison", 4), "forest wolf": ("wolf_bite", "bite", "pierce", 4), "dire forest wolf": ("dire_wolf_fangs", "fangs", "pierce", 7), "emberwood fox": ("fox_bite", "bite", "pierce", 2), "wild boar": ("boar_gore", "gore", "pierce", 5), "ashback bear": ("bear_claws", "claws", "slash", 8), "emberwood stag": ("stag_gore", "gore", "pierce", 3)}
        if name in table:
            nid, noun, dtype, base = table[name]
            return {"id": nid, "name": noun, "damage_type": dtype, "base_damage": base, "speed": 1, "reach": 1, "critical_multiplier": 2.0, "weapon": {"id": nid, "name": noun}, "attack_profile_record": {"id": noun, "name": noun}, "damage_profile_record": {"damage_types": [dtype], "base_damage": base}, "critical_profile_record": {"multiplier": 2.0}}
        return None

    def armor_value(self, equipment: dict[str, Any]) -> int:
        total = 0
        for item in equipment.values():
            if isinstance(item, dict):
                template = self.armor_templates.get(str(item.get("template_id") or item.get("id")), {}) | item
                total += _num(template.get("armor_value"), 0)
        return total
