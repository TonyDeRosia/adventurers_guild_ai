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
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from engine.actors import Actor
from engine.formulas import FormulaEngine
from engine.combat_equipment import CombatContentRegistry
from engine.phase5f import ActorLifecycleManager, BodyProfileRegistry
from engine.conditions import condition_key


class CombatState(StrEnum):
    IDLE = "idle"; ENGAGING = "engaging"; IN_COMBAT = "in_combat"; ATTACKING = "attacking"; RECOVERING = "recovering"
    FLEEING = "fleeing"; STUNNED = "stunned"; SLEEPING = "sleeping"; UNCONSCIOUS = "unconscious"; INCAPACITATED = "incapacitated"; DEAD = "dead"


DAMAGE_TYPES = ("physical","slash","pierce","blunt","fire","cold","lightning","poison","disease","acid","holy","shadow","arcane","psychic","true")
SUPPORTED_SAVE_TYPES = ("physical_save", "mental_save", "magic_save")


@dataclass(frozen=True)
class DamageTypeRegistry:
    types: tuple[str, ...] = DAMAGE_TYPES
    builder_types: tuple[str, ...] = ()
    def has(self, damage_type: str) -> bool: return damage_type in set(self.types) | set(self.builder_types)


class AttackKind(StrEnum):
    MELEE_WEAPON = "melee_weapon"; RANGED_WEAPON = "ranged_weapon"; UNARMED = "unarmed"; SPELL_ATTACK = "spell_attack"
    HEALING = "healing"; ABILITY = "ability"; ENVIRONMENTAL = "environmental"; DAMAGE_OVER_TIME = "damage_over_time"; REACTIVE = "reactive"


@dataclass(frozen=True)
class CombatResolutionContext:
    world_id: str = ""; zone_id: str = ""; area_id: str = ""; room_id: str = ""
    attacker_id: str = ""; defender_id: str = ""; ability_id: str | None = None
    attack_kind: str = AttackKind.UNARMED.value; damage_kind: str = "physical"; weapon_instance_id: str | None = None
    range: int = 0; distance: int = 0; attacker_position: str = "standing"; defender_position: str = "standing"
    attacker_conditions: tuple[str, ...] = (); defender_conditions: tuple[str, ...] = (); environment: tuple[str, ...] = ()
    world_time: int = 0; round_id: str = ""; action_id: str = ""; metadata: dict[str, Any] = field(default_factory=dict)

    def safe_metadata(self) -> dict[str, Any]:
        allowed={"difficulty","base_amount","damage_type","save_type","partial_percent","armor_penetration","minimum_damage","maximum_mitigation_percent","critical_multiplier"}
        return {str(k):v for k,v in (self.metadata or {}).items() if k in allowed and isinstance(v,(str,int,float,bool,type(None)))}


@dataclass
class CanonicalActorProjection:
    actor_id: str
    actor_type: str
    name: str
    level: int
    attributes: dict[str, Any]
    resources: dict[str, int]
    equipment_owner_id: str
    equipment: dict[str, Any]
    affects: Any
    resistance_profile: dict[str, Any]
    body_profile_id: str
    position: str
    room_id: str
    world_id: str
    persistence_identity: str
    inventory_owner_id: str

    def __post_init__(self):
        self.id = self.actor_id
        self.character_id = self.persistence_identity or self.actor_id
        self.hp = int(self.resources.get("health", 0)); self.max_health = int(self.resources.get("maximum_health", 0))
        self.mana = int(self.resources.get("mana", 0)); self.max_mana = int(self.resources.get("maximum_mana", 0))
        self.stamina = int(self.resources.get("stamina", 0)); self.max_stamina = int(self.resources.get("maximum_stamina", 0))
        self.resistances = self.resistance_profile


@dataclass(frozen=True)
class ResourceChange:
    actor_id: str; resource: str; before: int; amount: int; after: int; operation: str


@dataclass(frozen=True)
class SavingThrowResult:
    ok: bool
    save_type: str
    attacker_id: str
    defender_id: str
    ability_id: str | None
    formula_id: str
    difficulty: float
    attacker_value: float
    defender_value: float
    chance: int
    roll: int
    success: bool
    partial: bool = False
    partial_percent: int = 0
    negated: bool = False
    duration_multiplier: float = 1.0
    effect_multiplier: float = 1.0
    reason_code: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)
    events: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CriticalResult:
    critical_type: str
    attacker_chance: float
    defender_avoidance: float
    final_chance: int
    roll: int
    multiplier: float
    amount_before_critical: int
    amount_after_critical: int
    critical: bool


