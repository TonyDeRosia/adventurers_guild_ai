"""Canonical Phase 11C1 gathering foundation.

One data-driven service owns resource definitions, resource-node runtime state,
capacity/depletion, world-time regeneration, requirement/tool traces,
persistent sessions, deterministic yield/quality/rare foundations, and audit
records.  Gameplay-specific harvesting/mining/fishing/etc. commands are left to
Phase 11C2 and consume this service rather than creating parallel systems.
"""
from __future__ import annotations

import hashlib, json, random, sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GATHERING_COLLECTIONS = (
    "resource_definitions", "resource_node_definitions", "resource_capacity_profiles",
    "resource_regeneration_profiles", "resource_availability_profiles", "resource_environment_profiles",
    "gathering_profiles", "gathering_tool_profiles", "resource_yield_profiles",
    "gathering_resource_cost_profiles", "gathering_interruption_profiles", "gathering_cooldown_profiles",
    "gathering_profession_xp_profiles", "gathering_message_profiles", "gathering_render_profiles", "gathering_access_profiles",
)
RESOURCE_TYPES = {"herb","plant","wood","timber","ore","stone","gem","fish","hide","meat","bone","fiber","mushroom","mineral","clay","salt","water_placeholder","salvage","excavation","forage","custom"}
NODE_STATUSES = {"available","partially_depleted","depleted","regenerating","dormant","seasonally_unavailable","weather_blocked","disabled","destroyed_placeholder","archived"}
SESSION_STATUSES = {"started","in_progress","paused_placeholder","interrupted","completed","failed","cancelled","expired"}


def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True)
def _load_json(p: Path) -> Any:
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return []
def _records(root: Path, collection: str) -> list[dict[str, Any]]:
    out=[]
    for base in (root/collection, root/"builder"):
        paths = sorted((base.glob("*.json") if base.is_dir() else [])) if base.name == collection else ([base/f"{collection}.json"] if (base/f"{collection}.json").exists() else [])
        for p in paths:
            data=_load_json(p)
            if isinstance(data, list): out += [x for x in data if isinstance(x, dict)]
            elif isinstance(data, dict):
                val=data.get(collection) or data.get("records")
                out += (val if isinstance(val, list) else [data])
    return out
def _by_id(rows): return {str(r.get("id")): r for r in rows if r.get("id")}
def stable_id(*parts: Any) -> str: return hashlib.sha256(_json(parts).encode()).hexdigest()[:24]

