"""Phase 5F canonical body, equipment ownership, lifecycle, and population services.

This layer is deterministic data architecture only. It deliberately does not
implement combat, damage, AI combat, loot tables, skills, spells, crafting, or
economy behavior.
"""
from __future__ import annotations

import json, sqlite3, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIFECYCLE_STATES=("not_spawned","queued","spawned","alive","unconscious","dead","corpse","despawned","respawn_queue")
SPAWN_POLICIES={"once","persistent_unique","maintain_population","respawn_after_delay","scheduled","disabled","manual_only","world_event"}

@dataclass(frozen=True)
class BodySlot:
    id: str
    display_name: str
    order: int
    visible: bool=True
    allowed_item_categories: list[str]=field(default_factory=list)
    allows_multiple: bool=False
    exclusive_with: list[str]=field(default_factory=list)
    future_hit_location: dict[str,Any]=field(default_factory=dict)
    metadata: dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class BodyProfile:
    id: str
    display_name: str
    slots: list[BodySlot]
    metadata: dict[str,Any]=field(default_factory=dict)

    @classmethod
    def from_dict(cls,d:dict[str,Any])->"BodyProfile":
        slots=[BodySlot(id=str(s.get("id")), display_name=str(s.get("display_name") or s.get("name") or s.get("id")), order=int(s.get("order", s.get("sort_order", i*10))), visible=bool(s.get("visible", True)), allowed_item_categories=list(s.get("allowed_item_categories") or s.get("allows_item_types") or []), allows_multiple=bool(s.get("allows_multiple", False)), exclusive_with=list(s.get("exclusive_with") or []), future_hit_location=dict(s.get("future_hit_location") or {}), metadata=dict(s.get("metadata") or s.get("plugin_data") or {})) for i,s in enumerate(d.get("slots") or [])]
        return cls(str(d.get("id")), str(d.get("display_name") or d.get("name") or d.get("id")), sorted(slots,key=lambda s:(s.order,s.id)), dict(d.get("metadata") or {}))

    def to_dict(self)->dict[str,Any]: return asdict(self)
    def slot_ids(self)->list[str]: return [s.id for s in self.slots if s.visible]


def default_body_profiles()->list[BodyProfile]:
    def p(pid,names):
        return BodyProfile(pid, pid.replace('_',' ').title(), [BodySlot(sid, name, i*10, allowed_item_categories=cats) for i,(sid,name,cats) in enumerate(names)])
    armor=["armor","clothing"]; weapon=["weapon"]; trinket=["trinket","jewelry"]
    return [
        p("humanoid",[("head","Head",armor),("face","Face",armor),("neck","Neck",trinket),("shoulders","Shoulders",armor),("back","Back",armor+["container"]),("chest","Chest",armor),("arms","Arms",armor),("wrists","Wrists",armor+trinket),("hands","Hands",armor),("finger_left","Finger Left",trinket),("finger_right","Finger Right",trinket),("waist","Waist",armor),("legs","Legs",armor),("feet","Feet",armor),("main_hand","Main Hand",weapon),("off_hand","Off Hand",weapon+["shield","trinket"]),("accessory_1","Accessory 1",trinket),("accessory_2","Accessory 2",trinket),("light","Light",["light","tool","trinket"])]),
        p("wolf",[("head","Head",armor),("body","Body",armor),("collar","Collar",trinket),("front_legs","Front Legs",armor),("rear_legs","Rear Legs",armor),("tail","Tail",trinket)]),
        p("dragon",[("head","Head",armor),("neck","Neck",armor),("body","Body",armor),("left_wing","Left Wing",armor),("right_wing","Right Wing",armor),("tail","Tail",armor),("front_claws","Front Claws",weapon),("rear_claws","Rear Claws",weapon)]),
        p("spider",[("head","Head",armor),("thorax","Thorax",armor),("abdomen","Abdomen",armor),*((f"leg_{i}",f"Leg {i}",armor) for i in range(1,9))]),
        p("ghost",[("essence","Essence",trinket),("aura","Aura",trinket),("focus","Focus",trinket)]),
        p("elemental",[("core","Core",trinket),("aura","Aura",trinket)]),
    ]