@dataclass(frozen=True)
class CombatResolutionResult:
    ok: bool; reason_code: str; attacker_id: str; defender_id: str; attack_kind: str
    ability_id: str | None = None; weapon_instance_id: str | None = None; hit: bool = False; miss_reason: str = ""
    critical: bool = False; critical_kind: str = ""; raw_amount: int = 0; mitigated_amount: int = 0; final_amount: int = 0
    damage_type: str = "physical"; resource_changes: tuple[ResourceChange, ...] = (); affects_applied: tuple[dict[str, Any], ...] = ()
    defender_defeated: bool = False; messages: dict[str, str] = field(default_factory=dict); events: tuple[dict[str, Any], ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)


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
    def __init__(self, formula_engine: FormulaEngine | None = None, *, seed: str = "smartmud", lifecycle: ActorLifecycleManager | None = None, persist_history: bool = False, content: CombatContentRegistry | None = None, combat_stats: Any | None = None, event_bus: Any | None = None) -> None:
        self.formula_engine = formula_engine or FormulaEngine(); self.roller = DeterministicRoller(seed); self.lifecycle = lifecycle
        self.persist_history = persist_history; self.history: list[DamageEvent] = []; self.states: dict[str, CombatState] = {}; self.tick = 0; self.cooldowns: dict[str, int] = {}
        self.body_profiles = BodyProfileRegistry(); self.damage_types = DamageTypeRegistry(); self.content = content or CombatContentRegistry(); self.combat_stats = combat_stats; self.event_bus = event_bus; self.resolution = CombatResolutionService(self, combat_stats=combat_stats, event_bus=event_bus)

    def advance(self, ticks: int = 1) -> int:
        self.tick += max(0, int(ticks)); return self.tick

    def set_state(self, actor: Actor, state: CombatState | str) -> None:
        self.states[actor.actor_id] = CombatState(state); actor.combat_profile["combat_state"] = self.states[actor.actor_id].value

    def resolve_attack(self, attacker: Actor, defender: Actor, *, room_id: str = "", world_time: int | None = None) -> CombatResult:
        if self.combat_stats is None:
            if getattr(self, 'runtime', None) is not None:
                raise RuntimeError("CombatEngine requires CombatStatService for normal runtime resolution; use resolve_attack_legacy_for_migration_tests only in isolated migration tests.")
            return self.resolve_attack_legacy_for_migration_tests(attacker, defender, room_id=room_id, world_time=world_time)
        ctx=CombatResolutionContext(room_id=room_id, attacker_id=attacker.actor_id, defender_id=defender.actor_id, world_time=world_time if world_time is not None else self.tick)
        rr=self.resolution.resolve(attacker, defender, ctx)
        dmg=DamageEvent(attacker.actor_id, defender.actor_id, {}, {"name": self.attack_profile(attacker).name}, rr.damage_type, rr.raw_amount, rr.critical, rr.mitigated_amount, rr.final_amount, self.tick) if rr.hit else None
        return CombatResult(rr.hit, dmg, self.states.get(attacker.actor_id, CombatState.RECOVERING).value if attacker.actor_id in self.states else CombatState.RECOVERING.value, self.states.get(defender.actor_id, CombatState.IN_COMBAT).value if defender.actor_id in self.states else CombatState.IN_COMBAT.value, rr.messages, list(rr.diagnostics.get("trace", [])))

    def resolve_attack_legacy_for_migration_tests(self, attacker: Actor, defender: Actor, *, room_id: str = "", world_time: int | None = None) -> CombatResult:
        trace: list[dict[str, Any]] = [{"step":"resolve_attacker_actor","actor_id":attacker.actor_id},{"step":"resolve_defender_actor","actor_id":defender.actor_id}]
        self.set_state(attacker, CombatState.ATTACKING); self.set_state(defender, CombatState.IN_COMBAT)
        attack = self.attack_profile(attacker); trace.append({"step":"resolve_attack_profile","attack_profile":asdict(attack)})
        death = None
        acc = self._stat(attacker,"accuracy",50,trace); defense = self._stat(defender,"defense_rating",10,trace); roll = self.roller.roll_percent(attacker.actor_id, defender.actor_id, self.tick, "hit")
        hit = roll <= max(0, min(100, 50 + acc - defense))
        if not hit:
            self.set_state(attacker, CombatState.RECOVERING); return CombatResult(False, None, self.states[attacker.actor_id].value, self.states[defender.actor_id].value, self._messages(attacker, defender, "miss", None), trace)
        crit = self.roller.roll_percent(attacker.actor_id, defender.actor_id, self.tick, "crit") <= self._stat(attacker,"critical_chance",0,trace)
        power = self._stat(attacker,"attack_power",0,trace); base=max(0, attack.base_damage+power); raw=int(base*attack.critical_multiplier) if crit else base
        armor = 0 if attack.damage_type == "true" else self._stat(defender,"armor", self.content.armor_value((defender.equipment_profile or {}).get("equipped") or defender.equipment_profile or {}), trace)
        resist = 0 if attack.damage_type == "true" else _num((defender.resistance_profile or {}).get(attack.damage_type), 0)
        mitigation=max(0, armor+resist); final=max(0, raw-mitigation)
        rt=apply_damage(defender, final, metadata={"attacker_id":attacker.actor_id}); trace.append({"step":"apply_resource_changes", **rt})
        if defender.resources.health <= 0:
            self.set_state(defender, CombatState.DEAD)
            if self.lifecycle: death = self.lifecycle.actor_died(defender.actor_id, room_id, world_time if world_time is not None else self.tick, defender.lifecycle_profile.get("respawn_delay"), defender.lifecycle_profile.get("spawn_definition_id", ""))
        event=DamageEvent(attacker.actor_id, defender.actor_id, {}, asdict(attack), attack.damage_type, raw, crit, mitigation, final, self.tick)
        self.set_state(attacker, CombatState.RECOVERING); return CombatResult(True,event,self.states[attacker.actor_id].value,self.states[defender.actor_id].value,self._messages(attacker,defender,"hit",event),trace,death)

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


