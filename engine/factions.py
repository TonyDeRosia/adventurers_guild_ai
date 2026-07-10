"""Phase 8C canonical faction, reputation, standing, diplomacy, and access foundations.

Factions are organization-linked metadata. OrganizationService owns identity and
membership; FactionService owns actor-to-faction reputation, standing, event
history, diplomacy interpretation, access decisions, and traces.
"""
from __future__ import annotations

import hashlib, json, math, re, sqlite3, uuid
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
FACTION_TYPES = {"civil","military","merchant","religious","criminal_placeholder","monster","tribal","profession","political_placeholder","guild","clan","settlement_placeholder","kingdom_placeholder","custom"}
DIPLOMACY_STATES = {"allied","friendly","neutral","unfriendly","hostile","war_placeholder","ceasefire_placeholder","vassal_placeholder","parent","subordinate","rival","custom"}
ACCESS_TYPES = {"room_entry","zone_entry","area_entry","feature_use","shop_access","service_access","quest_access","conversation_choice","item_use","item_equip","workstation_use","bank_access","organization_application","custom"}
ACCESS_RESULTS = {"allow","deny","hidden","warn","restricted","custom"}
OPERATIONS = {"gain","loss","set","reset","decay","recovery","membership_grant","membership_penalty","admin_adjustment","custom"}
SOURCE_TYPES = {"quest","combat","organization_membership","organization_removal","conversation","world_event","reward","service","trade_placeholder","crafting_placeholder","exploration","admin","script","decay","recovery","custom"}
HOSTILITY_CLASSES = {"friendly","neutral","unfriendly","hostile","forbidden","protected","custom",""}
COLLECTIONS = ["faction_definitions","faction_reputation_profiles","faction_standing_tier_profiles","faction_membership_reputation_policies","faction_diplomacy_profiles","faction_hostility_profiles","faction_access_profiles","faction_guard_response_profiles","faction_economy_modifier_profiles","faction_reward_profiles","faction_reputation_decay_profiles","faction_combat_reputation_profiles","faction_title_profiles","faction_message_profiles"]


def utc_now(): return datetime.now(timezone.utc).isoformat()
def safe_id(v: Any) -> bool: return bool(v and SAFE_ID_RE.fullmatch(str(v)))
def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v: Any, default: Any = None) -> Any:
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
def _items(raw: Any, key: str) -> list[dict[str, Any]]:
    data = raw.get(key, raw) if isinstance(raw, dict) else raw
    if isinstance(data, dict):
        return [dict(v, id=v.get("id", k)) if isinstance(v, dict) else {"id": k} for k, v in data.items()]
    return [x for x in (data or []) if isinstance(x, dict)]
