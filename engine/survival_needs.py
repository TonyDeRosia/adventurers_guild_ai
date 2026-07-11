"""Phase 11D1 canonical survival needs and consumption foundation.

SQLite is authoritative for actor need state, consumption sessions, serving
counts, progression events, and audit history.  This service intentionally
extends the earlier LivingWorldService entity_needs table by migrating valid
legacy rows into actor_need_state rather than running a competing needs engine.
"""
from __future__ import annotations

import hashlib, json, math, sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SURVIVAL_COLLECTIONS = (
    "actor_need_definitions", "actor_needs_profiles", "needs_offline_policies",
    "need_threshold_profiles", "consumable_profiles", "consumable_portion_profiles",
    "food_freshness_profiles", "consumption_requirement_profiles",
    "consumption_interruption_profiles", "survival_message_profiles", "survival_render_profiles",
)
NEED_STATUSES = {"inactive","optimal","normal","warning","critical","recovering","suspended","immune","archived"}
SESSION_STATUSES = {"started","in_progress","interrupted","completed","failed","cancelled","expired"}
MAX_CATCHUP_MINUTES = 24 * 60
MAX_CYCLES_PER_TICK = 512

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True)
def _loads(v: Any, default: Any = None) -> Any:
    if v in (None, ""): return {} if default is None else default
    try: return json.loads(v)
    except Exception: return {} if default is None else default

def _stable(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:24]

def _records(root: Path, collection: str) -> list[dict[str, Any]]:
    out=[]; p=root/collection
    for jp in sorted(p.glob("*.json")):
        data=json.loads(jp.read_text(encoding="utf-8"))
        vals=data.get(collection) if isinstance(data,dict) else data
        if isinstance(vals,dict): vals=list(vals.values())
        if isinstance(vals,list): out.extend(x for x in vals if isinstance(x,dict))
    return out

class SurvivalContent:
    def __init__(self, world_root: Path):
        self.world_root=Path(world_root)
        self.records={c:{str(r.get('id')):r for r in _records(self.world_root,c) if r.get('id')} for c in SURVIVAL_COLLECTIONS}
    def list(self, c: str) -> list[dict[str, Any]]: return list(self.records.get(c,{}).values())
    def get(self, c: str, i: str|None) -> dict[str, Any]: return self.records.get(c,{}).get(str(i),{}) if i else {}
    def validate(self) -> list[str]:
        e=[]
        for n in self.list('actor_need_definitions'):
            if float(n.get('minimum_value',0)) > float(n.get('maximum_value',100)): e.append(f"need {n.get('id')} invalid bounds")
        for p in self.list('actor_needs_profiles'):
            for nid in p.get('need_definition_ids') or []:
                if nid not in self.records.get('actor_need_definitions',{}): e.append(f"needs profile {p.get('id')} missing need {nid}")
        for c in self.list('consumable_profiles'):
            if c.get('portion_profile_id') and c.get('portion_profile_id') not in self.records.get('consumable_portion_profiles',{}): e.append(f"consumable {c.get('id')} missing portion profile")
        return e

@dataclass
class ConsumptionCheck:
    ok: bool
    reason: str
    profile: dict[str, Any]
    item: dict[str, Any]
    servings_remaining: int

