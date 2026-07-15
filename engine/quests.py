"""Phase 8A canonical quest, conversation, and world-state foundations.

This module is intentionally conservative: quest definitions are data, runtime
state is SQLite-authoritative, objectives consume stable EventBus-style events
idempotently, rewards are handed to RewardService, and world-state mutations go
through WorldStateService. Unsupported custom behavior is validated/rejected; no
arbitrary Python or command execution is supported.
"""
from __future__ import annotations

import hashlib, json, re, sqlite3, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
QUEST_TYPES = {"story","side","task","tutorial","contract","bounty","profession","exploration","investigation","delivery","escort_placeholder","world_event","repeatable","custom"}
TERMINAL_STATES = {"none","completed","failed","cancelled"}
OBJECTIVE_TYPES = {"kill_actor","kill_template","kill_tag","collect_item","possess_item","deliver_item","give_item","use_item","equip_item","craft_item","craft_recipe","harvest_resource","interact_feature","enter_room","visit_zone","visit_area","speak_to_actor","conversation_complete","use_ability","apply_effect","remove_effect","gain_level","gain_profession_rank","earn_currency","spend_currency","purchase_item","sell_item","complete_quest","world_state_equals","survive_time","wait_until_world_time","protect_actor_placeholder","escort_actor_placeholder","custom"}
PROGRESS_MODES = {"increment","set","binary","unique_targets","unique_instances","accumulate_amount","maintain_state","timed","sequence","custom"}
QUEST_STATUSES = {"offered","accepted","active","ready_to_turn_in","completed_pending_reward","completed","failed","abandoned","expired","cancelled"}
SUPPORTED_ACTION_TYPES = {"offer_quest","accept_quest","advance_stage","complete_quest","fail_quest","set_world_state","increment_world_state","grant_reward","publish_event","start_conversation","turn_in_quest","custom"}
WORLD_STATE_SCOPES = {"world","area","zone","room","feature","actor","quest_instance","organization","custom"}
WORLD_STATE_VALUE_TYPES = {"boolean","integer","decimal","string","id","list","map","custom"}
COLLECTIONS = ["quest_definitions","quest_series","quest_chapters","quest_stages","quest_objectives","quest_availability_profiles","quest_acceptance_profiles","quest_repeat_policies","quest_failure_profiles","quest_abandon_profiles","quest_sharing_profiles","quest_action_definitions","conversation_definitions","conversation_nodes","conversation_choices","conversation_conditions","conversation_actions","quest_message_profiles","quest_time_limit_profiles","world_state_definitions"]
EVENT_OBJECTIVE_TYPES = {
    "actor_killed":{"kill_actor","kill_template","kill_tag"}, "actor_died":{"kill_actor","kill_template","kill_tag"}, "enemy_killed":{"kill_actor","kill_template","kill_tag"},
    "item_received":{"collect_item","possess_item"}, "item_picked_up":{"collect_item","possess_item"}, "item_collected":{"collect_item","possess_item"}, "quest_item_obtained":{"collect_item","possess_item"}, "corpse_looted":{"collect_item","possess_item","custom"}, "item_delivered":{"deliver_item"}, "item_given":{"give_item"}, "item_used":{"use_item"}, "item_equipped":{"equip_item"},
    "room_entered":{"enter_room"}, "zone_entered":{"visit_zone"}, "area_entered":{"visit_area"}, "feature_interacted":{"interact_feature"},
    "conversation_completed":{"conversation_complete","speak_to_actor"}, "ability_completed":{"use_ability"}, "ability_effect_applied":{"apply_effect"}, "ability_effect_removed":{"remove_effect"},
    "craft_job_completed":{"craft_recipe"}, "crafted_item_created":{"craft_item","craft_recipe"}, "resource_node_harvested":{"harvest_resource"}, "resource_gathered":{"harvest_resource","collect_item","possess_item"}, "profession_rank_increased":{"gain_profession_rank"}, "actor_leveled_up":{"gain_level"},
    "currency_credited":{"earn_currency"}, "currency_debited":{"spend_currency"}, "shop_item_purchased":{"purchase_item"}, "shop_item_sold":{"sell_item"}, "quest_completed":{"complete_quest"}, "world_state_changed":{"world_state_equals"}, "world_time_advanced":{"survive_time","wait_until_world_time"}, "custom":{"custom"}
}

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def safe_id(v: Any) -> bool: return bool(v and SAFE_ID_RE.fullmatch(str(v)))
def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v: Any, default: Any=None) -> Any:
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

def _items(raw: Any, key: str) -> list[dict[str, Any]]:
    data = raw.get(key, raw) if isinstance(raw, dict) else raw
    if isinstance(data, dict): return [dict(v, id=v.get("id", k)) if isinstance(v, dict) else {"id": k} for k,v in data.items()]
    return [x for x in (data or []) if isinstance(x, dict)]

