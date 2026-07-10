"""Phase 6D deterministic NPC combat behavior, hostility, threat, and tactics.

This layer is intentionally authoritative but conservative: it selects and
validates actions, while damage, healing, cooldowns, resources, effects,
lifecycle, and corpse/respawn ownership remain in existing services.
"""
from __future__ import annotations

import json, math, re, sqlite3, hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.actors import Actor
from engine.combat import CombatEngine
from engine.abilities import AbilityExecutionService, AbilityRegistry

SAFE_ID=re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
BEHAVIOR_ROLES={"civilian","brute","skirmisher","defender","guardian","healer","support","caster","ranged_placeholder","assassin","animal","pack_hunter","summon","pet","training_target","boss_placeholder","custom"}
AGGRESSION_POLICIES={"never","defensive_only","protective","territorial","conditional","hostile_tags","hostile_relationships","always","scripted","custom"}
THREAT_POLICIES={"none","highest","sticky_highest","recent_attacker","nearest_placeholder","protected_target_attacker","random_seeded","custom"}
ACTION_TYPES=["flee","surrender","call_for_help","heal","protect","assist","ability","buff","debuff","basic_attack","return_home","defend","wait","custom"]
TACTICAL_STATES={"idle","aware","engaging","attacking","casting","supporting","healing","defending","protecting","pursuing","fleeing","surrendering","calling_for_help","returning_home","disabled"}

def now(): return datetime.now(timezone.utc).isoformat()
def jdump(v): return json.dumps(v or {}, sort_keys=True)
def jload(v, default=None):
    try: return json.loads(v) if isinstance(v,str) and v else (v if v is not None else ({} if default is None else default))
    except Exception: return {} if default is None else default
def pct(cur,maxv):
    try: return 100.0*float(cur)/max(1.0,float(maxv))
    except Exception: return 100.0
def finite(v, default=0.0):
    try:
        n=float(v); return n if math.isfinite(n) else default
    except Exception: return default

