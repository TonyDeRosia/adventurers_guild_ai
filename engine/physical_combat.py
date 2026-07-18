"""Phase 19A physical-combat primitives.

This module deliberately has no database of its own.  ``DamageService`` takes
the small persistence callback used by runtime adapters to update the already
authoritative player/entity records.  It is also useful to tools and tests
which supply in-memory actors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
import json
import random
from typing import Any, Callable


class Position(IntEnum):
    DEAD = 0; MORTALLY_WOUNDED = 1; INCAPACITATED = 2; STUNNED = 3
    SLEEPING = 4; RESTING = 5; SITTING = 6; FIGHTING = 7; STANDING = 8


def trunc_toward_zero(value: int | float) -> int:
    """C-style integer division conversion; unlike ``//`` it is safe negative."""
    return int(value)


def normalize_actor_id(actor_id: str) -> str:
    prefix, _, raw = str(actor_id).partition(":")
    if prefix in {"player", "character"} and raw:
        return f"character:{raw}"
    return f"entity:{raw}" if prefix == "entity" and raw else str(actor_id)


def position_for_hp(hp: int, position: Position | str = Position.STANDING) -> Position:
    old = Position[str(position).upper()] if isinstance(position, str) else position
    if hp > 0 and old > Position.STUNNED: return old
    if hp > 0: return Position.STANDING
    if hp <= -11: return Position.DEAD
    if hp <= -6: return Position.MORTALLY_WOUNDED
    if hp <= -3: return Position.INCAPACITATED
    return Position.STUNNED


@dataclass
class CombatActor:
    actor_id: str; kind: str; world_id: str; room_id: str; name: str
    level: int = 1; hp: int = 1; max_hp: int = 1; position: Position = Position.STANDING
    hitroll: int = 0; damroll: int = 0; armor: int = 0; evasion: int = 0
    strength: int = 10; dexterity: int = 10; intelligence: int = 10; wisdom: int = 10; constitution: int = 10
    weapon: dict[str, Any] | None = None; natural_attack: dict[str, Any] | None = None
    effects: set[str] = field(default_factory=set); attackable: bool = True; visible: bool = True
    opponent_id: str = ""; engagement_id: str = ""; defeated: bool = False
    melee_crit_bonus: int = 0; melee_critical_multiplier_bonus: int = 0
    aliases: tuple[str, ...] = ()
    def __post_init__(self): self.actor_id = normalize_actor_id(self.actor_id)
    @property
    def alive(self) -> bool: return not self.defeated and self.position != Position.DEAD and self.hp > -11


@dataclass(frozen=True)
class AttackRollResult:
    offensive_hit: int; defensive_evasion: int; raw_hit_chance: int; hit_chance: int
    roll: int | None; automatic_hit_reason: str; hit: bool

@dataclass(frozen=True)
class CriticalResult:
    trigger_d20: int; secondary_roll: int | None; total_critical_chance: int
    multiplier_percent: int; critical: bool

@dataclass(frozen=True)
class DamageResult:
    source_actor_id: str; target_actor_id: str; engagement_id: str; attack_source_id: str
    attack_type: str; damage_type: str; hit: bool; critical: bool; raw_damage: int
    position_adjusted_damage: int; critical_adjusted_damage: int; armor: int; mitigated_damage: int
    final_damage: int; hp_before: int; hp_after: int; position_before: str; position_after: str
    defeated: bool; result_code: str

@dataclass(frozen=True)
class PhysicalFormulaProfile:
    profile_id: str = "smartmud.tba_custom_physical.v1"; version: int = 1
    min_hit_chance: int = 5; max_hit_chance: int = 95
    def validate(self) -> list[str]:
        return [] if self.profile_id == "smartmud.tba_custom_physical.v1" and self.version == 1 and 0 <= self.min_hit_chance <= self.max_hit_chance <= 100 else ["invalid physical formula profile"]
    @classmethod
    def load(cls, path: str | Path | None = None) -> "PhysicalFormulaProfile":
        if path:
            data=json.loads(Path(path).read_text())
            profile=cls(**{k:data[k] for k in ("profile_id","version","min_hit_chance","max_hit_chance") if k in data})
        else: profile=cls()
        if profile.validate(): raise ValueError("invalid physical formula profile")
        return profile