def dec(v: Any, default: str = "0") -> Decimal:
    try:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): raise InvalidOperation
        return Decimal(str(default if v is None or v == "" else v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except Exception as exc: raise ValueError(f"invalid decimal value {v!r}") from exc
def as_number(v: Decimal) -> int | str:
    return int(v) if v == v.to_integral_value() else format(v.normalize(), "f")
def clamp(v: Decimal, lo: Decimal, hi: Decimal) -> Decimal: return max(lo, min(hi, v))

DEFAULT_REPUTATION_PROFILE = {"id":"default_faction_reputation","default_value":0,"minimum_value":-3000,"maximum_value":3000,"gain_multiplier":1,"loss_multiplier":1,"member_starting_value":0,"nonmember_starting_value":0,"source_filters":list(SOURCE_TYPES)}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS actor_faction_reputation(reputation_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,faction_id TEXT,reputation_value TEXT,standing_tier_id TEXT,lifetime_gained TEXT,lifetime_lost TEXT,last_changed_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_faction_once ON actor_faction_reputation(world_id,actor_type,actor_id,faction_id);
CREATE TABLE IF NOT EXISTS faction_reputation_events(event_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,faction_id TEXT,operation TEXT,base_amount TEXT,modifier_amount TEXT,final_amount TEXT,source_type TEXT,source_id TEXT,reason TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_faction_event_source_once ON faction_reputation_events(world_id,actor_id,faction_id,operation,source_type,source_id) WHERE source_id <> '';
CREATE TABLE IF NOT EXISTS faction_reputation_history(history_id TEXT PRIMARY KEY,reputation_id TEXT,event_id TEXT,value_before TEXT,value_after TEXT,standing_before TEXT,standing_after TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS faction_standing_cache_placeholder(cache_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,faction_id TEXT,standing_tier_id TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS faction_access_audit(access_audit_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,faction_id TEXT,access_type TEXT,target_type TEXT,target_id TEXT,result TEXT,standing_tier_id TEXT,reason_codes_json TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS faction_relationships(relationship_id TEXT PRIMARY KEY,world_id TEXT,source_faction_id TEXT,target_faction_id TEXT,state TEXT,value TEXT,reciprocal INTEGER,hostility_override TEXT,access_override TEXT,trade_modifier_placeholder TEXT,quest_modifier_placeholder TEXT,effective_world_time INTEGER,expires_world_time INTEGER,source_type TEXT,source_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_faction_relationship_once ON faction_relationships(world_id,source_faction_id,target_faction_id);
CREATE TABLE IF NOT EXISTS faction_reward_claims(claim_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,faction_id TEXT,reward_id TEXT,reward_definition_id TEXT,claimed_world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_faction_reward_claim_once ON faction_reward_claims(world_id,actor_id,faction_id,reward_id);
"""

class FactionContent:
    collections = COLLECTIONS
    def __init__(self, world_root: str | Path = "worlds/shattered_realms"):
        self.world_root = Path(world_root); self.data = {c: self._load(c) for c in self.collections}
    def _load(self, c: str) -> dict[str, dict[str, Any]]:
        for p in (self.world_root / c / f"{c}.json", self.world_root / "builder" / f"{c}.json"):
            if p.exists(): return {str(x.get("id")): x for x in _items(json.loads(p.read_text(encoding="utf-8")), c) if x.get("id")}
        return {}
    def get(self, c: str, rid: Any) -> dict[str, Any] | None: return self.data.get(c, {}).get(str(rid or ""))
    def list(self, c: str) -> list[dict[str, Any]]: return sorted(self.data.get(c, {}).values(), key=lambda r: str(r.get("id", "")))

class FactionValidationResult(dict):
    @property
    def ok(self): return not self.get("errors")

class FactionValidator:
    def __init__(self, content: FactionContent, organization_content: Any = None): self.content=content; self.organization_content=organization_content
    def validate_all(self):
        e=[]; w=[]
        for c in COLLECTIONS:
            for r in self.content.list(c):
                fn = getattr(self, f"validate_{c[:-1] if c.endswith('s') else c}", None)
                if c == "faction_definitions": res=self.validate_faction_definition(r.get("id"))
                elif c == "faction_reputation_profiles": res=self.validate_reputation_profile(r.get("id"))
                elif c == "faction_standing_tier_profiles": res=self.validate_standing_profile(r.get("id"))
                elif c == "faction_access_profiles": res=self.validate_access_profile(r.get("id"))
                elif c == "faction_diplomacy_profiles": res=self.validate_diplomacy_profile(r.get("id"))
                else: res=FactionValidationResult(ok=True, errors=[], warnings=[])
                e += res["errors"]; w += res["warnings"]
        return FactionValidationResult(ok=not e, errors=e, warnings=w)
    def validate_faction_definition(self, fid):
        f=self.content.get("faction_definitions", fid); e=[]; w=[]
        if not f: return FactionValidationResult(ok=False, errors=[f"missing faction {fid}"], warnings=[])
        if not safe_id(f.get("id")): e.append("faction id is not safe")
        if f.get("faction_type", "custom") not in FACTION_TYPES: e.append("invalid faction_type")
        if not (f.get("organization_definition_id") or f.get("organization_instance_id")): w.append("faction has no organization link")
        if self.organization_content and f.get("organization_definition_id") and not self.organization_content.get("organization_definitions", f.get("organization_definition_id")): e.append("invalid organization link")
        for key, coll in (("reputation_profile_id","faction_reputation_profiles"),("standing_tier_profile_id","faction_standing_tier_profiles"),("access_profile_id","faction_access_profiles"),("reward_profile_id","faction_reward_profiles"),("economy_modifier_profile_id","faction_economy_modifier_profiles"),("guard_response_profile_id","faction_guard_response_profiles"),("decay_profile_id","faction_reputation_decay_profiles"),("membership_reputation_policy","faction_membership_reputation_policies")):
            if f.get(key) and not self.content.get(coll, f.get(key)): e.append(f"invalid {key}")
        try:
            mn=dec(f.get("minimum_reputation", -3000)); mx=dec(f.get("maximum_reputation",3000)); dv=dec(f.get("default_reputation",0))
            if mn > mx: e.append("minimum_reputation exceeds maximum_reputation")
            if not (mn <= dv <= mx): e.append("default_reputation outside bounds")
        except ValueError as exc: e.append(str(exc))
        mappings={}
        for other in self.content.list("faction_definitions"):
            for k in ("organization_definition_id","organization_instance_id"):
                if other.get(k): mappings.setdefault((k, other.get(k)), []).append(other.get("id"))
        for ids in mappings.values():
            if len(set(ids)) > 1 and f.get("id") in ids: e.append("duplicate faction organization mapping")
        return FactionValidationResult(ok=not e, errors=e, warnings=w)
    def validate_reputation_profile(self, pid):
        p=self.content.get("faction_reputation_profiles", pid); e=[]; w=[]
        if not p: return FactionValidationResult(ok=False, errors=[f"missing reputation profile {pid}"], warnings=[])
        try:
            mn=dec(p.get("minimum_value",-3000)); mx=dec(p.get("maximum_value",3000)); dv=dec(p.get("default_value",0)); dec(p.get("gain_multiplier",1)); dec(p.get("loss_multiplier",1))
            if mn > mx: e.append("minimum_value exceeds maximum_value")
            if not (mn <= dv <= mx): e.append("default_value outside bounds")
        except ValueError as exc: e.append(str(exc))
        for src in p.get("source_filters", []) or []:
            if src not in SOURCE_TYPES: e.append(f"invalid source filter {src}")
        return FactionValidationResult(ok=not e, errors=e, warnings=w)
    def validate_standing_profile(self, pid):
        p=self.content.get("faction_standing_tier_profiles", pid); e=[]; w=[]
        if not p: return FactionValidationResult(ok=False, errors=[f"missing standing profile {pid}"], warnings=[])
        tiers=sorted(p.get("tiers",[]), key=lambda t:(int(t.get("rank_order",0)), dec(t.get("minimum_reputation",0))))
        prev_hi=None
        for t in tiers:
            if not safe_id(t.get("id")): e.append("tier id is not safe")
            lo=dec(t.get("minimum_reputation",0)); hi=dec(t.get("maximum_reputation",lo))
            if lo > hi: e.append(f"tier {t.get('id')} has invalid range")
            if prev_hi is not None:
                if lo <= prev_hi: e.append("standing tier ranges overlap")
                elif lo > prev_hi + Decimal("0.0001"): w.append("standing profile has gaps")
            prev_hi=hi
            if t.get("hostility_class","") not in HOSTILITY_CLASSES: e.append("invalid hostility_class")
            try: dec(t.get("price_modifier",1))
            except ValueError: e.append("invalid price_modifier")
        if not tiers: w.append("faction has no standing tiers")
        return FactionValidationResult(ok=not e, errors=e, warnings=w)
    def validate_access_profile(self, pid):
        p=self.content.get("faction_access_profiles", pid); e=[]; w=[]
        if not p: return FactionValidationResult(ok=False, errors=[f"missing access profile {pid}"], warnings=[])
        if p.get("default_result","allow") not in ACCESS_RESULTS: e.append("invalid default_result")
        for r in p.get("rules",[]) or []:
            if r.get("access_type","custom") not in ACCESS_TYPES: e.append("invalid access type")
            if r.get("result","allow") not in ACCESS_RESULTS: e.append("invalid access result")
            if r.get("faction_id") and not self.content.get("faction_definitions", r.get("faction_id")): e.append("invalid access faction")
            if r.get("target_id") in {"*","all"} and r.get("result") in {"deny","hidden"}: w.append("access profile may lock starting room")
        return FactionValidationResult(ok=not e, errors=e, warnings=w)
    def validate_diplomacy_profile(self, pid):
        p=self.content.get("faction_diplomacy_profiles", pid); e=[]; w=[]
        if not p: return FactionValidationResult(ok=False, errors=[f"missing diplomacy profile {pid}"], warnings=[])
        for r in p.get("relationships",[]) or []:
            if r.get("state","neutral") not in DIPLOMACY_STATES: e.append("invalid diplomacy state")
            if r.get("source_faction_id") == r.get("target_faction_id") and r.get("state") in {"hostile","war_placeholder"}: e.append("self-hostility is not supported")
        return FactionValidationResult(ok=not e, errors=e, warnings=w)

class FactionService:
    def __init__(self, db_path=':memory:', world_root='worlds/shattered_realms', world_id='shattered_realms', event_bus=None, organization_service=None, reward_service=None, economy_service=None, quest_service=None):
        self.db_path=str(db_path); self._memory_con = sqlite3.connect(':memory:') if str(db_path)==':memory:' else None; self.world_id=world_id; self.content=FactionContent(world_root); self.event_bus=event_bus; self.organization_service=organization_service; self.reward_service=reward_service; self.economy_service=economy_service; self.quest_service=quest_service; self.ensure_schema()
    def ensure_schema(self):
        con = self._memory_con or sqlite3.connect(self.db_path)
        try:
            con.executescript(SCHEMA_SQL); con.commit()
        finally:
            if self._memory_con is None: con.close()
    def _con(self):
        if self._memory_con is not None:
            self._memory_con.row_factory=sqlite3.Row; return self._memory_con
        con=sqlite3.connect(self.db_path); con.row_factory=sqlite3.Row; return con
    def _publish(self, typ, payload):
        if self.event_bus and hasattr(self.event_bus, 'publish'): self.event_bus.publish(typ, payload, source_system='factions')
    def get_faction(self, faction_id): return self.content.get('faction_definitions', faction_id)
    def list_factions(self, actor_id=None): return [f for f in self.content.list('faction_definitions') if f.get('enabled', True)]
    def _profile(self, f): return self.content.get('faction_reputation_profiles', f.get('reputation_profile_id')) or DEFAULT_REPUTATION_PROFILE
    def _bounds(self, f):
        p=self._profile(f); return dec(f.get('minimum_reputation', p.get('minimum_value', -3000))), dec(f.get('maximum_reputation', p.get('maximum_value', 3000)))
    def _default(self, f): return dec(f.get('default_reputation', self._profile(f).get('default_value', 0)))
    def get_faction_organization(self, faction_id):
        f=self.get_faction(faction_id)
        if not f: return None
        if self.organization_service:
            oid=f.get('organization_instance_id') or f.get('organization_definition_id')
            if oid and hasattr(self.organization_service, 'get_organization'):
                try: return self.organization_service.get_organization(oid)
                except Exception: pass
        return {k:f.get(k) for k in ('organization_definition_id','organization_instance_id') if f.get(k)}
    def get_organization_faction(self, organization_id):
        for f in self.content.list('faction_definitions'):
            if organization_id in {f.get('organization_definition_id'), f.get('organization_instance_id')}: return f
        return None
    def trace_faction_linkage(self, faction_id): return {'faction':self.get_faction(faction_id),'linked_organization':self.get_faction_organization(faction_id),'authoritative_identity':'OrganizationService','membership_reputation_separate':True}
    def get_standing_tier(self, faction_id, reputation_value):
        f=self.get_faction(faction_id) or {}; p=self.content.get('faction_standing_tier_profiles', f.get('standing_tier_profile_id')) or {}; val=dec(reputation_value)
        tiers=sorted(p.get('tiers',[]), key=lambda t:(int(t.get('rank_order',0)), dec(t.get('minimum_reputation',0)), str(t.get('id',''))))
        for t in tiers:
            if dec(t.get('minimum_reputation',0)) <= val <= dec(t.get('maximum_reputation',0)): return deepcopy(t)
        return None
    def initialize_actor_reputation(self, actor_id, faction_id, *, actor_type='actor', world_time=0, event_id=None, source_type='custom', source_id='initialize'):
        f=self.get_faction(faction_id)
        if not f: raise ValueError(f'unknown faction {faction_id}')
        value=clamp(self._default(f), *self._bounds(f)); tier=self.get_standing_tier(faction_id, value) or {}
        rid=stable_id('afr', self.world_id, actor_type, actor_id, faction_id); now=utc_now()
        with self._con() as con:
            old=con.execute('SELECT * FROM actor_faction_reputation WHERE reputation_id=?',(rid,)).fetchone()
            if old: return dict(old)|{'metadata':_loads(old['metadata_json'])}
            con.execute('INSERT INTO actor_faction_reputation VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,self.world_id,actor_type,actor_id,faction_id,str(value),tier.get('id',''),'0','0',world_time,now,now,_json({})))
        self._publish('faction_reputation_initialized', {'reputation_id':rid,'actor_id':actor_id,'faction_id':faction_id,'standing_tier_id':tier.get('id','')})
        return self.get_actor_reputation(actor_id, faction_id, actor_type=actor_type)
    def get_actor_reputation(self, actor_id, faction_id, *, actor_type='actor'):
        with self._con() as con:
            r=con.execute('SELECT * FROM actor_faction_reputation WHERE world_id=? AND actor_type=? AND actor_id=? AND faction_id=?',(self.world_id,actor_type,actor_id,faction_id)).fetchone()
        return self.initialize_actor_reputation(actor_id, faction_id, actor_type=actor_type) if not r and self.get_faction(faction_id) else (None if not r else dict(r)|{'metadata':_loads(r['metadata_json'])})
    def get_actor_reputations(self, actor_id): return [self.get_actor_reputation(actor_id, f['id']) for f in self.list_factions() if self.get_actor_reputation(actor_id, f['id'])]
    def _event_id(self, actor_id, faction_id, operation, source_type, source_id, event_id): return event_id or stable_id('fre', self.world_id, actor_id, faction_id, operation, source_type, source_id or uuid.uuid4().hex)
    def modify_reputation(self, actor_id, faction_id, amount, source_type, source_id=None, reason=None, *, operation=None, event_id=None, world_time=0, actor_type='actor', metadata=None):
        if source_type not in SOURCE_TYPES: raise ValueError('unsupported reputation source type')
        amt=dec(amount); op=operation or ('gain' if amt >= 0 else 'loss')
        if op not in OPERATIONS: raise ValueError('unsupported reputation operation')
        f=self.get_faction(faction_id); p=self._profile(f) if f else None
        if not f: raise ValueError(f'unknown faction {faction_id}')
        if p.get('source_filters') and source_type not in set(p.get('source_filters') or []): raise ValueError('reputation source type rejected by profile')
        mult=dec(p.get('gain_multiplier' if amt >= 0 else 'loss_multiplier', 1)); final=(amt*mult).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        if op == 'loss' and final > 0: final = -final
        eid=self._event_id(actor_id,faction_id,op,source_type,source_id,event_id); row=self.initialize_actor_reputation(actor_id,faction_id,actor_type=actor_type,world_time=world_time)
        with self._con() as con:
            prior=con.execute('SELECT * FROM faction_reputation_events WHERE event_id=?',(eid,)).fetchone()
            if prior: return {'event':dict(prior),'applied':False,'idempotent':True,'reputation':self.get_actor_reputation(actor_id,faction_id,actor_type=actor_type)}
            r=con.execute('SELECT * FROM actor_faction_reputation WHERE reputation_id=?',(row['reputation_id'],)).fetchone(); before=dec(r['reputation_value']); before_tier=r['standing_tier_id'] or ''
            if op in {'set','admin_adjustment'}: after=clamp(amt,*self._bounds(f)); final=after-before
            elif op == 'reset': after=clamp(self._default(f),*self._bounds(f)); final=after-before
            else: after=clamp(before+final,*self._bounds(f))
            tier=self.get_standing_tier(faction_id, after) or {}; after_tier=tier.get('id','')
            gained=dec(r['lifetime_gained']) + (max(Decimal('0'), after-before)); lost=dec(r['lifetime_lost']) + (max(Decimal('0'), before-after)); now=utc_now()
            con.execute('INSERT INTO faction_reputation_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,self.world_id,actor_id,faction_id,op,str(amt),str(final-amt),str(final),source_type,source_id or '',reason or '',world_time,now,_json(metadata or {})))
            con.execute('UPDATE actor_faction_reputation SET reputation_value=?,standing_tier_id=?,lifetime_gained=?,lifetime_lost=?,last_changed_world_time=?,updated_at=? WHERE reputation_id=?',(str(after),after_tier,str(gained),str(lost),world_time,now,row['reputation_id']))
            hid=stable_id('frh', row['reputation_id'], eid)
            con.execute('INSERT INTO faction_reputation_history VALUES(?,?,?,?,?,?,?,?,?,?)',(hid,row['reputation_id'],eid,str(before),str(after),before_tier,after_tier,world_time,now,_json({'source_type':source_type,'source_id':source_id})))
        self._publish({'gain':'faction_reputation_gained','loss':'faction_reputation_lost','set':'faction_reputation_set','reset':'faction_reputation_reset','decay':'faction_reputation_decayed','recovery':'faction_reputation_recovered','membership_grant':'faction_membership_reputation_applied','membership_penalty':'faction_membership_reputation_applied'}.get(op,'faction_reputation_set'), {'event_id':eid,'actor_id':actor_id,'faction_id':faction_id,'amount':as_number(final)})
        if before_tier != after_tier:
            ev='faction_standing_changed'; self._publish(ev, {'actor_id':actor_id,'faction_id':faction_id,'before':before_tier,'after':after_tier,'event_id':eid})
            self._publish('faction_standing_increased' if after>before else 'faction_standing_decreased', {'actor_id':actor_id,'faction_id':faction_id,'before':before_tier,'after':after_tier,'event_id':eid})
        return {'event_id':eid,'applied':True,'idempotent':False,'value_before':as_number(before),'value_after':as_number(after),'standing_before':before_tier,'standing_after':after_tier,'reputation':self.get_actor_reputation(actor_id,faction_id,actor_type=actor_type)}
    def set_reputation(self, actor_id, faction_id, amount, reason=None, **kw): return self.modify_reputation(actor_id,faction_id,amount,'admin',kw.pop('source_id',None) or reason or 'set',reason,operation='set',**kw)
    def reset_reputation(self, actor_id, faction_id, **kw): return self.modify_reputation(actor_id,faction_id,0,'admin',kw.pop('source_id',None) or 'reset','reset',operation='reset',**kw)
    def resolve_standing(self, actor_id, faction_id):
        r=self.get_actor_reputation(actor_id,faction_id); tier=self.get_standing_tier(faction_id, r['reputation_value']) if r else None
        return {'actor_id':actor_id,'faction_id':faction_id,'reputation_value':as_number(dec(r['reputation_value'])) if r else None,'standing_tier':tier,'standing_tier_id':(tier or {}).get('id','')}
    def get_reputation_history(self, actor_id, faction_id=None, limit=None):
        sql='''SELECT h.*, e.actor_id, e.faction_id, e.operation, e.source_type, e.source_id, e.reason FROM faction_reputation_history h JOIN faction_reputation_events e ON e.event_id=h.event_id WHERE e.world_id=? AND e.actor_id=?'''; args=[self.world_id,actor_id]
        if faction_id: sql+=' AND e.faction_id=?'; args.append(faction_id)
        sql+=' ORDER BY h.created_at DESC';
        if limit: sql+=' LIMIT ?'; args.append(int(limit))
        with self._con() as con: return [dict(r)|{'metadata':_loads(r['metadata_json'])} for r in con.execute(sql,args)]
    def evaluate_faction_access(self, actor_id, faction_id, access_type, target=None, *, world_time=0, audit=True, admin_bypass=False):
        if access_type not in ACCESS_TYPES: raise ValueError('invalid access type')
        f=self.get_faction(faction_id); target=target or {}; target_type=target.get('target_type') or target.get('type') or ''; target_id=target.get('target_id') or target.get('id') or ''
        if admin_bypass: return {'result':'allow','reason_codes':['admin_bypass'],'standing_tier_id':''}
        r=self.get_actor_reputation(actor_id,faction_id); standing=r.get('standing_tier_id','') if r else ''; value=dec(r.get('reputation_value',0) if r else 0)
        prof=self.content.get('faction_access_profiles', (f or {}).get('access_profile_id')) or {}; default=prof.get('default_result','allow'); matched=None; reasons=[]
        rules=sorted(prof.get('rules',[]) or [], key=lambda x:(-int(x.get('priority',0) or 0), str(x.get('id',''))))
        for rule in rules:
            if rule.get('access_type') not in {access_type,'custom',None}: continue
            if rule.get('target_type') and target_type and rule.get('target_type') != target_type: continue
            if rule.get('target_id') and rule.get('target_id') not in {target_id,'*'}: continue
            if rule.get('faction_id') and rule.get('faction_id') != faction_id: continue
            if rule.get('minimum_reputation') is not None and value < dec(rule.get('minimum_reputation')): reasons.append('below_minimum_reputation'); continue
            if rule.get('maximum_reputation') is not None and value > dec(rule.get('maximum_reputation')): reasons.append('above_maximum_reputation'); continue
            min_t=rule.get('minimum_standing_tier_id'); max_t=rule.get('maximum_standing_tier_id')
            if min_t or max_t:
                tiers=sorted((self.content.get('faction_standing_tier_profiles',(f or {}).get('standing_tier_profile_id')) or {}).get('tiers',[]), key=lambda t:int(t.get('rank_order',0)))
                ranks={t.get('id'):int(t.get('rank_order',0)) for t in tiers}; sr=ranks.get(standing)
                if min_t and (sr is None or sr < ranks.get(min_t, 10**9)): reasons.append('below_minimum_standing'); continue
                if max_t and (sr is None or sr > ranks.get(max_t, -10**9)): reasons.append('above_maximum_standing'); continue
            matched=rule; break
        result=(matched or {}).get('result', default); reasons.append('matched_rule:'+matched.get('id')) if matched else reasons.append('default_'+result)
        if audit:
            with self._con() as con:
                con.execute('INSERT INTO faction_access_audit VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(stable_id('faa',self.world_id,actor_id,faction_id,access_type,target_type,target_id,world_time,uuid.uuid4().hex),self.world_id,actor_id,faction_id,access_type,target_type,target_id,result,standing,_json(reasons),world_time,utc_now(),_json({'rule':matched or {}})))
            self._publish('faction_access_allowed' if result == 'allow' else 'faction_access_denied', {'actor_id':actor_id,'faction_id':faction_id,'access_type':access_type,'target_id':target_id,'result':result})
        return {'result':result,'allowed':result in {'allow','warn'},'standing_tier_id':standing,'reason_codes':reasons,'matched_rule':matched}
    def set_faction_relationship(self, source_faction_id, target_faction_id, state='neutral', value=0, reciprocal=False, **kw):
        if state not in DIPLOMACY_STATES: raise ValueError('invalid diplomacy state')
        if source_faction_id == target_faction_id and state in {'hostile','war_placeholder'}: raise ValueError('self-hostility is not supported')
        rid=stable_id('frel',self.world_id,source_faction_id,target_faction_id); now=utc_now()
        with self._con() as con:
            con.execute('INSERT OR REPLACE INTO faction_relationships VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,self.world_id,source_faction_id,target_faction_id,state,str(dec(value)),1 if reciprocal else 0,kw.get('hostility_override',''),kw.get('access_override',''),kw.get('trade_modifier_placeholder',''),kw.get('quest_modifier_placeholder',''),kw.get('effective_world_time',0),kw.get('expires_world_time'),kw.get('source_type','admin'),kw.get('source_id',''),now,now,_json(kw.get('metadata') or {})))
        self._publish('faction_relationship_changed', {'relationship_id':rid,'source_faction_id':source_faction_id,'target_faction_id':target_faction_id,'state':state}); return self.get_faction_relationship(source_faction_id,target_faction_id)
    def get_faction_relationship(self, source_faction_id, target_faction_id):
        with self._con() as con:
            r=con.execute('SELECT * FROM faction_relationships WHERE world_id=? AND source_faction_id=? AND target_faction_id=?',(self.world_id,source_faction_id,target_faction_id)).fetchone()
            if not r:
                r=con.execute('SELECT * FROM faction_relationships WHERE world_id=? AND source_faction_id=? AND target_faction_id=? AND reciprocal=1',(self.world_id,target_faction_id,source_faction_id)).fetchone()
        if r: return dict(r)|{'metadata':_loads(r['metadata_json'])}
        for p in self.content.list('faction_diplomacy_profiles'):
            for rel in p.get('relationships',[]) or []:
                if rel.get('source_faction_id')==source_faction_id and rel.get('target_faction_id')==target_faction_id: return rel|{'profile_id':p.get('id')}
                if rel.get('reciprocal') and rel.get('source_faction_id')==target_faction_id and rel.get('target_faction_id')==source_faction_id: return rel|{'profile_id':p.get('id'),'resolved_reciprocal':True}
        return {'source_faction_id':source_faction_id,'target_faction_id':target_faction_id,'state':'neutral','value':'0','reciprocal':False}
    def clear_faction_relationship(self, source_faction_id, target_faction_id):
        with self._con() as con: con.execute('DELETE FROM faction_relationships WHERE world_id=? AND source_faction_id=? AND target_faction_id=?',(self.world_id,source_faction_id,target_faction_id))
        self._publish('faction_relationship_changed', {'source_faction_id':source_faction_id,'target_faction_id':target_faction_id,'state':'neutral'}); return True
    def resolve_actor_faction_relationship(self, observer_actor_id, target_actor_id):
        obs=[m for m in (self.organization_service.get_actor_memberships(observer_actor_id) if self.organization_service else [])]
        tgt=[m for m in (self.organization_service.get_actor_memberships(target_actor_id) if self.organization_service else [])]
        pairs=[]
        for om in obs:
            of=self.get_organization_faction(om.get('organization_definition_id') or om.get('organization_instance_id'))
            if not of: continue
            for tm in tgt:
                tf=self.get_organization_faction(tm.get('organization_definition_id') or tm.get('organization_instance_id'))
                if tf: pairs.append(self.get_faction_relationship(of['id'], tf['id']))
        state='neutral'
        if any(p.get('state') in {'hostile','war_placeholder','rival'} for p in pairs): state='hostile'
        elif any(p.get('state') in {'allied','friendly'} for p in pairs): state='friendly'
        return {'observer_actor_id':observer_actor_id,'target_actor_id':target_actor_id,'state':state,'relationships':pairs}
    def evaluate_faction_hostility(self, observer_actor_id, target_actor_id):
        rel=self.resolve_actor_faction_relationship(observer_actor_id,target_actor_id); contribution={'friendly':'friendly','neutral':'neutral','hostile':'hostile'}.get(rel['state'],'neutral')
        return {'observer_actor_id':observer_actor_id,'target_actor_id':target_actor_id,'faction_contribution':contribution,'decision_input_only':True,'pvp_introduced':False,'relationship':rel}
    def trace_reputation(self, actor_id, faction_id): return {'faction':self.get_faction(faction_id),'linked_organization':self.get_faction_organization(faction_id),'reputation':self.get_actor_reputation(actor_id,faction_id),'history':self.get_reputation_history(actor_id,faction_id,20),'idempotency':'event_id and source tuple are unique','restart_state':'sqlite-authoritative'}
    def trace_standing(self, actor_id, faction_id): return self.trace_reputation(actor_id,faction_id)|{'standing':self.resolve_standing(actor_id,faction_id)}
    def trace_faction_access(self, actor_id, faction_id, access_type, target=None): return {'trace':self.evaluate_faction_access(actor_id,faction_id,access_type,target,audit=False),'faction':self.get_faction(faction_id),'profile':self.content.get('faction_access_profiles',(self.get_faction(faction_id) or {}).get('access_profile_id'))}
    def trace_faction_hostility(self, observer_actor_id, target_actor_id): return self.evaluate_faction_hostility(observer_actor_id,target_actor_id)
    def trace_faction_relationship(self, source_faction_id, target_faction_id): return {'relationship':self.get_faction_relationship(source_faction_id,target_faction_id),'source':self.get_faction(source_faction_id),'target':self.get_faction(target_faction_id)}
    def get_actor_faction_context(self, actor_id):
        reps=[self.resolve_standing(actor_id,f['id']) for f in self.list_factions() if f.get('visible',True)]
        return {'actor_id':actor_id,'memberships':self.organization_service.get_actor_memberships(actor_id) if self.organization_service else [],'reputations':reps,'hostile_factions':[r for r in reps if (r.get('standing_tier') or {}).get('hostility_class')=='hostile'],'friendly_factions':[r for r in reps if (r.get('standing_tier') or {}).get('hostility_class')=='friendly'],'access_tags':sorted({tag for r in reps for tag in ((r.get('standing_tier') or {}).get('access_tags') or [])}),'unresolved_warnings':[],'source_traces':['FactionService']}
    def evaluate_reward_eligibility(self, actor_id, faction_id):
        f=self.get_faction(faction_id); prof=self.content.get('faction_reward_profiles',(f or {}).get('reward_profile_id')) or {}; standing=self.resolve_standing(actor_id,faction_id); value=dec(standing.get('reputation_value') or 0)
        out=[]
        with self._con() as con:
            claimed={r['reward_id'] for r in con.execute('SELECT reward_id FROM faction_reward_claims WHERE world_id=? AND actor_id=? AND faction_id=?',(self.world_id,actor_id,faction_id))}
        for rw in prof.get('standing_rewards',[]) or []:
            ok=(not rw.get('standing_tier_id') or rw.get('standing_tier_id')==standing.get('standing_tier_id')) and (rw.get('minimum_reputation') is None or value>=dec(rw.get('minimum_reputation')))
            out.append(rw|{'available':ok and (not rw.get('once_per_actor') or rw.get('id') not in claimed),'claimed':rw.get('id') in claimed})
        return out
    def claim_faction_reward(self, actor_id, faction_id, reward_id, *, world_time=0):
        eligible=[r for r in self.evaluate_reward_eligibility(actor_id,faction_id) if r.get('id')==reward_id and r.get('available')]
        if not eligible: raise ValueError('faction reward is not available')
        r=eligible[0]; cid=stable_id('fclaim',self.world_id,actor_id,faction_id,reward_id)
        with self._con() as con: con.execute('INSERT OR IGNORE INTO faction_reward_claims VALUES(?,?,?,?,?,?,?,?,?)',(cid,self.world_id,actor_id,faction_id,reward_id,r.get('reward_definition_id',''),world_time,utc_now(),_json({})))
        if self.reward_service and r.get('reward_definition_id') and hasattr(self.reward_service,'grant_reward'): self.reward_service.grant_reward(actor_id,r.get('reward_definition_id'),source_type='faction',source_id=cid)
        self._publish('faction_reward_claimed', {'actor_id':actor_id,'faction_id':faction_id,'reward_id':reward_id}); return {'claim_id':cid,'reward':r}
