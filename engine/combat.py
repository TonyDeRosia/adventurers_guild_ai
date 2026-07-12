"""Deterministic data-driven combat foundation for Smart MUD.

This is the canonical Smart MUD single-attack resolver. Encounter lifecycle,
rounds, persistence, command routing, and runtime state synchronization belong
to engine.combat_runtime.CombatRuntimeService.

Combat is Actor + equipment/effects + Formula Engine + lifecycle handoff.  This
module intentionally contains no AI, spellcasting, skills, PvP policy, loot, or
Builder mutation logic.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from engine.actors import Actor
from engine.formulas import FormulaEngine
from engine.combat_equipment import CombatContentRegistry
from engine.phase5f import ActorLifecycleManager, BodyProfileRegistry
from engine.conditions import condition_key


class CombatState(StrEnum):
    IDLE = "idle"; ENGAGING = "engaging"; IN_COMBAT = "in_combat"; ATTACKING = "attacking"; RECOVERING = "recovering"
    FLEEING = "fleeing"; STUNNED = "stunned"; SLEEPING = "sleeping"; UNCONSCIOUS = "unconscious"; INCAPACITATED = "incapacitated"; DEAD = "dead"


DAMAGE_TYPES = ("physical","slash","pierce","blunt","fire","cold","lightning","poison","disease","acid","holy","shadow","arcane","psychic","true")


@dataclass(frozen=True)
class DamageTypeRegistry:
    types: tuple[str, ...] = DAMAGE_TYPES
    builder_types: tuple[str, ...] = ()
    def has(self, damage_type: str) -> bool: return damage_type in set(self.types) | set(self.builder_types)


@dataclass
class AttackProfile:
    id: str = "unarmed"
    name: str = "unarmed strike"
    damage_type: str = "blunt"
    base_damage: int = 1
    speed: int = 1
    reach: int = 1
    critical_multiplier: float = 2.0
    source: str = "unarmed"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DamageEvent:
    attacker_id: str; defender_id: str; weapon: dict[str, Any]; attack_profile: dict[str, Any]
    damage_type: str; base_damage: int; critical: bool; mitigation: int; final_damage: int; timestamp: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CombatResult:
    hit: bool; damage_event: DamageEvent | None; attacker_state: str; defender_state: str
    messages: dict[str, str]; trace: list[dict[str, Any]]; death_handoff: dict[str, Any] | None = None


class DeterministicRoller:
    def __init__(self, seed: str = "smartmud") -> None: self.seed = str(seed)
    def roll_percent(self, *parts: Any) -> int:
        blob = "|".join([self.seed, *(str(p) for p in parts)]).encode()
        return int(hashlib.sha256(blob).hexdigest()[:8], 16) % 100 + 1


def _num(value: Any, default: int = 0) -> int:
    try: return int(float(value))
    except (TypeError, ValueError): return default


def apply_damage(actor: Actor, amount: int, *, source: str = "combat", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    before = _num(actor.resources.health); final = max(0, before - max(0, int(amount)))
    actor.resources.health = final
    return {"resource":"health","operation":"damage","before":before,"amount":max(0,int(amount)),"after":final,"source":source,"metadata":metadata or {}}


def apply_healing(actor: Actor, amount: int, *, source: str = "combat", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    before = _num(actor.resources.health); final = min(_num(actor.resources.maximum_health, before), before + max(0, int(amount)))
    actor.resources.health = final
    return {"resource":"health","operation":"healing","before":before,"amount":max(0,int(amount)),"after":final,"source":source,"metadata":metadata or {}}


def modify_resource(actor: Actor, resource: str, delta: int, *, source: str = "combat", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    before = _num(getattr(actor.resources, resource), 0); maximum = _num(getattr(actor.resources, f"maximum_{resource}", before), before)
    after = max(0, min(maximum, before + int(delta))); setattr(actor.resources, resource, after)
    return {"resource":resource,"operation":"modify","before":before,"delta":int(delta),"after":after,"source":source,"metadata":metadata or {}}


class CombatEngine:
    def __init__(self, formula_engine: FormulaEngine | None = None, *, seed: str = "smartmud", lifecycle: ActorLifecycleManager | None = None, persist_history: bool = False, content: CombatContentRegistry | None = None) -> None:
        self.formula_engine = formula_engine or FormulaEngine(); self.roller = DeterministicRoller(seed); self.lifecycle = lifecycle
        self.persist_history = persist_history; self.history: list[DamageEvent] = []; self.states: dict[str, CombatState] = {}; self.tick = 0; self.cooldowns: dict[str, int] = {}
        self.body_profiles = BodyProfileRegistry(); self.damage_types = DamageTypeRegistry(); self.content = content or CombatContentRegistry()

    def advance(self, ticks: int = 1) -> int:
        self.tick += max(0, int(ticks)); return self.tick

    def set_state(self, actor: Actor, state: CombatState | str) -> None:
        self.states[actor.actor_id] = CombatState(state); actor.combat_profile["combat_state"] = self.states[actor.actor_id].value

    def resolve_attack(self, attacker: Actor, defender: Actor, *, room_id: str = "", world_time: int | None = None) -> CombatResult:
        trace: list[dict[str, Any]] = [{"step":"resolve_attacker_actor","actor_id":attacker.actor_id},{"step":"resolve_defender_actor","actor_id":defender.actor_id}]
        self.set_state(attacker, CombatState.ATTACKING); self.set_state(defender, CombatState.IN_COMBAT)
        attack = self.attack_profile(attacker); trace.append({"step":"resolve_attack_profile","attack_profile":asdict(attack)})
        acc = self._stat(attacker,"accuracy",50,trace); defense = self._stat(defender,"defense_rating",10,trace); roll = self.roller.roll_percent(attacker.actor_id, defender.actor_id, self.tick, "hit")
        hit = roll <= max(0, min(100, 50 + acc - defense)); trace.append({"step":"resolve_hit_chance","roll":roll,"hit":hit})
        if not hit:
            self.set_state(attacker, CombatState.RECOVERING); return CombatResult(False, None, self.states[attacker.actor_id].value, self.states[defender.actor_id].value, self._messages(attacker, defender, "miss", None), trace)
        crit_chance = self._stat(attacker,"critical_chance",0,trace); crit = self.roller.roll_percent(attacker.actor_id, defender.actor_id, self.tick, "crit") <= crit_chance
        power = self._stat(attacker,"attack_power",0,trace); base = max(0, attack.base_damage + power); base = int(base * attack.critical_multiplier) if crit else base
        equipment_armor = self.content.armor_value((defender.equipment_profile or {}).get("equipped") or defender.equipment_profile or {})
        armor = 0 if attack.damage_type == "true" else self._stat(defender,"armor",equipment_armor,trace); resist = 0 if attack.damage_type == "true" else _num((defender.resistance_profile or {}).get(attack.damage_type), 0)
        mitigation = max(0, armor + resist); final = max(0, base - mitigation); trace.append({"step":"resolve_damage_and_mitigation","base":base,"armor":armor,"resistance":resist,"final":final})
        resource_trace = apply_damage(defender, final, metadata={"attacker_id":attacker.actor_id}); trace.append({"step":"apply_resource_changes", **resource_trace})
        event = DamageEvent(attacker.actor_id, defender.actor_id, attack.metadata.get("weapon", {}), asdict(attack), attack.damage_type, base, crit, mitigation, final, self.tick)
        if self.persist_history: self.history.append(event)
        death = None
        if defender.resources.health <= 0:
            self.set_state(defender, CombatState.DEAD); trace.append({"step":"check_death","dead":True})
            if self.lifecycle: death = self.lifecycle.actor_died(defender.actor_id, room_id, world_time if world_time is not None else self.tick, defender.lifecycle_profile.get("respawn_delay"), defender.lifecycle_profile.get("spawn_definition_id", "")); trace.append({"step":"pass_to_lifecycle_manager","handoff":death})
        self.set_state(attacker, CombatState.RECOVERING); self.cooldowns[attacker.actor_id] = self.tick + max(1, attack.speed)
        return CombatResult(True, event, self.states[attacker.actor_id].value, self.states[defender.actor_id].value, self._messages(attacker, defender, "hit", event), trace, death)

    def _stat(self, actor: Actor, stat: str, base: int, trace: list[dict[str, Any]]) -> int:
        r = actor.get_derived_value(stat, self.formula_engine, base_value=base); trace.append({"step":"resolve_derived_stat","actor_id":actor.actor_id,"stat":stat,"formula":r.formula_name,"value":r.final_value,"trace":r.calculation_trace}); return _num(r.final_value, base)

    def attack_profile(self, actor: Actor) -> AttackProfile:
        eq = actor.equipment_profile or {}; equipped = eq.get("equipped") or eq
        weapon = eq.get("weapon") or eq.get("main_hand") or equipped.get("main_hand") or equipped.get("primary_weapon")
        if isinstance(weapon, dict):
            data = self.content.weapon_attack_data(weapon) if self.content.weapon_templates or weapon.get("damage_profile") else dict(weapon.get("attack_profile") or weapon)
            return AttackProfile(id=str(data.get("id", weapon.get("id", "weapon"))), name=str(data.get("name", weapon.get("name", "weapon"))), damage_type=str(data.get("damage_type", (data.get("damage_types") or ["physical"])[0])), base_damage=_num(data.get("base_damage", data.get("damage", 1)),1), speed=max(1,_num(data.get("speed", data.get("attack_speed", 1)),1)), reach=_num(data.get("reach",1),1), critical_multiplier=float(data.get("critical_multiplier", 2.0)), source="weapon", metadata={"weapon":data.get("weapon", weapon), "attack_profile":data.get("attack_profile_record", {}), "damage_profile":data.get("damage_profile_record", {}), "critical_profile":data.get("critical_profile_record", {})})
        natural_data = self.content.natural_attack_data(actor)
        if natural_data:
            return AttackProfile(id=str(natural_data.get("id","natural")), name=str(natural_data.get("name", "natural attack")), damage_type=str(natural_data.get("damage_type","physical")), base_damage=_num(natural_data.get("base_damage",1),1), speed=max(1,_num(natural_data.get("speed",1),1)), reach=_num(natural_data.get("reach",1),1), critical_multiplier=float(natural_data.get("critical_multiplier", 2.0)), source="natural", metadata={"weapon": natural_data.get("weapon", {}), "body_profile": self.body_profiles.get(actor.body_profile_id).id, "attack_profile": natural_data.get("attack_profile_record", {}), "damage_profile": natural_data.get("damage_profile_record", {}), "critical_profile": natural_data.get("critical_profile_record", {})})
        natural = (actor.combat_profile or {}).get("natural_weapons") or []
        if natural:
            n = natural[0]; return AttackProfile(id=str(n.get("id","natural")), name=str(n.get("name", n.get("slot", "natural attack"))), damage_type=str(n.get("damage_type","physical")), base_damage=_num(n.get("base_damage",1),1), speed=max(1,_num(n.get("speed",1),1)), reach=_num(n.get("reach",1),1), source="natural", metadata={"body_profile": self.body_profiles.get(actor.body_profile_id).id, "anatomy": n.get("slot")})
        return AttackProfile()

    def consider(self, attacker: Actor, defender: Actor) -> str:
        a = max(1, _num(attacker.resources.maximum_health)+self._stat(attacker,"attack_power",0,[])+self._stat(attacker,"armor",0,[]))
        d = max(1, _num(defender.resources.maximum_health)+self._stat(defender,"attack_power",0,[])+self._stat(defender,"armor",0,[])); ratio = d / a
        for limit, word in [(0.5,"weak"),(0.8,"easy"),(1.2,"fair"),(1.6,"challenging"),(2.2,"dangerous"),(3.0,"deadly")]:
            if ratio <= limit: return word
        return "impossible"

    def _messages(self, a: Actor, d: Actor, outcome: str, e: DamageEvent | None) -> dict[str, str]:
        verb = str(((e.attack_profile if e else {}) or {}).get("name") or "strike")
        weapon = str(((e.weapon if e else {}) or {}).get("name") or verb).lower()
        dname = d.identity.name; aname = a.identity.name
        if outcome == "miss":
            return {"attacker":f"You narrowly miss {dname}.","victim":f"{aname}'s attack passes wide of you.","observers":f"{aname} misses {dname}."}
        dmg = max(0, e.final_damage if e else 0); maxhp = max(1, int(getattr(d.resources, "maximum_health", 1) or 1)); rel = dmg / maxhp
        if dmg <= 0: sev = "glances harmlessly from"
        elif rel < .08: sev = "grazes"
        elif rel < .18: sev = "strikes"
        elif rel < .35: sev = "wounds"
        else: sev = "devastates"
        if condition_key(d) == "dead": sev = "finishes"
        bang = "!" if (e and e.critical) or sev in {"devastates", "finishes"} else "."
        crit = " with a brutal critical blow" if e and e.critical else ""
        if "bite" in verb.lower():
            return {"attacker":f"You bite into {dname}{crit}{bang}","victim":f"{aname} bites into you{crit}{bang}","observers":f"{aname} bites into {dname}{crit}{bang}"}
        attacker_verb = "finish" if sev == "finishes" else ("glance harmlessly off" if sev == "glances harmlessly from" else (sev[:-1] if sev.endswith("s") else sev))
        return {"attacker":f"You {attacker_verb} {dname} with {weapon}, dealing damage{crit}{bang}","victim":f"{aname} {sev} you with {weapon}, dealing damage{crit}{bang}","observers":f"{aname} {sev} {dname} with {weapon}, dealing damage{crit}{bang}"}