class DamageService:
    def __init__(self, persist: Callable[[CombatActor], None] | None = None, publish: Callable[[str, dict], None] | None = None, death_processor: Callable[[Any], Any] | None = None):
        self.persist=persist or (lambda a: None); self.publish=publish or (lambda n,p: None); self.death_processor=death_processor
    def apply(self, attacker: CombatActor, target: CombatActor, *, engagement_id: str, source: dict[str, Any], critical: bool, raw: int, positioned: int, critical_damage: int, armor: int, final: int) -> DamageResult:
        before=target.hp; old=target.position; target.hp -= final; target.position=position_for_hp(target.hp, target.position)
        target.defeated = target.position == Position.DEAD
        self.persist(target)
        code="DEFEATED_PENDING_DEATH_PROCESSING" if target.defeated else "DAMAGE_APPLIED"
        result=DamageResult(attacker.actor_id,target.actor_id,engagement_id,str(source['id']),str(source['attack_type']),str(source['damage_type']),True,critical,raw,positioned,critical_damage,armor,final,final, before,before-final,old.name,target.position.name,target.defeated,code)
        self.publish("combat.damage.applied", result.__dict__)
        if target.defeated:
            self.publish("combat.actor.defeated", result.__dict__)
            # The physical pipeline owns terminal detection only.  Runtime
            # adapters inject the single canonical DeathRuntimeService path.
            if self.death_processor:
                from engine.death_runtime import DeathRequest
                self.death_processor(DeathRequest(death_id=f"terminal:{target.actor_id}:{source['id']}:{before}:{target.hp}", world_id=target.world_id, room_id=target.room_id, victim_actor_id=target.actor_id, immediate_source_actor_id=attacker.actor_id, damage_source_id=str(source['id']), damage_type=str(source['damage_type']), attack_or_ability_id=str(source['attack_type']), engagement_id=engagement_id, terminal_damage_event_id=f"damage:{target.actor_id}:{before}:{target.hp}", hp_before=before, hp_after=target.hp, victim_position=target.position.name))
        return result