def init_gathering_schema(db_path: str|Path) -> None:
    with sqlite3.connect(db_path) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS resource_node_instances (
            node_instance_id TEXT PRIMARY KEY, world_id TEXT, node_definition_id TEXT, placement_type TEXT, placement_id TEXT, room_id TEXT,
            status TEXT, capacity_current INTEGER, capacity_maximum INTEGER, quality_seed TEXT, yield_seed TEXT,
            spawned_world_time INTEGER, last_gathered_world_time INTEGER, depleted_world_time INTEGER, next_regeneration_world_time INTEGER,
            regeneration_cycle INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT DEFAULT '{}', UNIQUE(world_id,node_definition_id,placement_type,placement_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS gathering_sessions (
            gathering_session_id TEXT PRIMARY KEY, world_id TEXT, actor_id TEXT, node_instance_id TEXT, resource_definition_id TEXT,
            gathering_profile_id TEXT, tool_item_instance_id TEXT, status TEXT, started_world_time INTEGER, completes_world_time INTEGER,
            last_updated_world_time INTEGER, attempt_number INTEGER, idempotency_key TEXT UNIQUE, result_json TEXT, failure_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, metadata_json TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS gathering_session_costs (cost_id TEXT PRIMARY KEY,gathering_session_id TEXT,cost_type TEXT,definition_id TEXT,amount REAL,status TEXT,source_event_id TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS gathering_session_results (result_id TEXT PRIMARY KEY,gathering_session_id TEXT,result_type TEXT,definition_id TEXT,quantity INTEGER,quality_id TEXT,reward_packet_id TEXT,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS resource_node_history (history_id TEXT PRIMARY KEY,node_instance_id TEXT,operation TEXT,actor_id TEXT,session_id TEXT,capacity_before INTEGER,capacity_after INTEGER,world_time INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS resource_node_regeneration_events (regeneration_event_id TEXT PRIMARY KEY,node_instance_id TEXT,cycle_number INTEGER,amount INTEGER,capacity_before INTEGER,capacity_after INTEGER,world_time INTEGER,idempotency_key TEXT UNIQUE,created_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS actor_resource_node_state (actor_node_state_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,node_instance_id TEXT,capacity_current INTEGER,status TEXT,last_gathered_world_time INTEGER,next_regeneration_world_time INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}',UNIQUE(world_id,actor_id,node_instance_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS corpse_resource_extractions (extraction_id TEXT PRIMARY KEY,corpse_instance_id TEXT,resource_definition_id TEXT,actor_id TEXT,status TEXT,gathering_session_id TEXT,extracted_world_time INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}',UNIQUE(corpse_instance_id,resource_definition_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS gathering_event_consumption (consumption_id TEXT PRIMARY KEY,world_id TEXT,consumer_type TEXT,consumer_id TEXT,event_id TEXT,event_type TEXT,operation TEXT,consumed_world_time INTEGER,metadata_json TEXT DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS gathering_audit_events (audit_event_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,node_instance_id TEXT,session_id TEXT,operation TEXT,result TEXT,reason TEXT,world_time INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,metadata_json TEXT DEFAULT '{}')""")

@dataclass
class GatheringService:
    db_path: str|Path
    world_root: str|Path = "worlds/shattered_realms"
    world_id: str = "shattered_realms"
    event_bus: Any = None
    reward_service: Any = None
    environment_service: Any = None
    runtime: Any = None
    def __post_init__(self):
        self.db_path=Path(self.db_path); self.world_root=Path(self.world_root); init_gathering_schema(self.db_path)
        self.records={c:_by_id(_records(self.world_root,c)) for c in GATHERING_COLLECTIONS}
    def publish(self,n,p):
        if self.event_bus: self.event_bus.publish(n,p,source_system="gathering")
    def get_resource_definition(self, resource_id): return self.records["resource_definitions"].get(str(resource_id))
    def get_node_definition(self, node_definition_id): return self.records["resource_node_definitions"].get(str(node_definition_id))
    def _cap(self, nd):
        cp=self.records["resource_capacity_profiles"].get(str(nd.get("capacity_profile_id") or ""), {})
        mx=max(0,int(cp.get("capacity_maximum", cp.get("starting_capacity",1)) or 1)); st=int(cp.get("starting_capacity",mx) or mx)
        return max(0,min(st,mx)), mx, cp
    def _placements(self, nd):
        pt=nd.get("placement_type","room"); ids=nd.get("room_ids") if pt=="room" else nd.get("feature_ids") or nd.get("zone_ids") or nd.get("area_ids")
        return [(pt,str(x)) for x in (ids or [])]
    def materialize_node(self, node_definition_id, placement_id=None, world_time=0):
        nd=self.get_node_definition(node_definition_id); 
        if not nd or not nd.get("enabled", True): raise KeyError(f"invalid resource node definition {node_definition_id}")
        placements=[(nd.get("placement_type","room"), str(placement_id))] if placement_id else self._placements(nd)
        made=[]
        with sqlite3.connect(self.db_path) as c:
            for pt,pid in placements:
                cur,mx,_=self._cap(nd); iid="rni_"+stable_id(self.world_id,node_definition_id,pt,pid); q="q_"+stable_id(iid,"quality"); y="y_"+stable_id(iid,"yield")
                c.execute("""INSERT OR IGNORE INTO resource_node_instances(node_instance_id,world_id,node_definition_id,placement_type,placement_id,room_id,status,capacity_current,capacity_maximum,quality_seed,yield_seed,spawned_world_time,last_gathered_world_time,depleted_world_time,next_regeneration_world_time,regeneration_cycle,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(iid,self.world_id,node_definition_id,pt,pid,pid if pt=="room" else "","available" if cur>0 else "depleted",cur,mx,q,y,world_time,None,None,None,0,_json({})))
                self._history(c,iid,"materialized","",None,None,cur,world_time,{"node_definition_id":node_definition_id})
                made.append(self.get_node_instance(iid, c))
        self.publish("resource_node_materialized", {"node_definition_id":node_definition_id,"count":len(made)})
        return made[0] if placement_id else made
    def materialize_world_nodes(self, world_id=None):
        out=[]
        for nid in sorted(self.records["resource_node_definitions"]): out += self.materialize_node(nid)
        return out
    def get_node_instance(self, node_instance_id, con=None):
        close=con is None; con=con or sqlite3.connect(self.db_path); con.row_factory=sqlite3.Row
        row=con.execute("SELECT * FROM resource_node_instances WHERE node_instance_id=?",(node_instance_id,)).fetchone();
        if close: con.close()
        return dict(row) if row else None
    def get_nodes_in_room(self, room_id):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute("SELECT * FROM resource_node_instances WHERE room_id=? AND status NOT IN ('archived','disabled')",(room_id,))]
    def list_room_nodes(self, actor_id, room_id=None): return self.get_nodes_in_room(room_id or "")
    def get_available_nodes(self, actor_id, room_id): return [n for n in self.get_nodes_in_room(room_id) if self.evaluate_node_availability(actor_id,n["node_instance_id"])["available"]]
    def resolve_room_node(self, actor_id, room_id, query=None, gathering_type=None):
        nodes=self.get_available_nodes(actor_id, room_id)
        hits=[]
        for n in nodes:
            nd=self.get_node_definition(n["node_definition_id"]) or {}
            rids=nd.get("resource_definition_ids") or []
            resources=[self.get_resource_definition(r) or {} for r in rids]
            text=" ".join([nd.get("id",""),nd.get("name",""),nd.get("node_type","")]+[r.get("id","")+" "+r.get("name","") for r in resources]).lower()
            if gathering_type and not any((self.records["gathering_profiles"].get(str(r.get("gathering_profile_id") or ""),{}).get("gathering_type")==gathering_type) for r in resources): continue
            if query and str(query).isdigit():
                if len(hits)+1 == int(query): return {"ok":True,"node":n,"resource_id":(rids[0] if rids else None),"ambiguous":False}
            elif query and str(query).lower() not in text: continue
            hits.append((n,rids[0] if rids else None))
        if not hits: return {"ok":False,"reason":"no_matching_resource_node"}
        if len(hits)>1 and query: return {"ok":False,"reason":"ambiguous_resource_node","choices":[{"number":i+1,"name":self.get_node_definition(h[0]["node_definition_id"]).get("name")} for i,h in enumerate(hits)]}
        return {"ok":True,"node":hits[0][0],"resource_id":hits[0][1],"ambiguous":len(hits)>1}
    def survey_resources(self, actor_id, room_id, include_builder=False):
        out=[]
        for i,n in enumerate(self.get_available_nodes(actor_id, room_id),1):
            nd=self.get_node_definition(n["node_definition_id"]) or {}
            row={"number":i,"name":nd.get("name"),"status":n["status"],"capacity":f"{n['capacity_current']}/{n['capacity_maximum']}"}
            if include_builder: row.update({"node_instance_id":n["node_instance_id"],"node_definition_id":n["node_definition_id"],"yield_seed":n["yield_seed"]})
            out.append(row)
        return out
    def despawn_node(self,node_instance_id,reason=None):
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE resource_node_instances SET status='archived',updated_at=CURRENT_TIMESTAMP,metadata_json=? WHERE node_instance_id=?",(_json({"reason":reason}),node_instance_id)); self._audit(c,"",node_instance_id,"","despawn","ok",reason,0,{})
    def evaluate_node_availability(self, actor_id, node_instance_id, world_time=0, environment=None):
        n=self.get_node_instance(node_instance_id); nd=self.get_node_definition(n["node_definition_id"]) if n else {}; reasons=[]
        if not n: reasons.append("missing_node")
        elif n["status"] not in {"available","partially_depleted"}: reasons.append(f"status:{n['status']}")
        if n and int(n["capacity_current"] or 0)<=0: reasons.append("no_capacity")
        prof=self.records["resource_availability_profiles"].get(str((nd or {}).get("availability_profile_id") or ""), {})
        env=environment or {"season_id":"spring","weather_id":"clear","day_period":"day","light_class":"normal"}
        if prof.get("season_ids") and env.get("season_id") not in prof.get("season_ids"): reasons.append("seasonally_unavailable")
        if prof.get("weather_ids") and env.get("weather_id") not in prof.get("weather_ids"): reasons.append("weather_blocked")
        return {"available":not reasons,"reasons":reasons,"node":n,"availability_profile":prof,"environment":env}
    def evaluate_gathering_requirements(self, actor_id, node_instance_id, resource_id=None, tool_id=None):
        n=self.get_node_instance(node_instance_id); nd=self.get_node_definition(n["node_definition_id"]) if n else {}; rid=resource_id or ((nd.get("resource_definition_ids") or [None])[0] if nd else None); rd=self.get_resource_definition(rid) if rid else {}; gp=self.records["gathering_profiles"].get(str((rd or {}).get("gathering_profile_id") or ""), {})
        checks=[]; ok=True
        av=self.evaluate_node_availability(actor_id,node_instance_id); checks.append({"requirement":"node_availability","ok":av["available"],"details":av}); ok &= av["available"]
        t=self.validate_tool(actor_id,node_instance_id,tool_id,rd,gp); checks.append({"requirement":"tool","ok":t["ok"],"details":t}); ok &= t["ok"]
        unsupported=[k for k in ("level","class","race","faction","organization","quest") if gp.get(f"required_{k}")]
        for u in unsupported: checks.append({"requirement":u,"ok":False,"reason":"unsupported_placeholder"}); ok=False
        return {"ok":ok,"actor_id":actor_id,"node_instance_id":node_instance_id,"resource_definition":rd,"gathering_profile":gp,"checks":checks}
    def validate_tool(self, actor_id, node_instance_id, tool_id=None, rd=None, gp=None):
        prof_id=(rd or {}).get("tool_profile_id") or (gp or {}).get("tool_profile_id"); prof=self.records["gathering_tool_profiles"].get(str(prof_id or ""), {})
        if not prof_id: return {"ok":True,"profile":{},"tool_item_instance_id":None,"reason":"no_tool_required"}
        if not tool_id: return {"ok":False,"profile":prof,"reason":"tool_required"}
        meta={};
        with sqlite3.connect(self.db_path) as c:
            for table,idcol in (("item_instances","instance_id"),("item_instances","unique_id")):
                try:
                    c.row_factory=sqlite3.Row; row=c.execute(f"SELECT * FROM {table} WHERE {idcol}=?",(tool_id,)).fetchone(); meta=dict(row) if row else meta
                except Exception: pass
        text=_json(meta)
        if "reserved" in text: return {"ok":False,"profile":prof,"reason":"reserved_tool"}
        if "broken" in text: return {"ok":False,"profile":prof,"reason":"broken_tool"}
        allowed=set(map(str, prof.get("allowed_item_template_ids") or [])); tmpl=str(meta.get("template_id") or meta.get("item_template_id") or tool_id)
        if allowed and tmpl not in allowed: return {"ok":False,"profile":prof,"reason":"wrong_tool","template_id":tmpl}
        return {"ok":True,"profile":prof,"tool_item_instance_id":tool_id,"durability_hook":{"cost":prof.get("durability_cost",0)}}
    def preview_gathering(self,*a,**k): return self.evaluate_gathering_requirements(*a,**k)
    def start_gathering(self, actor_id, node_instance_id, resource_id=None, tool_id=None, world_time=0, idempotency_key=None):
        tr=self.evaluate_gathering_requirements(actor_id,node_instance_id,resource_id,tool_id); 
        if not tr["ok"]: return {"ok":False,"trace":tr}
        rd=tr["resource_definition"]; gp=tr["gathering_profile"]; sid="gs_"+stable_id(actor_id,node_instance_id,resource_id,world_time,idempotency_key or "") ; idem=idempotency_key or sid
        with sqlite3.connect(self.db_path) as c:
            active=c.execute("SELECT gathering_session_id FROM gathering_sessions WHERE actor_id=? AND status IN ('started','in_progress')",(actor_id,)).fetchone()
            if active: return {"ok":False,"reason":"active_session_exists","gathering_session_id":active[0]}
            c.execute("INSERT OR IGNORE INTO gathering_sessions(gathering_session_id,world_id,actor_id,node_instance_id,resource_definition_id,gathering_profile_id,tool_item_instance_id,status,started_world_time,completes_world_time,last_updated_world_time,attempt_number,idempotency_key,result_json,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,node_instance_id,rd.get("id"),gp.get("id"),tool_id,"started",world_time,world_time+int(gp.get("duration_minutes",0) or 0),world_time,1,idem,_json({}),_json({"trace":tr})))
            self._audit(c,actor_id,node_instance_id,sid,"start","ok","",world_time,{})
        self.publish("resource_node_gathering_started", {"gathering_session_id":sid}); return {"ok":True,"gathering_session_id":sid,"trace":tr}
    def complete_gathering(self, session_id, world_time=0):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; s=c.execute("SELECT * FROM gathering_sessions WHERE gathering_session_id=?",(session_id,)).fetchone()
            if not s: return {"ok":False,"reason":"missing_session"}
            if s["status"]=="completed": return json.loads(s["result_json"] or "{}") | {"ok":True,"idempotent":True}
            n=self.get_node_instance(s["node_instance_id"], c); before=int(n["capacity_current"]); cost=1
            if before < cost: c.execute("UPDATE gathering_sessions SET status='failed',failure_reason='depleted' WHERE gathering_session_id=?",(session_id,)); return {"ok":False,"reason":"depleted"}
            result=self._resolve_result(dict(s), n); after=max(0,before-cost); status="depleted" if after<=0 else ("partially_depleted" if after<n["capacity_maximum"] else "available")
            c.execute("UPDATE resource_node_instances SET capacity_current=?,status=?,last_gathered_world_time=?,depleted_world_time=CASE WHEN ?=0 THEN ? ELSE depleted_world_time END,updated_at=CURRENT_TIMESTAMP WHERE node_instance_id=? AND capacity_current>=?",(after,status,world_time,after,world_time,s["node_instance_id"],cost))
            if c.total_changes <= 0: return {"ok":False,"reason":"concurrent_capacity_conflict"}
            self._history(c,s["node_instance_id"],"gather",s["actor_id"],session_id,before,after,world_time,result)
            for y in result["yields"]:
                rid="gr_"+stable_id(session_id,y); c.execute("INSERT OR IGNORE INTO gathering_session_results VALUES(?,?,?,?,?,?,?,?,?,?)",(rid,session_id,"item",y["item_template_id"],y["quantity"],y.get("quality_id"),result.get("reward_packet_id"),"resolved",None,_json(y)))
            c.execute("UPDATE gathering_sessions SET status='completed',result_json=?,last_updated_world_time=?,updated_at=CURRENT_TIMESTAMP WHERE gathering_session_id=?",(_json(result),world_time,session_id))
            if result.get("profession_xp"):
                self.publish("gathering_profession_xp_awarded", {"gathering_session_id":session_id, **result["profession_xp"]})
            self._audit(c,s["actor_id"],s["node_instance_id"],session_id,"complete","ok","",world_time,result)
        self.publish("resource_node_capacity_changed", {"node_instance_id":s["node_instance_id"],"capacity_after":after})
        if after <= 0: self.publish("resource_node_depleted", {"node_instance_id":s["node_instance_id"]})
        self.publish("resource_quality_resolved", {"gathering_session_id":session_id,"quality_id":result.get("quality_id")})
        self.publish("resource_node_gathering_completed", {"gathering_session_id":session_id}); self.publish("resource_gathered", result)
        return {"ok":True, **result}
    def _resolve_result(self,s,n):
        rd=self.get_resource_definition(s["resource_definition_id"]); yp=self.records["resource_yield_profiles"].get(str(rd.get("yield_profile_id") or ""), {}) if rd else {}; rng=random.Random(stable_id(s["gathering_session_id"], n["yield_seed"], s["attempt_number"]))
        entries=yp.get("base_yields") or ([{"item_template_id":rd.get("yield_item_template_id"),"minimum_quantity":1,"maximum_quantity":1,"weight":1}] if rd and rd.get("yield_item_template_id") else [])
        yields=[]
        for e in entries[: max(1,int(yp.get("maximum_total_items",len(entries) or 1) or 1))]:
            q=rng.randint(int(e.get("minimum_quantity",1) or 1), int(e.get("maximum_quantity",1) or 1)); yields.append({"item_template_id":e.get("item_template_id"),"quantity":q,"quality_id":e.get("quality_profile_id") or rd.get("quality_profile_id") if rd else None})
        rare=[]
        for e in yp.get("rare_yields") or []:
            if rng.random() <= min(0.25, max(0.0,float(e.get("weight",0) or 0))): rare.append(e)
        xp=self.records["gathering_profession_xp_profiles"].get(str(rd.get("profession_xp_profile_id") or rd.get("profession_id") or ""), {}) if rd else {}
        profession_xp={"profession_id":rd.get("profession_id"),"base_xp":int(xp.get("base_xp",1) or 1),"advancement_api":"ProgressionService/profession hook"} if rd and rd.get("profession_id") else {}
        return {"success":True,"deterministic_seed":stable_id(s["gathering_session_id"],n["yield_seed"]),"yields":yields,"rare_yields":rare,"quality_id":(yields[0].get("quality_id") if yields else None),"profession_xp":profession_xp,"reward_source":{"source_type":"gathering","source_id":s["resource_definition_id"],"source_instance_id":s["gathering_session_id"]}}
    def gather_mode(self, mode, actor_id, room_id, query=None, tool_id=None, world_time=0):
        resolved=self.resolve_room_node(actor_id, room_id, query, mode)
        if not resolved["ok"]: return resolved
        start=self.start_gathering(actor_id,resolved["node"]["node_instance_id"],resolved["resource_id"],tool_id,world_time)
        if not start.get("ok"): return start
        return self.complete_gathering(start["gathering_session_id"],world_time)
    harvest=lambda self,*a,**k: self.gather_mode("harvesting",*a,**k)
    forage=lambda self,*a,**k: self.gather_mode("harvesting",*a,**k)
    mine=lambda self,*a,**k: self.gather_mode("mining",*a,**k)
    chop=lambda self,*a,**k: self.gather_mode("lumberjacking",*a,**k)
    fish=lambda self,*a,**k: self.gather_mode("fishing",*a,**k)
    salvage=lambda self,*a,**k: self.gather_mode("scavenging",*a,**k)
    dig=lambda self,*a,**k: self.gather_mode("excavation",*a,**k)
    excavate=dig
    def skin_corpse(self, actor_id, corpse_instance_id, node_instance_id, resource_id="small_beast_hide", tool_id=None, world_time=0):
        with sqlite3.connect(self.db_path) as c:
            if c.execute("SELECT 1 FROM corpse_resource_extractions WHERE corpse_instance_id=? AND resource_definition_id=? AND status='extracted'",(corpse_instance_id,resource_id)).fetchone():
                return {"ok":False,"reason":"corpse_resource_already_extracted"}
        s=self.start_gathering(actor_id,node_instance_id,resource_id,tool_id,world_time,idempotency_key=stable_id("corpse",corpse_instance_id,resource_id))
        if not s.get("ok"): return s
        r=self.complete_gathering(s["gathering_session_id"],world_time)
        if r.get("ok"):
            with sqlite3.connect(self.db_path) as c:
                c.execute("INSERT OR IGNORE INTO corpse_resource_extractions VALUES(?,?,?,?,?,?,?,?,?)",("cre_"+stable_id(corpse_instance_id,resource_id),corpse_instance_id,resource_id,actor_id,"extracted",s["gathering_session_id"],world_time,None,_json({"decay_policy":"may_reduce_yield_placeholder"})))
            self.publish("corpse_skinned", {"corpse_instance_id":corpse_instance_id,"resource_definition_id":resource_id,"gathering_session_id":s["gathering_session_id"]})
        return r
    butcher_corpse=skin_corpse
    def interrupt_gathering(self, session_id, reason):
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE gathering_sessions SET status='interrupted',failure_reason=?,updated_at=CURRENT_TIMESTAMP WHERE gathering_session_id=? AND status IN ('started','in_progress')",(reason,session_id)); self._audit(c,"","",session_id,"interrupt","ok",reason,0,{})
        self.publish("resource_node_gathering_interrupted", {"gathering_session_id":session_id,"reason":reason}); return {"ok":True}
    def cancel_gathering(self, actor_id):
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE gathering_sessions SET status='cancelled' WHERE actor_id=? AND status IN ('started','in_progress')",(actor_id,)); return {"ok":True,"cancelled":c.total_changes}
    def process_gathering_time(self, world_id, world_time): return self.process_node_regeneration(world_id, world_time)
    def process_node_regeneration(self, world_id, world_time):
        changed=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            for n in c.execute("SELECT * FROM resource_node_instances WHERE world_id=? AND capacity_current<capacity_maximum",(world_id,)).fetchall():
                nd=self.get_node_definition(n["node_definition_id"]); rp=self.records["resource_regeneration_profiles"].get(str((nd or {}).get("regeneration_profile_id") or ""), {})
                if not rp or rp.get("regeneration_mode") == "none": continue
                interval=max(1,int(rp.get("interval_minutes",60) or 60)); elapsed=max(0,int(world_time)-int(n["last_gathered_world_time"] or n["spawned_world_time"] or 0)); cycles=min(int(rp.get("maximum_cycles_per_tick",10) or 10), elapsed//interval)
                if cycles<=0: continue
                amount=int(rp.get("amount_per_interval",1) or 1)*cycles; before=int(n["capacity_current"]); after=min(int(n["capacity_maximum"]), before+max(0,amount)); key=stable_id(n["node_instance_id"], world_time)
                cur=c.execute("INSERT OR IGNORE INTO resource_node_regeneration_events VALUES(?,?,?,?,?,?,?,?,?,?)",("gre_"+key,n["node_instance_id"],int(n["regeneration_cycle"])+1,after-before,before,after,world_time,key,None,_json({"bounded_cycles":cycles})))
                if cur.rowcount:
                    c.execute("UPDATE resource_node_instances SET capacity_current=?,status=?,regeneration_cycle=regeneration_cycle+1,updated_at=CURRENT_TIMESTAMP WHERE node_instance_id=?",(after,"available" if after==n["capacity_maximum"] else "partially_depleted",n["node_instance_id"])); changed.append(n["node_instance_id"])
        return {"ok":True,"regenerated":changed}
    def discover_node(self, actor_id, node_instance_id, source_type, source_id=None, world_time=0):
        sid="arns_"+stable_id(self.world_id,actor_id,node_instance_id)
        with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO actor_resource_node_state(actor_node_state_id,world_id,actor_id,node_instance_id,capacity_current,status,last_gathered_world_time,next_regeneration_world_time,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,node_instance_id,None,"discovered",None,None,_json({"source_type":source_type,"source_id":source_id})))
        self.publish("resource_node_discovered", {"actor_id":actor_id,"node_instance_id":node_instance_id}); return {"ok":True}
    def get_actor_gathering_sessions(self,actor_id):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute("SELECT * FROM gathering_sessions WHERE actor_id=?",(actor_id,))]
    def get_node_history(self,node_instance_id):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute("SELECT * FROM resource_node_history WHERE node_instance_id=?",(node_instance_id,))]
    def trace_gathering(self,session_id): return {"session_id":session_id,"session": self.get_actor_gathering_sessions("") ,"idempotency":"SQLite idempotency_key prevents duplicate completion grants"}
    def trace_node(self,node_instance_id): return {"node":self.get_node_instance(node_instance_id),"history":self.get_node_history(node_instance_id),"restart_state":"SQLite authoritative"}
    def trace_yield(self,session_id): return {"session_id":session_id,"deterministic":True,"reward_handoff":"RewardService source_type=gathering"}
    def trace_regeneration(self,node_instance_id): return {"node":self.get_node_instance(node_instance_id),"bounded_catchup":True}
    def trace_requirement(self,actor_id,node_instance_id): return self.evaluate_gathering_requirements(actor_id,node_instance_id)
    def trace_tool(self,actor_id,node_instance_id,tool_id=None): return self.validate_tool(actor_id,node_instance_id,tool_id)
    def trace_capacity(self,node_instance_id): return {"node":self.get_node_instance(node_instance_id),"atomic_decrement":"UPDATE ... WHERE capacity_current>=cost"}
    def trace_availability(self,actor_id,node_instance_id): return self.evaluate_node_availability(actor_id,node_instance_id)
    def trace_profession(self,actor_id,resource_id): return {"actor_id":actor_id,"resource_definition":self.get_resource_definition(resource_id),"profession_source":"canonical profession/progression APIs"}
    def trace_corpse_extraction(self,corpse_instance_id):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; rows=[dict(r) for r in c.execute("SELECT * FROM corpse_resource_extractions WHERE corpse_instance_id=?",(corpse_instance_id,))]
        return {"corpse_instance_id":corpse_instance_id,"extractions":rows}
    def score_section(self,actor_id,section="gathering",include_builder=False):
        active=[s for s in self.get_actor_gathering_sessions(actor_id) if s["status"] in ("started","in_progress")]
        data={"section":section,"active_gathering_session":active[0]["gathering_session_id"] if active else None,"recent_resources":[json.loads(s["result_json"] or "{}").get("yields",[]) for s in self.get_actor_gathering_sessions(actor_id)[-5:]],"tool_warning":None,"inventory_full_warning":"inventory overflow is delegated to reward/inventory policy","discovered_nodes_count":0}
        if include_builder: data["builder_detail"]="node/session ids, capacity, seeds, result ids, reward packet ids, and event-consumption ids are visible to staff traces"
        return data
    trace_node_materialization=lambda self,nid: {"node_definition":self.get_node_definition(nid),"placements":self._placements(self.get_node_definition(nid) or {})}
    def _history(self,c,nid,op,actor,sid,before,after,wt,meta): c.execute("INSERT OR IGNORE INTO resource_node_history VALUES(?,?,?,?,?,?,?,?,?,?)",("rnh_"+stable_id(nid,op,sid,wt,before,after),nid,op,actor,sid,before,after,wt,None,_json(meta)))
    def _audit(self,c,actor,nid,sid,op,result,reason,wt,meta): c.execute("INSERT OR IGNORE INTO gathering_audit_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",("gae_"+stable_id(actor,nid,sid,op,wt),self.world_id,actor,nid,sid,op,result,reason,wt,None,_json(meta)))
    def validate_content(self):
        errors=[]; warnings=[]; safe=lambda x: bool(x) and all(ch.isalnum() or ch=='_' for ch in str(x))
        items={str(r.get('id')) for r in _records(self.world_root,'items') if r.get('id')}
        rooms={str(r.get('id')) for r in _records(self.world_root,'rooms') if r.get('id')}
        for rid,r in self.records['resource_definitions'].items():
            if not safe(rid): errors.append(f"resource {rid} has unsafe id")
            if r.get('resource_type') not in RESOURCE_TYPES: errors.append(f"resource {rid} invalid resource_type")
            if r.get('yield_item_template_id') and r['yield_item_template_id'] not in items: warnings.append(f"resource {rid} has no valid yield item")
            if float(r.get('rarity',0) or 0)<0: errors.append(f"resource {rid} negative rarity")
        for nid,n in self.records['resource_node_definitions'].items():
            if not n.get('resource_definition_ids'): errors.append(f"node {nid} has no resources")
            for rr in n.get('resource_definition_ids') or []:
                if str(rr) not in self.records['resource_definitions']: errors.append(f"node {nid} references missing resource {rr}")
            for rr in n.get('room_ids') or []:
                if str(rr) not in rooms: warnings.append(f"node {nid} has no valid placement {rr}")
            if n.get('capacity_profile_id') and n['capacity_profile_id'] not in self.records['resource_capacity_profiles']: errors.append(f"node {nid} missing capacity profile")
        for cid,c in self.records['resource_capacity_profiles'].items():
            if int(c.get('capacity_maximum',0) or 0)<0 or int(c.get('starting_capacity',0) or 0)<0: errors.append(f"capacity {cid} negative capacity")
        for rid,r in self.records['resource_regeneration_profiles'].items():
            if r.get('regeneration_mode') != 'none' and int(r.get('interval_minutes',1) or 0)<=0: errors.append(f"regeneration {rid} invalid interval")
        return {"ok":not errors,"errors":errors,"warnings":warnings}