class BodyProfileRegistry:
    def __init__(self,profiles:list[dict[str,Any]]|None=None):
        source=profiles or [p.to_dict() for p in default_body_profiles()]
        self.profiles={p.id:p for p in (BodyProfile.from_dict(x) for x in source)}
    def get(self,pid:str|None)->BodyProfile: return self.profiles.get(pid or "humanoid") or self.profiles["humanoid"]
    def validate(self)->list[str]:
        errors=[]
        for p in self.profiles.values():
            seen=set()
            for s in p.slots:
                if s.id in seen: errors.append(f"{p.id}: duplicate slot {s.id}")
                seen.add(s.id)
        return errors

def item_occupancy(item_template:dict[str,Any])->list[str]:
    occ=item_template.get("occupies_slots") or item_template.get("occupancy") or item_template.get("equipment_slots") or item_template.get("wear_slots") or []
    return [str(s) for s in ([occ] if isinstance(occ,str) else occ)]

def validate_item_occupancy(profile:BodyProfile, item_template:dict[str,Any])->list[str]:
    slots=set(profile.slot_ids()); occ=item_occupancy(item_template); errors=[]
    if not occ: errors.append("item declares no occupancy")
    for s in occ:
        if s not in slots: errors.append(f"slot {s} is not in body profile {profile.id}")
    return errors

def ensure_lifecycle_schema(db_path:Path)->None:
    with sqlite3.connect(db_path) as con:
        con.executescript("""
CREATE TABLE IF NOT EXISTS actor_lifecycle(actor_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,state TEXT,body_profile_id TEXT,lifecycle_profile_id TEXT,spawn_definition_id TEXT,room_id TEXT,updated_world_time INTEGER,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS corpse_instances(corpse_id TEXT PRIMARY KEY,world_id TEXT,source_actor_id TEXT,owner_actor_id TEXT,room_id TEXT,created_world_time INTEGER,despawn_world_time INTEGER,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS respawn_queue(respawn_id TEXT PRIMARY KEY,world_id TEXT,spawn_definition_id TEXT,actor_id TEXT,room_id TEXT,due_world_time INTEGER,policy TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS population_instances(instance_id TEXT PRIMARY KEY,world_id TEXT,spawn_definition_id TEXT,actor_id TEXT,template_id TEXT,room_id TEXT,state TEXT,unique_key TEXT,created_world_time INTEGER,metadata_json TEXT);
""")