class AttackResolutionService:
    def __init__(self, profile: PhysicalFormulaProfile | None = None, rng: Any | None = None, damage_service: DamageService | None = None, publish: Callable[[str,dict],None] | None = None):
        self.profile=profile or PhysicalFormulaProfile.load(); self.rng=rng or random.Random(); self.damage=damage_service or DamageService(); self.publish=publish or (lambda n,p: None)
    def _roll(self, lo:int, hi:int) -> int: return self.rng.randint(lo,hi)
    @staticmethod
    def armor(a: CombatActor) -> int: return max(0,a.armor + 10 + (a.constitution-10) + trunc_toward_zero((a.strength-10)/2))
    @staticmethod
    def evasion(a: CombatActor) -> int: return max(0,a.evasion + 10 + (a.dexterity-10)*2) + a.level
    def attack_roll(self,a:CombatActor,d:CombatActor)->AttackRollResult:
        defensive=self.evasion(d); mental=trunc_toward_zero((a.intelligence-10)/4)+trunc_toward_zero((a.wisdom-10)/4); gap=a.level-d.level
        gap_bonus=trunc_toward_zero(gap/2)+trunc_toward_zero(gap/4) if gap>0 else trunc_toward_zero(gap/3) if gap<0 else 0
        conceal=0 if d.visible else (6 if "true_sight" in a.effects else 3 if a.effects & {"detect_invisibility","sense_life"} else -12)
        off=30+a.level+a.hitroll+trunc_toward_zero((a.strength-10)/2)+mental+gap_bonus+conceal
        raw=50+off-defensive
        if d.position <= Position.SLEEPING: return AttackRollResult(off,defensive,raw,max(self.profile.min_hit_chance,min(self.profile.max_hit_chance,raw)),None,"TARGET_NOT_AWAKE",True)
        chance=max(self.profile.min_hit_chance,min(self.profile.max_hit_chance,raw)); roll=self._roll(1,100)
        return AttackRollResult(off,defensive,raw,chance,roll,"",roll<=chance)
    def source(self,a:CombatActor)->dict[str,Any]:
        if a.weapon: s=dict(a.weapon); s.setdefault("id",s.get("item_instance_id", "weapon")); s.setdefault("dice_count",s.get("damage_dice_count",1)); s.setdefault("die_size",s.get("damage_die_size",2)); s.setdefault("attack_type","weapon"); s.setdefault("damage_type","physical"); return s
        if a.kind in {"npc","mob","entity"}:
            s=dict(a.natural_attack or {}); s.setdefault("id","natural:fallback"); s.setdefault("dice_count",1); s.setdefault("die_size",max(2,min(6,2+trunc_toward_zero(a.level/20)))); s.setdefault("attack_type","natural"); s.setdefault("damage_type","physical"); return s
        return {"id":"unarmed","attack_type":"unarmed","damage_type":"blunt","dice_count":min(4,1+trunc_toward_zero(a.level/30)),"die_size":min(7,2+trunc_toward_zero(a.level/20)),"unarmed":True}
    def resolve(self,a:CombatActor,d:CombatActor,engagement_id:str="") -> tuple[AttackRollResult, DamageResult | None]:
        if not a.alive or a.position < Position.FIGHTING: raise ValueError("ATTACKER_CANNOT_ATTACK")
        if not d.alive or not d.attackable: raise ValueError("TARGET_NOT_ATTACKABLE")
        source=self.source(a); roll=self.attack_roll(a,d); self.publish("combat.attack.attempted",{"source_actor_id":a.actor_id,"target_actor_id":d.actor_id})
        if not roll.hit:
            self.publish("combat.attack.missed",{"source_actor_id":a.actor_id,"target_actor_id":d.actor_id, "roll":roll.roll})
            return roll, None
        dice=max(1,int(source["dice_count"])); sides=max(1,int(source["die_size"])); raw=trunc_toward_zero((a.strength-10)/2)+a.damroll*2+max(0,trunc_toward_zero((a.strength-10)/2))+max(0,trunc_toward_zero(a.level/10))+sum(self._roll(1,sides) for _ in range(dice))
        if source.get("unarmed"): raw += max(0,trunc_toward_zero(a.level/30))
        if a.level>d.level:
            gap=a.level-d.level; raw += max(1,trunc_toward_zero(gap/6))+(trunc_toward_zero(gap/2) if gap>=10 else 0)
        multipliers={Position.FIGHTING:100,Position.STANDING:100,Position.SITTING:133,Position.RESTING:166,Position.SLEEPING:200,Position.STUNNED:233,Position.INCAPACITATED:266,Position.MORTALLY_WOUNDED:300}; positioned=max(1,trunc_toward_zero(raw*multipliers.get(d.position,100)/100))
        chance=max(0,min(100,trunc_toward_zero(a.dexterity/2)+max(0,trunc_toward_zero((a.dexterity-10)/3))+a.melee_crit_bonus)); trigger=self._roll(1,20); secondary=self._roll(1,100) if trigger in (18,19) else None; crit=trigger==20 or (trigger in (18,19) and secondary<=chance); multi=max(100,200+a.melee_critical_multiplier_bonus+max(0,a.strength-10)+max(0,trunc_toward_zero((a.dexterity-10)/2))); critical_damage=trunc_toward_zero(positioned*(multi if crit else 100)/100); armor=self.armor(d); final=max(1,trunc_toward_zero(critical_damage*100/(100+armor)))
        result=self.damage.apply(a,d,engagement_id=engagement_id,source=source,critical=crit,raw=raw,positioned=positioned,critical_damage=critical_damage,armor=armor,final=final)
        self.publish("combat.attack.critical" if crit else "combat.attack.hit",result.__dict__); return roll,result
