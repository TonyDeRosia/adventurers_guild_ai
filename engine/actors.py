"""Permanent Smart MUD Actor architecture foundation.

This module is intentionally data-first.  It does not implement combat,
formulas, skills, spells, AI decisions, classes, races, or equipment bonuses.
Every living thing can own this same Actor shape so future systems extend one
architecture instead of creating separate player/NPC/mob combat models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from engine.formulas import FormulaEngine, FormulaResult


PRIMARY_ATTRIBUTE_DEFAULTS: dict[str, int] = {
    "strength": 10,
    "dexterity": 10,
    "constitution": 10,
    "intelligence": 10,
    "wisdom": 10,
    "charisma": 10,
}

DERIVED_STAT_FORMULAS: dict[str, str] = {
    "attack_rating": "attack_rating",
    "defense_rating": "defense_rating",
    "armor": "armor",
    "critical": "critical",
    "critical_avoidance": "critical_avoidance",
    "parry": "parry",
    "block": "block",
    "dodge": "dodge",
    "initiative": "initiative",
    "threat": "threat",
    "spell_power": "spell_power",
    "healing_power": "healing_power",
    "hit_bonus": "hit_bonus",
    "damage_bonus": "damage_bonus",
    "movement_speed": "movement_speed",
    "casting_speed": "casting_speed",
    "carry_weight": "carry_weight",
    "carry_capacity": "carry_capacity",
    "reach": "reach",
    "range": "range",
}


@dataclass
class FormulaDefinition:
    name: str
    expression: str = ""
    source: str = "placeholder"
    description: str = "Future Builder-overridable formula placeholder."


@dataclass
class FormulaRegistry:
    formulas: dict[str, FormulaDefinition] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "FormulaRegistry":
        registry = cls()
        for name in sorted(set(DERIVED_STAT_FORMULAS.values()) | {"mana_regeneration", "movement_regeneration"}):
            registry.register(name)
        return registry

    def register(self, name: str, expression: str = "", source: str = "placeholder") -> None:
        self.formulas[name] = FormulaDefinition(name=name, expression=expression, source=source)

    def has(self, name: str) -> bool:
        return name in self.formulas

    def to_dict(self) -> dict[str, Any]:
        return {name: asdict(defn) for name, defn in self.formulas.items()}


@dataclass
class ActorIdentity:
    name: str = "Unnamed"
    title: str = ""
    description: str = ""
    race: str = "Unknown"
    class_placeholder: str = "None"
    profession_placeholder: str = "None"
    guild: str = "None"
    clan: str = "None"
    religion: str = "None"
    alignment: str = "Neutral"
    gender: str = "Unspecified"
    age: int | None = None
    height: str = "Unknown"
    weight: str = "Unknown"
    languages: list[str] = field(default_factory=lambda: ["Common"])
    speaking_language: str = "Common"
    position: str = "Standing"
    current_location: str = "Unknown"
    current_zone: str = "Unknown"
    current_area: str = "Unknown"
    current_world: str = "Unknown"


@dataclass
class ActorResources:
    health: int = 100
    maximum_health: int = 100
    mana: int = 50
    maximum_mana: int = 50
    movement: int = 100
    maximum_movement: int = 100
    stamina: int = 100
    maximum_stamina: int = 100
    hunger: int = 0
    thirst: int = 0
    fatigue: int = 0
    drunkenness: int = 0
    warmth: str = "placeholder"
    body_temperature: str = "placeholder"
    corruption: str = "placeholder"
    sanity: str = "placeholder"
    oxygen: str = "placeholder"


@dataclass
class DerivedStatistic:
    key: str
    label: str
    formula_name: str
    value: Any = None
    status: str = "placeholder"


@dataclass
class Actor:
    actor_id: str
    actor_type: str = "actor"
    identity: ActorIdentity = field(default_factory=ActorIdentity)
    resources: ActorResources = field(default_factory=ActorResources)
    attributes: dict[str, int | None] = field(default_factory=lambda: dict(PRIMARY_ATTRIBUTE_DEFAULTS))
    combat_profile: dict[str, Any] = field(default_factory=lambda: {"aggression": "never", "attack": "none", "flee": "immediate", "combat_profile": "Civilian"})
    body_profile_id: str = "humanoid"
    lifecycle_state: str = "alive"
    lifecycle_profile: dict[str, Any] = field(default_factory=dict)
    equipment_profile: dict[str, Any] = field(default_factory=dict)
    resistance_profile: dict[str, Any] = field(default_factory=dict)
    condition_profile: dict[str, Any] = field(default_factory=dict)
    relationship_profile: dict[str, Any] = field(default_factory=dict)
    need_profile: dict[str, Any] = field(default_factory=dict)
    goal_profile: dict[str, Any] = field(default_factory=dict)
    memory_profile: dict[str, Any] = field(default_factory=dict)
    simulation_profile: dict[str, Any] = field(default_factory=dict)
    progression_profile: dict[str, Any] = field(default_factory=lambda: {"level": 1, "experience": 0})
    effect_container: dict[str, Any] = field(default_factory=dict)
    derived_statistics_cache: dict[str, DerivedStatistic] = field(default_factory=dict)
    builder_metadata: dict[str, Any] = field(default_factory=dict)
    plugin_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, actor_id: str, name: str, actor_type: str = "actor", **overrides: Any) -> "Actor":
        actor = cls(actor_id=actor_id, actor_type=actor_type)
        actor.identity.name = name
        actor.derived_statistics_cache = default_derived_statistics()
        for key, value in overrides.items():
            if hasattr(actor, key):
                setattr(actor, key, value)
        return actor

    def get_derived_value(self, stat: str, engine: FormulaEngine | None = None, base_value: Any = 0, variables: dict[str, Any] | None = None) -> FormulaResult:
        """Resolve a derived statistic exclusively through the Formula Engine."""
        return (engine or FormulaEngine()).calculate(self, stat, base_value=base_value, variables=variables)

    def invalidate_derived_statistics(self) -> None:
        """Compatibility hook: derived values are not permanently cached in Phase 5D."""
        for stat in self.derived_statistics_cache.values():
            stat.value = None
            stat.status = "invalidated"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Actor":
        identity = ActorIdentity(**data.get("identity", {}))
        resources = ActorResources(**data.get("resources", {}))
        raw_derived = data.get("derived_statistics_cache", {}) or {}
        derived = {k: (v if isinstance(v, DerivedStatistic) else DerivedStatistic(**v)) for k, v in raw_derived.items()}
        return cls(identity=identity, resources=resources, derived_statistics_cache=derived, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k not in {"identity", "resources", "derived_statistics_cache"}})


def default_derived_statistics(extra: dict[str, str] | None = None) -> dict[str, DerivedStatistic]:
    stats = dict(DERIVED_STAT_FORMULAS)
    stats.update(extra or {})
    return {key: DerivedStatistic(key=key, label=key.replace("_", " ").title(), formula_name=formula) for key, formula in stats.items()}


def actor_from_runtime_character(character: Any, world_id: str = "") -> Actor:
    actor_data = getattr(character, "actor_data", None)
    if isinstance(actor_data, dict) and actor_data.get("actor_id"):
        actor = Actor.from_dict(actor_data)
    else:
        actor = Actor.create(getattr(character, "id", "actor"), getattr(character, "name", "Unnamed"), "player")
    actor.identity.name = getattr(character, "name", actor.identity.name)
    actor.identity.current_location = getattr(character, "room_id", "") or actor.identity.current_location
    actor.identity.current_world = world_id or actor.identity.current_world
    actor.resources.health = getattr(character, "hp", actor.resources.health)
    actor.resources.maximum_health = getattr(character, "max_hp", actor.resources.maximum_health)
    actor.resources.mana = getattr(character, "mana", actor.resources.mana)
    actor.resources.maximum_mana = getattr(character, "max_mana", actor.resources.maximum_mana)
    actor.resources.stamina = getattr(character, "stamina", actor.resources.stamina)
    actor.resources.maximum_stamina = getattr(character, "max_stamina", actor.resources.maximum_stamina)
    actor.progression_profile.update({"level": getattr(character, "level", 1), "experience": getattr(character, "xp", 0)})
    actor.equipment_profile.setdefault("equipped", getattr(character, "equipment", {}) or {})
    actor.effect_container.setdefault("affects", getattr(character, "affects", {}) or {})
    actor.builder_metadata.setdefault("role", getattr(character, "role", "player"))
    actor.builder_metadata.setdefault("account_role", getattr(character, "account_role", "player"))
    actor.plugin_data.setdefault("currencies", {"gold": getattr(character, "gold", 0)})
    if not actor.derived_statistics_cache:
        actor.derived_statistics_cache = default_derived_statistics()
    return actor
