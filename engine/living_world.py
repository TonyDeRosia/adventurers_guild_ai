"""Deterministic Phase 5B living-world services."""
from __future__ import annotations
import json, sqlite3, uuid
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

NEED_TYPES=("energy","hunger","thirst","safety","social","duty","comfort")
GOAL_STATUSES={"pending","active","blocked","completed","failed","cancelled"}

def now(): return datetime.now(timezone.utc).isoformat()
def jload(v,d):
    try: return json.loads(v or json.dumps(d))
    except Exception: return deepcopy(d)
def clamp(v, lo=-100, hi=100): return max(lo, min(hi, float(v)))

def init_living_schema(db_path):
    with sqlite3.connect(db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS world_time (world_id TEXT PRIMARY KEY,current_day INTEGER,current_hour INTEGER,current_minute INTEGER,time_scale REAL DEFAULT 1,paused INTEGER DEFAULT 1,last_real_timestamp TEXT,updated_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS entity_simulation_state (entity_instance_id TEXT PRIMARY KEY,world_id TEXT,template_id TEXT,source_spawn_id TEXT,personal_name TEXT,display_name TEXT,room_id TEXT,home_room_id TEXT,work_room_id TEXT,spawn_room_id TEXT,current_state TEXT,current_activity TEXT,current_goal_id TEXT,schedule_id TEXT,schedule_entry_id TEXT,simulation_enabled INTEGER DEFAULT 1,last_simulated_at TEXT,next_simulation_at TEXT,created_at TEXT,updated_at TEXT,custom_state JSON,plugin_data JSON,emotional_state JSON)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_entity_sim_world ON entity_simulation_state(world_id)")
        c.execute("CREATE TABLE IF NOT EXISTS entity_needs (id TEXT PRIMARY KEY,world_id TEXT,entity_instance_id TEXT,need_type TEXT,current_value REAL,minimum REAL,maximum REAL,decay_rate REAL,recovery_rate REAL,threshold_low REAL,threshold_critical REAL,disabled INTEGER DEFAULT 0,last_updated_at TEXT,created_at TEXT,updated_at TEXT,plugin_data JSON,UNIQUE(entity_instance_id,need_type))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_entity_needs_entity ON entity_needs(entity_instance_id)")
        c.execute("CREATE TABLE IF NOT EXISTS entity_goals (id TEXT PRIMARY KEY,world_id TEXT,entity_instance_id TEXT,goal_type TEXT,title TEXT,description TEXT,source TEXT,priority INTEGER,status TEXT,target_entity_id TEXT,target_room_id TEXT,target_feature_id TEXT,target_item_instance_id TEXT,created_at TEXT,updated_at TEXT,expires_at TEXT,completed_at TEXT,failure_reason TEXT,metadata JSON)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_entity_goals_entity ON entity_goals(entity_instance_id,status,priority,created_at,id)")
        c.execute("CREATE TABLE IF NOT EXISTS entity_relationships (id TEXT PRIMARY KEY,world_id TEXT,source_entity_instance_id TEXT,target_type TEXT,target_id TEXT,relationship_type TEXT,affinity REAL,trust REAL,fear REAL,respect REAL,familiarity REAL,debt REAL,status TEXT,first_met_at TEXT,last_interaction_at TEXT,created_at TEXT,updated_at TEXT,metadata JSON,UNIQUE(source_entity_instance_id,target_type,target_id,relationship_type))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_entity_relationships_source ON entity_relationships(source_entity_instance_id)")
        c.execute("CREATE TABLE IF NOT EXISTS entity_memories (id TEXT PRIMARY KEY,world_id TEXT,entity_instance_id TEXT,memory_type TEXT,subject_type TEXT,subject_id TEXT,summary TEXT,facts JSON,importance INTEGER,emotional_valence REAL,confidence REAL,source_event_type TEXT,source_event_id TEXT,occurred_at TEXT,created_at TEXT,last_recalled_at TEXT,recall_count INTEGER DEFAULT 0,expires_at TEXT,permanent INTEGER DEFAULT 0,tags JSON,metadata JSON,UNIQUE(entity_instance_id,source_event_type,source_event_id))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_entity_memories_entity ON entity_memories(entity_instance_id,importance,created_at)")
        c.commit()

class LivingWorldService:
    def __init__(self, runtime): self.rt=runtime; init_living_schema(runtime.state_store.db_path)
    @property
    def db(self): return self.rt.state_store.db_path
    def ensure_world_time(self, world_id):
        t=now()
        with sqlite3.connect(self.db) as c:
            r=c.execute("SELECT world_id,current_day,current_hour,current_minute,time_scale,paused,last_real_timestamp,updated_at FROM world_time WHERE world_id=?",(world_id,)).fetchone()
            if not r:
                c.execute("INSERT INTO world_time VALUES(?,?,?,?,?,?,?,?)",(world_id,1,6,0,1.0,1,t,t)); r=(world_id,1,6,0,1.0,1,t,t)
        return {"world_id":r[0],"day":r[1],"hour":r[2],"minute":r[3],"time_scale":r[4],"paused":bool(r[5]),"last_real_timestamp":r[6],"updated_at":r[7]}
    def set_world_time(self, world_id, day, hhmm=None, hour=None, minute=None):
        if hhmm is not None: hour,minute=[int(x) for x in str(hhmm).split(":",1)]
        day=max(1,int(day)); hour=int(hour)%24; minute=int(minute)%60; t=now()
        with sqlite3.connect(self.db) as c: c.execute("INSERT OR REPLACE INTO world_time VALUES(?,?,?,?,COALESCE((SELECT time_scale FROM world_time WHERE world_id=?),1),COALESCE((SELECT paused FROM world_time WHERE world_id=?),1),?,?)",(world_id,day,hour,minute,world_id,world_id,t,t))
        return self.ensure_world_time(world_id)
    def advance_world_time(self, world_id, minutes):
        cur=self.ensure_world_time(world_id); total=(cur['day']-1)*1440+cur['hour']*60+cur['minute']+int(minutes); day=total//1440+1; rem=total%1440
        out=self.set_world_time(world_id,day,hour=rem//60,minute=rem%60); self.rt.event_bus.publish('world_time_advanced', {'world_id':world_id,'minutes':int(minutes),**out}, source_system='simulation', world_id=world_id); return out
    def pause_world_time(self, world_id):
        self.ensure_world_time(world_id); t=now()
        with sqlite3.connect(self.db) as c: c.execute("UPDATE world_time SET paused=1,updated_at=? WHERE world_id=?",(t,world_id))
        return self.ensure_world_time(world_id)
    def resume_world_time(self, world_id):
        self.ensure_world_time(world_id); t=now()
        with sqlite3.connect(self.db) as c: c.execute("UPDATE world_time SET paused=0,last_real_timestamp=?,updated_at=? WHERE world_id=?",(t,t,world_id))
        return self.ensure_world_time(world_id)
    def _schedules(self): return {str(s.get('id')):s for s in getattr(self.rt.active_world,'schedules',[]) or [] if s.get('id')}
    def ensure_entity_state(self, ent):
        eid=ent['instance_id']; st=ent.get('state') or {}; plug=ent.get('plugin_data') or {}; tmpl=dict(self.rt.entity_templates.get(ent.get('template_id') or '',{})); sim={**(tmpl.get('plugin_data') or {}).get('simulation',{}), **plug.get('simulation',{}), **st.get('simulation',{})}
        spawn=st.get('source_spawn_id',''); sp=(self.rt._live_entity_spawns().get(spawn,{}) if hasattr(self.rt,'_live_entity_spawns') else {})
        for k in ('schedule_id','home_room_id','work_room_id','simulation_enabled'):
            if sp.get(k) not in (None,''): sim[k]=sp.get(k)
        t=now()
        vals=(eid,ent.get('world_id') or self.rt.active_world_id,ent.get('template_id'),spawn,sim.get('personal_name') or ent.get('name'),sim.get('display_name') or ent.get('name'),ent.get('room_id'),sim.get('home_room_id') or st.get('spawn_origin'),sim.get('work_room_id') or ent.get('room_id'),st.get('spawn_origin') or ent.get('room_id'),st.get('current_state','idle'),st.get('current_activity') or sim.get('default_activity','idle'),sim.get('current_goal_id',''),sim.get('schedule_id',''),sim.get('schedule_entry_id',''),0 if sim.get('simulation_enabled') is False else 1,t,'',t,t,json.dumps(st.get('custom_state') or {}),json.dumps(plug),json.dumps(sim.get('emotional_state') or {"valence":0,"arousal":0,"fear":0,"anger":0,"trust":0,"stress":0,"contentment":0}))
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT OR IGNORE INTO entity_simulation_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
        self.ensure_needs(eid)
        return self.get_sim_state(eid)
    def get_sim_state(self,eid):
        with sqlite3.connect(self.db) as c: r=c.execute("SELECT * FROM entity_simulation_state WHERE entity_instance_id=?",(eid,)).fetchone(); cols=[x[1] for x in c.execute('PRAGMA table_info(entity_simulation_state)')]
        return dict(zip(cols,r)) if r else {}
    def ensure_needs(self,eid):
        ent=self.rt.find_entity(eid); defaults=((ent or {}).get('plugin_data') or {}).get('need_profile',{}) if ent else {}; t=now()
        with sqlite3.connect(self.db) as c:
            for n in NEED_TYPES:
                d=defaults.get(n,{}) if isinstance(defaults.get(n,{}),dict) else {}
                c.execute("INSERT OR IGNORE INTO entity_needs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(f"need_{eid}_{n}", self.rt.active_world_id or '', eid,n,float(d.get('current_value',100)),0,100,float(d.get('decay_rate',0.01)),float(d.get('recovery_rate',0.05)),float(d.get('threshold_low',30)),float(d.get('threshold_critical',10)),1 if d.get('disabled') else 0,t,t,t,json.dumps(d.get('plugin_data',{}))))
    def get_entity_profile(self,eid):
        ent=self.rt.find_entity(eid) or {}; tmpl=dict(self.rt.entity_templates.get(ent.get('template_id') or '',{})); base=deepcopy((tmpl.get('plugin_data') or {}).get('ai_profile') or (tmpl.get('plugin_data') or {}).get('profile') or {})
        over=deepcopy((ent.get('plugin_data') or {}).get('ai_profile') or (ent.get('plugin_data') or {}).get('profile') or {})
        def merge(a,b):
            for k,v in b.items(): a[k]=merge(a.get(k,{}) if isinstance(a.get(k),dict) else {},v) if isinstance(v,dict) else deepcopy(v)
            return a
        prof=merge(base,over); sim=self.ensure_entity_state(ent) if ent else {}
        prof.setdefault('identity',{}).update({k:v for k,v in {'personal_name':sim.get('personal_name') or ent.get('name'),'species':tmpl.get('race'),'occupation':tmpl.get('class')}.items() if v})
        return prof
    def evaluate_schedule(self,eid, world_time=None):
        ent=self.rt.find_entity(eid) or {}; sim=self.ensure_entity_state(ent); sched=self._schedules().get(sim.get('schedule_id') or '')
        wt=world_time or self.ensure_world_time(ent.get('world_id') or self.rt.active_world_id or ''); minute=wt['hour']*60+wt['minute']; best=None
        if sched:
            for e in sched.get('entries') or []:
                sh,sm=[int(x) for x in e.get('start_time','00:00').split(':')]; eh,em=[int(x) for x in e.get('end_time','23:59').split(':')]; s=sh*60+sm; end=eh*60+em; inwin=(s<=minute<end) if end>s else (minute>=s or minute<end)
                if inwin and (best is None or int(e.get('priority',0))>int(best.get('priority',0)) or str(e.get('id'))<str(best.get('id'))): best=e
        if not best: best={'id':'fallback','activity':'idle','target_room_id':sim.get('room_id') or ent.get('room_id'),'required_state':'idle'}
        
        activity=best.get('activity') or best.get('fallback_activity') or 'idle'
        target=best.get('target_room_id') or best.get('fallback_room_id')
        if not target and activity in {'working','guarding','patrolling'}: target=sim.get('work_room_id')
        if not target and activity in {'sleeping','resting'}: target=sim.get('home_room_id')
        return {'entity_instance_id':eid,'schedule_id':sim.get('schedule_id'),'schedule_entry_id':best.get('id'),'activity':activity,'target_room_id':target or sim.get('room_id'),'state':best.get('required_state') or 'active','entry':best}
    def apply_schedule(self,eid, world_time=None):
        ev=self.evaluate_schedule(eid,world_time); ent=self.rt.find_entity(eid) or {}; sim=self.ensure_entity_state(ent); t=now()
        state=ent.get('state') or {}; state['current_state']=ev['state']; state['current_activity']=ev['activity']; self.rt.update_entity_state(eid,state,source_system='simulation')
        with sqlite3.connect(self.db) as c: c.execute("UPDATE entity_simulation_state SET current_state=?,current_activity=?,schedule_entry_id=?,room_id=?,last_simulated_at=?,updated_at=? WHERE entity_instance_id=?",(ev['state'],ev['activity'],ev['schedule_entry_id'],ent.get('room_id'),t,t,eid))
        target=ev.get('target_room_id')
        if target and target!=ent.get('room_id'):
            path=self.find_room_path(ent.get('room_id'), target)
            if path.get('ok') and len(path['path'])>1: self.rt.move_entity(eid,path['path'][1],source_system='simulation',schedule_entry_id=ev['schedule_entry_id'])
            elif not path.get('ok'): self.create_entity_goal(eid,'go_to_room','Go to scheduled room','schedule',target_room_id=target,status='blocked',failure_reason=path.get('reason','unreachable'))
        self.rt.event_bus.publish('entity_schedule_entry_started', ev, source_system='simulation', world_id=ent.get('world_id',''), room_id=target or '')
        return ev
    def find_room_path(self,start,target,max_depth=20):
        if start==target: return {'ok':True,'path':[start]}
        rooms={str(r.get('id')):r for r in getattr(self.rt.active_world,'rooms',[]) or []}; q=deque([(start,[start])]); seen={start}
        while q:
            rid,path=q.popleft()
            if len(path)>max_depth: continue
            exits=rooms.get(rid,{}).get('exits') or []
            if isinstance(exits,dict): exits=exits.values()
            edges=[]
            for ex in exits:
                if (ex.get('flags') and any(f in ex.get('flags') for f in ['broken','closed','locked','hidden'])): continue
                to=ex.get('target_room_id') or ex.get('destination_room_id') or ex.get('room_id') or ex.get('to') or ex.get('target')
                if to in rooms: edges.append(str(to))
            for nxt in sorted(set(edges)):
                if nxt in seen: continue
                if nxt==target: return {'ok':True,'path':path+[nxt]}
                seen.add(nxt); q.append((nxt,path+[nxt]))
        return {'ok':False,'path':[],'reason':'unreachable_or_depth_exceeded'}
    def list_needs(self,eid):
        with sqlite3.connect(self.db) as c: rows=c.execute("SELECT need_type,current_value,minimum,maximum,threshold_low,threshold_critical,disabled FROM entity_needs WHERE entity_instance_id=? ORDER BY need_type",(eid,)).fetchall()
        return [{'need_type':r[0],'current_value':r[1],'minimum':r[2],'maximum':r[3],'threshold_low':r[4],'threshold_critical':r[5],'disabled':bool(r[6])} for r in rows]
    def advance_needs(self,eid,minutes):
        self.ensure_needs(eid); out=[]; t=now()
        low_energy=False
        with sqlite3.connect(self.db) as c:
            rows=c.execute("SELECT id,need_type,current_value,minimum,maximum,decay_rate,recovery_rate,threshold_low,disabled FROM entity_needs WHERE entity_instance_id=?",(eid,)).fetchall()
            for r in rows:
                if r[8]: continue
                nv=max(r[3],min(r[4],float(r[2])-float(r[5])*minutes)); c.execute("UPDATE entity_needs SET current_value=?,last_updated_at=?,updated_at=? WHERE id=?",(nv,t,t,r[0])); out.append((r[1],nv))
                if r[1]=='energy' and nv<=float(r[7]): low_energy=True
        if low_energy: self.create_entity_goal(eid,'rest','Rest','need',priority=70,metadata={'need':'energy'})
        return out
    def create_entity_goal(self,eid,goal_type,title,source,priority=50,status='pending',target_room_id='',failure_reason='',metadata=None,**kw):
        metadata=metadata or {}; gid=kw.get('goal_id') or f"goal_{eid}_{source}_{goal_type}_{target_room_id or metadata.get('need','') or 'generic'}"
        t=now(); ent=self.rt.find_entity(eid) or {}
        with sqlite3.connect(self.db) as c:
            exists=c.execute("SELECT id FROM entity_goals WHERE id=?",(gid,)).fetchone()
            if not exists: c.execute("INSERT INTO entity_goals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(gid,ent.get('world_id') or self.rt.active_world_id,eid,goal_type,title,kw.get('description',''),source,int(priority),status,kw.get('target_entity_id',''),target_room_id,kw.get('target_feature_id',''),kw.get('target_item_instance_id',''),t,t,kw.get('expires_at',''),kw.get('completed_at',''),failure_reason,json.dumps(metadata)))
        return gid
    def list_goals(self,eid,status=None):
        q="SELECT id,goal_type,title,source,priority,status,target_room_id,created_at,failure_reason FROM entity_goals WHERE entity_instance_id=?"+(" AND status=?" if status else "")+" ORDER BY priority DESC,created_at,id"; params=(eid,status) if status else (eid,)
        with sqlite3.connect(self.db) as c: rows=c.execute(q,params).fetchall()
        return [dict(zip(['id','goal_type','title','source','priority','status','target_room_id','created_at','failure_reason'],r)) for r in rows]
    def select_goal(self,eid):
        gs=self.list_goals(eid); return next((g for g in gs if g['status'] in ('active','pending','blocked')), None)
    def record_memory(self,eid,memory_type,summary,subject_type='',subject_id='',source_event_type='',source_event_id='',importance=1,permanent=False,facts=None,metadata=None):
        mid=f"mem_{eid}_{source_event_type or memory_type}_{source_event_id or uuid.uuid4().hex}"; ent=self.rt.find_entity(eid) or {}; t=now()
        with sqlite3.connect(self.db) as c: c.execute("INSERT OR IGNORE INTO entity_memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,ent.get('world_id') or self.rt.active_world_id,eid,memory_type,subject_type,subject_id,summary,json.dumps(facts or {}),int(importance),0,1,source_event_type,source_event_id,t,t,'',0,'',1 if permanent else 0,json.dumps([]),json.dumps(metadata or {})))
        return mid
    def query_memories(self,eid,subject_type='',subject_id='',limit=10):
        q="SELECT id,memory_type,subject_type,subject_id,summary,importance,created_at,permanent FROM entity_memories WHERE entity_instance_id=?"; p=[eid]
        if subject_type: q+=' AND subject_type=?'; p.append(subject_type)
        if subject_id: q+=' AND subject_id=?'; p.append(subject_id)
        q+=' ORDER BY importance DESC,created_at DESC,id LIMIT ?'; p.append(int(limit))
        with sqlite3.connect(self.db) as c: rows=c.execute(q,p).fetchall()
        return [dict(zip(['id','memory_type','subject_type','subject_id','summary','importance','created_at','permanent'],r)) for r in rows]
    def get_context(self,eid):
        ent=self.rt.find_entity(eid) or {}; sim=self.ensure_entity_state(ent); room=self.rt._live_room_data(ent.get('room_id')) or {}; contents=self.rt.get_room_contents(ent.get('room_id')) if ent.get('room_id') else {'entity_instances':[],'item_instances':[],'features':[]}
        return {'identity':{'instance_id':eid,'template_id':ent.get('template_id'),'display_name':sim.get('display_name') or ent.get('name')},'profile':self.get_entity_profile(eid),'current_room':{k:room.get(k) for k in ('id','name','description','area_id','zone_id')},'world_time':self.ensure_world_time(ent.get('world_id') or self.rt.active_world_id or ''),'current_state':sim.get('current_state'),'current_activity':sim.get('current_activity'),'current_schedule_entry':self.evaluate_schedule(eid),'active_goals':self.list_goals(eid,'active') or ([self.select_goal(eid)] if self.select_goal(eid) else []),'needs_summary':self.list_needs(eid),'recent_important_memories':self.query_memories(eid,limit=5),'visible_entity_instances':[{'instance_id':x.get('instance_id'),'template_id':x.get('template_id'),'name':x.get('name')} for x in contents.get('entity_instances',[]) if x.get('instance_id')!=eid],'visible_item_instances':contents.get('item_instances',[]),'visible_room_features':contents.get('features',[]),'known_facts_topics':(self.get_entity_profile(eid).get('knowledge') or {}),'knowledge_boundaries':(self.get_entity_profile(eid).get('boundaries') or {})}
    def simulate_world(self,world_id,minutes):
        self.rt.event_bus.publish('simulation_tick_started',{'world_id':world_id,'minutes':minutes},source_system='simulation',world_id=world_id); wt=self.advance_world_time(world_id,minutes)
        for ent in self.rt._fetch_entities('world_id=?',(world_id,)):
            self.ensure_entity_state(ent); self.advance_needs(ent['instance_id'],minutes); self.apply_schedule(ent['instance_id'],wt)
        self.rt.event_bus.publish('simulation_tick_completed',{'world_id':world_id,'minutes':minutes},source_system='simulation',world_id=world_id); return wt