class QuestContent:
    collections = COLLECTIONS
    def __init__(self, world_root: str|Path="worlds/shattered_realms") -> None:
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}
        self.objectives_by_stage: dict[str,list[dict[str,Any]]] = {}
        for o in self.list("quest_objectives"): self.objectives_by_stage.setdefault(str(o.get("stage_id","")), []).append(o)
    def _load(self, c: str) -> dict[str, dict[str, Any]]:
        paths=(self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json")
        for p in paths:
            if p.exists():
                arr=_items(json.loads(p.read_text(encoding="utf-8")), c)
                return {str(x.get("id")): x for x in arr if x.get("id")}
        return {}
    def get(self, c: str, rid: str|None) -> dict[str,Any]|None: return self.data.get(c,{}).get(str(rid or ""))
    def list(self, c: str) -> list[dict[str,Any]]: return sorted(self.data.get(c,{}).values(), key=lambda r: str(r.get("id","")))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS actor_quest_instances(quest_instance_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,quest_id TEXT,definition_version INTEGER,status TEXT,current_stage_id TEXT,accepted_world_time INTEGER,completed_world_time INTEGER,failed_world_time INTEGER,abandoned_world_time INTEGER,repeat_key TEXT,source_type TEXT,source_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_quest_one_active ON actor_quest_instances(world_id,actor_id,quest_id,repeat_key) WHERE status IN ('offered','accepted','active','ready_to_turn_in','completed_pending_reward');
CREATE TABLE IF NOT EXISTS actor_quest_stage_state(stage_state_id TEXT PRIMARY KEY,quest_instance_id TEXT,stage_id TEXT,status TEXT,entered_world_time INTEGER,completed_world_time INTEGER,failed_world_time INTEGER,branch_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS actor_quest_objective_state(objective_state_id TEXT PRIMARY KEY,quest_instance_id TEXT,stage_id TEXT,objective_id TEXT,status TEXT,progress_current REAL,progress_required REAL,progress_json TEXT,started_world_time INTEGER,completed_world_time INTEGER,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_quest_objective_once ON actor_quest_objective_state(quest_instance_id,objective_id);
CREATE TABLE IF NOT EXISTS actor_quest_event_consumption(consumption_id TEXT PRIMARY KEY,quest_instance_id TEXT,objective_id TEXT,event_id TEXT,event_type TEXT,consumed_world_time INTEGER,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_quest_event_once ON actor_quest_event_consumption(quest_instance_id,objective_id,event_id);
CREATE TABLE IF NOT EXISTS actor_quest_history(history_id TEXT PRIMARY KEY,actor_id TEXT,quest_id TEXT,quest_instance_id TEXT,operation TEXT,stage_id TEXT,objective_id TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS actor_quest_offers(offer_id TEXT PRIMARY KEY,actor_id TEXT,quest_id TEXT,source_type TEXT,source_id TEXT,status TEXT,offered_world_time INTEGER,expires_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS actor_quest_timers(timer_id TEXT PRIMARY KEY,quest_instance_id TEXT,stage_id TEXT,objective_id TEXT,timer_type TEXT,started_world_time INTEGER,expires_world_time INTEGER,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS quest_reward_claims(claim_id TEXT PRIMARY KEY,quest_instance_id TEXT,quest_id TEXT,actor_id TEXT,reward_definition_id TEXT,reward_packet_id TEXT,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
"""
WORLD_STATE_SQL = """
CREATE TABLE IF NOT EXISTS world_state_values(world_state_id TEXT PRIMARY KEY,world_id TEXT,scope_type TEXT,scope_id TEXT,state_key TEXT,value_type TEXT,value_json TEXT,version INTEGER,updated_world_time INTEGER,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_world_state_key ON world_state_values(world_id,scope_type,scope_id,state_key);
CREATE TABLE IF NOT EXISTS world_state_history(history_id TEXT PRIMARY KEY,world_state_id TEXT,operation TEXT,old_value_json TEXT,new_value_json TEXT,source_type TEXT,source_id TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
"""

class WorldStateService:
    def __init__(self, db_path: str|Path=":memory:", world_id: str="shattered_realms", event_bus: Any|None=None) -> None:
        self.db_path=str(db_path); self.world_id=world_id; self.event_bus=event_bus; self.ensure_schema()
    def ensure_schema(self):
        with sqlite3.connect(self.db_path) as con: con.executescript(WORLD_STATE_SQL)
    def _type(self, v: Any) -> str:
        if isinstance(v,bool): return "boolean"
        if isinstance(v,int) and not isinstance(v,bool): return "integer"
        if isinstance(v,float): return "decimal"
        if isinstance(v,list): return "list"
        if isinstance(v,dict): return "map"
        return "string"
    def set_state(self, scope_type: str, scope_id: str, key: str, value: Any, *, world_time: int=0, source_type: str="system", source_id: str="") -> dict[str,Any]:
        if scope_type not in WORLD_STATE_SCOPES or not safe_id(key): raise ValueError("invalid world-state scope or key")
        now=utc_now(); wid=stable_id("wstate", self.world_id, scope_type, scope_id, key)
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; old=con.execute("SELECT * FROM world_state_values WHERE world_state_id=?",(wid,)).fetchone(); oldv=old["value_json"] if old else ""; ver=int(old["version"] if old else 0)+1
            con.execute("INSERT OR REPLACE INTO world_state_values VALUES(?,?,?,?,?,?,?,?,?,?,?)",(wid,self.world_id,scope_type,scope_id,key,self._type(value),_json(value),ver,world_time,now,_json({})))
            con.execute("INSERT INTO world_state_history VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("wsh",wid,ver,"set"),wid,"set",oldv,_json(value),source_type,source_id,world_time,now,_json({})))
        self._publish("world_state_changed", {"world_state_id":wid,"scope_type":scope_type,"scope_id":scope_id,"state_key":key,"value":value})
        return self.get_state(scope_type, scope_id, key) or {}
    def increment_state(self, scope_type: str, scope_id: str, key: str, amount: int|float=1, **kw) -> dict[str,Any]:
        cur=self.get_state(scope_type, scope_id, key); val=(cur or {}).get("value",0); return self.set_state(scope_type, scope_id, key, val+amount, **kw)
    def clear_state(self, scope_type: str, scope_id: str, key: str, *, world_time:int=0, source_type:str="system", source_id:str="") -> bool:
        wid=stable_id("wstate", self.world_id, scope_type, scope_id, key); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; old=con.execute("SELECT * FROM world_state_values WHERE world_state_id=?",(wid,)).fetchone()
            if not old: return False
            con.execute("DELETE FROM world_state_values WHERE world_state_id=?",(wid,)); con.execute("INSERT INTO world_state_history VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("wsh",wid,old["version"],"clear"),wid,"clear",old["value_json"],"",source_type,source_id,world_time,now,_json({})))
        self._publish("world_state_cleared", {"world_state_id":wid,"state_key":key}); return True
    def get_state(self, scope_type: str, scope_id: str, key: str) -> dict[str,Any]|None:
        wid=stable_id("wstate", self.world_id, scope_type, scope_id, key)
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM world_state_values WHERE world_state_id=?",(wid,)).fetchone()
        return None if not r else dict(r)|{"value":_loads(r["value_json"], None)}
    def compare_state(self, scope_type: str, scope_id: str, key: str, expected: Any) -> bool:
        s=self.get_state(scope_type, scope_id, key); return (s or {}).get("value") == expected
    def get_state_history(self, scope_type: str, scope_id: str, key: str) -> list[dict[str,Any]]:
        wid=stable_id("wstate", self.world_id, scope_type, scope_id, key)
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM world_state_history WHERE world_state_id=? ORDER BY created_at",(wid,))]
    def trace_state(self, scope_type: str, scope_id: str, key: str) -> dict[str,Any]: return {"current":self.get_state(scope_type,scope_id,key),"history":self.get_state_history(scope_type,scope_id,key)}
    def _publish(self, typ: str, payload: dict[str,Any]):
        if self.event_bus and hasattr(self.event_bus,"publish"): self.event_bus.publish(typ, payload, source_system="world_state")

class QuestValidationResult(dict):
    @property
    def ok(self) -> bool: return not self.get("errors")

class QuestValidator:
    def __init__(self, content: QuestContent) -> None: self.content=content
    def validate_all(self) -> QuestValidationResult:
        errors=[]; warnings=[]
        for q in self.content.list("quest_definitions"):
            r=self.validate_quest(q.get("id")); errors+=r["errors"]; warnings+=r["warnings"]
        for c in self.content.list("conversation_definitions"):
            r=self.validate_conversation(c.get("id")); errors+=r["errors"]; warnings+=r["warnings"]
        return QuestValidationResult(ok=not errors, errors=errors, warnings=warnings)
    def validate_quest(self, quest_id: str) -> QuestValidationResult:
        e=[]; w=[]; q=self.content.get("quest_definitions", quest_id)
        if not q: return QuestValidationResult(ok=False, errors=[f"missing quest {quest_id}"], warnings=[])
        if not safe_id(q.get("id")): e.append("quest id is not safe")
        if q.get("quest_type","custom") not in QUEST_TYPES: e.append("unsupported quest_type")
        stages=[self.content.get("quest_stages", sid) for sid in q.get("stage_ids",[])]; stages=[s for s in stages if s]
        if q.get("start_stage_id") not in {s.get("id") for s in stages}: e.append("missing start stage")
        if q.get("reward_definition_id") and not safe_id(q.get("reward_definition_id")): e.append("invalid reward")
        if not q.get("offer_sources"): w.append("quest has no offer source")
        if not q.get("turn_in_sources"): w.append("quest has no turn-in source")
        obj_ids=[]
        for s in stages:
            sr=self.validate_stage(s.get("id")); e+=sr["errors"]; w+=sr["warnings"]; obj_ids += list(s.get("objective_ids",[]))
        if len(obj_ids)!=len(set(obj_ids)): e.append("duplicate objective IDs")
        return QuestValidationResult(ok=not e, errors=e, warnings=w)
    def validate_stage(self, stage_id: str) -> QuestValidationResult:
        e=[]; w=[]; s=self.content.get("quest_stages", stage_id)
        if not s: return QuestValidationResult(ok=False, errors=[f"missing stage {stage_id}"], warnings=[])
        if s.get("terminal_state","none") not in TERMINAL_STATES: e.append("invalid terminal state")
        if s.get("terminal_state","none")=="none" and not (s.get("next_stage_id") or s.get("branch_rules")): e.append("dead-end nonterminal stage")
        for oid in s.get("objective_ids",[]):
            r=self.validate_objective(oid); e+=r["errors"]; w+=r["warnings"]
        qid=s.get("quest_id"); valid_stages={x.get("id") for x in self.content.list("quest_stages") if x.get("quest_id")==qid}
        if s.get("next_stage_id") and s.get("next_stage_id") not in valid_stages: e.append("invalid next stage")
        for b in s.get("branch_rules",[]):
            if b.get("next_stage_id") and b.get("next_stage_id") not in valid_stages: e.append("invalid branch destination")
        return QuestValidationResult(ok=not e, errors=e, warnings=w)
    def validate_objective(self, objective_id: str) -> QuestValidationResult:
        o=self.content.get("quest_objectives", objective_id); e=[]; w=[]
        if not o: return QuestValidationResult(ok=False, errors=[f"missing objective {objective_id}"], warnings=[])
        if o.get("objective_type") not in OBJECTIVE_TYPES: e.append("invalid objective type")
        if o.get("progress_mode","increment") not in PROGRESS_MODES: e.append("invalid progress mode")
        if float(o.get("required_count",1) or 0) < 0: e.append("invalid required count")
        if o.get("objective_type") not in set().union(*EVENT_OBJECTIVE_TYPES.values()): w.append("objective cannot receive any known event")
        tgt=o.get("target_definition",{}) or {}
        if isinstance(tgt,dict) and tgt.get("display_name") and len(tgt)==1: e.append("display-name-only target")
        return QuestValidationResult(ok=not e, errors=e, warnings=w)
    def validate_conversation(self, conversation_id: str) -> QuestValidationResult:
        c=self.content.get("conversation_definitions", conversation_id); e=[]; w=[]
        if not c: return QuestValidationResult(ok=False, errors=[f"missing conversation {conversation_id}"], warnings=[])
        nodes=[n for n in self.content.list("conversation_nodes") if n.get("conversation_id")==conversation_id]; ids={n.get("id") for n in nodes}
        if c.get("start_node_id") not in ids: e.append("invalid start node")
        if not any(n.get("terminal") for n in nodes): w.append("conversation has no terminal path")
        for ch in [x for x in self.content.list("conversation_choices") if x.get("conversation_id")==conversation_id]:
            if ch.get("next_node_id") and ch.get("next_node_id") not in ids: e.append("invalid next node")
            for a in ch.get("actions",[]):
                if a.get("action_type") not in SUPPORTED_ACTION_TYPES: e.append("conversation action bypasses QuestService or is unsupported")
        return QuestValidationResult(ok=not e, errors=e, warnings=w)

class QuestService:
    def __init__(self, db_path: str|Path=":memory:", world_root: str|Path="worlds/shattered_realms", world_id: str="shattered_realms", event_bus: Any|None=None, reward_service: Any|None=None) -> None:
        self.db_path=str(db_path); self.world_id=world_id; self.content=QuestContent(world_root); self.event_bus=event_bus; self.reward_service=reward_service; self.world_state=WorldStateService(db_path, world_id, event_bus); self.ensure_schema()
    def ensure_schema(self):
        with sqlite3.connect(self.db_path) as con: con.executescript(SCHEMA_SQL)
    def get_quest_definition(self, quest_id): return self.content.get("quest_definitions", quest_id)
    def list_available_quests(self, actor_id, source=None): return [q for q in self.content.list("quest_definitions") if self.evaluate_quest_availability(actor_id,q.get("id"),source)["available"]]
    def evaluate_quest_availability(self, actor_id, quest_id, source=None):
        q=self.get_quest_definition(quest_id); trace=[]
        if not q or not q.get("enabled", True): return {"available":False,"trace":["missing or disabled"]}
        with sqlite3.connect(self.db_path) as con:
            active=con.execute("SELECT 1 FROM actor_quest_instances WHERE world_id=? AND actor_id=? AND quest_id=? AND status IN ('offered','accepted','active','ready_to_turn_in','completed_pending_reward')",(self.world_id,actor_id,quest_id)).fetchone()
            done=con.execute("SELECT 1 FROM actor_quest_instances WHERE world_id=? AND actor_id=? AND quest_id=? AND status='completed'",(self.world_id,actor_id,quest_id)).fetchone()
        if active: return {"available":False,"trace":["already active"]}
        rp=self.content.get("quest_repeat_policies", q.get("repeat_policy_id")) or {"policy":"never"}
        if done and rp.get("policy","never") in {"never","once_per_actor","once_per_character"}: return {"available":False,"trace":["already completed"]}
        prof=self.content.get("quest_availability_profiles", q.get("availability_profile_id")) or {}
        ok=True
        for cond in prof.get("conditions",[]):
            ctype=cond.get("condition_type") or cond.get("type"); passed=True
            if ctype=="world_state_equals": passed=self.world_state.compare_state(cond.get("scope_type","world"), cond.get("scope_id",self.world_id), cond.get("key") or cond.get("world_state_key"), cond.get("value"))
            elif ctype in {"quest_completed","required_quest_completed"}:
                req=cond.get("quest_id") or cond.get("required_quest_id")
                with sqlite3.connect(self.db_path) as con:
                    passed=bool(con.execute("SELECT 1 FROM actor_quest_instances WHERE world_id=? AND actor_id=? AND quest_id=? AND status='completed'",(self.world_id,actor_id,req)).fetchone())
            elif ctype in (None, "custom"): passed = ctype is None
            else: passed=False
            trace.append({"condition":cond,"passed":passed}); ok = ok and passed
        return {"available":ok,"trace":trace}
    trace_quest_availability = evaluate_quest_availability
    def offer_quest(self, actor_id, quest_id, source=None):
        av=self.evaluate_quest_availability(actor_id,quest_id,source)
        if not av["available"]: raise ValueError("quest unavailable")
        source=source or {}; now=utc_now(); oid=stable_id("qoffer",self.world_id,actor_id,quest_id,source.get("source_type",""),source.get("source_id",""))
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR REPLACE INTO actor_quest_offers VALUES(?,?,?,?,?,?,?,?,?,?,?)",(oid,actor_id,quest_id,source.get("source_type",""),source.get("source_id",""),"offered",source.get("world_time",0),source.get("expires_world_time"),now,now,_json({})))
        self._history(actor_id,quest_id,"", "offered", world_time=source.get("world_time",0)); self._publish("quest_offered",{"actor_id":actor_id,"quest_id":quest_id,"offer_id":oid}); return {"offer_id":oid,"quest_id":quest_id,"status":"offered"}
    def accept_quest(self, actor_id, quest_id, source=None):
        q=self.get_quest_definition(quest_id); source=source or {}; av=self.evaluate_quest_availability(actor_id,quest_id,source)
        if not q or not av["available"]: raise ValueError("quest unavailable")
        iid=stable_id("qinst",self.world_id,actor_id,quest_id,source.get("repeat_key","default")); now=utc_now(); wt=int(source.get("world_time",0)); stage=q.get("start_stage_id")
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO actor_quest_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,"actor",actor_id,quest_id,int(q.get("version",1)),"active",stage,wt,None,None,None,source.get("repeat_key","default"),source.get("source_type",""),source.get("source_id",""),now,now,_json({"reward_delivered":False})))
        self._enter_stage(iid, stage, wt); self._history(actor_id,quest_id,iid,"accepted",stage,world_time=wt); self._publish("quest_accepted",{"quest_instance_id":iid,"quest_id":quest_id,"actor_id":actor_id}); return self.get_quest_instance(iid)
    def _enter_stage(self, iid, stage_id, wt=0):
        now=utc_now(); sid=stable_id("qstage",iid,stage_id)
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO actor_quest_stage_state VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid,iid,stage_id,"active",wt,None,None,"",now,now,_json({})))
            for o in self.content.objectives_by_stage.get(stage_id,[]): con.execute("INSERT OR IGNORE INTO actor_quest_objective_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(stable_id("qobj",iid,o["id"]),iid,stage_id,o["id"],"active",0,float(o.get("required_count",1) or 1),_json({}),wt,None,now,_json({})))
        self._publish("quest_stage_entered",{"quest_instance_id":iid,"stage_id":stage_id})
    def get_quest_instance(self, quest_instance_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM actor_quest_instances WHERE quest_instance_id=?",(quest_instance_id,)).fetchone(); return dict(r) if r else None
    def get_actor_quests(self, actor_id, status=None):
        sql="SELECT * FROM actor_quest_instances WHERE world_id=? AND actor_id=?" + (" AND status=?" if status else "")
        args=(self.world_id,actor_id) + ((status,) if status else ())
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute(sql,args)]
    def get_quest_journal(self, actor_id):
        out=[]
        for inst in self.get_actor_quests(actor_id):
            q=self.get_quest_definition(inst["quest_id"]) or {}; stage=self.content.get("quest_stages", inst["current_stage_id"]) or {}
            objs=self._objective_states(inst["quest_instance_id"])
            out.append({"quest_instance_id":inst["quest_instance_id"],"quest_id":inst["quest_id"],"name":q.get("name",inst["quest_id"]),"summary":q.get("summary",""),"description":q.get("description",q.get("summary","")),"status":inst["status"],"current_stage":stage.get("name",inst["current_stage_id"]),"stage_text":stage.get("journal_text",stage.get("description","")),"objectives":objs,"ready_to_turn_in":inst["status"]=="ready_to_turn_in","repeatable":(self.content.get("quest_repeat_policies", q.get("repeat_policy_id")) or {}).get("policy") not in {"never","once_per_actor","once_per_character"},"cooldown":(self.content.get("quest_repeat_policies", q.get("repeat_policy_id")) or {}).get("cooldown_seconds",0),"prerequisites":(self.content.get("quest_availability_profiles", q.get("availability_profile_id")) or {}).get("conditions",[]),"rewards":q.get("reward_definition_id","")})
        return out
    def process_quest_event(self, event):
        event=dict(event); eid=event.get("event_id") or stable_id("evt", event); event["event_id"]=eid; et=event.get("event_type") or event.get("type"); actor=event.get("actor_id") or event.get("killer_actor_id") or event.get("recipient_actor_id") or event.get("player_actor_id")
        if not actor or et not in EVENT_OBJECTIVE_TYPES: return {"event_id":eid,"matched":0,"trace":["ignored event"]}
        matched=0; trace=[]
        for inst in self.get_actor_quests(actor, "active") + self.get_actor_quests(actor, "ready_to_turn_in"):
            stage=inst["current_stage_id"]
            for obj in self.content.objectives_by_stage.get(stage,[]):
                if obj.get("objective_type") not in EVENT_OBJECTIVE_TYPES[et]: continue
                tr=self.trace_objective_match(inst["quest_instance_id"], obj["id"], event); trace.append(tr)
                if tr["matched"] and self._consume_event(inst, obj, event): matched+=1
            self.evaluate_quest_instance(inst["quest_instance_id"])
        return {"event_id":eid,"matched":matched,"trace":trace}
    def trace_objective_match(self, quest_instance_id, objective_id, event):
        obj=self.content.get("quest_objectives", objective_id) or {}; tgt=obj.get("target_definition",{}) or {}; et=event.get("event_type") or event.get("type"); reasons=[]; ok=True
        mapping={"actor_instance_id":"target_actor_id","actor_template_id":"target_actor_template_id","spawn_definition_id":"spawn_definition_id","actor_tag":"target_actor_tags","item_template_id":"item_template_id","item_instance_id":"item_instance_id","item_tag":"item_tags","recipe_id":"recipe_id","profession_id":"profession_id","feature_id":"feature_id","feature_tag":"feature_tags","room_id":"room_id","zone_id":"zone_id","area_id":"area_id","ability_id":"ability_id","effect_template_id":"effect_template_id","currency_id":"currency_id","quest_id":"quest_id","world_state_key":"state_key"}
        for k,evk in mapping.items():
            if k in tgt:
                val=event.get(evk); want=tgt[k]
                passed = (want in val) if isinstance(val,list) else (str(val)==str(want))
                reasons.append({"target":k,"expected":want,"actual":val,"passed":passed}); ok=ok and passed
        return {"quest_instance_id":quest_instance_id,"objective_id":objective_id,"event_id":event.get("event_id"),"event_type":et,"matched":ok,"reasons":reasons or ["no target criteria"]}
    def _consume_event(self, inst, obj, event):
        eid=event["event_id"]; now=utc_now(); wt=int(event.get("world_time",0)); oid=obj["id"]
        with sqlite3.connect(self.db_path) as con:
            try: con.execute("INSERT INTO actor_quest_event_consumption VALUES(?,?,?,?,?,?,?)",(stable_id("qcons",inst["quest_instance_id"],oid,eid),inst["quest_instance_id"],oid,eid,event.get("event_type") or event.get("type"),wt,_json({"event":event})))
            except sqlite3.IntegrityError: return False
            st=con.execute("SELECT progress_current,progress_required,progress_json FROM actor_quest_objective_state WHERE quest_instance_id=? AND objective_id=?",(inst["quest_instance_id"],oid)).fetchone(); cur=float(st[0]); req=float(st[1]); pj=_loads(st[2])
            mode=obj.get("progress_mode","increment"); amount=float(event.get("amount", event.get("quantity",1)) or 1)
            if mode in {"unique_targets","unique_instances","sequence"}: key=str(event.get("target_actor_id") or event.get("item_instance_id") or event.get("room_id") or event.get("target_id") or eid); seen=set(pj.get("seen",[]));
            if mode in {"unique_targets","unique_instances","sequence"}:
                if key in seen: return False
                seen.add(key); pj["seen"]=sorted(seen); cur=len(seen)
            elif mode=="set": cur=amount
            elif mode=="binary": cur=1
            elif mode in {"accumulate_amount","increment","custom"}: cur += amount
            else: cur += amount
            status="completed" if cur>=req else "active"; completed=wt if status=="completed" else None
            con.execute("UPDATE actor_quest_objective_state SET progress_current=?,progress_json=?,status=?,completed_world_time=?,updated_at=? WHERE quest_instance_id=? AND objective_id=?",(cur,_json(pj),status,completed,now,inst["quest_instance_id"],oid))
        self._history(inst["actor_id"],inst["quest_id"],inst["quest_instance_id"],"objective_progressed",inst["current_stage_id"],oid,wt,{"event_id":eid}); self._publish("quest_objective_progressed",{"quest_instance_id":inst["quest_instance_id"],"objective_id":oid,"progress_current":cur,"progress_required":req})
        if status=="completed": self._publish("quest_objective_completed",{"quest_instance_id":inst["quest_instance_id"],"objective_id":oid})
        return True
    def _objective_states(self, iid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM actor_quest_objective_state WHERE quest_instance_id=? ORDER BY objective_id",(iid,))]
    def evaluate_quest_instance(self, quest_instance_id):
        inst=self.get_quest_instance(quest_instance_id); 
        if not inst or inst["status"] not in {"active","ready_to_turn_in"}: return inst
        stage=self.content.get("quest_stages",inst["current_stage_id"]) or {}; objs=[o for o in self._objective_states(quest_instance_id) if not (self.content.get("quest_objectives",o["objective_id"]) or {}).get("optional")]
        if objs and all(o["status"]=="completed" for o in objs): return self.advance_quest_stage(quest_instance_id)
        return inst
    def advance_quest_stage(self, quest_instance_id):
        inst=self.get_quest_instance(quest_instance_id); stage=self.content.get("quest_stages",inst["current_stage_id"]) or {}; wt=0; now=utc_now()
        branch=self._select_branch(stage, inst); next_stage=(branch or {}).get("next_stage_id") or stage.get("next_stage_id"); terminal=(branch or {}).get("terminal_state") or stage.get("terminal_state","none")
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_stage_state SET status='completed',completed_world_time=?,branch_id=?,updated_at=? WHERE quest_instance_id=? AND stage_id=?",(wt,(branch or {}).get("id",""),now,quest_instance_id,stage.get("id")))
        self._publish("quest_stage_completed",{"quest_instance_id":quest_instance_id,"stage_id":stage.get("id")})
        if branch: self._publish("quest_branch_selected",{"quest_instance_id":quest_instance_id,"branch_id":branch.get("id")})
        if terminal=="completed" or (not next_stage and terminal=="none"): return self.complete_quest(quest_instance_id, ready_only=True)
        if terminal in {"failed","cancelled"}: return self.fail_quest(quest_instance_id, terminal)
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_instances SET current_stage_id=?,updated_at=? WHERE quest_instance_id=?",(next_stage,now,quest_instance_id))
        self._enter_stage(quest_instance_id,next_stage,wt); return self.get_quest_instance(quest_instance_id)
    def _select_branch(self, stage, inst):
        branches=sorted(stage.get("branch_rules",[]), key=lambda b:(-int(b.get("priority",0)), str(b.get("id",""))))
        for b in branches:
            if self._conditions_pass(b.get("conditions",[]), inst): return b
        return None
    def _conditions_pass(self, conds, inst):
        for c in conds or []:
            if (c.get("type") or c.get("condition_type"))=="world_state_equals":
                if not self.world_state.compare_state(c.get("scope_type","world"), c.get("scope_id",self.world_id), c.get("key") or c.get("world_state_key"), c.get("value")): return False
            elif c.get("type") in (None,"always"): continue
            else: return False
        return True
    def complete_quest(self, quest_instance_id, ready_only=False):
        inst=self.get_quest_instance(quest_instance_id); now=utc_now(); status="ready_to_turn_in" if ready_only else "completed_pending_reward"
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_instances SET status=?,completed_world_time=COALESCE(completed_world_time,?),updated_at=? WHERE quest_instance_id=? AND status NOT IN ('completed','failed','abandoned','cancelled')",(status,0,now,quest_instance_id))
        self._publish("quest_ready_to_turn_in" if ready_only else "quest_completed",{"quest_instance_id":quest_instance_id}); return self.get_quest_instance(quest_instance_id)
    def turn_in_quest(self, actor_id, quest_instance_id, source=None):
        inst=self.get_quest_instance(quest_instance_id)
        if not inst or inst["actor_id"]!=actor_id: raise ValueError("quest instance not found")
        if inst["status"]=="completed": return inst
        if inst["status"] not in {"ready_to_turn_in","completed_pending_reward"}: raise ValueError("quest is not ready to turn in")
        q=self.get_quest_definition(inst["quest_id"]) or {}; packet_id=""
        with sqlite3.connect(self.db_path) as con:
            existing=con.execute("SELECT reward_packet_id FROM quest_reward_claims WHERE quest_instance_id=? AND status='delivered'",(quest_instance_id,)).fetchone()
            if existing: packet_id=existing[0]
        if not packet_id and q.get("reward_definition_id") and self.reward_service:
            try:
                from engine.rewards import RewardSource, RewardRecipient
                resolver=getattr(self.reward_service,"resolve_reward",None) or getattr(self.reward_service,"resolve_reward_definition")
                packet=resolver(q["reward_definition_id"], RewardSource("quest", q["id"], quest_instance_id, self.world_id), RewardRecipient("actor", actor_id))
                deliver=getattr(self.reward_service,"deliver_packet",None) or getattr(self.reward_service,"deliver_reward_packet",None)
                if deliver: deliver(packet["reward_packet_id"] if isinstance(packet,dict) else packet.reward_packet_id)
                packet_id=packet["reward_packet_id"] if isinstance(packet,dict) else getattr(packet,"reward_packet_id","")
            except Exception as exc: self._record_reward_claim(quest_instance_id,inst,q,"pending",str(exc)); raise
        self._record_reward_claim(quest_instance_id,inst,q,"delivered",packet_id)
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_instances SET status='completed',updated_at=? WHERE quest_instance_id=? AND status!='completed'",(utc_now(),quest_instance_id))
        self._history(actor_id,inst["quest_id"],quest_instance_id,"completed",inst["current_stage_id"],world_time=0,metadata={"reward_packet_id":packet_id}); self._publish("quest_turned_in",{"quest_instance_id":quest_instance_id}); self._publish("quest_reward_delivered",{"quest_instance_id":quest_instance_id,"reward_packet_id":packet_id}); return self.get_quest_instance(quest_instance_id)
    def _record_reward_claim(self,iid,inst,q,status,packet):
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO quest_reward_claims VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("qreward",iid),iid,q.get("id"),inst["actor_id"],q.get("reward_definition_id",""),packet,status,utc_now(),utc_now(),_json({})))
    def abandon_quest(self, actor_id, quest_instance_id):
        inst=self.get_quest_instance(quest_instance_id); 
        if not inst or inst["actor_id"]!=actor_id: raise ValueError("quest instance not found")
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_instances SET status='abandoned',abandoned_world_time=0,updated_at=? WHERE quest_instance_id=? AND status NOT IN ('completed','failed','abandoned')",(utc_now(),quest_instance_id))
        self._history(actor_id,inst["quest_id"],quest_instance_id,"abandoned",inst["current_stage_id"]); self._publish("quest_abandoned",{"quest_instance_id":quest_instance_id}); return self.get_quest_instance(quest_instance_id)
    def fail_quest(self, quest_instance_id, reason=None):
        inst=self.get_quest_instance(quest_instance_id)
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_instances SET status='failed',failed_world_time=0,updated_at=?,metadata_json=? WHERE quest_instance_id=? AND status NOT IN ('completed','failed','abandoned')",(utc_now(),_json({"reason":reason}),quest_instance_id))
        if inst: self._history(inst["actor_id"],inst["quest_id"],quest_instance_id,"failed",inst["current_stage_id"],metadata={"reason":reason})
        self._publish("quest_failed",{"quest_instance_id":quest_instance_id,"reason":reason}); return self.get_quest_instance(quest_instance_id)
    def cancel_quest(self, quest_instance_id, reason=None):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_quest_instances SET status='cancelled',updated_at=?,metadata_json=? WHERE quest_instance_id=?",(utc_now(),_json({"reason":reason}),quest_instance_id))
        return self.get_quest_instance(quest_instance_id)
    def trace_quest(self, quest_instance_id): return {"instance":self.get_quest_instance(quest_instance_id),"objectives":self._objective_states(quest_instance_id),"history":self._history_rows(quest_instance_id),"consumed_events":self._consumed_rows(quest_instance_id)}
    def _history_rows(self,iid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM actor_quest_history WHERE quest_instance_id=? ORDER BY created_at",(iid,))]
    def _consumed_rows(self,iid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM actor_quest_event_consumption WHERE quest_instance_id=? ORDER BY consumed_world_time",(iid,))]
    def _history(self,actor,quest,iid,op,stage_id="",objective_id="",world_time=0,metadata=None):
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO actor_quest_history VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("qhist",actor,quest,iid,op,utc_now(),uuid.uuid4().hex),actor,quest,iid,op,stage_id,objective_id,world_time,utc_now(),_json(metadata or {})))
    def _publish(self, typ, payload):
        if self.event_bus and hasattr(self.event_bus,"publish"): self.event_bus.publish(typ, payload, source_system="quest")

class QuestEventRouter:
    def __init__(self, quest_service: QuestService) -> None: self.quest_service=quest_service
    def handle_event(self, event: dict[str,Any]) -> dict[str,Any]: return self.quest_service.process_quest_event(event)
    def subscribe(self, event_bus: Any) -> None:
        for typ in EVENT_OBJECTIVE_TYPES:
            if hasattr(event_bus,"subscribe"): event_bus.subscribe(typ, self.handle_event)

class ConversationService:
    def __init__(self, quest_service: QuestService) -> None: self.quest_service=quest_service; self.sessions={}
    def start_conversation(self, actor_id: str, conversation_id: str, npc_id: str="") -> dict[str,Any]:
        c=self.quest_service.content.get("conversation_definitions", conversation_id)
        if not c: raise ValueError("missing conversation")
        sid=stable_id("conv",actor_id,conversation_id,npc_id); self.sessions[sid]={"actor_id":actor_id,"conversation_id":conversation_id,"node_id":c.get("start_node_id"),"npc_id":npc_id}
        self.quest_service._publish("conversation_started",{"conversation_session_id":sid,"conversation_id":conversation_id}); return self.enter_node(sid, c.get("start_node_id"))
    def enter_node(self, session_id: str, node_id: str) -> dict[str,Any]:
        s=self.sessions[session_id]; node=self.quest_service.content.get("conversation_nodes", node_id); s["node_id"]=node_id
        choices=[c for c in self.quest_service.content.list("conversation_choices") if c.get("node_id")==node_id]
        self.quest_service._publish("conversation_node_entered",{"conversation_session_id":session_id,"node_id":node_id})
        return {"conversation_session_id":session_id,"node":node,"choices":choices,"terminal":bool((node or {}).get("terminal"))}
    def choose(self, session_id: str, choice_number: int) -> dict[str,Any]:
        s=self.sessions[session_id]; choices=[c for c in self.quest_service.content.list("conversation_choices") if c.get("node_id")==s["node_id"]]
        ch=choices[choice_number-1]
        for a in ch.get("actions",[]): self._execute_action(s,a)
        self.quest_service._publish("conversation_choice_selected",{"conversation_session_id":session_id,"choice_id":ch.get("id")})
        if ch.get("ends_conversation"):
            self.quest_service._publish("conversation_completed",{"conversation_session_id":session_id,"conversation_id":s["conversation_id"],"actor_id":s["actor_id"]}); return {"completed":True,"choice":ch}
        return self.enter_node(session_id, ch.get("next_node_id"))
    def _execute_action(self, s, a):
        t=a.get("action_type")
        if t=="offer_quest": self.quest_service.offer_quest(s["actor_id"], a.get("quest_id"), {"source_type":"conversation","source_id":s["conversation_id"]})
        elif t=="accept_quest": self.quest_service.accept_quest(s["actor_id"], a.get("quest_id"), {"source_type":"conversation","source_id":s["conversation_id"]})
        elif t=="complete_quest": self.quest_service.complete_quest(a.get("quest_instance_id"), ready_only=True)
        elif t=="turn_in_quest":
            qs=[q for q in self.quest_service.get_actor_quests(s["actor_id"]) if q["quest_id"]==a.get("quest_id") and q["status"] in {"ready_to_turn_in","completed_pending_reward"}]
            if qs: self.quest_service.turn_in_quest(s["actor_id"], qs[0]["quest_instance_id"], {"source_type":"conversation","source_id":s["conversation_id"]})
        elif t=="set_world_state": self.quest_service.world_state.set_state(a.get("scope_type","world"), a.get("scope_id",self.quest_service.world_id), a.get("key"), a.get("value"), source_type="conversation", source_id=s["conversation_id"])
        elif t=="increment_world_state": self.quest_service.world_state.increment_state(a.get("scope_type","world"), a.get("scope_id",self.quest_service.world_id), a.get("key"), a.get("amount",1), source_type="conversation", source_id=s["conversation_id"])
        elif t in {"custom",None}: raise ValueError("unsupported conversation action")
