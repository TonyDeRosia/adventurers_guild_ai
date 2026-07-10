"""Phase 9B canonical achievement, title, accolade, collection foundation.

One AchievementService owns definitions, event-driven criteria progress, SQLite
runtime state, title/accolade ownership, collection state, milestones, reward
handoff, and diagnostics. Subsystems publish canonical events; this service
consumes them idempotently and delegates rewards to RewardService.
"""
from __future__ import annotations

import hashlib, json, re, sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE=re.compile(r"^[A-Za-z0-9_.:-]+$")
ACHIEVEMENT_COLLECTIONS=["achievement_definitions","achievement_categories","achievement_series","achievement_criteria_groups","achievement_criteria","achievement_repeat_policies","achievement_availability_profiles","achievement_milestone_profiles","achievement_completion_profiles","achievement_progress_display_profiles","title_definitions","accolade_definitions","collection_definitions","collection_entries","achievement_message_profiles"]
ACHIEVEMENT_TYPES={"achievement","milestone","feat","challenge","collection","exploration","combat","quest","crafting","economy","faction","organization","training","profession","story","secret","custom"}
EVALUATION_MODES={"all","any","at_least","sequence","weighted_threshold","custom"}
PROGRESS_MODES={"incremental","derived","binary","unique_targets","unique_instances","unique_templates","unique_rooms","unique_zones","unique_areas","unique_recipes","unique_factions","unique_titles","aggregate","maintain_state","sequence","custom"}
COMPARISONS={"equal","not_equal","greater_than","greater_than_or_equal","less_than","less_than_or_equal","contains","not_contains","in","not_in","exists","not_exists","custom"}
VISIBILITY={"visible","hidden_until_progress","hidden_until_completed","secret","hidden"}
STATUSES={"locked","available","in_progress","completed","completed_pending_reward","repeatable_ready","failed_placeholder","hidden","archived"}
EVENT_TYPES={"actor_killed","actor_died","combat_damage_applied","healing_applied","ability_started","ability_completed","ability_learned","ability_rank_increased","actor_leveled_up","quest_completed","quest_stage_completed","crafted_item_created","craft_job_completed","salvage_completed","resource_node_harvested","profession_learned","profession_rank_increased","training_transaction_completed","attribute_trained","resource_trained","currency_credited","currency_debited","shop_item_purchased","shop_item_sold","item_created","item_received","item_equipped","room_entered","zone_entered","area_entered","feature_interacted","faction_reputation_gained","faction_standing_changed","organization_member_joined","organization_role_assigned","party_created","group_quest_credit_awarded","conversation_completed","world_state_changed","recipe_granted","custom"}
TARGET_FIELDS={"actor_instance_id","actor_template_id","actor_tag","population_definition_id","faction_id","organization_id","quest_id","quest_category_id","quest_series_id","item_template_id","item_tag","recipe_id","profession_id","ability_id","trainer_id","training_offer_id","currency_id","room_id","zone_id","area_id","feature_id","feature_tag","world_state_key","standing_tier_id","role_id","quality_profile_id","custom_target_id"}
CRITERIA_EVENT_DEFAULTS={"kill_actor":"actor_killed","kill_template":"actor_killed","kill_tag":"actor_killed","kill_faction":"actor_killed","deal_damage":"combat_damage_applied","receive_damage":"combat_damage_applied","heal_actor":"healing_applied","use_ability":"ability_completed","learn_ability":"ability_learned","increase_ability_rank":"ability_rank_increased","gain_level":"actor_leveled_up","reach_level":"actor_leveled_up","complete_quest":"quest_completed","complete_quest_category":"quest_completed","complete_quest_series":"quest_completed","craft_item":"crafted_item_created","craft_recipe":"craft_job_completed","craft_quality":"crafted_item_created","salvage_item":"salvage_completed","harvest_resource":"resource_node_harvested","learn_profession":"profession_learned","reach_profession_rank":"profession_rank_increased","train_attribute":"attribute_trained","train_resource":"resource_trained","complete_training_offer":"training_transaction_completed","earn_currency":"currency_credited","spend_currency":"currency_debited","purchase_item":"shop_item_purchased","sell_item":"shop_item_sold","own_item":"item_received","collect_item_template":"item_received","collect_item_tag":"item_received","equip_item":"item_equipped","visit_room":"room_entered","visit_zone":"zone_entered","visit_area":"area_entered","interact_feature":"feature_interacted","gain_faction_reputation":"faction_reputation_gained","reach_faction_standing":"faction_standing_changed","join_organization":"organization_member_joined","reach_organization_role":"organization_role_assigned","create_party":"party_created","complete_group_quest":"group_quest_credit_awarded","conversation_complete":"conversation_completed","discover_faction":"faction_standing_changed","discover_recipe":"recipe_granted","discover_ability":"ability_learned","world_state_equals":"world_state_changed","quest_state_equals":"quest_stage_completed"}
SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS actor_achievement_state(achievement_state_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,achievement_id TEXT,definition_version TEXT,status TEXT,progress_value REAL,progress_json TEXT,started_world_time INTEGER,completed_world_time INTEGER,repeat_key TEXT,completion_count INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_achievement_once ON actor_achievement_state(world_id,actor_id,achievement_id,repeat_key);
CREATE TABLE IF NOT EXISTS actor_achievement_criteria_state(criteria_state_id TEXT PRIMARY KEY,achievement_state_id TEXT,criteria_group_id TEXT,criteria_id TEXT,status TEXT,progress_current REAL,progress_required REAL,progress_json TEXT,started_world_time INTEGER,completed_world_time INTEGER,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_criteria_state ON actor_achievement_criteria_state(achievement_state_id,criteria_id);
CREATE TABLE IF NOT EXISTS achievement_event_consumption(consumption_id TEXT PRIMARY KEY,achievement_state_id TEXT,criteria_id TEXT,event_id TEXT,event_type TEXT,consumed_world_time INTEGER,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_achievement_event_once ON achievement_event_consumption(achievement_state_id,criteria_id,event_id);
CREATE TABLE IF NOT EXISTS achievement_completion_history(completion_history_id TEXT PRIMARY KEY,actor_id TEXT,achievement_id TEXT,achievement_state_id TEXT,completion_number INTEGER,repeat_key TEXT,completed_world_time INTEGER,reward_packet_id TEXT,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_achievement_completion_once ON achievement_completion_history(achievement_state_id,completion_number);
CREATE TABLE IF NOT EXISTS achievement_progress_history(progress_history_id TEXT PRIMARY KEY,actor_id TEXT,achievement_id TEXT,criteria_id TEXT,event_id TEXT,old_progress_json TEXT,new_progress_json TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS actor_titles(actor_title_id TEXT PRIMARY KEY,actor_id TEXT,title_id TEXT,source_type TEXT,source_id TEXT,granted_world_time INTEGER,active INTEGER,selected INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_title_source ON actor_titles(actor_id,title_id,source_type,source_id);
CREATE TABLE IF NOT EXISTS actor_accolades(actor_accolade_id TEXT PRIMARY KEY,actor_id TEXT,accolade_id TEXT,source_type TEXT,source_id TEXT,granted_world_time INTEGER,active INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_accolade_source ON actor_accolades(actor_id,accolade_id,source_type,source_id);
CREATE TABLE IF NOT EXISTS actor_collection_state(collection_state_id TEXT PRIMARY KEY,actor_id TEXT,collection_id TEXT,entry_id TEXT,source_type TEXT,source_id TEXT,acquired_world_time INTEGER,active INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_collection_entry ON actor_collection_state(actor_id,collection_id,entry_id);
CREATE TABLE IF NOT EXISTS achievement_reward_claims(claim_id TEXT PRIMARY KEY,actor_id TEXT,achievement_id TEXT,achievement_state_id TEXT,reward_definition_id TEXT,reward_packet_id TEXT,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_achievement_reward_once ON achievement_reward_claims(actor_id,achievement_id,achievement_state_id,reward_definition_id);
"""
def utc_now(): return datetime.now(timezone.utc).isoformat()
def jdump(v): return json.dumps(v if v is not None else {},sort_keys=True,ensure_ascii=False)
def jload(v,d=None):
    try: return json.loads(v) if v else ({} if d is None else d)
    except Exception: return {} if d is None else d
def stable_id(prefix,*parts): return f"{prefix}_"+hashlib.sha256("|".join(json.dumps(p,sort_keys=True,default=str) for p in parts).encode()).hexdigest()[:32]
def safe_id(v): return bool(v and SAFE_ID_RE.fullmatch(str(v)))

def init_achievement_schema(db_path):
    with sqlite3.connect(db_path) as con: con.executescript(SCHEMA_SQL)

class AchievementContent:
    collections=ACHIEVEMENT_COLLECTIONS
    def __init__(self, world_root: str|Path="worlds/shattered_realms"):
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}; self.criteria_by_event={}
        for c in self.list("achievement_criteria"):
            for ev in c.get("event_types") or ([CRITERIA_EVENT_DEFAULTS.get(c.get("criteria_type"),"custom")]): self.criteria_by_event.setdefault(ev,[]).append(c)
    def _load(self,c):
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text()); items=raw.get(c,raw) if isinstance(raw,dict) else raw
                if isinstance(items,list): return {str(x.get("id")):x for x in items if isinstance(x,dict) and x.get("id")}
                if isinstance(items,dict): return {str(k):({**v,"id":v.get("id",k)} if isinstance(v,dict) else {"id":k}) for k,v in items.items()}
        return {}
    def get(self,c,i): return self.data.get(c,{}).get(str(i or ""))
    def list(self,c): return sorted(self.data.get(c,{}).values(),key=lambda x:str(x.get("sort_order",x.get("id",""))))
    def validate(self):
        e=[]; w=[]; cats=set(self.data["achievement_categories"]); groups=set(self.data["achievement_criteria_groups"]); crit_ids=set()
        for a in self.list("achievement_definitions"):
            aid=a.get("id");
            if not safe_id(aid): e.append(f"achievement {aid}: unsafe id")
            if a.get("achievement_type","achievement") not in ACHIEVEMENT_TYPES: e.append(f"achievement {aid}: invalid type")
            if a.get("category_id") and a.get("category_id") not in cats: e.append(f"achievement {aid}: invalid category")
            for gid in a.get("criteria_group_ids") or []:
                if gid not in groups: e.append(f"achievement {aid}: invalid criteria group {gid}")
            if not a.get("criteria_group_ids") and not a.get("milestone_profile_id"): w.append(f"achievement {aid} has no criteria")
            if not a.get("reward_definition_id") and not a.get("title_reward_ids") and not a.get("accolade_reward_ids"): w.append(f"achievement {aid} has no reward")
        for g in self.list("achievement_criteria_groups"):
            if g.get("evaluation_mode","all") not in EVALUATION_MODES: e.append(f"criteria group {g.get('id')}: invalid evaluation mode")
            if g.get("progress_mode","incremental") not in PROGRESS_MODES: e.append(f"criteria group {g.get('id')}: invalid progress mode")
        for c in self.list("achievement_criteria"):
            cid=c.get("id")
            if cid in crit_ids: e.append(f"duplicate criteria ID {cid}")
            crit_ids.add(cid)
            if not safe_id(cid): e.append(f"criteria {cid}: unsafe id")
            for ev in c.get("event_types") or []:
                if ev not in EVENT_TYPES: e.append(f"criteria {cid}: invalid event type {ev}")
            if c.get("comparison","greater_than_or_equal") not in COMPARISONS: e.append(f"criteria {cid}: invalid comparison")
            if c.get("progress_mode","incremental") not in PROGRESS_MODES: e.append(f"criteria {cid}: invalid progress mode")
            td=c.get("target_definition") or {}
            if any(k not in TARGET_FIELDS for k in td): e.append(f"criteria {cid}: invalid target")
            if not (c.get("event_types") or CRITERIA_EVENT_DEFAULTS.get(c.get("criteria_type"))): w.append(f"criteria {cid} listens to no event")
        for p in self.list("achievement_milestone_profiles"):
            vals=[m.get("threshold") for m in p.get("milestones") or []]
            if vals != sorted(vals): e.append(f"milestone {p.get('id')}: thresholds not ascending")
            if len(vals)!=len(set(vals)): e.append(f"milestone {p.get('id')}: duplicate thresholds")
        return {"errors":e,"warnings":w}

@dataclass
class AchievementEventRouter:
    service: Any
    event_types: tuple[str,...]=tuple(sorted(EVENT_TYPES))
    def subscribe(self,event_bus=None):
        bus=event_bus or self.service.event_bus
        if not bus: return self
        for ev in self.event_types: bus.subscribe(ev,self.handle,priority=80,source="achievements")
        return self
    def handle(self,event): return self.service.process_achievement_event(event)

class AchievementService:
    def __init__(self, db_path: str|Path, world_id="shattered_realms", world_root: str|Path|None=None, event_bus=None, reward_service=None):
        self.db_path=Path(db_path); self.world_id=world_id; init_achievement_schema(self.db_path); self.content=AchievementContent(world_root or Path("worlds")/world_id); self.event_bus=event_bus; self.reward_service=reward_service
    def publish(self,n,p):
        if self.event_bus: self.event_bus.publish(n,p,source_system="achievements",world_id=self.world_id)
    def get_achievement_definition(self,achievement_id): return self.content.get("achievement_definitions",achievement_id)
    def list_achievements(self,actor_id=None,filters=None):
        admin=(filters or {}).get("admin",False); out=[]
        for a in self.content.list("achievement_definitions"):
            if not a.get("enabled",True): continue
            if not admin and a.get("visibility","visible") in {"secret","hidden"}: continue
            out.append(a)
        return out
    def initialize_achievement_state(self,actor_id,achievement_id,repeat_key=""):
        a=self.get_achievement_definition(achievement_id); now=utc_now()
        if not a: raise KeyError(achievement_id)
        sid=stable_id("achstate",self.world_id,actor_id,achievement_id,repeat_key); status="hidden" if a.get("visibility") in {"hidden_until_progress","hidden_until_completed","secret"} else "available"
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO actor_achievement_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,achievement_id,str(a.get("version",1)),status,0,jdump({}),None,None,repeat_key,0,now,now,jdump({})))
            for gid in a.get("criteria_group_ids") or []:
                g=self.content.get("achievement_criteria_groups",gid) or {}; ids=g.get("criteria_ids") or [c["id"] for c in self.content.list("achievement_criteria") if c.get("criteria_group_id")==gid]
                for cid in ids:
                    c=self.content.get("achievement_criteria",cid) or {}; req=float(c.get("required_value",1) or 1); csid=stable_id("achcrit",sid,cid)
                    con.execute("INSERT OR IGNORE INTO actor_achievement_criteria_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(csid,sid,gid,cid,"available",0,req,jdump({}),None,None,now,jdump({})))
        return self.get_actor_achievement(actor_id,achievement_id)
    def get_actor_achievement(self,actor_id,achievement_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM actor_achievement_state WHERE world_id=? AND actor_id=? AND achievement_id=? ORDER BY created_at DESC LIMIT 1",(self.world_id,actor_id,achievement_id)).fetchone()
            return self._state(dict(r)) if r else None
    def get_actor_achievements(self,actor_id,status=None):
        sql="SELECT * FROM actor_achievement_state WHERE world_id=? AND actor_id=?"+(" AND status=?" if status else "")
        args=(self.world_id,actor_id,status) if status else (self.world_id,actor_id)
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; return [self._state(dict(r)) for r in con.execute(sql,args)]
    def _state(self,s): s["progress"]=jload(s.pop("progress_json"),{}); s["metadata"]=jload(s.pop("metadata_json"),{}); return s
    def process_achievement_event(self,event):
        name=getattr(event,"event_name",None) or event.get("event_type") or event.get("event_name"); payload=getattr(event,"payload",None) if not isinstance(event,dict) else event.get("payload",event); eid=getattr(event,"event_id",None) or payload.get("event_id") or stable_id("event",name,payload); world_time=payload.get("world_time")
        actor_ids=self._actors(payload); results=[]
        for actor_id in actor_ids:
            for c in self.content.criteria_by_event.get(name,[]):
                for a in self._achievements_for_criteria(c["id"]):
                    st=self.get_actor_achievement(actor_id,a["id"]) or self.initialize_achievement_state(actor_id,a["id"])
                    if st["status"]=="completed" and (self._repeat_policy(a).get("policy","never")=="never"): continue
                    results.append(self._consume(actor_id,st,a,c,eid,name,payload,world_time))
            self._process_collections(actor_id,name,payload,world_time)
        return results
    def _actors(self,p): return [str(x) for x in (p.get("actor_ids") or [p.get("actor_id") or p.get("killer_actor_id") or p.get("recipient_id") or p.get("character_id")]) if x]
    def _achievements_for_criteria(self,cid):
        out=[]
        for a in self.content.list("achievement_definitions"):
            for gid in a.get("criteria_group_ids") or []:
                g=self.content.get("achievement_criteria_groups",gid) or {}
                if cid in (g.get("criteria_ids") or []): out.append(a)
        return out
    def _repeat_policy(self,a): return self.content.get("achievement_repeat_policies",a.get("repeat_policy_id")) or {"policy":"never"}
    def _match(self,c,p):
        td=c.get("target_definition") or {}
        aliases={"actor_template_id":["target_template_id","victim_template_id","actor_template_id"],"actor_tag":["target_tags","victim_tags","actor_tags"],"faction_id":["faction_id","target_faction_id"],"quest_id":["quest_id"],"item_template_id":["item_template_id"],"recipe_id":["recipe_id"],"profession_id":["profession_id"],"ability_id":["ability_id"],"training_offer_id":["training_offer_id","offer_id"],"currency_id":["currency_id"],"room_id":["room_id"],"zone_id":["zone_id"],"area_id":["area_id"],"quality_profile_id":["quality_profile_id","quality"],"organization_id":["organization_id"],"standing_tier_id":["standing_tier_id","standing"]}
        trace=[]
        for k,v in td.items():
            vals=[p.get(a) for a in aliases.get(k,[k]) if a in p]; ok=any((v==x) or (isinstance(x,list) and v in x) for x in vals)
            trace.append({"field":k,"expected":v,"actual":vals,"matched":ok})
            if not ok: return False,trace
        return True,trace
    def _amount(self,c,p):
        typ=c.get("criteria_type")
        if typ in {"deal_damage","receive_damage","heal_actor","earn_currency","spend_currency"}: return float(p.get("amount",p.get("damage",p.get("healing",1))) or 1)
        if typ in {"reach_level","reach_profession_rank","reach_faction_standing"}: return float(p.get("level",p.get("rank",p.get("standing_value",1))) or 1)
        return 1.0
    def _consume(self,actor_id,st,a,c,eid,event_type,payload,world_time):
        ok,trace=self._match(c,payload)
        if not ok: return {"ignored":True,"reason":"target_mismatch","trace":trace}
        sid=st["achievement_state_id"]; cid=c["id"]; now=utc_now(); cons=stable_id("achcons",sid,cid,eid)
        with sqlite3.connect(self.db_path) as con:
            cur=con.execute("INSERT OR IGNORE INTO achievement_event_consumption VALUES(?,?,?,?,?,?,?)",(cons,sid,cid,eid,event_type,world_time,jdump({"target_trace":trace})))
            if cur.rowcount==0: return {"ignored":True,"reason":"duplicate_event","event_id":eid}
            con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM actor_achievement_criteria_state WHERE achievement_state_id=? AND criteria_id=?",(sid,cid)).fetchone()
            old=dict(r) if r else {}; prog=jload(old.get("progress_json"),{}) if old else {}; current=float(old.get("progress_current",0) if old else 0); req=float(c.get("required_value",1) or 1)
            mode=c.get("progress_mode","incremental"); key=self._unique_key(c,payload)
            if mode.startswith("unique") or mode=="unique_targets":
                ids=sorted(set(prog.get("ids",[])+([key] if key else []))); prog["ids"]=ids; new=float(len(ids))
            elif mode=="binary": new=req
            elif mode=="derived": new=max(current,self._amount(c,payload))
            else: new=current+self._amount(c,payload)
            done=new>=req; prog.update({"current":new,"required":req,"last_event_id":eid})
            con.execute("UPDATE actor_achievement_criteria_state SET status=?,progress_current=?,progress_required=?,progress_json=?,started_world_time=COALESCE(started_world_time,?),completed_world_time=CASE WHEN ? THEN COALESCE(completed_world_time,?) ELSE completed_world_time END,updated_at=? WHERE achievement_state_id=? AND criteria_id=?",("completed" if done else "in_progress",new,req,jdump(prog),world_time,1 if done else 0,world_time,now,sid,cid))
            con.execute("INSERT INTO achievement_progress_history VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("achprog",sid,cid,eid,now),actor_id,a["id"],cid,eid,jdump(old),jdump(prog),world_time,now,jdump({})))
            con.execute("UPDATE actor_achievement_state SET status=CASE WHEN status IN ('available','hidden') THEN 'in_progress' ELSE status END,progress_value=?,progress_json=?,started_world_time=COALESCE(started_world_time,?),updated_at=? WHERE achievement_state_id=?",(self._achievement_progress(con,sid),jdump({"last_event_id":eid}),world_time,now,sid))
        self.publish("achievement_criteria_progressed",{"actor_id":actor_id,"achievement_id":a["id"],"criteria_id":cid,"event_id":eid})
        if done: self.publish("achievement_criteria_completed",{"actor_id":actor_id,"achievement_id":a["id"],"criteria_id":cid})
        if self.evaluate_achievement(actor_id,a["id"]): return self.complete_achievement(actor_id,a["id"],world_time=world_time)
        return {"progressed":True,"achievement_id":a["id"],"criteria_id":cid,"progress":new}
    def _unique_key(self,c,p):
        for f in c.get("unique_key_fields") or []:
            if p.get(f) is not None: return str(p.get(f))
        for f in ("room_id","zone_id","area_id","recipe_id","faction_id","item_template_id","target_template_id","victim_template_id","ability_id","title_id"):
            if p.get(f) is not None: return str(p.get(f))
        return None
    def _achievement_progress(self,con,sid):
        rows=con.execute("SELECT progress_current,progress_required FROM actor_achievement_criteria_state WHERE achievement_state_id=?",(sid,)).fetchall()
        return 0 if not rows else sum(min(float(r[0]),float(r[1] or 1))/float(r[1] or 1) for r in rows)/len(rows)
    def evaluate_achievement(self,actor_id,achievement_id):
        st=self.get_actor_achievement(actor_id,achievement_id) or self.initialize_achievement_state(actor_id,achievement_id)
        with sqlite3.connect(self.db_path) as con:
            rows=con.execute("SELECT status FROM actor_achievement_criteria_state WHERE achievement_state_id=?",(st["achievement_state_id"],)).fetchall()
        return bool(rows) and all(r[0]=="completed" for r in rows)
    def complete_achievement(self,actor_id,achievement_id,world_time=None):
        st=self.get_actor_achievement(actor_id,achievement_id) or self.initialize_achievement_state(actor_id,achievement_id); a=self.get_achievement_definition(achievement_id); now=utc_now(); sid=st["achievement_state_id"]
        if st["status"]=="completed": return {"idempotent":True,"achievement_id":achievement_id}
        packet_id=""
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE actor_achievement_state SET status='completed',completed_world_time=?,completion_count=completion_count+1,updated_at=? WHERE achievement_state_id=?",(world_time,now,sid))
            con.execute("INSERT OR IGNORE INTO achievement_completion_history VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("achhist",sid,1),actor_id,achievement_id,sid,1,st.get("repeat_key",""),world_time,"",now,jdump({})))
        for tid in a.get("title_reward_ids") or []: self.grant_title(actor_id,tid,"achievement",achievement_id,world_time)
        for aid in a.get("accolade_reward_ids") or []: self.grant_accolade(actor_id,aid,"achievement",achievement_id,world_time)
        if a.get("reward_definition_id"): packet_id=self.claim_achievement_reward(actor_id,achievement_id).get("reward_packet_id","")
        self.publish("achievement_completed",{"actor_id":actor_id,"achievement_id":achievement_id,"achievement_state_id":sid,"reward_packet_id":packet_id})
        return {"completed":True,"achievement_id":achievement_id,"reward_packet_id":packet_id}
    def claim_achievement_reward(self,actor_id,achievement_id):
        from engine.rewards import RewardService, RewardSource, RewardRecipient
        st=self.get_actor_achievement(actor_id,achievement_id); a=self.get_achievement_definition(achievement_id); rd=a.get("reward_definition_id") if a else ""
        if not (st and rd): return {"status":"no_reward"}
        cid=stable_id("achclaim",actor_id,achievement_id,st["achievement_state_id"],rd); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            r=con.execute("SELECT reward_packet_id,status FROM achievement_reward_claims WHERE claim_id=?",(cid,)).fetchone()
            if r: return {"claim_id":cid,"reward_packet_id":r[0],"status":r[1],"idempotent":True}
        svc=self.reward_service or RewardService(db_path=self.db_path,world_id=self.world_id,event_bus=self.event_bus)
        pkt=svc.resolve_reward_definition(rd,RewardSource("achievement",achievement_id,st["achievement_state_id"],self.world_id),RewardRecipient("actor",actor_id)); delivered=svc.deliver_reward_packet(pkt["reward_packet_id"]); status="delivered" if delivered and delivered.get("status")=="delivered" else "pending"
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO achievement_reward_claims VALUES(?,?,?,?,?,?,?,?,?,?)",(cid,actor_id,achievement_id,st["achievement_state_id"],rd,pkt["reward_packet_id"],status,now,now,jdump({})))
        self.publish("achievement_reward_requested",{"actor_id":actor_id,"achievement_id":achievement_id,"reward_packet_id":pkt["reward_packet_id"]})
        return {"claim_id":cid,"reward_packet_id":pkt["reward_packet_id"],"status":status}
    def grant_title(self,actor_id,title_id,source_type="achievement",source_id="",world_time=None):
        tid=stable_id("acttitle",actor_id,title_id,source_type,source_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO actor_titles VALUES(?,?,?,?,?,?,?,?,?,?,?)",(tid,actor_id,title_id,source_type,source_id,world_time,1,0,now,now,jdump({})))
        self.publish("title_granted",{"actor_id":actor_id,"title_id":title_id,"source_type":source_type,"source_id":source_id}); return tid
    def revoke_title(self,actor_id,title_id,source_type=None):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_titles SET active=0,selected=0,updated_at=? WHERE actor_id=? AND title_id=?"+(" AND source_type=?" if source_type else ""),(utc_now(),actor_id,title_id,source_type) if source_type else (utc_now(),actor_id,title_id))
        self.publish("title_revoked",{"actor_id":actor_id,"title_id":title_id})
    def list_titles(self,actor_id): return self.list_actor_titles(actor_id)
    def list_actor_titles(self,actor_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM actor_titles WHERE actor_id=? AND active=1 ORDER BY selected DESC,title_id",(actor_id,))]
    def select_title(self,actor_id,title_id): return self.select_actor_title(actor_id,title_id)
    def select_actor_title(self,actor_id,title_id):
        with sqlite3.connect(self.db_path) as con:
            if not con.execute("SELECT 1 FROM actor_titles WHERE actor_id=? AND title_id=? AND active=1",(actor_id,title_id)).fetchone(): raise ValueError("title not owned")
            con.execute("UPDATE actor_titles SET selected=0,updated_at=? WHERE actor_id=?",(utc_now(),actor_id)); con.execute("UPDATE actor_titles SET selected=1,updated_at=? WHERE actor_id=? AND title_id=?",(utc_now(),actor_id,title_id))
        self.publish("title_selected",{"actor_id":actor_id,"title_id":title_id})
    def clear_selected_title(self,actor_id):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_titles SET selected=0,updated_at=? WHERE actor_id=?",(utc_now(),actor_id))
        self.publish("title_cleared",{"actor_id":actor_id})
    def render_actor_title(self,actor_id):
        titles=self.list_actor_titles(actor_id); sel=next((t for t in titles if t.get("selected")),None)
        if not sel: return ""
        d=self.content.get("title_definitions",sel["title_id"]) or {}; return d.get("display_name") or d.get("name") or sel["title_id"]
    def grant_accolade(self,actor_id,accolade_id,source_type="achievement",source_id="",world_time=None):
        aid=stable_id("actacc",actor_id,accolade_id,source_type,source_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO actor_accolades VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,actor_id,accolade_id,source_type,source_id,world_time,1,now,now,jdump({})))
        self.publish("accolade_granted",{"actor_id":actor_id,"accolade_id":accolade_id}); return aid
    def list_accolades(self,actor_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM actor_accolades WHERE actor_id=? AND active=1 ORDER BY accolade_id",(actor_id,))]
    def add_collection_entry(self,actor_id,collection_id,entry_id,source_type="event",source_id="",world_time=None):
        csid=stable_id("coll",actor_id,collection_id,entry_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO actor_collection_state VALUES(?,?,?,?,?,?,?,?,?,?)",(csid,actor_id,collection_id,entry_id,source_type,source_id,world_time,1,now,jdump({})))
        self.publish("collection_entry_added",{"actor_id":actor_id,"collection_id":collection_id,"entry_id":entry_id}); return csid
    def _process_collections(self,actor_id,event_type,payload,world_time):
        event_targets={"room_entered":"room_id","zone_entered":"zone_id","area_entered":"area_id","recipe_granted":"recipe_id","faction_standing_changed":"faction_id","ability_learned":"ability_id","quest_completed":"quest_id","item_received":"item_template_id"}
        field=event_targets.get(event_type)
        if not field: return
        val=payload.get(field)
        for e in self.content.list("collection_entries"):
            if e.get("target_id")==val or (e.get("target_type") in {field.replace("_id",""),field} and e.get("target_id")==val): self.add_collection_entry(actor_id,e.get("collection_id"),e.get("id"),event_type,payload.get("event_id",""),world_time)
    def get_collection_progress(self,actor_id,collection_id):
        d=self.content.get("collection_definitions",collection_id) or {}; req=set(d.get("entry_ids") or [e["id"] for e in self.content.list("collection_entries") if e.get("collection_id")==collection_id])
        with sqlite3.connect(self.db_path) as con: got={r[0] for r in con.execute("SELECT entry_id FROM actor_collection_state WHERE actor_id=? AND collection_id=? AND active=1",(actor_id,collection_id))}
        return {"collection_id":collection_id,"acquired_entry_ids":sorted(got),"required_entry_ids":sorted(req),"completed":bool(req) and req.issubset(got)}
    def get_completion_history(self,actor_id,achievement_id=None):
        sql="SELECT * FROM achievement_completion_history WHERE actor_id=?"+(" AND achievement_id=?" if achievement_id else "")
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute(sql,(actor_id,achievement_id) if achievement_id else (actor_id,))]
    def get_progress_history(self,actor_id,achievement_id=None):
        sql="SELECT * FROM achievement_progress_history WHERE actor_id=?"+(" AND achievement_id=?" if achievement_id else "")
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute(sql,(actor_id,achievement_id) if achievement_id else (actor_id,))]
    def get_achievement_progress(self,actor_id,achievement_id): return self.get_actor_achievement(actor_id,achievement_id)
    def get_actor_achievement_points(self,actor_id): return sum(int((self.get_achievement_definition(h["achievement_id"]) or {}).get("point_value",0) or 0) for h in self.get_completion_history(actor_id))
    def trace_achievement(self,actor_id,achievement_id): return {"definition":self.get_achievement_definition(achievement_id),"state":self.get_actor_achievement(actor_id,achievement_id),"progress_history":self.get_progress_history(actor_id,achievement_id),"completion_history":self.get_completion_history(actor_id,achievement_id),"idempotency":"achievement_event_consumption unique index"}
    def trace_achievement_event(self,actor_id,achievement_id,event): return {"achievement_id":achievement_id,"event":event,"would_process":True,"criteria":[c for c in self.content.list("achievement_criteria") if c.get("id") in str(self.get_achievement_definition(achievement_id).get("criteria_group_ids",[]))]}
    def trace_criteria(self,actor_id,achievement_id,criteria_id): return {"actor_id":actor_id,"achievement_id":achievement_id,"criteria":self.content.get("achievement_criteria",criteria_id),"state":self.get_actor_achievement(actor_id,achievement_id)}
    trace_title=lambda self,actor_id,title_id:{"definition":self.content.get("title_definitions",title_id),"owned":[t for t in self.list_actor_titles(actor_id) if t["title_id"]==title_id]}
    trace_accolade=lambda self,actor_id,accolade_id:{"definition":self.content.get("accolade_definitions",accolade_id),"owned":[a for a in self.list_accolades(actor_id) if a["accolade_id"]==accolade_id]}
    trace_collection=lambda self,actor_id,collection_id:{"definition":self.content.get("collection_definitions",collection_id),"progress":self.get_collection_progress(actor_id,collection_id)}