class CombatResolutionService:
    """Authoritative combat outcome pipeline backed by CombatStatService snapshots."""
    def __init__(self, engine: CombatEngine, *, combat_stats: Any | None = None, event_bus: Any | None = None, rng: Callable[..., int] | None = None, runtime: Any | None = None) -> None:
        self.engine=engine; self.combat_stats=combat_stats; self.event_bus=event_bus; self.rng=rng or engine.roller.roll_percent; self.runtime=runtime

    def _actor_view(self, actor: Actor, context: CombatResolutionContext | None = None) -> CanonicalActorProjection:
        ctx=context or CombatResolutionContext()
        pid=actor.actor_id.split(':',1)[1] if ':' in actor.actor_id else actor.actor_id
        if actor.actor_id.startswith('character:'):
            actor_type='player'
        else:
            actor_type=str(getattr(actor.identity, 'actor_type', '') or getattr(actor, 'actor_type', '') or 'npc')
        resources={
            'health': _num(actor.resources.health), 'maximum_health': _num(actor.resources.maximum_health),
            'mana': _num(actor.resources.mana), 'maximum_mana': _num(actor.resources.maximum_mana),
            'stamina': _num(actor.resources.stamina), 'maximum_stamina': _num(actor.resources.maximum_stamina),
        }
        return CanonicalActorProjection(actor.actor_id, actor_type, actor.identity.name, int((actor.progression_profile or {}).get('level',1) or 1), dict(actor.attributes or {}), resources, pid, dict(actor.equipment_profile or {}), actor.effect_container or {}, dict(actor.resistance_profile or {}), str(actor.body_profile_id or ''), str((actor.combat_profile or {}).get('combat_state') or ctx.attacker_position or 'standing'), str(actor.identity.current_location or ctx.room_id), str(actor.identity.current_world or ctx.world_id), pid, pid)

    def _snapshot(self, actor: Actor, context: CombatResolutionContext):
        if not self.combat_stats: return None
        return self.combat_stats.get_combat_snapshot(self._actor_view(actor, context), {"combat_context": asdict(context), "runtime": self.runtime})

    @property
    def runtime(self):
        return getattr(self, '_runtime', None) or getattr(self.engine, 'runtime', None)

    @runtime.setter
    def runtime(self, value):
        self._runtime=value

    def _publish(self, name: str, payload: dict[str, Any]) -> None:
        if self.event_bus:
            self.event_bus.publish(name, payload, source_system='combat_resolution', world_id=payload.get('world_id',''))

    def _world_root(self) -> Path:
        if self.combat_stats and getattr(self.combat_stats, "world_root", None):
            return Path(self.combat_stats.world_root)
        return Path("worlds") / "shattered_realms"

    def _load_combat_json(self, name: str, default: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads((self._world_root() / "combat" / name).read_text())
        except Exception:
            return default

    def _formula(self, formula_id: str, expression: str, variables: dict[str, Any]) -> float:
        if self.combat_stats and getattr(self.combat_stats,'formulas',None): expression=self.combat_stats.formulas.get(formula_id, expression)
        return float(self.engine.formula_engine.evaluate_expression(formula_id, expression, variables).final_value)

    def _posture_rule(self, posture_id: str) -> dict[str, Any]:
        data = self._load_combat_json("postures.json", {})
        rules = {str(p.get("posture_id")): p for p in data.get("postures", []) if p.get("enabled", True)}
        return rules.get(str(posture_id).lower(), data.get("unknown_posture_policy", {"attack_allowed": False, "defense_evasion_modifier": -25}))

    def _range_modifier(self, ctx: CombatResolutionContext, profile: AttackProfile) -> tuple[int, dict[str, Any]]:
        rules = self._load_combat_json("range_rules.json", {}).get("range_rules", {})
        reach = int(profile.reach or rules.get("melee_reach_default", 1) or 1)
        distance = int(ctx.distance or ctx.range or 0)
        formula_id = str(rules.get("distance_penalty_formula_id") or "range_distance_penalty")
        mod = round(self._formula(formula_id, "0 if distance <= reach else (distance - reach) * -5", {"distance": distance, "reach": reach, "point_blank_penalty": int(rules.get("point_blank_penalty", -10) or -10)}))
        return int(mod), {"formula_id": formula_id, "distance": distance, "reach": reach, "modifier": int(mod), "rules": rules}

    def resolve_saving_throw(self, attacker_snapshot: Any, defender_snapshot: Any, ctx: CombatResolutionContext, declaration: dict[str, Any] | None = None) -> SavingThrowResult:
        dec = dict(declaration or ctx.safe_metadata() or {})
        save_type = str(dec.get("save_type") or "").lower()
        if not save_type:
            return SavingThrowResult(True, "", ctx.attacker_id, ctx.defender_id, ctx.ability_id, "", 0, 0, 0, 0, 0, False, reason_code="no_save_declared")
        if save_type not in SUPPORTED_SAVE_TYPES:
            result = SavingThrowResult(False, save_type, ctx.attacker_id, ctx.defender_id, ctx.ability_id, str(dec.get("save_formula_id") or "saving_throw_resolution"), 0, 0, 0, 0, 0, False, reason_code="unknown_save_type")
            self._publish("saving_throw_resolved", asdict(result))
            return result
        formula_id = str(dec.get("save_formula_id") or "saving_throw_resolution")
        difficulty = float(dec.get("save_difficulty") or dec.get("difficulty") or 50)
        attacker_stat_name = str(dec.get("save_attacker_stat") or "spell_power")
        attacker_value = float((getattr(attacker_snapshot, "offense", {}) or {}).get(attacker_stat_name, 0) or 0)
        defender_value = float((getattr(defender_snapshot, "saves", {}) or {}).get(save_type, 0) or 0)
        inputs = {"attacker_stat": attacker_value, "defender_save": defender_value, "save_rating": defender_value, "difficulty": difficulty, "level_difference": float(getattr(attacker_snapshot, "level", 1) - getattr(defender_snapshot, "level", 1)) if hasattr(attacker_snapshot, "level") else 0, "ability_proficiency": float(dec.get("ability_proficiency") or 0), "situational_modifier": float(dec.get("situational_modifier") or 0)}
        raw = self._formula(formula_id, "50 + defender_save - difficulty + attacker_stat + level_difference + ability_proficiency + situational_modifier", inputs)
        lo = int(dec.get("minimum_success_chance") or 5); hi = int(dec.get("maximum_success_chance") or 95)
        chance = max(lo, min(hi, round(raw)))
        roll = self.rng(ctx.attacker_id, ctx.defender_id, ctx.round_id or self.engine.tick, ctx.action_id or "save", save_type)
        success = roll <= chance
        partial_percent = int(dec.get("partial_percent") or dec.get("reduced_amount_percent") or 0)
        duration_multiplier = (100 - int(dec.get("reduced_duration_percent") or 0)) / 100 if success else 1.0
        effect_multiplier = (100 - int(dec.get("reduced_amount_percent") or partial_percent or 0)) / 100 if success else 1.0
        negated = bool(success and dec.get("negates"))
        result = SavingThrowResult(True, save_type, ctx.attacker_id, ctx.defender_id, ctx.ability_id, formula_id, difficulty, attacker_value, defender_value, chance, roll, success, bool(success and partial_percent), partial_percent if success else 0, negated, duration_multiplier, effect_multiplier, "success" if success else "failure", {"inputs": inputs, "raw": raw, "clamp": [lo, hi]}, ())
        event = {**asdict(result), "event": "saving_throw_resolved"}
        object.__setattr__(result, "events", (event,))
        self._publish("saving_throw_resolved", event)
        return result

    def resolve(self, attacker: Actor, defender: Actor, context: CombatResolutionContext | None = None) -> CombatResolutionResult:
        ctx=context or CombatResolutionContext(attacker_id=attacker.actor_id, defender_id=defender.actor_id, world_time=self.engine.tick)
        events=[]; trace=[{"step":"combat_snapshot_consumed","attacker_id":attacker.actor_id,"defender_id":defender.actor_id}]
        self.engine.set_state(attacker, CombatState.ATTACKING); self.engine.set_state(defender, CombatState.IN_COMBAT)
        atk=self.engine.attack_profile(attacker); attack_kind=ctx.attack_kind or (AttackKind.MELEE_WEAPON.value if atk.source=='weapon' else AttackKind.UNARMED.value)
        a=self._snapshot(attacker, ctx); d=self._snapshot(defender, ctx)
        if not a or not d: return CombatResolutionResult(False,'missing_combat_stat_service',attacker.actor_id,defender.actor_id,attack_kind,diagnostics={"trace":trace})
        if attack_kind == AttackKind.HEALING.value and not bool(ctx.safe_metadata().get('requires_hit_roll')):
            heal_power=int(a.offense.get('healing_power', a.offense.get('spell_power', a.offense.get('attack_power',0))) or 0)
            coeff=float(ctx.safe_metadata().get('healing_coefficient') or 1.0)
            base=int(ctx.safe_metadata().get('base_amount') or max(1, heal_power or 10))
            crit_chance=max(0,min(100,int(a.critical.get('critical_heal',0))-int(d.critical.get('critical_avoidance',0))))
            crit_roll=self.rng(attacker.actor_id,defender.actor_id,ctx.round_id or self.engine.tick,ctx.action_id or 'heal_crit')
            crit=bool(ctx.safe_metadata().get('can_critical', True)) and crit_roll<=crit_chance
            mult=float(ctx.safe_metadata().get('critical_multiplier') or 1.5)
            raw=round(self._formula('healing_resolution','base_amount + healing_power * healing_coefficient', {'base_amount':base,'healing_power':heal_power,'healing_coefficient':coeff}))
            effective=int(raw*mult) if crit else int(raw)
            rt=apply_healing(defender, effective, source='combat_healing', metadata={'attacker_id':attacker.actor_id})
            actual=int(rt['after'])-int(rt['before']); overheal=max(0,effective-actual)
            change=ResourceChange(defender.actor_id,str(ctx.safe_metadata().get('resource_target') or 'health'),int(rt['before']),actual,int(rt['after']),'healing')
            events.extend([{'event':'critical_resolved','critical':crit,'critical_kind':'critical_heal'},{'event':'healing_calculated','actor_id':defender.actor_id,'raw':raw,'effective':actual,'overheal':overheal},{'event':'healing_applied','actor_id':defender.actor_id,'amount':actual}])
            for ev in events: self._publish(ev.get('event','combat_event'), ev)
            trace.append({'step':'healing_calculated','formula_id':'healing_resolution','inputs':{'base_amount':base,'healing_power':heal_power,'healing_coefficient':coeff},'raw':raw,'effective':actual,'overheal':overheal,'critical':crit})
            self.engine.set_state(attacker, CombatState.RECOVERING)
            return CombatResolutionResult(True,'healed',attacker.actor_id,defender.actor_id,attack_kind,ctx.ability_id,ctx.weapon_instance_id,True,'',crit,'critical_heal',raw,0,actual,'healing',(change,),(),False,{'attacker':f'You heal {defender.identity.name} for {actual}.','victim':f'{attacker.identity.name} heals you for {actual}.','observers':f'{attacker.identity.name} heals {defender.identity.name}.'},tuple(events),{'trace':trace,'attacker_source_version':a.source_version,'defender_source_version':d.source_version,'overheal':overheal})
        acc=int(a.offense.get('accuracy',0)); hit_bonus=int(a.offense.get('hit_bonus',0)); evasion=int(d.defense.get('evasion',0))
        attacker_posture = self._posture_rule(ctx.attacker_position)
        defender_posture = self._posture_rule(ctx.defender_position)
        if not attacker_posture.get("attack_allowed", True):
            return CombatResolutionResult(False,'attacker_posture_forbids_attack',attacker.actor_id,defender.actor_id,attack_kind,diagnostics={"trace":trace,"posture_rule":attacker_posture})
        posture=int(defender_posture.get("defense_evasion_modifier", 0) or 0)
        range_mod, range_diag = self._range_modifier(ctx, atk)
        if defender_posture.get("automatic_hit_against"):
            chance = 100
        else:
            chance=max(5,min(95,round(self._formula('attack_hit_resolution','50 + accuracy + hit_bonus - evasion + posture_modifier + range_modifier', {'accuracy':acc,'hit_bonus':hit_bonus,'evasion':evasion,'posture_modifier':posture,'range_modifier':range_mod}))))
        roll=self.rng(attacker.actor_id,defender.actor_id,ctx.round_id or self.engine.tick,ctx.action_id or 'hit')
        hit=roll<=chance; trace.append({'step':'attack_roll_resolved','formula_id':'attack_hit_resolution','inputs':{'accuracy':acc,'hit_bonus':hit_bonus,'evasion':evasion,'posture_modifier':posture,'range_modifier':range_mod},'chance':chance,'roll':roll,'hit':hit})
        events.append({'event':'attack_roll_resolved','attacker_id':attacker.actor_id,'defender_id':defender.actor_id,'chance':chance,'roll':roll,'hit':hit})
        if not hit:
            self.engine.set_state(attacker, CombatState.RECOVERING); messages=self.engine._messages(attacker,defender,'miss',None); events.append({'event':'attack_missed','attacker_id':attacker.actor_id,'defender_id':defender.actor_id})
            for ev in events: self._publish(ev.get('event','combat_event'), ev)
            return CombatResolutionResult(True,'miss',attacker.actor_id,defender.actor_id,attack_kind,ctx.ability_id,ctx.weapon_instance_id,False,'evasion',messages=messages,events=tuple(events),diagnostics={'trace':trace,'attacker_source_version':a.source_version,'defender_source_version':d.source_version})
        save_result = self.resolve_saving_throw(a, d, ctx) if ctx.safe_metadata().get("save_type") else None
        if save_result and not save_result.ok:
            return CombatResolutionResult(False, save_result.reason_code, attacker.actor_id, defender.actor_id, attack_kind, ctx.ability_id, ctx.weapon_instance_id, diagnostics={"trace": trace, "saving_throw": asdict(save_result)})
        if save_result and save_result.negated:
            events.append({'event':'effect_resisted','attacker_id':attacker.actor_id,'defender_id':defender.actor_id,'save':asdict(save_result)})
            for ev in events: self._publish(ev.get('event','combat_event'), ev)
            return CombatResolutionResult(True,'save_negated',attacker.actor_id,defender.actor_id,attack_kind,ctx.ability_id,ctx.weapon_instance_id,True,events=tuple(events),diagnostics={'trace':trace,'saving_throw':asdict(save_result)})
        crit_stat='critical_spell' if attack_kind==AttackKind.SPELL_ATTACK.value else 'critical_heal' if attack_kind==AttackKind.HEALING.value else 'critical_melee'
        crit_raw=self._formula('critical_resolution','critical_rating - critical_avoidance', {'critical_rating':int(a.critical.get(crit_stat,0)),'critical_avoidance':int(d.critical.get('critical_avoidance',0))})
        crit_chance=max(0,min(100,round(crit_raw)))
        crit_roll=self.rng(attacker.actor_id,defender.actor_id,ctx.round_id or self.engine.tick,ctx.action_id or 'crit')
        crit=crit_roll<=crit_chance; mult=float(ctx.safe_metadata().get('critical_multiplier') or 2.0); trace.append({'step':'critical_resolved','critical_kind':crit_stat,'chance':crit_chance,'roll':crit_roll,'critical':crit})
        profile=a.weapon_profile if atk.source=='weapon' and a.weapon_profile else a.unarmed_profile
        base=max(int(profile.minimum_damage), int((int(profile.minimum_damage)+int(profile.maximum_damage))/2)) + int(a.offense.get('attack_power',0)) + int(a.offense.get('damage_bonus',0))
        raw=int(base*mult) if crit else int(base); dtype=ctx.damage_kind or profile.damage_type or atk.damage_type
        penetration=int(ctx.safe_metadata().get('armor_penetration') or 0); armor=int(d.defense.get('armor',0))
        after_armor = raw if dtype == "true" else round(self._formula('armor_mitigation','max(minimum_damage, raw_damage - max(0, armor - armor_penetration))', {'raw_damage':raw,'armor':armor,'armor_penetration':penetration,'attacker_level':1,'defender_level':1,'maximum_mitigation_percent':95,'minimum_damage':int(ctx.safe_metadata().get('minimum_damage') or 0)}))
        resist=int(d.resistances.get(dtype,0) or 0)
        final = raw if dtype == "true" else max(0, round(self._formula('resistance_mitigation','0 if immunity else damage_after_armor * (100 - min(resistance_cap, max(0, resistance_value)) + max(0, vulnerability)) / 100', {'damage_after_armor':after_armor,'post_armor_damage':after_armor,'resistance_value':resist,'resistance_percent':resist,'resistance_cap':95,'immunity':0,'vulnerability':0,'damage_type':0})))
        if save_result and save_result.partial:
            final = max(0, round(final * (save_result.partial_percent / 100)))
        mitigated=raw-final
        armor_event={'event':'armor_mitigation_resolved','raw_damage':raw,'armor':armor,'armor_penetration':penetration,'damage_after_armor':after_armor}
        resist_event={'event':'resistance_mitigation_resolved','damage_after_armor':after_armor,'resistance_value':resist,'final_damage':final}
        events.extend([armor_event,resist_event,{'event':'damage_calculated','raw_amount':raw,'final_amount':final,'damage_type':dtype}])
        trace.append({'step':'damage_mitigated','raw':raw,'armor':armor,'armor_penetration':penetration,'after_armor':after_armor,'resistance_value':resist,'order':'armor_then_resistance','final':final,'range':range_diag,'posture_rule':defender_posture,'saving_throw':asdict(save_result) if save_result else None})
        rt=apply_healing(defender, final, source='combat_healing', metadata={'attacker_id':attacker.actor_id}) if attack_kind==AttackKind.HEALING.value else apply_damage(defender, final, metadata={'attacker_id':attacker.actor_id})
        change=ResourceChange(defender.actor_id,'health',int(rt['before']),int(rt.get('amount',final)),int(rt['after']),str(rt['operation']))
        defeated=defender.resources.health<=0 and attack_kind!=AttackKind.HEALING.value
        if defeated: self.engine.set_state(defender, CombatState.DEAD); events.append({'event':'actor_defeated','actor_id':defender.actor_id})
        self.engine.set_state(attacker, CombatState.RECOVERING); evname='healing_applied' if attack_kind==AttackKind.HEALING.value else 'damage_applied'; events.extend([{'event':'attack_hit','attacker_id':attacker.actor_id,'defender_id':defender.actor_id},{'event':'critical_resolved','critical':crit,'critical_kind':crit_stat},{'event':evname,'actor_id':defender.actor_id,'amount':final}])
        de=DamageEvent(attacker.actor_id,defender.actor_id,atk.metadata.get('weapon',{}),asdict(atk),dtype,raw,crit,mitigated,final,self.engine.tick); messages=self.engine._messages(attacker,defender,'hit',de)
        for ev in events: self._publish(ev.get('event','combat_event'), ev)
        return CombatResolutionResult(True,'hit',attacker.actor_id,defender.actor_id,attack_kind,ctx.ability_id,ctx.weapon_instance_id,True,'',crit,crit_stat,raw,mitigated,final,dtype,(change,),(),defeated,messages,tuple(events),{'trace':trace,'attacker_source_version':a.source_version,'defender_source_version':d.source_version})
