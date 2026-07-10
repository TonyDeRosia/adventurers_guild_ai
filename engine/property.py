"""Phase 10B canonical property, lease, access, storage, and home foundations."""
from __future__ import annotations
import hashlib, json, re, sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE=re.compile(r"^[A-Za-z0-9_.:-]+$")
def utc_now(): return datetime.now(timezone.utc).isoformat()
def jdump(v): return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def jload(v, default=None):
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def stable_id(prefix,*parts):
    raw="|".join(json.dumps(p,sort_keys=True,default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
def safe_id(v): return bool(v and SAFE_ID_RE.fullmatch(str(v)))

PROPERTY_TYPES={"inn_room","apartment","house","locker","safe_deposit_box","warehouse","guild_storage_placeholder","organization_property","private_room","rental_unit","owned_unit","custom"}
PROPERTY_STATUSES={"available","reserved","occupied","leased","owned","delinquent","suspended","expired","closed","archived","custom"}
LEASE_STATUSES={"pending","active","grace","delinquent","terminated","expired","evicted","cancelled","refunded"}
ACTIONS={"enter","exit","open_door","close_door","lock","unlock","store","retrieve","invite_guest","remove_guest","manage_access","renew","terminate","transfer","inspect","custom"}

SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS property_instances(property_instance_id TEXT PRIMARY KEY,world_id TEXT,property_definition_id TEXT,property_type TEXT,name TEXT,status TEXT,owner_type TEXT,owner_id TEXT,lease_id TEXT,primary_room_id TEXT,entry_room_id TEXT,parent_property_id TEXT,created_world_time INTEGER,activated_world_time INTEGER,expired_world_time INTEGER,closed_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,property_definition_id,parent_property_id));
CREATE INDEX IF NOT EXISTS idx_property_instances_owner ON property_instances(owner_type,owner_id,status);
CREATE TABLE IF NOT EXISTS property_leases(lease_id TEXT PRIMARY KEY,world_id TEXT,property_instance_id TEXT,tenant_type TEXT,tenant_id TEXT,landlord_type TEXT,landlord_id TEXT,status TEXT,started_world_time INTEGER,ends_world_time INTEGER,next_payment_world_time INTEGER,grace_ends_world_time INTEGER,deposit_transaction_id TEXT,rent_transaction_id TEXT,renewal_count INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_property_active_lease ON property_leases(property_instance_id) WHERE status IN ('pending','active','grace','delinquent');
CREATE TABLE IF NOT EXISTS property_occupants(occupancy_id TEXT PRIMARY KEY,property_instance_id TEXT,actor_id TEXT,occupancy_type TEXT,status TEXT,entered_world_time INTEGER,left_world_time INTEGER,access_grant_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_property_active_occupant ON property_occupants(property_instance_id,actor_id,occupancy_type) WHERE status='active';
CREATE TABLE IF NOT EXISTS property_access_grants(access_grant_id TEXT PRIMARY KEY,property_instance_id TEXT,subject_type TEXT,subject_id TEXT,grant_type TEXT,permissions_json TEXT,status TEXT,granted_by_actor_id TEXT,granted_world_time INTEGER,expires_world_time INTEGER,revoked_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_property_grants_subject ON property_access_grants(subject_type,subject_id,status);
CREATE TABLE IF NOT EXISTS property_storage_containers(storage_container_id TEXT PRIMARY KEY,world_id TEXT,property_instance_id TEXT,storage_profile_id TEXT,owner_type TEXT,owner_id TEXT,name TEXT,status TEXT,capacity_items INTEGER,capacity_weight INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,property_instance_id,storage_profile_id,owner_type,owner_id));
CREATE TABLE IF NOT EXISTS actor_home_locations(home_location_id TEXT PRIMARY KEY,actor_id TEXT,property_instance_id TEXT,room_id TEXT,status TEXT,set_world_time INTEGER,cleared_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_active_home ON actor_home_locations(actor_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS property_audit_events(audit_event_id TEXT PRIMARY KEY,property_instance_id TEXT,actor_id TEXT,operation TEXT,target_type TEXT,target_id TEXT,old_value_json TEXT,new_value_json TEXT,reason TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
"""
def init_property_schema(db_path):
    with sqlite3.connect(db_path) as con: con.executescript(SCHEMA_SQL)

class PropertyContent:
    collections=["property_definitions","property_ownership_profiles","property_lease_profiles","property_pricing_profiles","property_access_profiles","property_key_profiles","property_storage_profiles","property_occupancy_profiles","property_guest_profiles","property_retention_profiles","property_eviction_profiles","property_message_profiles","property_render_profiles"]
    def __init__(self, world_root="worlds/shattered_realms"):
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}
    def _load(self,c):
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text()); items=raw.get(c,raw) if isinstance(raw,dict) else raw
                if isinstance(items,list): return {str(x.get('id')):x for x in items if isinstance(x,dict) and x.get('id')}
                if isinstance(items,dict): return {str(k):(v|{'id':v.get('id',k)} if isinstance(v,dict) else {'id':k}) for k,v in items.items()}
        return {}
    def get(self,c,i): return self.data.get(c,{}).get(str(i or ""))
    def list(self,c): return sorted(self.data.get(c,{}).values(), key=lambda x:x.get('id',''))
    def validate(self, room_ids=None, item_template_ids=None):
        errors=[]; warnings=[]; room_ids=set(room_ids or []); item_template_ids=set(item_template_ids or [])
        assigned={}
        for c, items in self.data.items():
            for iid,item in items.items():
                if not safe_id(iid): errors.append(f"{c}:{iid}: unsafe id")
                if c=="property_definitions":
                    if item.get('property_type','custom') not in PROPERTY_TYPES: errors.append(f"property {iid} invalid property_type")
                    for r in item.get('room_ids') or []:
                        if room_ids and r not in room_ids: errors.append(f"property {iid} unknown room {r}")
                        if item.get('private', True) and r in assigned: errors.append(f"room {r} assigned to conflicting properties {assigned[r]} and {iid}")
                        assigned[r]=iid
                    er=item.get('entry_room_id')
                    if er and room_ids and er not in room_ids: errors.append(f"property {iid} unknown entry room {er}")
                    if not er: warnings.append(f"property {iid} has no entry room")
                    for field, coll in [('access_profile_id','property_access_profiles'),('ownership_profile_id','property_ownership_profiles'),('lease_profile_id','property_lease_profiles'),('pricing_profile_id','property_pricing_profiles'),('key_profile_id','property_key_profiles')]:
                        if item.get(field) and item[field] not in self.data.get(coll,{}): errors.append(f"property {iid} unknown {field} {item[field]}")
                if c=="property_storage_profiles":
                    if int(item.get('capacity_items',0) or 0)<0 or int(item.get('capacity_weight',0) or 0)<0: errors.append(f"storage {iid} invalid capacity")
                    if int(item.get('capacity_items',0) or 0)==0: warnings.append(f"storage {iid} capacity is zero")
                if c=="property_key_profiles" and item.get('item_template_id') and item_template_ids and item.get('item_template_id') not in item_template_ids: errors.append(f"key {iid} unknown item template")
        return {"errors":errors,"warnings":warnings}

@dataclass(frozen=True)
class PropertyQuote:
    quote_id:str; quote_type:str; total:dict[str,int]; status:str="active"; trace:dict[str,Any]=field(default_factory=dict)

class PropertyService:
    def __init__(self, db_path, world_id="shattered_realms", world_root=None, event_bus=None, economy_service=None, written_content_service=None):
        self.db_path=Path(db_path); self.world_id=world_id; self.event_bus=event_bus; init_property_schema(self.db_path); self.content=PropertyContent(world_root or f"worlds/{world_id}"); self.economy=economy_service; self.written=written_content_service
    def publish(self,e,p):
        if self.event_bus and hasattr(self.event_bus,'publish'):
            try: self.event_bus.publish(e,p,source_system='property')
            except TypeError: self.event_bus.publish(e,p)
    def audit(self, con, pid, actor, op, target_type='', target_id='', old=None, new=None, reason='', world_time=0):
        aid=stable_id('paudit',pid,actor,op,target_type,target_id,world_time,utc_now()); con.execute("INSERT INTO property_audit_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(aid,pid,actor,op,target_type,target_id,jdump(old),jdump(new),reason,world_time,utc_now(),jdump({})))
    def get_property_definition(self, property_id): return self.content.get('property_definitions',property_id)
    def get_property_instance(self, pid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM property_instances WHERE property_instance_id=?",(pid,)).fetchone(); return dict(r) if r else None
    def materialize_property(self, definition_id, world_time=0, parent_property_id=''):
        d=self.get_property_definition(definition_id); 
        if not d: raise ValueError('unknown property definition')
        pid=stable_id('property',self.world_id,definition_id,parent_property_id); now=utc_now(); primary=(d.get('interior_room_ids') or d.get('room_ids') or [''])[0]
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO property_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,definition_id,d.get('property_type','custom'),d.get('name',definition_id),'available','','','',primary,d.get('entry_room_id',''),parent_property_id,world_time,None,None,None,now,now,jdump({'definition_version':d.get('version',1)})))
            if con.total_changes: self.audit(con,pid,'system','property_materialized','definition',definition_id,None,d,world_time=world_time); self.publish('property_materialized',{'property_instance_id':pid,'definition_id':definition_id})
        for spid in d.get('storage_profile_ids') or []: self.ensure_storage_container(pid, spid)
        return self.get_property_instance(pid)
    def list_available_properties(self, actor_id='', location=None, property_type=None):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; q="SELECT * FROM property_instances WHERE world_id=? AND status='available'"; p=[self.world_id]
            if property_type: q+=" AND property_type=?"; p.append(property_type)
            return [dict(r) for r in con.execute(q,p)]
    def _profile_price(self, definition, kind):
        pp=self.content.get('property_pricing_profiles',definition.get('pricing_profile_id')) or {}; currency=pp.get('currency_id','gold'); key={'rent':'rent_price','purchase':'purchase_price','renewal':'renewal_price','deposit':'deposit_amount'}.get(kind,kind); return currency, int(pp.get(key,0) or 0)
    def _quote(self, actor_id, pid, kind, duration=None):
        inst=self.get_property_instance(pid); d=self.get_property_definition(inst['property_definition_id']) if inst else None
        if not inst or not d: raise ValueError('unknown property')
        currency, amount=self._profile_price(d,kind); trace={'property_instance_id':pid,'duration':duration,'pricing_profile_id':d.get('pricing_profile_id'),'access_profile_id':d.get('access_profile_id'),'faction_modifier':d.get('faction_id'),'organization_modifier':d.get('organization_id')}
        qid=stable_id('pquote',self.world_id,kind,actor_id,pid,duration,amount)
        if self.economy and hasattr(self.economy,'quote_price'):
            eq=self.economy.quote_price(kind,buyer_id=actor_id,service_id=pid,base_price={currency:amount},currency_id=currency,metadata={'property_quote_id':qid,**trace}); qid=eq.quote_id
        return PropertyQuote(qid,kind,{currency:amount},'active',trace)
    def quote_rent(self, actor_id, property_instance_id, duration=None): return self._quote(actor_id,property_instance_id,'rent',duration)
    def quote_purchase(self, actor_id, property_instance_id): return self._quote(actor_id,property_instance_id,'purchase')
    def quote_renewal(self, actor_id, lease_id):
        lease=self.get_lease(lease_id); return self._quote(actor_id,lease['property_instance_id'],'renewal',None)
    def _charge_quote(self, actor_id, quote):
        tid=stable_id('ptxn',quote.quote_id,actor_id)
        if self.economy and hasattr(self.economy,'transfer_currency'):
            for cur,amt in quote.total.items():
                if amt: self.economy.transfer_currency('actor',actor_id,'system','property',cur,amt,transaction_id=tid,reason=f"property {quote.quote_type}",source_type='property_quote',source_id=quote.quote_id)
            if hasattr(self.economy,'create_transaction'): self.economy.create_transaction('service','actor',actor_id,'system','property',quote.total,quote_id=quote.quote_id,transaction_id=tid,status='completed',metadata={'property_quote':quote.trace})
        return tid
    def confirm_rent(self, actor_id, quote_id, duration_minutes=60, world_time=0):
        qrow=self.economy.get_quote(quote_id) if self.economy and hasattr(self.economy,'get_quote') else None; meta=jload(qrow.get('metadata_json') if qrow else '{}'); pid=(meta or {}).get('property_instance_id') or (qrow or {}).get('service_id')
        if not pid: raise ValueError('quote does not reference property')
        inst=self.get_property_instance(pid)
        if inst['status'] not in {'available','reserved'}: raise ValueError('property unavailable')
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; exists=con.execute("SELECT * FROM property_leases WHERE json_extract(metadata_json,'$.quote_id')=?",(quote_id,)).fetchone()
            if exists: return dict(exists)
        total=jload(qrow.get('currency_cost_json'),{}) if qrow else {}; tx=self._charge_quote(actor_id,PropertyQuote(quote_id,'rent',total,trace={'property_instance_id':pid}))
        lid=stable_id('lease',self.world_id,pid,actor_id,quote_id); now=utc_now(); ends=world_time+int(duration_minutes or 60)
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO property_leases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(lid,self.world_id,pid,'actor',actor_id,'system','property','active',world_time,ends,ends,ends, '',tx,0,now,now,jdump({'quote_id':quote_id})))
            con.execute("UPDATE property_instances SET status='leased', lease_id=?, owner_type='actor', owner_id=?, updated_at=? WHERE property_instance_id=?",(lid,actor_id,now,pid))
            self.grant_access(actor_id,pid,actor_id,['enter','exit','store','retrieve','renew','terminate','invite_guest'],grant_type='tenant',world_time=world_time,con=con)
            self.audit(con,pid,actor_id,'property_rented','lease',lid,None,{'lease_id':lid},world_time=world_time)
        self.publish('property_rented',{'property_instance_id':pid,'lease_id':lid,'actor_id':actor_id}); self.publish('lease_created',{'lease_id':lid}); return self.get_lease(lid)
    def get_lease(self,lid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM property_leases WHERE lease_id=?",(lid,)).fetchone(); return dict(r) if r else None
    def grant_access(self, requesting_actor_id, property_id, subject_id, permissions, grant_type='guest', subject_type='actor', expires_world_time=None, world_time=0, con=None):
        gid=stable_id('pgrant',property_id,subject_type,subject_id,grant_type); now=utc_now(); close=False
        if con is None: con=sqlite3.connect(self.db_path); close=True
        con.execute("INSERT OR REPLACE INTO property_access_grants VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(gid,property_id,subject_type,subject_id,grant_type,jdump(list(permissions)),'active',requesting_actor_id,world_time,expires_world_time,None,now,now,jdump({})))
        self.audit(con,property_id,requesting_actor_id,'access_granted',subject_type,subject_id,None,permissions,world_time=world_time)
        if close: con.commit(); con.close()
        self.publish('property_access_granted',{'property_instance_id':property_id,'subject_id':subject_id,'permissions':list(permissions)}); return gid
    def revoke_access(self, requesting_actor_id, property_id, subject_id, world_time=0):
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE property_access_grants SET status='revoked',revoked_world_time=?,updated_at=? WHERE property_instance_id=? AND subject_id=? AND status='active'",(world_time,utc_now(),property_id,subject_id)); self.audit(con,property_id,requesting_actor_id,'access_revoked','actor',subject_id,world_time=world_time)
        self.publish('property_access_revoked',{'property_instance_id':property_id,'subject_id':subject_id})
    def evaluate_property_access(self, actor_id, property_instance_id, action, world_time=0):
        inst=self.get_property_instance(property_instance_id); allowed=False; reasons=[]
        if not inst: return {'allowed':False,'reasons':['unknown_property']}
        d=self.get_property_definition(inst['property_definition_id']) or {}
        if not d.get('private',True): allowed=True; reasons.append('public')
        if inst.get('owner_id')==actor_id: allowed=True; reasons.append('owner_or_tenant')
        with sqlite3.connect(self.db_path) as con:
            rows=con.execute("SELECT permissions_json,grant_type,expires_world_time FROM property_access_grants WHERE property_instance_id=? AND subject_type='actor' AND subject_id=? AND status='active'",(property_instance_id,actor_id)).fetchall()
        for perms,gt,exp in rows:
            if exp is not None and int(exp) <= int(world_time): continue
            p=jload(perms,[])
            if action in p or 'custom' in p or 'all' in p: allowed=True; reasons.append(gt)
        if not allowed: self.publish('property_access_denied',{'property_instance_id':property_instance_id,'actor_id':actor_id,'action':action})
        return {'allowed':allowed,'reasons':reasons or ['default_deny'],'property_instance_id':property_instance_id,'action':action}
    def invite_guest(self, actor_id, property_id, guest_actor_id, world_time=0):
        gid=self.grant_access(actor_id,property_id,guest_actor_id,['enter','exit'],grant_type='guest',world_time=world_time); self.publish('property_guest_invited',{'property_instance_id':property_id,'guest_actor_id':guest_actor_id}); return gid
    def remove_guest(self, actor_id, property_id, guest_actor_id, world_time=0): self.revoke_access(actor_id,property_id,guest_actor_id,world_time); self.publish('property_guest_removed',{'property_instance_id':property_id,'guest_actor_id':guest_actor_id})
    def ensure_storage_container(self, property_id, storage_profile_id, owner_type='property', owner_id=''):
        p=self.get_property_instance(property_id); prof=self.content.get('property_storage_profiles',storage_profile_id) or {}; cid=stable_id('pstorage',self.world_id,property_id,storage_profile_id,owner_type,owner_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO property_storage_containers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(cid,self.world_id,property_id,storage_profile_id,owner_type,owner_id,prof.get('name',storage_profile_id),'active',int(prof.get('capacity_items',0) or 0),int(prof.get('capacity_weight',0) or 0),now,now,jdump({})))
        return self.get_storage_container(cid)
    def get_storage_container(self,cid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM property_storage_containers WHERE storage_container_id=?",(cid,)).fetchone(); return dict(r) if r else None
    def get_storage_containers(self, actor_id, property_id):
        if not self.evaluate_property_access(actor_id,property_id,'store')['allowed']: return []
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM property_storage_containers WHERE property_instance_id=? AND status IN ('active','locked')",(property_id,))]
    def store_item(self, actor_id, storage_container_id, item_instance_id):
        c=self.get_storage_container(storage_container_id); 
        if not c or not self.evaluate_property_access(actor_id,c['property_instance_id'],'store')['allowed']: raise ValueError('access denied')
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; item=con.execute("SELECT * FROM item_instances WHERE instance_id=? AND destroyed_at IS NULL",(item_instance_id,)).fetchone()
            if not item or item['owner_type']!='actor' or item['owner_id']!=actor_id: raise ValueError('item not carried')
            if item['equipped_slot']: raise ValueError('equipped items cannot be stored')
            flags=jload(item['custom_flags'],{})
            if flags.get('reserved') or flags.get('protected'): raise ValueError('reserved or protected item')
            count=con.execute("SELECT COUNT(*) FROM item_instances WHERE owner_type='property_storage' AND owner_id=? AND destroyed_at IS NULL",(storage_container_id,)).fetchone()[0]
            if c['capacity_items'] and count>=int(c['capacity_items']): raise ValueError('storage capacity reached')
            con.execute("UPDATE item_instances SET owner_type='property_storage',owner_id=?,room_id='',equipped_slot='',updated_at=? WHERE instance_id=?",(storage_container_id,utc_now(),item_instance_id)); self.audit(con,c['property_instance_id'],actor_id,'item_stored','item',item_instance_id,{'owner_type':'actor','owner_id':actor_id},{'owner_type':'property_storage','owner_id':storage_container_id})
        self.publish('property_item_stored',{'storage_container_id':storage_container_id,'item_instance_id':item_instance_id}); return True
    def retrieve_item(self, actor_id, storage_container_id, item_instance_id):
        c=self.get_storage_container(storage_container_id)
        if not c or not self.evaluate_property_access(actor_id,c['property_instance_id'],'retrieve')['allowed']: raise ValueError('access denied')
        with sqlite3.connect(self.db_path) as con:
            cur=con.execute("UPDATE item_instances SET owner_type='actor',owner_id=?,updated_at=? WHERE instance_id=? AND owner_type='property_storage' AND owner_id=? AND destroyed_at IS NULL",(actor_id,utc_now(),item_instance_id,storage_container_id))
            if cur.rowcount != 1: raise ValueError('item not in storage')
            self.audit(con,c['property_instance_id'],actor_id,'item_retrieved','item',item_instance_id,{'owner_type':'property_storage','owner_id':storage_container_id},{'owner_type':'actor','owner_id':actor_id})
        self.publish('property_item_retrieved',{'storage_container_id':storage_container_id,'item_instance_id':item_instance_id}); return True
    def set_home(self, actor_id, property_id, room_id=None, world_time=0):
        inst=self.get_property_instance(property_id); d=self.get_property_definition(inst['property_definition_id']) if inst else {}
        rid=room_id or inst.get('primary_room_id') or inst.get('entry_room_id')
        if not d.get('home_location_enabled',False): raise ValueError('home not enabled')
        if not self.evaluate_property_access(actor_id,property_id,'enter')['allowed']: raise ValueError('access denied')
        hid=stable_id('home',actor_id,property_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE actor_home_locations SET status='cleared',cleared_world_time=?,updated_at=? WHERE actor_id=? AND status='active'",(world_time,now,actor_id)); con.execute("INSERT OR REPLACE INTO actor_home_locations VALUES(?,?,?,?,?,?,?,?,?,?)",(hid,actor_id,property_id,rid,'active',world_time,None,now,now,jdump({}))); self.audit(con,property_id,actor_id,'home_set','actor',actor_id,world_time=world_time)
        self.publish('property_home_set',{'actor_id':actor_id,'property_instance_id':property_id,'room_id':rid}); return hid
    def clear_home(self, actor_id, world_time=0):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_home_locations SET status='cleared',cleared_world_time=?,updated_at=? WHERE actor_id=? AND status='active'",(world_time,utc_now(),actor_id))
        self.publish('property_home_cleared',{'actor_id':actor_id})
    def process_property_time(self, world_id, world_time):
        expired=[]
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row
            for l in con.execute("SELECT * FROM property_leases WHERE world_id=? AND status='active' AND ends_world_time<=?",(world_id,world_time)).fetchall():
                con.execute("UPDATE property_leases SET status='expired',updated_at=? WHERE lease_id=? AND status='active'",(utc_now(),l['lease_id'])); con.execute("UPDATE property_instances SET status='expired',expired_world_time=?,updated_at=? WHERE property_instance_id=?",(world_time,utc_now(),l['property_instance_id'])); con.execute("UPDATE property_access_grants SET status='expired',updated_at=? WHERE property_instance_id=? AND grant_type IN ('tenant','key_holder') AND status='active'",(utc_now(),l['property_instance_id'])); self.audit(con,l['property_instance_id'],l['tenant_id'],'lease_expired','lease',l['lease_id'],world_time=world_time); expired.append(l['lease_id'])
        for lid in expired: self.publish('lease_expired',{'lease_id':lid})
        return expired
    def trace_property(self,pid): return {'property_instance':self.get_property_instance(pid),'definition':self.get_property_definition((self.get_property_instance(pid) or {}).get('property_definition_id')),'audit':self.audit_events(pid)}
    def trace_lease(self,lid):
        l=self.get_lease(lid); return {'lease':l,'property':self.trace_property(l['property_instance_id']) if l else None}
    def trace_property_access(self,actor_id,pid,action): return self.evaluate_property_access(actor_id,pid,action)
    def audit_events(self,pid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM property_audit_events WHERE property_instance_id=? ORDER BY created_at",(pid,))]