def init_combat_behavior_schema(db_path: str|Path) -> None:
    with sqlite3.connect(db_path) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS actor_threat_entries(
        threat_entry_id TEXT PRIMARY KEY, world_id TEXT, owner_actor_type TEXT, owner_actor_id TEXT,
        target_actor_type TEXT, target_actor_id TEXT, threat_value REAL, hostility_value REAL,
        damage_threat REAL, healing_threat REAL, control_threat REAL, proximity_threat REAL, scripted_threat REAL,
        last_updated_world_time INTEGER, expires_world_time INTEGER, active INTEGER, created_at TEXT, updated_at TEXT, metadata_json TEXT,
        UNIQUE(world_id, owner_actor_id, target_actor_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS actor_combat_behavior_state(
        state_id TEXT PRIMARY KEY, world_id TEXT, actor_type TEXT, actor_id TEXT, behavior_profile_id TEXT,
        current_target_id TEXT, current_action_type TEXT, current_ability_id TEXT, current_tactical_state TEXT,
        last_decision_world_time INTEGER, next_decision_world_time INTEGER, last_attack_world_time INTEGER,
        last_assist_world_time INTEGER, last_flee_attempt_world_time INTEGER, last_call_for_help_world_time INTEGER,
        protected_actor_ids_json TEXT, home_room_id TEXT, leash_origin_room_id TEXT, leash_distance INTEGER,
        decision_counter INTEGER, deterministic_seed TEXT, active INTEGER, created_at TEXT, updated_at TEXT, metadata_json TEXT,
        UNIQUE(world_id, actor_id, active))""")

@dataclass
class CombatBehaviorProfile:
    id:str; name:str=""; description:str=""; enabled:bool=True; behavior_role:str="brute"
    aggression_policy:dict[str,Any]=field(default_factory=lambda:{"type":"defensive_only"})
    hostility_policy:dict[str,Any]=field(default_factory=dict); target_selection_policy:dict[str,Any]=field(default_factory=lambda:{"type":"highest"})
    threat_policy:dict[str,Any]=field(default_factory=lambda:{"type":"highest"}); ability_selection_policy:dict[str,Any]=field(default_factory=dict)
    movement_policy:dict[str,Any]=field(default_factory=dict); assist_policy:dict[str,Any]=field(default_factory=lambda:{"type":"never"})
    protect_policy:dict[str,Any]=field(default_factory=dict); flee_policy:dict[str,Any]=field(default_factory=dict)
    surrender_policy:dict[str,Any]=field(default_factory=lambda:{"type":"never"}); pursuit_policy:dict[str,Any]=field(default_factory=lambda:{"type":"same_room_only"})
    call_for_help_policy:dict[str,Any]=field(default_factory=dict); resource_policy:dict[str,Any]=field(default_factory=dict); cooldown_policy:dict[str,Any]=field(default_factory=dict)
    control_resistance_policy:dict[str,Any]=field(default_factory=dict); idle_combat_policy:dict[str,Any]=field(default_factory=dict)
    priority_rules:list[dict[str,Any]]=field(default_factory=list); fallback_rules:list[dict[str,Any]]=field(default_factory=lambda:[{"action_type":"basic_attack"},{"action_type":"wait"}])
    tags:list[str]=field(default_factory=list); plugin_data:dict[str,Any]=field(default_factory=dict); version:str="1.0.0"
    @classmethod
    def from_dict(cls, raw):
        data={k:raw.get(k) for k in cls.__dataclass_fields__ if k in raw}; data.setdefault("name", raw.get("id","")); return cls(**data)
    def to_dict(self): return asdict(self)

@dataclass
class CombatActionCandidate:
    candidate_id:str; actor_id:str; action_type:str; ability_id:str=""; target_id:str=""; priority:int=100; score:float=0.0; valid:bool=True
    invalid_reasons:list[str]=field(default_factory=list); resource_status:dict[str,Any]=field(default_factory=dict); cooldown_status:dict[str,Any]=field(default_factory=dict)
    range_status:dict[str,Any]=field(default_factory=dict); target_status:dict[str,Any]=field(default_factory=dict); state_status:dict[str,Any]=field(default_factory=dict)
    behavior_rule_id:str=""; trace:list[dict[str,Any]]=field(default_factory=list); metadata:dict[str,Any]=field(default_factory=dict)
    def to_dict(self): return asdict(self)

class CombatBehaviorRegistry:
    def __init__(self, package:Any|None=None, records:dict[str,list[dict[str,Any]]]|None=None):
        records=records or {}; get=lambda n: list(records.get(n) or getattr(package,n,[]) or [])
        base=[p.to_dict() for p in default_profiles()]
        self.profiles={p.id:p for p in [CombatBehaviorProfile.from_dict(x) for x in base + get("combat_behavior_profiles") if isinstance(x,dict) and x.get("id")]}
        self.combat_groups={str(x.get("id")):x for x in get("combat_groups") if isinstance(x,dict) and x.get("id")}
    def get(self, pid): return self.profiles.get(pid) or self.safe_default({})
    def safe_default(self, actor_or_data:Any):
        data = actor_or_data if isinstance(actor_or_data,dict) else getattr(actor_or_data,"plugin_data",{}) or {}
        tags=set(data.get("tags") or getattr(actor_or_data,"plugin_data",{}).get("tags",[]) or [])
        role=str(data.get("role") or getattr(actor_or_data,"builder_metadata",{}).get("role","")).lower()
        if "training" in tags: return self.get("training_dummy_passive")
        if "guard" in tags or role=="guard": return self.get("town_guard_defender")
        if "pet" in tags: return self.get("pet_default")
        if "summon" in tags: return self.get("summon_default")
        if "animal" in tags: return self.get("animal_brute")
        if "hostile" in tags or "mob" in tags: return self.get("brute_default")
        return self.get("civilian_safe")
    def validate_profile(self,p):
        errors=[]; warnings=[]
        if not SAFE_ID.fullmatch(p.id): errors.append(f"behavior profile ID unsafe: {p.id}")
        if p.behavior_role not in BEHAVIOR_ROLES: errors.append(f"behavior {p.id} unknown role: {p.behavior_role}")
        ap=str((p.aggression_policy or {}).get("type", p.aggression_policy if isinstance(p.aggression_policy,str) else "defensive_only"))
        if ap not in AGGRESSION_POLICIES: errors.append(f"behavior {p.id} unknown aggression policy: {ap}")
        tp=str((p.threat_policy or {}).get("type", "highest"))
        if tp not in THREAT_POLICIES: errors.append(f"behavior {p.id} unknown threat policy: {tp}")
        if not p.fallback_rules: warnings.append(f"behavior {p.id} has no fallback action")
        if p.behavior_role=="civilian" and ap in {"always","territorial","hostile_tags"} and not p.plugin_data.get("acknowledge_unconditional_aggression"):
            errors.append(f"civilian behavior {p.id} has unconditional aggression")
        return errors,warnings
    def validate(self):
        out=[]
        for p in self.profiles.values(): out.extend(self.validate_profile(p)[0])
        return out

class ThreatService:
    def __init__(self, db_path:Path|str|None=None, world_id:str="", event_bus:Any|None=None):
        self.db_path=Path(db_path) if db_path else None; self.world_id=world_id; self.event_bus=event_bus; self.memory={}
        if self.db_path: init_combat_behavior_schema(self.db_path)
    def add_threat(self, owner_actor_id, target_actor_id, amount, source="custom", world_time:int=0):
        amt=max(0.0,min(1_000_000.0,finite(amount))); key=(owner_actor_id,target_actor_id); cur=self.memory.get(key,{"threat_value":0,"metadata":{}}); cur["threat_value"]+=amt; cur[source+"_threat"]=cur.get(source+"_threat",0)+amt; self.memory[key]=cur
        if self.db_path:
            tid=f"thr_{self.world_id}_{owner_actor_id}_{target_actor_id}"; ts=now(); col={"damage":"damage_threat","healing":"healing_threat","control":"control_threat","proximity":"proximity_threat","scripted":"scripted_threat"}.get(source,"scripted_threat")
            with sqlite3.connect(self.db_path) as c:
                c.execute("INSERT OR IGNORE INTO actor_threat_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,self.world_id,"actor",owner_actor_id,"actor",target_actor_id,0,0,0,0,0,0,0,world_time,None,1,ts,ts,"{}"))
                c.execute(f"UPDATE actor_threat_entries SET threat_value=MIN(1000000,threat_value+?), {col}=MIN(1000000,{col}+?), last_updated_world_time=?, updated_at=? WHERE world_id=? AND owner_actor_id=? AND target_actor_id=?",(amt,amt,world_time,ts,self.world_id,owner_actor_id,target_actor_id))
        self._pub("threat_added", {"owner_actor_id":owner_actor_id,"target_actor_id":target_actor_id,"amount":amt,"source":source}); return self.get_actor_threat_table(owner_actor_id)
    def set_threat(self, owner_actor_id,target_actor_id,amount,source="custom"):
        self.remove_threat(owner_actor_id,target_actor_id); return self.add_threat(owner_actor_id,target_actor_id,amount,source)
    def remove_threat(self, owner_actor_id,target_actor_id):
        self.memory.pop((owner_actor_id,target_actor_id),None)
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("UPDATE actor_threat_entries SET active=0, updated_at=? WHERE world_id=? AND owner_actor_id=? AND target_actor_id=?",(now(),self.world_id,owner_actor_id,target_actor_id))
        self._pub("threat_removed", {"owner_actor_id":owner_actor_id,"target_actor_id":target_actor_id})
    def clear_actor_threat(self, actor_id):
        for k in list(self.memory):
            if k[0]==actor_id: self.memory.pop(k,None)
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("UPDATE actor_threat_entries SET active=0, updated_at=? WHERE world_id=? AND owner_actor_id=?",(now(),self.world_id,actor_id))
    def get_actor_threat_table(self, actor_id):
        rows=[]
        if self.db_path:
            with sqlite3.connect(self.db_path) as c:
                for r in c.execute("SELECT target_actor_id, threat_value, damage_threat, healing_threat, control_threat, proximity_threat, scripted_threat FROM actor_threat_entries WHERE world_id=? AND owner_actor_id=? AND active=1 ORDER BY threat_value DESC,target_actor_id",(self.world_id,actor_id)):
                    rows.append({"target_actor_id":r[0],"threat_value":r[1],"damage_threat":r[2],"healing_threat":r[3],"control_threat":r[4],"proximity_threat":r[5],"scripted_threat":r[6]})
        else:
            rows=[{"target_actor_id":t,"threat_value":v.get("threat_value",0),**{k:v.get(k,0) for k in ("damage_threat","healing_threat","control_threat","proximity_threat","scripted_threat")}} for (o,t),v in self.memory.items() if o==actor_id]
            rows.sort(key=lambda r:(-r["threat_value"],r["target_actor_id"]))
        return rows
    def get_highest_threat_target(self, actor_id):
        rows=self.get_actor_threat_table(actor_id); return rows[0]["target_actor_id"] if rows else ""
    def decay_threat(self, actor_id, elapsed_world_time): return self.get_actor_threat_table(actor_id)
    def _pub(self,n,p):
        if self.event_bus: self.event_bus.publish(n,p,source_system="combat_behavior",world_id=self.world_id)

class HostilityService:
    def __init__(self, actors:dict[str,Actor], registry:CombatBehaviorRegistry|None=None, threat:ThreatService|None=None, rooms:dict[str,Any]|None=None, event_bus:Any|None=None):
        self.actors=actors; self.registry=registry or CombatBehaviorRegistry(); self.threat=threat; self.rooms=rooms or {}; self.event_bus=event_bus
    def evaluate_hostility(self, observer_actor_id, target_actor_id):
        trace=[]; o=self.actors.get(observer_actor_id); t=self.actors.get(target_actor_id)
        if not o or not t: return {"result":"forbidden","reason_codes":["actor_missing"],"source_rules":[],"trace":[{"rule":"actor_exists","ok":False}]}
        if observer_actor_id==target_actor_id: return {"result":"friendly","reason_codes":["self"],"source_rules":["self"],"trace":trace}
        if t.lifecycle_state not in {"alive","active",""}: return {"result":"forbidden","reason_codes":["target_not_alive"],"source_rules":["lifecycle"],"trace":trace}
        if o.identity.current_location and t.identity.current_location and o.identity.current_location != t.identity.current_location:
            return {"result":"forbidden","reason_codes":["not_same_room"],"source_rules":["awareness"],"trace":trace}
        if self._safe_room(o.identity.current_location): return {"result":"forbidden","reason_codes":["safe_room"],"source_rules":["room_flags"],"trace":trace}
        rel=(o.relationship_profile or {}).get(target_actor_id) or (o.relationship_profile or {}).get("relationships",{}).get(target_actor_id)
        if rel in {"enemy","hostile"}: res="hostile"; reasons=["explicit_enemy_relationship"]
        elif rel in {"ally","friend","friendly"}: res="friendly"; reasons=["explicit_friendly_relationship"]
        elif self.threat and any(r["target_actor_id"]==target_actor_id for r in self.threat.get_actor_threat_table(observer_actor_id)): res="hostile"; reasons=["active_threat"]
        else:
            prof=self.registry.get((o.combat_profile or {}).get("combat_behavior_profile_id") or (o.plugin_data or {}).get("combat_behavior_profile_id") or "")
            pol=str((prof.aggression_policy or {}).get("type","defensive_only")); ttags=set((t.plugin_data or {}).get("tags",[]) or []) | set((t.builder_metadata or {}).get("tags",[]) or [])
            if pol=="always": res="hostile"; reasons=["aggression_always"]
            elif pol=="hostile_tags" and ttags & set((prof.aggression_policy or {}).get("tags",["hostile","intruder"])): res="hostile"; reasons=["hostile_tag_match"]
            else: res="neutral"; reasons=["no_hostility_rule"]
        out={"result":res,"reason_codes":reasons,"source_rules":reasons,"trace":trace+[ {"rule":"final","result":res,"reasons":reasons} ]}
        if self.event_bus: self.event_bus.publish("hostility_evaluated", {"observer_actor_id":observer_actor_id,"target_actor_id":target_actor_id,**out}, source_system="combat_behavior")
        return out
    def list_hostile_targets(self, actor_id): return [aid for aid in sorted(self.actors) if self.evaluate_hostility(actor_id,aid)["result"]=="hostile"]
    def can_actor_attack(self, actor_id,target_actor_id): return self.evaluate_hostility(actor_id,target_actor_id)["result"]=="hostile"
    def _safe_room(self,rid):
        room=self.rooms.get(rid,{}) if rid else {}; return "safe" in (room.get("flags") or []) or bool(room.get("safe_room"))

class CombatBehaviorService:
    def __init__(self, actors:dict[str,Actor]|None=None, package:Any|None=None, db_path:Path|str|None=None, ability_service:AbilityExecutionService|None=None, event_bus:Any|None=None, rooms:dict[str,Any]|None=None, world_id:str=""):
        self.actors=actors or {}; self.registry=CombatBehaviorRegistry(package); self.world_id=world_id or getattr(package,"id",""); self.event_bus=event_bus; self.rooms=rooms or {r.get("id"):r for r in getattr(package,"rooms",[]) or []}
        self.threat=ThreatService(db_path,self.world_id,event_bus); self.hostility=HostilityService(self.actors,self.registry,self.threat,self.rooms,event_bus); self.ability_service=ability_service; self.combat=CombatEngine(content=getattr(ability_service,"combat",None).content if ability_service else None); self.state={}
    def register_actor(self, actor): self.actors[actor.actor_id]=actor; return actor
    def get_actor_combat_behavior(self, actor_id):
        a=self.actors.get(actor_id); pid=((a.plugin_data or {}).get("combat_behavior_profile_id") or (a.combat_profile or {}).get("combat_behavior_profile_id") or (a.combat_profile or {}).get("behavior_profile_id")) if a else ""
        return self.registry.get(pid) if pid else self.registry.safe_default(a or {})
    def trace_actor_combat_behavior(self, actor_id):
        p=self.get_actor_combat_behavior(actor_id); return {"actor_id":actor_id,"behavior_profile_id":p.id,"profile":p.to_dict(),"resolution_priority":["actor_instance_override","spawn_override","entity_template","combat_profile","safe_default"]}
    def scan_actor_combat_awareness(self, actor_id):
        a=self.actors.get(actor_id); targets=[]
        if not a: return {"actor_id":actor_id,"aware":False,"targets":[],"trace":["actor missing"]}
        for tid,t in self.actors.items():
            if tid==actor_id: continue
            if a.identity.current_location and t.identity.current_location and a.identity.current_location!=t.identity.current_location: continue
            h=self.hostility.evaluate_hostility(actor_id,tid)
            if h["result"]=="hostile":
                th=next((r["threat_value"] for r in self.threat.get_actor_threat_table(actor_id) if r["target_actor_id"]==tid),0)
                targets.append({"actor_id":tid,"threat":th,"hostility":h})
        targets.sort(key=lambda x:(-x["threat"], x["actor_id"]))
        return {"actor_id":actor_id,"aware":bool(targets),"targets":targets,"ordering":["current_attacker","threat","protection_violation","hostility_priority","actor_id"]}
    def evaluate_room_combat_awareness(self, room_id): return [self.scan_actor_combat_awareness(aid) for aid,a in sorted(self.actors.items()) if a.identity.current_location==room_id]
    def evaluate_world_combat_awareness(self, world_id=None): return [self.scan_actor_combat_awareness(aid) for aid in sorted(self.actors)]
    def select_target(self, actor_id):
        cur=self.threat.get_highest_threat_target(actor_id)
        if cur and cur in self.actors: return cur
        aw=self.scan_actor_combat_awareness(actor_id); return aw["targets"][0]["actor_id"] if aw["targets"] else ""
    def build_combat_action_candidates(self, actor_id):
        a=self.actors.get(actor_id); p=self.get_actor_combat_behavior(actor_id); target=self.select_target(actor_id); out=[]
        if not a: return []
        hp=pct(a.resources.health,a.resources.maximum_health)
        flee=p.flee_policy or {}; surrender=p.surrender_policy or {}
        if flee.get("enabled") and hp <= finite(flee.get("health_threshold_percent",0),0): out.append(CombatActionCandidate(f"{actor_id}:flee",actor_id,"flee",target_id=target,priority=int(flee.get("priority",5)),trace=[{"reason":"health_threshold","health_percent":hp}]))
        stype=str(surrender.get("type","never"));
        if stype in {"low_health","civilian_default"} and hp <= finite(surrender.get("health_threshold_percent",25),25): out.append(CombatActionCandidate(f"{actor_id}:surrender",actor_id,"surrender",target_id=target,priority=8,trace=[{"reason":"surrender_policy","health_percent":hp}]))
        if self.ability_service:
            self.ability_service.register_actor(a)
            for row in self.ability_service.get_actor_abilities(actor_id):
                aid=row["id"]; tr=self.ability_service.trace_ability(actor_id,aid,target or actor_id); atype="heal" if row.get("healing_components") or row.get("ability_type")=="heal" else ("buff" if row.get("ability_type")=="buff" else "ability")
                valid=bool(tr.get("ok")); out.append(CombatActionCandidate(f"{actor_id}:ability:{aid}:{target}",actor_id,atype,aid,target or actor_id,priority=self._ability_priority(row,p),valid=valid,invalid_reasons=[str(e.get("step")) for e in tr.get("errors",[])],resource_status={"trace":tr.get("costs",[])},cooldown_status=tr.get("cooldowns",{}),target_status=tr.get("targets",{}),trace=tr.get("trace",[])))
        if target:
            can=self.hostility.can_actor_attack(actor_id,target); out.append(CombatActionCandidate(f"{actor_id}:basic_attack:{target}",actor_id,"basic_attack",target_id=target,priority=80,valid=can,invalid_reasons=[] if can else ["target_not_hostile"]))
        out.append(CombatActionCandidate(f"{actor_id}:wait",actor_id,"wait",priority=999,score=0,valid=True))
        out.sort(key=self._candidate_key); 
        if self.event_bus: self.event_bus.publish("combat_candidates_built", {"actor_id":actor_id,"count":len(out)}, source_system="combat_behavior")
        return out
    def _ability_priority(self,row,p):
        if row.get("healing_components") or row.get("ability_type")=="heal": return 20
        if row.get("ability_type")=="buff": return 60
        return 50
    def select_combat_action(self, actor_id, candidates=None):
        candidates=candidates or self.build_combat_action_candidates(actor_id); valid=[c for c in candidates if c.valid]
        choice=(valid or candidates)[0] if candidates else None
        if self.event_bus and choice: self.event_bus.publish("combat_action_selected", choice.to_dict(), source_system="combat_behavior")
        return choice
    def execute_selected_combat_action(self, actor_id, action):
        if not action: return {"ok":False,"message":"no action"}
        a=self.actors.get(actor_id); t=self.actors.get(action.target_id)
        if action.action_type in {"ability","heal","buff","debuff"} and self.ability_service: res=self.ability_service.start_ability(actor_id,action.ability_id,action.target_id)
        elif action.action_type=="basic_attack" and a and t: res=asdict(self.combat.resolve_attack(a,t))
        elif action.action_type=="flee": res={"ok":True,"action":"flee","message":"flee intent recorded"}; a.combat_profile["combat_state"]="fleeing"
        elif action.action_type=="surrender": res={"ok":True,"action":"surrender","message":"surrender intent recorded"}; a.combat_profile["combat_state"]="surrendering"
        else: res={"ok":True,"action":action.action_type}
        if self.event_bus: self.event_bus.publish("combat_action_executed" if res.get("ok",True) else "combat_action_failed", {"actor_id":actor_id,"action":action.to_dict(),"result":res}, source_system="combat_behavior")
        return res
    def evaluate_actor_combat_behavior(self, actor_id, world_time:int=0):
        c=self.build_combat_action_candidates(actor_id); a=self.select_combat_action(actor_id,c); return self.execute_selected_combat_action(actor_id,a)
    def evaluate_world_combat_behavior(self, world_id=None, world_time:int=0): return [self.evaluate_actor_combat_behavior(aid,world_time) for aid in sorted(self.actors) if self.actors[aid].actor_type!="player"]
    def trace_combat_decision(self, actor_id):
        c=self.build_combat_action_candidates(actor_id); s=self.select_combat_action(actor_id,c); return {"actor_id":actor_id,"behavior":self.trace_actor_combat_behavior(actor_id),"awareness":self.scan_actor_combat_awareness(actor_id),"threat_table":self.threat.get_actor_threat_table(actor_id),"current_target":self.select_target(actor_id),"candidates":[x.to_dict() for x in c],"selected_action":s.to_dict() if s else None,"tie_breaking":["priority","score","action_type_order","ability_id","target_id","candidate_id"]}
    trace_actor_combat_decision=trace_combat_decision
    def _candidate_key(self,c): return (c.priority, -c.score, ACTION_TYPES.index(c.action_type) if c.action_type in ACTION_TYPES else 99, c.ability_id, c.target_id, c.candidate_id)

def default_profiles():
    def P(id,name,role,agg,**kw): return CombatBehaviorProfile(id=id,name=name,behavior_role=role,aggression_policy={"type":agg},**kw)
    return [
        P("civilian_safe","Civilian Safe","civilian","never",flee_policy={"enabled":True,"health_threshold_percent":90,"surrender_if_no_exit":True,"priority":5},surrender_policy={"type":"civilian_default","health_threshold_percent":30},call_for_help_policy={"enabled":True,"maximum_room_distance":0},fallback_rules=[{"action_type":"flee"},{"action_type":"surrender"},{"action_type":"wait"}]),
        P("town_guard_defender","Town Guard Defender","guardian","protective",assist_policy={"type":"guard"},protect_policy={"rooms":[],"actors":[]}),
        P("rat_aggressive","Rat Aggressive","animal","always",tags=["animal","hostile"]),
        P("wolf_pack","Wolf Pack","pack_hunter","always",assist_policy={"type":"pack"},pursuit_policy={"type":"leash_distance","maximum_depth":1,"leash_distance":2}),
        P("healer_support","Healer Support","healer","defensive_only",ability_selection_policy={"prefer":"healing"}),
        P("training_dummy_passive","Training Dummy Passive","training_target","never",flee_policy={"enabled":False},call_for_help_policy={"enabled":False}),
        P("apprentice_mage_defensive","Apprentice Mage Defensive","caster","defensive_only"),
        P("brute_default","Brute Default","brute","defensive_only"), P("animal_brute","Animal Brute","animal","defensive_only"), P("pet_default","Pet Default","pet","defensive_only"), P("summon_default","Summon Default","summon","defensive_only")]

# Compatibility free functions used by diagnostics/tests.
_default_service=CombatBehaviorService()
def get_actor_combat_behavior(actor_id): return _default_service.get_actor_combat_behavior(actor_id)
def trace_actor_combat_behavior(actor_id): return _default_service.trace_actor_combat_behavior(actor_id)
def evaluate_hostility(observer_actor_id,target_actor_id): return _default_service.hostility.evaluate_hostility(observer_actor_id,target_actor_id)
def list_hostile_targets(actor_id): return _default_service.hostility.list_hostile_targets(actor_id)
def can_actor_attack(actor_id,target_actor_id): return _default_service.hostility.can_actor_attack(actor_id,target_actor_id)
def scan_actor_combat_awareness(actor_id): return _default_service.scan_actor_combat_awareness(actor_id)
def build_combat_action_candidates(actor_id): return _default_service.build_combat_action_candidates(actor_id)
def select_combat_action(actor_id,candidates=None): return _default_service.select_combat_action(actor_id,candidates)
def execute_selected_combat_action(actor_id,action): return _default_service.execute_selected_combat_action(actor_id,action)
def trace_combat_decision(actor_id): return _default_service.trace_combat_decision(actor_id)
