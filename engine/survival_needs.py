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
    "consumption_interruption_profiles",
    "rest_quality_profiles", "rest_location_profiles", "sleep_profiles", "campfire_profiles",
    "campfire_fuel_profiles", "campsite_profiles",
    "survival_message_profiles", "survival_render_profiles",
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
        for r in self.list('rest_location_profiles'):
            if int(r.get('capacity',1) or 1) <= 0: e.append(f"rest location {r.get('id')} invalid capacity")
            if r.get('rest_quality_profile_id') and r.get('rest_quality_profile_id') not in self.records.get('rest_quality_profiles',{}): e.append(f"rest location {r.get('id')} missing quality profile")
        for q in self.list('rest_quality_profiles'):
            if float(q.get('minimum_quality',0)) > float(q.get('maximum_quality',100)): e.append(f"rest quality {q.get('id')} invalid bounds")
        for cf in self.list('campfire_profiles'):
            if int(cf.get('duration_minutes',1) or 0) <= 0: e.append(f"campfire {cf.get('id')} invalid duration")
        for cs in self.list('campsite_profiles'):
            if int(cs.get('duration_minutes',1) or 0) <= 0: e.append(f"campsite {cs.get('id')} invalid duration")
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
        self.db_path=Path(db_path); self.world_root=Path(world_root); self.world_id=world_id; self.event_bus=event_bus; self.runtime=runtime; self.content=SurvivalContent(self.world_root); init_survival_schema(self.db_path); self.process_due_runtime_objects(self._world_minutes())
    def _world_minutes(self) -> int:
        if self.runtime and getattr(self.runtime,'living_world',None):
            wt=self.runtime.living_world.ensure_world_time(self.world_id); return int(wt.get('total_minutes') or (int(wt.get('day',1))-1)*1440+int(wt.get('hour',0))*60+int(wt.get('minute',0)))
        return 0
    def _actor_row(self, actor_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='characters'").fetchone():
                return {"id":actor_id,"world_id":self.world_id,"data":"{}"}
            columns={r[1] for r in c.execute("PRAGMA table_info(characters)").fetchall()}
            if "id" in columns:
                r=c.execute("SELECT * FROM characters WHERE id=?",(actor_id,)).fetchone()
                return dict(r) if r else {"id":actor_id,"world_id":self.world_id,"data":"{}"}
            if "character_id" in columns:
                r=c.execute("SELECT * FROM characters WHERE character_id=?",(actor_id,)).fetchone()
                if r:
                    d=dict(r); d.setdefault("id", d.get("character_id", actor_id)); d.setdefault("room_id", d.get("current_room_id", "")); d.setdefault("data", "{}"); return d
            return {"id":actor_id,"world_id":self.world_id,"data":"{}"}
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
        target=int((world_time.get('total_minutes') if world_time.get('total_minutes') is not None else (int(world_time.get('day',1))-1)*1440+int(world_time.get('hour',0))*60+int(world_time.get('minute',0))) if isinstance(world_time,dict) else world_time); self.initialize_actor_needs(actor_id); changed=[]
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
        if item.get('owner_type') not in ('actor','character','room') or (item.get('owner_type') in ('actor','character') and item.get('owner_id')!=actor_id): return ConsumptionCheck(False,'not_owned_or_accessible',prof,item,servings)
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

    def _active_rest_session(self, actor_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            r=c.execute("SELECT * FROM actor_rest_sessions WHERE world_id=? AND actor_id=? AND status IN ('started','resting','sleeping') ORDER BY started_world_time DESC LIMIT 1",(self.world_id,actor_id)).fetchone()
            return dict(r) if r else None
    def _room_for_actor(self, actor_id: str) -> str:
        row=self._actor_row(actor_id); data=_loads(row.get('data'),{})
        return row.get('room_id') or row.get('current_room_id') or data.get('room_id') or data.get('current_room_id') or 'guildhall_crossing_square'
    def _rest_location(self, location_id: str|None, rest_type: str) -> dict[str, Any]:
        if location_id: return self.content.get('rest_location_profiles', location_id) or {'id':location_id,'location_type':'custom','rest_allowed':True,'sleep_allowed':rest_type=='sleep','capacity':1,'rest_quality_profile_id':'ground_rest'}
        pref='ground_rest' if rest_type!='sleep' else 'basic_bed'
        return self.content.get('rest_location_profiles', pref) or {'id':pref,'location_type':'ground','rest_allowed':True,'sleep_allowed':rest_type!='sleep','capacity':99,'rest_quality_profile_id':'ground_rest'}
    def get_shelter_context(self, actor_id: str) -> dict[str, Any]:
        room_id=self._room_for_actor(actor_id); ctx={'actor_id':actor_id,'room_id':room_id,'indoors':False,'sheltered':False,'temperature_c':18,'precipitation':'none','wind':'calm','room_exposure':'normal','property_access':False,'private_room_access':False,'inn_room':False}
        env=getattr(self.runtime,'environment',None) if self.runtime else None
        if env and hasattr(env,'get_environment_context'):
            try: ctx.update(env.get_environment_context(self.world_id,room_id) or {})
            except TypeError: ctx.update(env.get_environment_context(room_id) or {})
            except Exception: pass
        prop=getattr(self.runtime,'property_service',None) if self.runtime else None
        if prop and hasattr(prop,'actor_has_room_access'):
            try: ctx['property_access']=bool(prop.actor_has_room_access(actor_id,room_id)); ctx['private_room_access']=ctx['property_access']
            except Exception: pass
        ctx['sheltered']=bool(ctx.get('sheltered') or ctx.get('indoors') or ctx.get('property_access'))
        return ctx
    def _quality(self, actor_id: str, location: dict[str,Any]) -> float:
        qp=self.content.get('rest_quality_profiles', location.get('rest_quality_profile_id')) or self.content.get('rest_quality_profiles','ground_rest')
        shelter=self.get_shelter_context(actor_id)
        q=float(qp.get('base_quality',50)); q+=float(qp.get('bed_modifier',0) if location.get('location_type') in {'bed','inn_bed','property_bed','camp_bed','bedroll'} else 0)
        q+=float(qp.get('shelter_modifier',0) if shelter.get('sheltered') else 0)
        return max(float(qp.get('minimum_quality',0)), min(float(qp.get('maximum_quality',100)), q))
    def can_rest(self, actor_id: str, room_id: str|None=None) -> dict[str,Any]:
        if self._active_rest_session(actor_id): return {'ok':False,'reason':'already_resting'}
        return {'ok':True,'reason':'ok','room_id':room_id or self._room_for_actor(actor_id)}
    def start_rest(self, actor_id: str, location_id: str|None=None): return self._start_rest(actor_id,'rest',location_id)
    def start_sleep(self, actor_id: str, location_id: str|None=None): return self._start_rest(actor_id,'sleep',location_id)
    def _start_rest(self, actor_id: str, rest_type: str, location_id: str|None=None):
        check=self.can_rest(actor_id); loc=self._rest_location(location_id,rest_type)
        if not check['ok']: return check
        if rest_type=='sleep' and not loc.get('sleep_allowed',True): return {'ok':False,'reason':'sleep_not_allowed'}
        if rest_type=='rest' and not loc.get('rest_allowed',True): return {'ok':False,'reason':'rest_not_allowed'}
        wt=self._world_minutes(); dur=int((loc.get('plugin_data') or {}).get('duration_minutes', 480 if rest_type=='sleep' else 60)); sid=f"rest_{_stable(self.world_id,actor_id,rest_type,loc.get('id'),wt)}"; now=utc_now(); status='sleeping' if rest_type=='sleep' else 'resting'; quality=self._quality(actor_id,loc)
        with sqlite3.connect(self.db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM actor_rest_sessions WHERE world_id=? AND actor_id=? AND status IN ('started','resting','sleeping')",(self.world_id,actor_id)).fetchone(): return {'ok':False,'reason':'already_resting'}
            c.execute("INSERT INTO actor_rest_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,actor_id,rest_type,loc.get('location_type','ground'),loc.get('id'),check['room_id'],status,wt,wt+dur,wt,quality,'',sid,_json({}),now,now,_json({'shelter':self.get_shelter_context(actor_id)})))
        self._publish('sleep_started' if rest_type=='sleep' else 'rest_started', {'actor_id':actor_id,'rest_session_id':sid,'quality_score':quality})
        return {'ok':True,'rest_session_id':sid,'status':status,'quality_score':quality,'planned_end_world_time':wt+dur}
    def process_rest_sessions(self, world_id: str, world_time: int|dict[str,Any]):
        target=int(world_time.get('total_minutes',0) if isinstance(world_time,dict) else world_time); out=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; rows=c.execute("SELECT * FROM actor_rest_sessions WHERE world_id=? AND status IN ('started','resting','sleeping') ORDER BY started_world_time,rest_session_id",(world_id,)).fetchall()
        for r in rows:
            elapsed=max(0,target-int(r['last_updated_world_time'] or r['started_world_time'] or 0));
            if elapsed:
                mult=max(0.25,float(r['quality_score'] or 50)/50.0); self.modify_actor_need(r['actor_id'],'fatigue', elapsed*0.05*mult, 'rest_recovery', r['rest_session_id']) if self.get_actor_need(r['actor_id'],'fatigue') else None
                with sqlite3.connect(self.db_path) as c: c.execute("UPDATE actor_rest_sessions SET last_updated_world_time=?,updated_at=? WHERE rest_session_id=?",(target,utc_now(),r['rest_session_id']))
            if target >= int(r['planned_end_world_time'] or target+1): out.append(self.complete_rest(r['rest_session_id']))
        return out
    def complete_rest(self, session_id: str):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM actor_rest_sessions WHERE rest_session_id=?",(session_id,)).fetchone()
            if not r: return {'ok':False,'reason':'not_found'}
            if r['status']=='completed': return {'ok':True,'rest_session_id':session_id,'status':'completed','duplicate':True}
            result={'completed_world_time':self._world_minutes(),'quality_score':r['quality_score']}; c.execute("UPDATE actor_rest_sessions SET status='completed',result_json=?,updated_at=? WHERE rest_session_id=? AND status IN ('started','resting','sleeping')",(_json(result),utc_now(),session_id)); c.execute("INSERT OR IGNORE INTO rest_session_results VALUES(?,?,?,?,?,?,?)",(f"restres_{session_id}",session_id,self.world_id,r['actor_id'],self._world_minutes(),utc_now(),_json(result)))
        self._publish('sleep_completed' if r['rest_type']=='sleep' else 'rest_completed', {'actor_id':r['actor_id'],'rest_session_id':session_id}); return {'ok':True,'rest_session_id':session_id,'status':'completed'}
    def interrupt_rest(self, session_id: str, reason: str):
        tr=self.trace_rest(session_id); 
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE actor_rest_sessions SET status='interrupted',interruption_reason=?,updated_at=? WHERE rest_session_id=? AND status IN ('started','resting','sleeping')",(reason,utc_now(),session_id))
        if tr: self._publish('actor_woke' if tr.get('rest_type')=='sleep' else 'rest_interrupted', {'actor_id':tr.get('actor_id'),'rest_session_id':session_id,'reason':reason})
        return self.trace_rest(session_id)
    def wake_actor(self, actor_id: str, reason: str|None=None):
        s=self._active_rest_session(actor_id); return self.interrupt_rest(s['rest_session_id'], reason or 'wake') if s else {'ok':False,'reason':'not_resting'}
    def get_rest_context(self, actor_id: str): return {'actor_id':actor_id,'active_session':self._active_rest_session(actor_id),'shelter':self.get_shelter_context(actor_id)}
    def trace_rest(self, session_id):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM actor_rest_sessions WHERE rest_session_id=?",(session_id,)).fetchone(); return dict(r) if r else {}
    def _runtime_event_payload(self, row: dict[str, Any], object_id_key: str, reason: str = "") -> dict[str, Any]:
        meta=_loads(row.get('metadata_json'),{})
        return {'world_id':row.get('world_id',self.world_id),'room_id':row.get('room_id',''),'object_id':row.get(object_id_key,''),'template_profile_id':row.get('profile_id',''),'owner_actor_id':row.get('owner_actor_id') or row.get('created_by_actor_id',''),'creator_actor_id':row.get('created_by_actor_id',''),'source_ability_id':meta.get('source_ability_id',''),'lifecycle_reason':reason,'world_time':self._world_minutes()}

    def _active_campsite_for_owner(self, c, actor_id: str, room_id: str | None = None):
        sql="SELECT * FROM campsite_instances WHERE world_id=? AND created_by_actor_id=? AND status IN ('active','occupied','abandoned')"
        params=[self.world_id,actor_id]
        if room_id is not None: sql += " AND room_id=?"; params.append(room_id)
        sql += " ORDER BY created_world_time DESC, created_at DESC LIMIT 1"
        return c.execute(sql,params).fetchone()

    def _active_campfire_for_owner(self, c, actor_id: str, room_id: str | None = None):
        sql="SELECT * FROM campfire_instances WHERE world_id=? AND created_by_actor_id=? AND status IN ('unlit','lit','extinguished','low_fuel')"
        params=[self.world_id,actor_id]
        if room_id is not None: sql += " AND room_id=?"; params.append(room_id)
        sql += " ORDER BY last_updated_world_time DESC, created_at DESC LIMIT 1"
        return c.execute(sql,params).fetchone()

    def _retire_child_campfires(self, c, campsite_id: str, status: str, reason: str, wt: int, now: str):
        rows=c.execute("SELECT * FROM campfire_instances WHERE json_extract(metadata_json,'$.parent_object_id')=? AND status IN ('unlit','lit','extinguished','low_fuel')",(campsite_id,)).fetchall()
        for r in rows:
            c.execute("UPDATE campfire_instances SET status=?,last_updated_world_time=?,updated_at=? WHERE campfire_instance_id=?",(status,wt,now,r['campfire_instance_id']))


    def create_campfire(self, actor_id, profile_id='basic_campfire', room_id=None):
        prof=self.content.get('campfire_profiles',profile_id); room_id=room_id or self._room_for_actor(actor_id); wt=self._world_minutes(); now=utc_now(); exp=wt+int(prof.get('duration_minutes',120) or 120)
        iid=f"campfire_{_stable(self.world_id,profile_id,room_id,actor_id,wt)}"
        replaced=False
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; c.execute('BEGIN IMMEDIATE')
            cs=self._active_campsite_for_owner(c,actor_id,room_id)
            if not cs:
                if self._active_campsite_for_owner(c,actor_id): return {'ok':False,'reason':'requires_campsite'}
                csid=f"campsite_{_stable(self.world_id,'basic_campsite',room_id,actor_id,wt,'implicit')}"
                c.execute("INSERT OR IGNORE INTO campsite_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(csid,self.world_id,'basic_campsite',room_id,actor_id,'active',_json([actor_id]),wt,wt+480,now,now,_json({'object_type':'campsite','owner_actor_id':actor_id,'implicit_for':'campfire'}),f"{self.world_id}:{actor_id}:implicit:{wt}"))
                cs=c.execute("SELECT * FROM campsite_instances WHERE campsite_instance_id=?",(csid,)).fetchone()
            prev=self._active_campfire_for_owner(c,actor_id)
            if prev:
                replaced=True; c.execute("UPDATE campfire_instances SET status='replaced',last_updated_world_time=?,updated_at=? WHERE campfire_instance_id=?",(wt,now,prev['campfire_instance_id']))

            meta={'profile':prof.get('id'),'object_type':'campfire','owner_actor_id':actor_id,'creator_actor_id':actor_id,'source_ability_id':'build_campfire','source_service':'SurvivalNeedsService','created_world_time':wt,'expires_world_time':exp,'lifecycle_status':'active','uniqueness_scope':'owner','uniqueness_group':'campfire','replacement_policy':'replace_previous','parent_object_id':cs['campsite_instance_id'],'description_source':'campfire_profile','keywords':['campfire','fire','ashes']}
            c.execute("INSERT OR REPLACE INTO campfire_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,profile_id,room_id,actor_id,'unlit',0,None,exp,wt,now,now,_json(meta)))
        self._publish('runtime_object_created', {'world_id':self.world_id,'room_id':room_id,'object_id':iid,'template_profile_id':profile_id,'owner_actor_id':actor_id,'creator_actor_id':actor_id,'source_ability_id':'build_campfire','lifecycle_reason':'created','world_time':wt})
        self._publish('campfire_built', {'actor_id':actor_id,'campfire_instance_id':iid,'room_id':room_id,'world_time':wt})
        return {'ok':True,'campfire_instance_id':iid,'status':'unlit','expires_world_time':exp,'replaced_previous':replaced}
    def light_campfire(self, actor_id, campfire_instance_id):
        wt=self._world_minutes(); now=utc_now()
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM campfire_instances WHERE campfire_instance_id=? AND status IN ('unlit','low_fuel','extinguished')",(campfire_instance_id,)).fetchone()
            if not r: return {'ok':False,'reason':'not_found_or_inactive'}
            c.execute("UPDATE campfire_instances SET status='lit',lit_world_time=?,last_updated_world_time=?,updated_at=? WHERE campfire_instance_id=?",(wt,wt,now,campfire_instance_id))
        self._publish('runtime_object_state_changed', self._runtime_event_payload(dict(r) if hasattr(r, 'keys') else {'campfire_instance_id': r[0], 'world_id': r[1], 'profile_id': r[2], 'room_id': r[3], 'owner_actor_id': r[4], 'status': r[5], 'expires_world_time': r[8]},'campfire_instance_id','lit'))
        self._publish('campfire_lit', {'actor_id':actor_id,'campfire_instance_id':campfire_instance_id}); return {'ok':True,'status':'lit','expires_world_time':(r['expires_world_time'] if hasattr(r, 'keys') else r[8])}
    def add_campfire_fuel(self, actor_id, campfire_instance_id, item_instance_id=None):
        eid=f"fuel_{_stable(campfire_instance_id,item_instance_id or 'generic',actor_id)}"; now=utc_now()
        with sqlite3.connect(self.db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM campfire_fuel_events WHERE fuel_event_id=?",(eid,)).fetchone(): return {'ok':True,'duplicate':True}
            c.execute("UPDATE campfire_instances SET fuel_current=MAX(0,COALESCE(fuel_current,0))+1,status=CASE WHEN status='extinguished' THEN 'unlit' ELSE status END,updated_at=? WHERE campfire_instance_id=? AND status IN ('unlit','lit','extinguished','low_fuel')",(now,campfire_instance_id)); c.execute("INSERT INTO campfire_fuel_events VALUES(?,?,?,?,?,?,?,?,?)",(eid,campfire_instance_id,self.world_id,actor_id,item_instance_id,1,self._world_minutes(),now,_json({})))
        self._publish('campfire_fueled', {'actor_id':actor_id,'campfire_instance_id':campfire_instance_id}); return {'ok':True,'fuel_added':1}
    def extinguish_campfire(self, actor_id, campfire_instance_id):
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE campfire_instances SET status='extinguished',updated_at=? WHERE campfire_instance_id=? AND status='lit'",(utc_now(),campfire_instance_id))
        self._publish('campfire_extinguished', {'actor_id':actor_id,'campfire_instance_id':campfire_instance_id}); return {'ok':True,'status':'extinguished'}
    def trace_campfire(self, iid):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM campfire_instances WHERE campfire_instance_id=?",(iid,)).fetchone(); return dict(r) if r else {}
    def create_campsite(self, actor_id, profile_id='basic_campsite', room_id=None):
        room_id=room_id or self._room_for_actor(actor_id); wt=self._world_minutes(); iid=f"campsite_{_stable(self.world_id,profile_id,room_id,actor_id,wt)}"; prof=self.content.get('campsite_profiles',profile_id); now=utc_now(); exp=wt+int(prof.get('duration_minutes',480) or 480); replaced=False
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; c.execute('BEGIN IMMEDIATE')
            prev_here=self._active_campsite_for_owner(c,actor_id,room_id)
            if prev_here:
                return {'ok':False,'reason':'existing_campsite','message':'A campsite is already established here.','campsite_instance_id':prev_here['campsite_instance_id']}
            prev=self._active_campsite_for_owner(c,actor_id)
            if prev:
                replaced=True; c.execute("UPDATE campsite_instances SET status='replaced',updated_at=? WHERE campsite_instance_id=?",(now,prev['campsite_instance_id']))
                self._retire_child_campfires(c,prev['campsite_instance_id'],'replaced','parent_replaced',wt,now)

            meta={'object_type':'campsite','owner_actor_id':actor_id,'creator_actor_id':actor_id,'source_ability_id':'set_camp','source_service':'SurvivalNeedsService','created_world_time':wt,'expires_world_time':exp,'lifecycle_status':'active','uniqueness_scope':'owner','uniqueness_group':'campsite','replacement_policy':'replace_previous','description_source':'campsite_profile','keywords':['campsite','camp','site']}
            c.execute("INSERT OR REPLACE INTO campsite_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,profile_id,room_id,actor_id,'active',_json([actor_id]),wt,exp,now,now,_json(meta),f"{self.world_id}:{actor_id}:campsite:{room_id}:{wt}"))
        self._publish('runtime_object_created', {'world_id':self.world_id,'room_id':room_id,'object_id':iid,'template_profile_id':profile_id,'owner_actor_id':actor_id,'creator_actor_id':actor_id,'source_ability_id':'set_camp','lifecycle_reason':'created','world_time':wt})
        self._publish('campsite_established', {'actor_id':actor_id,'campsite_instance_id':iid,'room_id':room_id,'world_time':wt}); return {'ok':True,'campsite_instance_id':iid,'status':'active','expires_world_time':exp,'replaced_previous':replaced}
    def dismantle_campsite(self, actor_id, campsite_instance_id=''):
        wt=self._world_minutes(); now=utc_now()
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            r=c.execute("SELECT * FROM campsite_instances WHERE campsite_instance_id=?",(campsite_instance_id,)).fetchone() if campsite_instance_id else self._active_campsite_for_owner(c,actor_id,self._room_for_actor(actor_id))
            if not r: return {'ok':False,'reason':'not_found'}
            c.execute("UPDATE campsite_instances SET status='dismantled',updated_at=? WHERE campsite_instance_id=? AND status IN ('active','occupied','abandoned')",(now,r['campsite_instance_id']))
            self._retire_child_campfires(c,r['campsite_instance_id'],'dismantled','parent_dismantled',wt,now)
        self._publish('campsite_dismantled', {'actor_id':actor_id,'campsite_instance_id':r['campsite_instance_id']}); return {'ok':True,'status':'dismantled'}
    def trace_campsite(self, iid):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM campsite_instances WHERE campsite_instance_id=?",(iid,)).fetchone(); return dict(r) if r else {}

    def process_due_runtime_objects(self, world_time: int|dict[str,Any]):
        target=int((world_time.get('total_minutes') if world_time.get('total_minutes') is not None else (int(world_time.get('day',1))-1)*1440+int(world_time.get('hour',0))*60+int(world_time.get('minute',0))) if isinstance(world_time,dict) else world_time); now=utc_now(); expired=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; c.execute('BEGIN IMMEDIATE')
            for r in c.execute("SELECT * FROM campsite_instances WHERE world_id=? AND status IN ('active','occupied','abandoned') AND expires_world_time IS NOT NULL AND expires_world_time<=?",(self.world_id,target)).fetchall():
                c.execute("UPDATE campsite_instances SET status='expired',updated_at=? WHERE campsite_instance_id=?",(now,r['campsite_instance_id'])); self._retire_child_campfires(c,r['campsite_instance_id'],'expired','parent_expired',target,now); expired.append(('runtime_object_expired', self._runtime_event_payload(dict(r),'campsite_instance_id','expired')))
            for r in c.execute("SELECT * FROM campfire_instances WHERE world_id=? AND status IN ('unlit','lit','extinguished','low_fuel') AND expires_world_time IS NOT NULL AND expires_world_time<=?",(self.world_id,target)).fetchall():
                c.execute("UPDATE campfire_instances SET status='expired',last_updated_world_time=?,updated_at=? WHERE campfire_instance_id=?",(target,now,r['campfire_instance_id'])); expired.append(('runtime_object_expired', self._runtime_event_payload(dict(r),'campfire_instance_id','expired')))
            for r in c.execute("SELECT cf.* FROM campfire_instances cf LEFT JOIN campsite_instances cs ON json_extract(cf.metadata_json,'$.parent_object_id')=cs.campsite_instance_id WHERE cf.world_id=? AND cf.status IN ('unlit','lit','extinguished','low_fuel') AND json_extract(cf.metadata_json,'$.parent_object_id') IS NOT NULL AND (cs.campsite_instance_id IS NULL OR cs.status NOT IN ('active','occupied','abandoned'))",(self.world_id,)).fetchall():
                c.execute("UPDATE campfire_instances SET status='expired',last_updated_world_time=?,updated_at=? WHERE campfire_instance_id=?",(target,now,r['campfire_instance_id'])); expired.append(('runtime_object_parent_removed', self._runtime_event_payload(dict(r),'campfire_instance_id','orphan_cleanup')))
        for event,payload in expired: self._publish(event,payload)
        return {'expired_count':len(expired),'events':[p for _,p in expired]}

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
        c.execute("CREATE TABLE IF NOT EXISTS actor_rest_sessions(rest_session_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,rest_type TEXT,location_type TEXT,location_id TEXT,room_id TEXT,status TEXT,started_world_time INTEGER,planned_end_world_time INTEGER,last_updated_world_time INTEGER,quality_score REAL,interruption_reason TEXT,idempotency_key TEXT UNIQUE,result_json TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_rest_one_active ON actor_rest_sessions(world_id,actor_id) WHERE status IN ('started','resting','sleeping')")
        c.execute("CREATE TABLE IF NOT EXISTS rest_session_results(rest_session_result_id TEXT PRIMARY KEY,rest_session_id TEXT UNIQUE,world_id TEXT,actor_id TEXT,completed_world_time INTEGER,created_at TEXT,result_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS campfire_instances(campfire_instance_id TEXT PRIMARY KEY,world_id TEXT,profile_id TEXT,room_id TEXT,created_by_actor_id TEXT,status TEXT,fuel_current INTEGER,lit_world_time INTEGER,expires_world_time INTEGER,last_updated_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS campfire_fuel_events(fuel_event_id TEXT PRIMARY KEY,campfire_instance_id TEXT,world_id TEXT,actor_id TEXT,item_instance_id TEXT,fuel_added INTEGER,world_time INTEGER,created_at TEXT,metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS campsite_instances(campsite_instance_id TEXT PRIMARY KEY,world_id TEXT,profile_id TEXT,room_id TEXT,created_by_actor_id TEXT,status TEXT,occupant_actor_ids_json TEXT,created_world_time INTEGER,expires_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,idempotency_key TEXT UNIQUE)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actor_need_state_actor ON actor_need_state(actor_id,status)")