class ActorLifecycleManager:
    def __init__(self,db_path:Path, world_id:str=""):
        self.db_path=Path(db_path); self.world_id=world_id; ensure_lifecycle_schema(self.db_path)
    def set_state(self,actor_id:str,state:str,*,actor_type="npc",body_profile_id="humanoid",room_id="",world_time:int=0,spawn_definition_id="",metadata=None):
        if state not in LIFECYCLE_STATES: raise ValueError(f"invalid lifecycle state: {state}")
        with sqlite3.connect(self.db_path) as con: con.execute("REPLACE INTO actor_lifecycle VALUES(?,?,?,?,?,?,?,?,?,?)",(actor_id,self.world_id,actor_type,state,body_profile_id,"default",spawn_definition_id,room_id,int(world_time),json.dumps(metadata or {})))
        return self.get(actor_id)
    def get(self,actor_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM actor_lifecycle WHERE actor_id=?",(actor_id,)).fetchone(); return dict(r) if r else None
    def actor_died(self,actor_id:str,room_id:str,world_time:int=0,respawn_delay:int|None=None,spawn_definition_id:str=""):
        self.set_state(actor_id,"dead",room_id=room_id,world_time=world_time,spawn_definition_id=spawn_definition_id)
        cid=f"corpse_{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO corpse_instances VALUES(?,?,?,?,?,?,?,?)",(cid,self.world_id,actor_id,actor_id,room_id,int(world_time),None,json.dumps({"loot_owner":"corpse","loot_not_implemented":True})))
        self.set_state(actor_id,"corpse",room_id=room_id,world_time=world_time,spawn_definition_id=spawn_definition_id,metadata={"corpse_id":cid})
        if respawn_delay is not None: self.queue_respawn(spawn_definition_id, actor_id, room_id, int(world_time)+int(respawn_delay), "respawn_after_delay")
        return {"corpse_id":cid,"actor_id":actor_id}
    def queue_respawn(self,spawn_definition_id,actor_id,room_id,due_world_time,policy):
        rid=f"respawn_{uuid.uuid4().hex}"
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO respawn_queue VALUES(?,?,?,?,?,?,?,?)",(rid,self.world_id,spawn_definition_id,actor_id,room_id,int(due_world_time),policy,json.dumps({})))
        return rid
    def respawn_due(self,world_time:int):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM respawn_queue WHERE world_id=? AND due_world_time<=? ORDER BY due_world_time,respawn_id",(self.world_id,int(world_time)))]

class PopulationManager:
    def __init__(self,db_path:Path, world_id:str, definitions:list[dict[str,Any]]|None=None):
        self.db_path=Path(db_path); self.world_id=world_id; self.definitions=definitions or []; ensure_lifecycle_schema(self.db_path); self.lifecycle=ActorLifecycleManager(db_path,world_id)
    def validate(self)->list[str]:
        errors=[]
        for d in self.definitions:
            if d.get("spawn_policy") not in SPAWN_POLICIES: errors.append(f"{d.get('id')}: invalid spawn_policy")
            if not d.get("id"): errors.append("population definition missing id")
        return errors
    def startup(self,world_time:int=0):
        spawned=[]
        for d in sorted(self.definitions,key=lambda x:str(x.get("id"))):
            if d.get("spawn_policy") in {"disabled","manual_only","scheduled","world_event"}: continue
            spawned.extend(self.maintain_definition(d,world_time))
        return spawned
    def maintain_definition(self,d:dict[str,Any],world_time:int=0):
        target=int(d.get("target_population", d.get("maximum_population", d.get("spawn_count",1))) or 1)
        if d.get("spawn_policy") in {"once","persistent_unique"}: target=1
        existing=self.instances(d.get("id"))
        if d.get("spawn_policy")=="persistent_unique" and existing: return []
        made=[]
        for _ in range(max(0,target-len([e for e in existing if e.get("state") in {"spawned","alive"}]))):
            iid=f"pop_{uuid.uuid4().hex}"; actor_id=d.get("actor_id") or f"actor_{uuid.uuid4().hex}"; room=d.get("room_id") or d.get("spawn_room") or ""
            with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO population_instances VALUES(?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,d.get("id"),actor_id,d.get("template_id") or d.get("npc_id") or "",room,"alive",d.get("unique_key") or (actor_id if d.get("spawn_policy")=="persistent_unique" else ""),int(world_time),json.dumps(d.get("metadata") or {})))
            self.lifecycle.set_state(actor_id,"alive",room_id=room,world_time=world_time,spawn_definition_id=d.get("id"),body_profile_id=d.get("body_profile_id","humanoid"))
            made.append({"instance_id":iid,"actor_id":actor_id,"room_id":room})
        return made
    def instances(self,spawn_definition_id:str|None=None):
        where="world_id=?"+(" AND spawn_definition_id=?" if spawn_definition_id else ""); params=(self.world_id,spawn_definition_id) if spawn_definition_id else (self.world_id,)
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute(f"SELECT * FROM population_instances WHERE {where} ORDER BY created_world_time,instance_id",params)]