class SurvivalNeedsService:
    def __init__(self, db_path: Path, world_root: Path, world_id: str, event_bus: Any = None, runtime: Any = None):
        self.db_path=Path(db_path); self.world_root=Path(world_root); self.world_id=world_id; self.event_bus=event_bus; self.runtime=runtime; self.content=SurvivalContent(self.world_root); init_survival_schema(self.db_path)
    def _world_minutes(self) -> int:
        if self.runtime and getattr(self.runtime,'living_world',None):
            wt=self.runtime.living_world.ensure_world_time(self.world_id); return int(wt.get('total_minutes') or (int(wt.get('day',1))-1)*1440+int(wt.get('hour',0))*60+int(wt.get('minute',0)))
        return 0
    def _actor_row(self, actor_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='characters'").fetchone():
                return {"id":actor_id,"world_id":self.world_id,"data":"{}"}
            r=c.execute("SELECT * FROM characters WHERE id=?",(actor_id,)).fetchone()
            return dict(r) if r else {"id":actor_id,"world_id":self.world_id,"data":"{}"}
    def _profile_for_actor(self, actor_id: str) -> dict[str, Any]:
        data=_loads(self._actor_row(actor_id).get('data'),{})
        actor_type='player' if actor_id.startswith('char_') or data.get('role','player')=='player' else data.get('actor_type','npc')
        for p in self.content.list('actor_needs_profiles'):
            if not p.get('enabled',True): continue
            types=set(p.get('actor_type_ids') or [])
            if not types or actor_type in types or 'player' in types: return p
        return {"id":"builtin_humanoid_survival","need_definition_ids":[n['id'] for n in self.content.list('actor_need_definitions') if n.get('enabled',True)],"default_values":{},"enabled":True}
    def _status(self, need: dict[str, Any], value: float) -> str:
        if not need.get('enabled',True): return 'inactive'
        if value <= max([float(x) for x in (need.get('critical_thresholds') or [10])] or [10]): return 'critical'
        if value <= max([float(x) for x in (need.get('warning_thresholds') or [30])] or [30]): return 'warning'
        if float(need.get('optimal_minimum',70)) <= value <= float(need.get('optimal_maximum',100)): return 'optimal'
        return 'normal'
    def _bounded(self, need: dict[str, Any], value: Any) -> float:
        try: v=float(value)
        except Exception: v=float(need.get('starting_value',100))
        if not math.isfinite(v): v=float(need.get('starting_value',100))
        return max(float(need.get('minimum_value',0)), min(float(need.get('maximum_value',100)), v))
    def initialize_actor_needs(self, actor_id: str) -> list[dict[str, Any]]:
        prof=self._profile_for_actor(actor_id); nowt=self._world_minutes(); t=utc_now(); out=[]
        with sqlite3.connect(self.db_path) as c:
            for nid in prof.get('need_definition_ids') or []:
                n=self.content.get('actor_need_definitions',nid)
                if not n or not n.get('enabled',True): continue
                sid=f"need_{_stable(self.world_id,actor_id,nid)}"; val=self._bounded(n, (prof.get('default_values') or {}).get(nid, n.get('starting_value',100)))
                legacy=c.execute("SELECT current_value FROM entity_needs WHERE entity_instance_id=? AND need_type=?",(actor_id,n.get('need_type',nid))).fetchone() if self._table(c,'entity_needs') else None
                if legacy and legacy[0] is not None: val=self._bounded(n, legacy[0])
                c.execute("INSERT OR IGNORE INTO actor_need_state(actor_need_state_id,world_id,actor_id,need_definition_id,current_value,status,last_updated_world_time,last_progression_world_time,next_threshold_world_time,source_profile_id,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,nid,val,self._status(n,val),nowt,nowt,None,prof.get('id'),t,t,_json({'legacy_migrated':bool(legacy)})))
            c.commit()
        return self.get_actor_needs(actor_id)
    def _table(self,c,name): return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())
    def get_actor_needs(self, actor_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as c:
            count=c.execute("SELECT COUNT(*) FROM actor_need_state WHERE actor_id=? AND status!='archived'",(actor_id,)).fetchone()[0]
        if count == 0:
            setattr(self, '_initializing', True)
            try: self.initialize_actor_needs(actor_id)
            finally: setattr(self, '_initializing', False)
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute("SELECT * FROM actor_need_state WHERE actor_id=? AND status!='archived' ORDER BY need_definition_id",(actor_id,))]
    def get_actor_need(self, actor_id: str, need_id: str) -> dict[str, Any] | None:
        for n in self.get_actor_needs(actor_id):
            if n['need_definition_id']==need_id: return n
        return None
    def _mutate(self, actor_id, need_id, value, reason, delta=False, source_event_id=None):
        self.initialize_actor_needs(actor_id); n=self.content.get('actor_need_definitions',need_id); wt=self._world_minutes(); t=utc_now()
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM actor_need_state WHERE actor_id=? AND need_definition_id=?",(actor_id,need_id)).fetchone()
            if not r: raise KeyError(need_id)
            old=float(r['current_value']); new=self._bounded(n, old+float(value) if delta else value); st=self._status(n,new)
            c.execute("UPDATE actor_need_state SET current_value=?,status=?,last_updated_world_time=?,updated_at=? WHERE actor_need_state_id=?",(new,st,wt,t,r['actor_need_state_id']))
            hid=f"needhist_{_stable(r['actor_need_state_id'],reason,old,new,wt,source_event_id or '')}"; c.execute("INSERT OR IGNORE INTO actor_need_history VALUES(?,?,?,?,?,?,?,?,?,?,?)",(hid,self.world_id,actor_id,need_id,old,new,reason,source_event_id,wt,t,_json({})))
        self._publish('actor_need_changed',{'actor_id':actor_id,'need_id':need_id,'old':old,'new':new,'reason':reason}); return self.get_actor_need(actor_id,need_id)
    def set_actor_need(self, actor_id, need_id, value, reason, source_event_id=None): return self._mutate(actor_id,need_id,value,reason,False,source_event_id)
    def modify_actor_need(self, actor_id, need_id, amount, reason, source_event_id=None): return self._mutate(actor_id,need_id,amount,reason,True,source_event_id)
    def reset_actor_needs(self, actor_id, reason=None):
        for n in self.content.list('actor_need_definitions'): self.set_actor_need(actor_id,n['id'],n.get('starting_value',100),reason or 'reset')
        return self.get_actor_needs(actor_id)
    def process_actor_needs(self, actor_id: str, world_time: int|dict[str,Any]) -> list[dict[str, Any]]:
        target=int(world_time.get('total_minutes',0) if isinstance(world_time,dict) else world_time); self.initialize_actor_needs(actor_id); changed=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; rows=c.execute("SELECT * FROM actor_need_state WHERE actor_id=? AND status NOT IN ('inactive','suspended','immune','archived')",(actor_id,)).fetchall()
            for r in rows:
                n=self.content.get('actor_need_definitions',r['need_definition_id']); elapsed=max(0,min(MAX_CATCHUP_MINUTES,target-int(r['last_progression_world_time'] or 0)))
                if elapsed<=0: continue
                rate=float((n.get('plugin_data') or {}).get('progression_per_minute', -0.01 if n.get('need_type')!='satiation' else -0.02)); new=self._bounded(n,float(r['current_value'])+rate*elapsed); st=self._status(n,new); t=utc_now()
                c.execute("UPDATE actor_need_state SET current_value=?,status=?,last_updated_world_time=?,last_progression_world_time=?,updated_at=? WHERE actor_need_state_id=?",(new,st,target,target,t,r['actor_need_state_id']))
                eid=f"needprog_{_stable(r['actor_need_state_id'],r['last_progression_world_time'],target,new)}"; c.execute("INSERT OR IGNORE INTO need_progression_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,self.world_id,actor_id,r['need_definition_id'],int(r['last_progression_world_time'] or 0),target,float(r['current_value']),new,t,_json({'bounded_minutes':elapsed})))
                changed.append({'need_definition_id':r['need_definition_id'],'old':r['current_value'],'new':new,'elapsed_minutes':elapsed})
        return changed
    def process_world_needs(self, world_id: str, world_time: int|dict[str,Any]):
        with sqlite3.connect(self.db_path) as c: actors=[r[0] for r in c.execute("SELECT DISTINCT actor_id FROM actor_need_state WHERE world_id=?",(world_id,))]
        return {a:self.process_actor_needs(a,world_time) for a in actors[:MAX_CYCLES_PER_TICK]}
    def preview_need_progression(self, actor_id, duration):
        base=self.get_actor_needs(actor_id); target=self._world_minutes()+int(duration); out=[]
        for r in base:
            n=self.content.get('actor_need_definitions',r['need_definition_id']); elapsed=min(MAX_CATCHUP_MINUTES,int(duration)); rate=float((n.get('plugin_data') or {}).get('progression_per_minute', -0.01)); out.append({'need_definition_id':r['need_definition_id'],'current_value':r['current_value'],'preview_value':self._bounded(n,float(r['current_value'])+rate*elapsed),'target_world_time':target})
        return out
    def _item(self,item_instance_id):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM item_instances WHERE instance_id=? AND destroyed_at IS NULL",(item_instance_id,)).fetchone(); return dict(r) if r else {}
    def _servings(self,item,profile):
        meta=_loads(item.get('custom_flags'),{}); pp=self.content.get('consumable_portion_profiles',profile.get('portion_profile_id'))
        return int(meta.get('servings_remaining', pp.get('starting_servings', pp.get('maximum_servings',1)) or 1))
    def _profile_for_item(self,item):
        tid=item.get('template_id')
        for p in self.content.list('consumable_profiles'):
            if p.get('enabled',True) and (tid in (p.get('allowed_item_template_ids') or [])): return p
        return {}
    def can_consume(self, actor_id, item_instance_id) -> ConsumptionCheck:
        item=self._item(item_instance_id); prof=self._profile_for_item(item) if item else {}; servings=self._servings(item,prof) if prof else 0
        if not item: return ConsumptionCheck(False,'item_not_found',{}, {},0)
        if item.get('owner_type') not in ('actor','room') or (item.get('owner_type')=='actor' and item.get('owner_id')!=actor_id): return ConsumptionCheck(False,'not_owned_or_accessible',prof,item,servings)
        if not prof: return ConsumptionCheck(False,'not_consumable',{},item,servings)
        if servings <= 0: return ConsumptionCheck(False,'no_servings_remaining',prof,item,servings)
        sat=self.get_actor_need(actor_id,'satiation')
        if sat and float(sat['current_value']) >= 98: return ConsumptionCheck(False,'already_full',prof,item,servings)
        return ConsumptionCheck(True,'ok',prof,item,servings)
    def preview_consumption(self, actor_id,item_instance_id):
        chk=self.can_consume(actor_id,item_instance_id); return {**chk.__dict__,'need_changes':chk.profile.get('need_changes',{}) if chk.profile else {}}
    def consume_item(self, actor_id,item_instance_id,servings=1):
        chk=self.can_consume(actor_id,item_instance_id); wt=self._world_minutes(); sid=f"consume_{_stable(self.world_id,actor_id,item_instance_id,servings,wt,chk.servings_remaining)}"; t=utc_now()
        if not chk.ok: return {'ok':False,'reason':chk.reason,'consumption_session_id':sid}
        servings=max(1,int(servings)); prof=chk.profile; pp=self.content.get('consumable_portion_profiles',prof.get('portion_profile_id')); per=int(pp.get('consume_per_use',1) or 1); take=min(servings*per,chk.servings_remaining)
        with sqlite3.connect(self.db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            item=self._item(item_instance_id); cur=self._servings(item,prof)
            if cur < take:
                c.execute("INSERT OR IGNORE INTO consumption_sessions(consumption_session_id,world_id,actor_id,item_instance_id,consumable_profile_id,status,servings_requested,servings_consumed,started_world_time,completes_world_time,last_updated_world_time,idempotency_key,result_json,failure_reason,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,item_instance_id,prof['id'],'failed',servings,0,wt,wt,wt,sid,_json({}),'no_servings_remaining',t,t,_json({})))
                return {'ok':False,'reason':'no_servings_remaining','consumption_session_id':sid}
            meta=_loads(item.get('custom_flags'),{}); meta['servings_remaining']=cur-take; meta['portion_profile_id']=pp.get('id')
            c.execute("UPDATE item_instances SET custom_flags=?,servings_remaining=?,updated_at=? WHERE instance_id=? AND destroyed_at IS NULL",(_json(meta),int(meta['servings_remaining']),t,item_instance_id))
            status='completed'; result={'need_changes':prof.get('need_changes',{}),'servings_consumed':take}
            c.execute("INSERT OR IGNORE INTO consumption_sessions(consumption_session_id,world_id,actor_id,item_instance_id,consumable_profile_id,status,servings_requested,servings_consumed,started_world_time,completes_world_time,last_updated_world_time,idempotency_key,result_json,failure_reason,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,item_instance_id,prof['id'],status,servings,take,wt,wt,wt,sid,_json(result),'',t,t,_json({'item_template_id':item.get('template_id')})))
            c.execute("INSERT OR IGNORE INTO consumption_results VALUES(?,?,?,?,?,?,?,?,?)",(f"result_{sid}",sid,self.world_id,actor_id,item_instance_id,prof['id'],wt,t,_json(result)))
        for nid,delta in (prof.get('need_changes') or {}).items():
            if self.get_actor_need(actor_id,nid): self.modify_actor_need(actor_id,nid,float(delta)*take,'consumption',sid)
        self._publish('survival_event_consumption',{'actor_id':actor_id,'item_instance_id':item_instance_id,'consumable_profile_id':prof['id'],'servings':take})
        return {'ok':True,'consumption_session_id':sid,'servings_consumed':take,'servings_remaining':cur-take,'result':result}
    def interrupt_consumption(self, session_id, reason):
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE consumption_sessions SET status='interrupted',failure_reason=?,updated_at=? WHERE consumption_session_id=? AND status IN ('started','in_progress')",(reason,utc_now(),session_id))
        return self.trace_consumption(session_id)
    def trace_actor_needs(self, actor_id): return {'actor_id':actor_id,'needs':self.get_actor_needs(actor_id),'preview_60':self.preview_need_progression(actor_id,60)}
    def trace_need_progression(self, actor_id, need_id=None):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; rows=c.execute("SELECT * FROM need_progression_events WHERE actor_id=? ORDER BY created_at DESC LIMIT 20",(actor_id,)).fetchall()
        return [dict(r) for r in rows if not need_id or r['need_definition_id']==need_id]
    def trace_consumption(self, session_id):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM consumption_sessions WHERE consumption_session_id=?",(session_id,)).fetchone(); return dict(r) if r else {}
    def get_actor_needs_context(self, actor_id): return self.trace_actor_needs(actor_id)
    def _publish(self,event,payload):
        with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR IGNORE INTO survival_audit_events VALUES(?,?,?,?,?,?,?)",(f"audit_{_stable(event,payload,utc_now())}",self.world_id,event,payload.get('actor_id',''),self._world_minutes(),utc_now(),_json(payload)))
        if self.event_bus: self.event_bus.publish(event,payload,source_system='survival_needs')

def init_survival_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS actor_need_state(actor_need_state_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,need_definition_id TEXT,current_value REAL,status TEXT,last_updated_world_time INTEGER,last_progression_world_time INTEGER,next_threshold_world_time INTEGER,source_profile_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,actor_id,need_definition_id))")
        c.execute("CREATE TABLE IF NOT EXISTS actor_need_history(actor_need_history_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,need_definition_id TEXT,old_value REAL,new_value REAL,reason TEXT,source_event_id TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS need_progression_events(need_progression_event_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,need_definition_id TEXT,from_world_time INTEGER,to_world_time INTEGER,old_value REAL,new_value REAL,created_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS consumption_sessions(consumption_session_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,item_instance_id TEXT,consumable_profile_id TEXT,status TEXT,servings_requested INTEGER,servings_consumed INTEGER,started_world_time INTEGER,completes_world_time INTEGER,last_updated_world_time INTEGER,idempotency_key TEXT UNIQUE,result_json TEXT,failure_reason TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS consumption_results(consumption_result_id TEXT PRIMARY KEY,consumption_session_id TEXT,world_id TEXT,actor_id TEXT,item_instance_id TEXT,consumable_profile_id TEXT,world_time INTEGER,created_at TEXT,result_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS survival_event_consumption(event_id TEXT PRIMARY KEY,consumption_session_id TEXT,world_id TEXT,actor_id TEXT,item_instance_id TEXT,created_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS survival_audit_events(audit_event_id TEXT PRIMARY KEY,world_id TEXT,event_type TEXT,actor_id TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS item_instances(instance_id TEXT PRIMARY KEY,world_id TEXT,template_id TEXT,owner_type TEXT,owner_id TEXT,room_id TEXT,equipped_slot TEXT,stack_count INTEGER DEFAULT 1,condition TEXT DEFAULT 'normal',durability INTEGER DEFAULT 100,created_at TEXT,updated_at TEXT,custom_flags TEXT,plugin_data TEXT,destroyed_at TEXT,destroy_reason TEXT)")
        cols={r[1] for r in c.execute("PRAGMA table_info(item_instances)")}
        for name,ddl in {'freshness_created_world_time':'INTEGER','freshness_profile_id':'TEXT','servings_remaining':'INTEGER'}.items():
            if name not in cols: c.execute(f"ALTER TABLE item_instances ADD COLUMN {name} {ddl}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actor_need_state_actor ON actor_need_state(actor_id,status)")
