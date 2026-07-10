"""Phase 8B canonical organization, party, guild, clan, and NPC group foundations."""
from __future__ import annotations
import hashlib, json, re, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE=re.compile(r"^[A-Za-z0-9_.:-]+$")
ORG_TYPES={"party","group","raid_placeholder","guild","clan","order","company","guard_unit","merchant_group","profession_group","religious_order","npc_faction_placeholder","settlement_placeholder","kingdom_placeholder","custom"}
ORG_STATUSES={"forming","active","inactive","disbanded","archived","suspended","custom"}
MEMBER_TYPES={"actor","player","npc","pet_placeholder","organization_placeholder","custom"}
MEMBERSHIP_STATUSES={"invited","applied","pending","active","inactive","suspended","removed","left","declined","expired","banned_placeholder"}
INVITATION_STATUSES={"pending","accepted","declined","expired","cancelled","invalidated"}
APPLICATION_STATUSES={"pending","approved","rejected","withdrawn","expired","cancelled"}
ROLE_TYPES={"leader","officer","member","recruit","guest","specialist","treasurer_placeholder","quest_officer_placeholder","raid_leader_placeholder","custom"}
PERMISSIONS={"invite","cancel_invite","approve_application","reject_application","remove_member","promote_member","demote_member","assign_role","edit_public_note","edit_officer_note","edit_organization_name","edit_organization_description","set_home","manage_subgroups","manage_chat","manage_shared_quests","manage_rewards_placeholder","manage_treasury_placeholder","view_officer_notes","view_audit","transfer_leadership","disband","custom"}
COLLECTIONS=["organization_definitions","organization_roles","organization_membership_policies","organization_invitation_policies","organization_application_policies","organization_leadership_policies","organization_permission_profiles","organization_communication_profiles","organization_group_combat_profiles","organization_shared_quest_profiles","organization_reward_profiles","organization_relationship_profiles","organization_seeds","organization_message_profiles"]

def utc_now(): return datetime.now(timezone.utc).isoformat()
def safe_id(v): return bool(v and SAFE_ID_RE.fullmatch(str(v)))
def _json(v): return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v, default=None):
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def stable_id(prefix,*parts):
    raw="|".join(json.dumps(p,sort_keys=True,default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
def _items(raw,key):
    data=raw.get(key,raw) if isinstance(raw,dict) else raw
    if isinstance(data,dict): return [dict(v,id=v.get('id',k)) if isinstance(v,dict) else {'id':k} for k,v in data.items()]
    return [x for x in (data or []) if isinstance(x,dict)]

class OrganizationContent:
    collections=COLLECTIONS
    def __init__(self, world_root: str|Path="worlds/shattered_realms"):
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}
    def _load(self,c):
        paths=(self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json")
        for p in paths:
            if p.exists():
                return {str(x.get('id')):x for x in _items(json.loads(p.read_text(encoding='utf-8')),c) if x.get('id')}
        return {}
    def get(self,c,rid): return self.data.get(c,{}).get(str(rid or ""))
    def list(self,c): return sorted(self.data.get(c,{}).values(), key=lambda r:str(r.get('id','')))

SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS organization_instances(organization_instance_id TEXT PRIMARY KEY,world_id TEXT,organization_definition_id TEXT,organization_type TEXT,name TEXT,short_name TEXT,description TEXT,status TEXT,persistent INTEGER,created_by_actor_id TEXT,leader_actor_id TEXT,parent_organization_id TEXT,home_room_id TEXT,home_zone_id TEXT,home_area_id TEXT,created_world_time INTEGER,disbanded_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_static_once ON organization_instances(world_id,organization_definition_id) WHERE persistent=1 AND parent_organization_id='';
CREATE TABLE IF NOT EXISTS organization_memberships(membership_id TEXT PRIMARY KEY,world_id TEXT,organization_instance_id TEXT,member_type TEXT,member_id TEXT,actor_id TEXT,account_id_placeholder TEXT,role_id TEXT,status TEXT,joined_world_time INTEGER,left_world_time INTEGER,invited_by_actor_id TEXT,approved_by_actor_id TEXT,last_active_world_time INTEGER,display_title TEXT,public_note TEXT,officer_note TEXT,contribution_score_placeholder REAL,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_member_active_once ON organization_memberships(world_id,organization_instance_id,actor_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS organization_invitations(invitation_id TEXT PRIMARY KEY,world_id TEXT,organization_instance_id TEXT,inviter_actor_id TEXT,invitee_actor_id TEXT,intended_role_id TEXT,status TEXT,created_world_time INTEGER,expires_world_time INTEGER,responded_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_invite_pending_once ON organization_invitations(world_id,organization_instance_id,invitee_actor_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS organization_applications(application_id TEXT PRIMARY KEY,world_id TEXT,organization_instance_id TEXT,applicant_actor_id TEXT,requested_role_id TEXT,message TEXT,status TEXT,reviewed_by_actor_id TEXT,created_world_time INTEGER,reviewed_world_time INTEGER,expires_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_app_pending_once ON organization_applications(world_id,organization_instance_id,applicant_actor_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS organization_audit_events(audit_event_id TEXT PRIMARY KEY,world_id TEXT,organization_instance_id TEXT,actor_id TEXT,operation TEXT,target_type TEXT,target_id TEXT,old_value_json TEXT,new_value_json TEXT,reason TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS organization_subgroups(subgroup_id TEXT PRIMARY KEY,organization_instance_id TEXT,name TEXT,subgroup_type TEXT,leader_actor_id TEXT,maximum_members INTEGER,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS organization_subgroup_members(subgroup_membership_id TEXT PRIMARY KEY,subgroup_id TEXT,actor_id TEXT,role TEXT,joined_world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_subgroup_member_once ON organization_subgroup_members(subgroup_id,actor_id);
CREATE TABLE IF NOT EXISTS organization_messages(message_id TEXT PRIMARY KEY,organization_instance_id TEXT,channel_id TEXT,sender_actor_id TEXT,message_text TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS group_combat_participation(participation_id TEXT PRIMARY KEY,world_id TEXT,organization_instance_id TEXT,combat_instance_id TEXT,actor_id TEXT,target_actor_id TEXT,damage_contribution REAL,healing_contribution REAL,support_contribution REAL,control_contribution REAL,presence_contribution_placeholder REAL,eligible INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_group_combat_once ON group_combat_participation(world_id,organization_instance_id,combat_instance_id,actor_id,target_actor_id);
CREATE TABLE IF NOT EXISTS organization_relationships(relationship_id TEXT PRIMARY KEY,world_id TEXT,source_organization_id TEXT,target_organization_id TEXT,relationship_type TEXT,value REAL,status TEXT,created_world_time INTEGER,updated_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_rel_once ON organization_relationships(world_id,source_organization_id,target_organization_id,relationship_type);
CREATE TABLE IF NOT EXISTS organization_shared_quest_offers(offer_id TEXT PRIMARY KEY,world_id TEXT,organization_instance_id TEXT,quest_id TEXT,sharer_actor_id TEXT,recipient_actor_id TEXT,status TEXT,created_world_time INTEGER,responded_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_shared_offer_once ON organization_shared_quest_offers(world_id,quest_id,recipient_actor_id) WHERE status='pending';
"""

class OrganizationValidationResult(dict):
    @property
    def ok(self): return not self.get('errors')

class OrganizationValidator:
    def __init__(self, content): self.content=content
    def validate_all(self):
        e=[]; w=[]
        for d in self.content.list('organization_definitions'):
            r=self.validate_definition(d.get('id')); e+=r['errors']; w+=r['warnings']
        for r0 in self.content.list('organization_roles'):
            r=self.validate_role(r0.get('id')); e+=r['errors']; w+=r['warnings']
        return OrganizationValidationResult(ok=not e, errors=e, warnings=w)
    def validate_definition(self, oid):
        d=self.content.get('organization_definitions',oid); e=[]; w=[]
        if not d: return OrganizationValidationResult(ok=False, errors=[f'missing organization {oid}'], warnings=[])
        if not safe_id(d.get('id')): e.append('organization id is not safe')
        if d.get('organization_type','custom') not in ORG_TYPES: e.append('invalid organization_type')
        if d.get('maximum_members') is not None and d.get('minimum_members',0)>d.get('maximum_members'): e.append('impossible member limits')
        roles=[r for r in self.content.list('organization_roles') if r.get('organization_definition_id')==d.get('id')]
        # Phase 8B permits reusable role templates across compatible persistent organization definitions.
        ids={r.get('id') for r in self.content.list('organization_roles')}
        for key in ('default_role_id','leader_role_id'):
            if d.get(key) and d.get(key) not in ids: e.append(f'{key} missing')
        if d.get('persistent') and not d.get('leader_role_id'): w.append('persistent organization has no leader role')
        if d.get('organization_type')=='party' and not d.get('maximum_members'): w.append('party allows unlimited members')
        return OrganizationValidationResult(ok=not e, errors=e, warnings=w)
    def validate_role(self, rid):
        r=self.content.get('organization_roles',rid); e=[]; w=[]
        if not r: return OrganizationValidationResult(ok=False, errors=[f'missing role {rid}'], warnings=[])
        if not safe_id(r.get('id')): e.append('role id is not safe')
        if r.get('role_type','custom') not in ROLE_TYPES: e.append('invalid role_type')
        for p in r.get('permissions',[]):
            if p not in PERMISSIONS: e.append(f'invalid permission {p}')
        seen=set(); stack=[]
        def visit(x):
            if x in stack: return False
            if x in seen: return True
            seen.add(x); stack.append(x); rr=self.content.get('organization_roles',x) or {}
            ok=all(visit(y) for y in rr.get('inherits_from_role_ids',[])); stack.pop(); return ok
        if not visit(r.get('id')): e.append('role inheritance cycle')
        if r.get('role_type')=='leader' and 'invite' not in r.get('permissions',[]): w.append('leader role lacks leadership permissions')
        return OrganizationValidationResult(ok=not e, errors=e, warnings=w)

class OrganizationService:
    def __init__(self, db_path=':memory:', world_root='worlds/shattered_realms', world_id='shattered_realms', event_bus=None, quest_service=None, reward_service=None, world_state_service=None):
        self.db_path=str(db_path); self.world_id=world_id; self.content=OrganizationContent(world_root); self.event_bus=event_bus; self.quest_service=quest_service; self.reward_service=reward_service; self.world_state=world_state_service; self.ensure_schema()
    def ensure_schema(self):
        with sqlite3.connect(self.db_path) as con: con.executescript(SCHEMA_SQL)
    def _con(self):
        con=sqlite3.connect(self.db_path); con.row_factory=sqlite3.Row; return con
    def _publish(self, typ,payload):
        if self.event_bus and hasattr(self.event_bus,'publish'): self.event_bus.publish(typ,payload,source_system='organizations')
    def _audit(self, con, org, actor, operation, target_type='', target_id='', old=None, new=None, reason='', world_time=0):
        con.execute("INSERT INTO organization_audit_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(stable_id('oa',org,operation,target_type,target_id,utc_now(),uuid.uuid4().hex),self.world_id,org,actor or '',operation,target_type,target_id,_json(old),_json(new),reason,world_time,utc_now(),_json({})))
    def _definition(self, did):
        d=self.content.get('organization_definitions',did)
        if not d: raise ValueError(f'unknown organization definition {did}')
        vr=OrganizationValidator(self.content).validate_definition(did)
        if not vr.ok: raise ValueError('; '.join(vr['errors']))
        return d
    def create_organization(self, definition_id, creator_actor_id='', name=None, *, world_time=0, parent_organization_id=''):
        d=self._definition(definition_id); persistent=bool(d.get('persistent'))
        oid = stable_id('org', self.world_id, definition_id, parent_organization_id or 'root') if persistent and not d.get('player_created') else stable_id('org', self.world_id, definition_id, creator_actor_id, name or d.get('name'), uuid.uuid4().hex)
        now=utc_now()
        with self._con() as con:
            old=con.execute("SELECT * FROM organization_instances WHERE organization_instance_id=?",(oid,)).fetchone()
            if old: return dict(old)
            if persistent and not parent_organization_id:
                old=con.execute("SELECT * FROM organization_instances WHERE world_id=? AND organization_definition_id=? AND persistent=1 AND parent_organization_id=''",(self.world_id,definition_id)).fetchone()
                if old: return dict(old)
            con.execute("INSERT INTO organization_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,self.world_id,definition_id,d.get('organization_type','custom'),name or d.get('name',definition_id),d.get('short_name',''),d.get('description',''),'active',1 if persistent else 0,creator_actor_id,creator_actor_id,parent_organization_id,d.get('home_room_id',''),d.get('home_zone_id',''),d.get('home_area_id',''),world_time,None,now,now,_json({'definition_version':d.get('version',1)})))
            role=d.get('leader_role_id') or d.get('default_role_id') or 'member';
            if creator_actor_id: self._add_member_tx(con, oid, creator_actor_id, role, 'creator', world_time=world_time, approved_by_actor_id=creator_actor_id)
            self._audit(con,oid,creator_actor_id,'organization_created','organization',oid,None,d,world_time=world_time)
        self._publish('organization_created',{'organization_instance_id':oid,'organization_type':d.get('organization_type')})
        if d.get('organization_type')=='party': self._publish('party_created',{'organization_instance_id':oid})
        return self.get_organization(oid)
    def get_organization(self, organization_id):
        with self._con() as con:
            r=con.execute("SELECT * FROM organization_instances WHERE organization_instance_id=? OR organization_definition_id=? OR name=?",(organization_id,organization_id,organization_id)).fetchone()
            return None if not r else dict(r)|{'metadata':_loads(r['metadata_json'])}
    def list_organizations(self, actor_id=None, organization_type=None):
        with self._con() as con:
            if actor_id:
                rows=con.execute("SELECT o.* FROM organization_instances o JOIN organization_memberships m ON m.organization_instance_id=o.organization_instance_id WHERE m.actor_id=? AND m.status='active' AND (? IS NULL OR o.organization_type=?)",(actor_id,organization_type,organization_type)).fetchall()
            else:
                rows=con.execute("SELECT * FROM organization_instances WHERE (? IS NULL OR organization_type=?) ORDER BY name",(organization_type,organization_type)).fetchall()
            return [dict(r) for r in rows]
    def _roles_for_def(self, definition_id): return [r for r in self.content.list('organization_roles') if r.get('organization_definition_id')==definition_id]
    def _role(self, rid): return self.content.get('organization_roles',rid) or {'id':rid,'permissions':[],'inherits_from_role_ids':[],'rank_order':999}
    def _policy(self, org):
        d=self.content.get('organization_definitions',org['organization_definition_id']) or {}; return self.content.get('organization_membership_policies',d.get('membership_policy_id')) or {}
    def _check_membership_allowed(self, con, org, actor_id):
        pol=self._policy(org); typ=org['organization_type']
        max_members=pol.get('maximum_members') or (self.content.get('organization_definitions',org['organization_definition_id']) or {}).get('maximum_members')
        if max_members:
            count=con.execute("SELECT count(*) FROM organization_memberships WHERE organization_instance_id=? AND status='active'",(org['organization_instance_id'],)).fetchone()[0]
            if count>=int(max_members): raise ValueError('organization is full')
        if typ=='party' and not pol.get('allow_multiple_parties',False):
            r=con.execute("SELECT 1 FROM organization_memberships m JOIN organization_instances o ON o.organization_instance_id=m.organization_instance_id WHERE m.actor_id=? AND m.status='active' AND o.organization_type='party' AND o.status='active'",(actor_id,)).fetchone()
            if r: raise ValueError('actor already has an active party')
        if typ=='guild' and not pol.get('allow_multiple_guilds',False):
            r=con.execute("SELECT 1 FROM organization_memberships m JOIN organization_instances o ON o.organization_instance_id=m.organization_instance_id WHERE m.actor_id=? AND m.status='active' AND o.organization_type='guild' AND o.status='active'",(actor_id,)).fetchone()
            if r: raise ValueError('actor already has an active guild')
    def _add_member_tx(self, con, oid, actor_id, role_id, source='', *, world_time=0, invited_by_actor_id='', approved_by_actor_id=''):
        org=dict(con.execute("SELECT * FROM organization_instances WHERE organization_instance_id=?",(oid,)).fetchone())
        existing=con.execute("SELECT * FROM organization_memberships WHERE organization_instance_id=? AND actor_id=? AND status='active'",(oid,actor_id)).fetchone()
        if existing: return dict(existing)
        self._check_membership_allowed(con,org,actor_id)
        mid=stable_id('om',self.world_id,oid,actor_id,uuid.uuid4().hex); now=utc_now()
        con.execute("INSERT INTO organization_memberships VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,self.world_id,oid,'actor',actor_id,actor_id,'',role_id,'active',world_time,None,invited_by_actor_id,approved_by_actor_id,world_time,'','','',0,now,now,_json({'source':source})))
        self._audit(con,oid,approved_by_actor_id or invited_by_actor_id or actor_id,'member_joined','actor',actor_id,None,{'role_id':role_id},world_time=world_time)
        return {'membership_id':mid,'actor_id':actor_id,'role_id':role_id,'status':'active'}
    def add_member(self, organization_id, actor_id, role_id=None, source=None, *, world_time=0):
        org=self.get_organization(organization_id); d=self.content.get('organization_definitions',org['organization_definition_id']) or {}; role_id=role_id or d.get('default_role_id') or 'member'
        with self._con() as con: m=self._add_member_tx(con,org['organization_instance_id'],actor_id,role_id,source or 'direct',world_time=world_time)
        self._publish('organization_member_joined',{'organization_instance_id':org['organization_instance_id'],'actor_id':actor_id})
        if org['organization_type']=='party': self._publish('party_member_joined',{'organization_instance_id':org['organization_instance_id'],'actor_id':actor_id})
        return m
    def get_members(self, organization_id, status=None):
        org=self.get_organization(organization_id); oid=org['organization_instance_id'] if org else organization_id
        with self._con() as con:
            rows=con.execute("SELECT * FROM organization_memberships WHERE organization_instance_id=? AND (? IS NULL OR status=?) ORDER BY joined_world_time, actor_id",(oid,status,status)).fetchall()
            return [dict(r)|{'metadata':_loads(r['metadata_json'])} for r in rows]
    def get_actor_memberships(self, actor_id, status='active'):
        with self._con() as con:
            rows=con.execute("SELECT m.*,o.name,o.organization_type FROM organization_memberships m JOIN organization_instances o ON o.organization_instance_id=m.organization_instance_id WHERE m.actor_id=? AND (? IS NULL OR m.status=?)",(actor_id,status,status)).fetchall()
            return [dict(r) for r in rows]
    def has_permission(self, actor_id, organization_id, permission): return self.trace_permission(actor_id,organization_id,permission)['allowed']
    has_organization_permission=has_permission
    def trace_permission(self, actor_id, organization_id, permission):
        org=self.get_organization(organization_id); oid=org['organization_instance_id'] if org else organization_id
        trace=[]
        with self._con() as con: m=con.execute("SELECT * FROM organization_memberships WHERE organization_instance_id=? AND actor_id=? AND status='active'",(oid,actor_id)).fetchone()
        if not m: return {'allowed':False,'trace':['no active membership'],'permission':permission}
        def collect(rid, seen=None):
            seen=seen or set()
            if rid in seen: return set()
            seen.add(rid); r=self._role(rid); out=set(r.get('permissions',[]))
            for p in r.get('inherits_from_role_ids',[]): out |= collect(p,seen)
            return out
        perms=collect(m['role_id']); allowed=permission in perms or 'custom' in perms
        return {'allowed':allowed,'trace':[{'membership_id':m['membership_id'],'role_id':m['role_id'],'permissions':sorted(perms)}, 'granted' if allowed else 'default deny'],'permission':permission}
    trace_organization_permission=trace_permission
    def require(self, actor, org, perm):
        if not self.has_permission(actor,org,perm): raise PermissionError(f'missing organization permission: {perm}')
    def invite_actor(self, organization_id, inviter_actor_id, invitee_actor_id, role_id=None, *, world_time=0, expires_world_time=None):
        org=self.get_organization(organization_id); self.require(inviter_actor_id,org['organization_instance_id'],'invite')
        d=self.content.get('organization_definitions',org['organization_definition_id']) or {}; role_id=role_id or d.get('default_role_id') or 'member'; now=utc_now(); iid=stable_id('oi',self.world_id,org['organization_instance_id'],invitee_actor_id,role_id)
        with self._con() as con:
            self._check_membership_allowed(con,org,invitee_actor_id)
            con.execute("INSERT INTO organization_invitations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,org['organization_instance_id'],inviter_actor_id,invitee_actor_id,role_id,'pending',world_time,expires_world_time,None,now,now,_json({})))
            self._audit(con,org['organization_instance_id'],inviter_actor_id,'member_invited','actor',invitee_actor_id,None,{'role_id':role_id},world_time=world_time)
        self._publish('organization_member_invited',{'invitation_id':iid,'organization_instance_id':org['organization_instance_id']}); return self.get_invitation(iid)
    def get_invitation(self, iid):
        with self._con() as con:
            r=con.execute("SELECT * FROM organization_invitations WHERE invitation_id=?",(iid,)).fetchone(); return None if not r else dict(r)
    def list_invitations(self, actor_id):
        with self._con() as con: return [dict(r) for r in con.execute("SELECT * FROM organization_invitations WHERE invitee_actor_id=? AND status='pending'",(actor_id,))]
    def accept_invitation(self, invitee_actor_id, invitation_id, *, world_time=0):
        with self._con() as con:
            inv=con.execute("SELECT * FROM organization_invitations WHERE invitation_id=? AND invitee_actor_id=? AND status='pending'",(invitation_id,invitee_actor_id)).fetchone()
            if not inv: raise ValueError('pending invitation not found')
            if inv['expires_world_time'] is not None and inv['expires_world_time']<world_time: con.execute("UPDATE organization_invitations SET status='expired' WHERE invitation_id=?",(invitation_id,)); raise ValueError('invitation expired')
            con.execute("UPDATE organization_invitations SET status='accepted',responded_world_time=?,updated_at=? WHERE invitation_id=?",(world_time,utc_now(),invitation_id))
            m=self._add_member_tx(con,inv['organization_instance_id'],invitee_actor_id,inv['intended_role_id'],'invitation',world_time=world_time,invited_by_actor_id=inv['inviter_actor_id'],approved_by_actor_id=inv['inviter_actor_id'])
            self._audit(con,inv['organization_instance_id'],invitee_actor_id,'invitation_accepted','invitation',invitation_id,None,dict(inv),world_time=world_time)
        self._publish('organization_invitation_accepted',{'invitation_id':invitation_id}); return m
    def decline_invitation(self, invitee_actor_id, invitation_id, *, world_time=0):
        with self._con() as con: con.execute("UPDATE organization_invitations SET status='declined',responded_world_time=?,updated_at=? WHERE invitation_id=? AND invitee_actor_id=? AND status='pending'",(world_time,utc_now(),invitation_id,invitee_actor_id))
        self._publish('organization_invitation_declined',{'invitation_id':invitation_id}); return True
    def cancel_invitation(self, inviter_actor_id, invitation_id):
        inv=self.get_invitation(invitation_id); self.require(inviter_actor_id,inv['organization_instance_id'],'cancel_invite')
        with self._con() as con: con.execute("UPDATE organization_invitations SET status='cancelled',updated_at=? WHERE invitation_id=?",(utc_now(),invitation_id))
        return True
    def apply_to_organization(self, actor_id, organization_id, message=None, requested_role_id=None, *, world_time=0):
        org=self.get_organization(organization_id); now=utc_now(); aid=stable_id('oapp',self.world_id,org['organization_instance_id'],actor_id)
        with self._con() as con:
            self._check_membership_allowed(con,org,actor_id)
            con.execute("INSERT INTO organization_applications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,self.world_id,org['organization_instance_id'],actor_id,requested_role_id,message or '','pending','',world_time,None,None,now,now,_json({})))
            self._audit(con,org['organization_instance_id'],actor_id,'application_submitted','actor',actor_id,None,{'message':message},world_time=world_time)
        self._publish('organization_application_submitted',{'application_id':aid}); return self.get_application(aid)
    def get_application(self, aid):
        with self._con() as con:
            r=con.execute("SELECT * FROM organization_applications WHERE application_id=?",(aid,)).fetchone(); return None if not r else dict(r)
    def approve_application(self, reviewer_actor_id, application_id, *, world_time=0):
        app=self.get_application(application_id); self.require(reviewer_actor_id,app['organization_instance_id'],'approve_application')
        org=self.get_organization(app['organization_instance_id']); d=self.content.get('organization_definitions',org['organization_definition_id']) or {}; role=app['requested_role_id'] or d.get('default_role_id') or 'member'
        with self._con() as con:
            con.execute("UPDATE organization_applications SET status='approved',reviewed_by_actor_id=?,reviewed_world_time=?,updated_at=? WHERE application_id=?",(reviewer_actor_id,world_time,utc_now(),application_id))
            m=self._add_member_tx(con,app['organization_instance_id'],app['applicant_actor_id'],role,'application',world_time=world_time,approved_by_actor_id=reviewer_actor_id)
            self._audit(con,app['organization_instance_id'],reviewer_actor_id,'application_approved','application',application_id,None,app,world_time=world_time)
        self._publish('organization_application_approved',{'application_id':application_id}); return m
    def reject_application(self, reviewer_actor_id, application_id, *, world_time=0):
        app=self.get_application(application_id); self.require(reviewer_actor_id,app['organization_instance_id'],'reject_application')
        with self._con() as con: con.execute("UPDATE organization_applications SET status='rejected',reviewed_by_actor_id=?,reviewed_world_time=?,updated_at=? WHERE application_id=?",(reviewer_actor_id,world_time,utc_now(),application_id))
        self._publish('organization_application_rejected',{'application_id':application_id}); return True
    def withdraw_application(self, actor_id, application_id):
        with self._con() as con: con.execute("UPDATE organization_applications SET status='withdrawn',updated_at=? WHERE application_id=? AND applicant_actor_id=? AND status='pending'",(utc_now(),application_id,actor_id)); return True
    def remove_member(self, requesting_actor_id, organization_id, actor_id, reason=None, *, world_time=0):
        org=self.get_organization(organization_id); self.require(requesting_actor_id,org['organization_instance_id'],'remove_member')
        with self._con() as con:
            con.execute("UPDATE organization_memberships SET status='removed',left_world_time=?,updated_at=? WHERE organization_instance_id=? AND actor_id=? AND status='active'",(world_time,utc_now(),org['organization_instance_id'],actor_id))
            self._audit(con,org['organization_instance_id'],requesting_actor_id,'member_removed','actor',actor_id,None,{'reason':reason},reason or '',world_time)
        self._publish('organization_member_removed',{'organization_instance_id':org['organization_instance_id'],'actor_id':actor_id}); return True
    def leave_organization(self, actor_id, organization_id, *, world_time=0):
        org=self.get_organization(organization_id)
        with self._con() as con:
            con.execute("UPDATE organization_memberships SET status='left',left_world_time=?,updated_at=? WHERE organization_instance_id=? AND actor_id=? AND status='active'",(world_time,utc_now(),org['organization_instance_id'],actor_id))
            self._audit(con,org['organization_instance_id'],actor_id,'member_left','actor',actor_id,None,None,world_time=world_time)
            count=con.execute("SELECT count(*) FROM organization_memberships WHERE organization_instance_id=? AND status='active'",(org['organization_instance_id'],)).fetchone()[0]
            if org['organization_type']=='party' and count==0: con.execute("UPDATE organization_instances SET status='disbanded',disbanded_world_time=?,updated_at=? WHERE organization_instance_id=?",(world_time,utc_now(),org['organization_instance_id']))
        self._publish('organization_member_left',{'organization_instance_id':org['organization_instance_id'],'actor_id':actor_id}); return True
    def assign_role(self, requesting_actor_id, organization_id, actor_id, role_id, *, world_time=0):
        org=self.get_organization(organization_id); self.require(requesting_actor_id,org['organization_instance_id'],'assign_role')
        with self._con() as con:
            old=con.execute("SELECT * FROM organization_memberships WHERE organization_instance_id=? AND actor_id=? AND status='active'",(org['organization_instance_id'],actor_id)).fetchone()
            con.execute("UPDATE organization_memberships SET role_id=?,updated_at=? WHERE organization_instance_id=? AND actor_id=? AND status='active'",(role_id,utc_now(),org['organization_instance_id'],actor_id))
            self._audit(con,org['organization_instance_id'],requesting_actor_id,'role_assigned','actor',actor_id,dict(old) if old else None,{'role_id':role_id},world_time=world_time)
        self._publish('organization_role_assigned',{'organization_instance_id':org['organization_instance_id'],'actor_id':actor_id,'role_id':role_id}); return True
    def transfer_leadership(self, requesting_actor_id, organization_id, target_actor_id, *, world_time=0):
        org=self.get_organization(organization_id); self.require(requesting_actor_id,org['organization_instance_id'],'transfer_leadership')
        d=self.content.get('organization_definitions',org['organization_definition_id']) or {}; role=d.get('leader_role_id') or 'leader'
        with self._con() as con:
            if not con.execute("SELECT 1 FROM organization_memberships WHERE organization_instance_id=? AND actor_id=? AND status='active'",(org['organization_instance_id'],target_actor_id)).fetchone(): raise ValueError('target is not an active member')
            con.execute("UPDATE organization_instances SET leader_actor_id=?,updated_at=? WHERE organization_instance_id=?",(target_actor_id,utc_now(),org['organization_instance_id']))
            con.execute("UPDATE organization_memberships SET role_id=?,updated_at=? WHERE organization_instance_id=? AND actor_id=? AND status='active'",(role,utc_now(),org['organization_instance_id'],target_actor_id))
            self._audit(con,org['organization_instance_id'],requesting_actor_id,'leadership_transferred','actor',target_actor_id,{'old':org.get('leader_actor_id')},{'new':target_actor_id},world_time=world_time)
        self._publish('organization_leadership_transferred',{'organization_instance_id':org['organization_instance_id'],'actor_id':target_actor_id}); return True
    def disband_organization(self, actor_id, organization_id, reason=None, *, world_time=0):
        org=self.get_organization(organization_id); self.require(actor_id,org['organization_instance_id'],'disband')
        with self._con() as con:
            con.execute("UPDATE organization_instances SET status='disbanded',disbanded_world_time=?,updated_at=? WHERE organization_instance_id=?",(world_time,utc_now(),org['organization_instance_id']))
            self._audit(con,org['organization_instance_id'],actor_id,'organization_disbanded','organization',org['organization_instance_id'],org,None,reason or '',world_time)
        self._publish('organization_disbanded',{'organization_instance_id':org['organization_instance_id']});
        if org['organization_type']=='party': self._publish('party_disbanded',{'organization_instance_id':org['organization_instance_id']})
        return True
    def create_party(self, leader_actor_id, name=None, **kw): return self.create_organization('starter_party',leader_actor_id,name or 'Party',**kw)
    def get_actor_party(self, actor_id):
        ms=[m for m in self.get_actor_memberships(actor_id) if m.get('organization_type')=='party']; return self.get_organization(ms[0]['organization_instance_id']) if ms else None
    def send_message(self, organization_id, channel_id, sender_actor_id, message_text, *, world_time=0):
        org=self.get_organization(organization_id)
        if not self.get_members(org['organization_instance_id'],'active'): raise PermissionError('sender is not a member')
        mid=stable_id('omsg',org['organization_instance_id'],channel_id,sender_actor_id,world_time,uuid.uuid4().hex)
        with self._con() as con: con.execute("INSERT INTO organization_messages VALUES(?,?,?,?,?,?,?,?)",(mid,org['organization_instance_id'],channel_id,sender_actor_id,message_text,world_time,utc_now(),_json({})))
        self._publish('organization_message_sent',{'message_id':mid,'organization_instance_id':org['organization_instance_id'],'channel_id':channel_id}); return {'message_id':mid}
    def record_group_combat_participation(self, organization_id, combat_instance_id, actor_id, target_actor_id='', damage=0, healing=0, support=0, control=0, eligible=True, metadata=None):
        org=self.get_organization(organization_id); pid=stable_id('gcp',self.world_id,org['organization_instance_id'],combat_instance_id,actor_id,target_actor_id); now=utc_now()
        with self._con() as con:
            old=con.execute("SELECT * FROM group_combat_participation WHERE participation_id=?",(pid,)).fetchone()
            if old:
                con.execute("UPDATE group_combat_participation SET damage_contribution=?,healing_contribution=?,support_contribution=?,control_contribution=?,eligible=?,updated_at=?,metadata_json=? WHERE participation_id=?",(max(0,float(old['damage_contribution'])+float(damage)),max(0,float(old['healing_contribution'])+float(healing)),max(0,float(old['support_contribution'])+float(support)),max(0,float(old['control_contribution'])+float(control)),1 if eligible else 0,now,_json(metadata or _loads(old['metadata_json'])),pid))
            else:
                con.execute("INSERT INTO group_combat_participation VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,org['organization_instance_id'],combat_instance_id,actor_id,target_actor_id,max(0,float(damage)),max(0,float(healing)),max(0,float(support)),max(0,float(control)),0,1 if eligible else 0,now,now,_json(metadata or {})))
        self._publish('group_combat_participation_updated',{'participation_id':pid}); return self.trace_group_combat(org['organization_instance_id'],combat_instance_id)
    def trace_group_combat(self, organization_id, combat_instance_id=None):
        org=self.get_organization(organization_id); oid=org['organization_instance_id'] if org else organization_id
        with self._con() as con: rows=con.execute("SELECT * FROM group_combat_participation WHERE organization_instance_id=? AND (? IS NULL OR combat_instance_id=?)",(oid,combat_instance_id,combat_instance_id)).fetchall()
        return [dict(r)|{'metadata':_loads(r['metadata_json'])} for r in rows]
    def share_quest_offer(self, organization_id, sharer_actor_id, quest_id, recipient_actor_id=None, *, world_time=0):
        org=self.get_organization(organization_id); recipients=[recipient_actor_id] if recipient_actor_id else [m['actor_id'] for m in self.get_members(org['organization_instance_id'],'active') if m['actor_id']!=sharer_actor_id]
        out=[]
        with self._con() as con:
            for rid in recipients:
                oid=stable_id('oqo',self.world_id,org['organization_instance_id'],quest_id,sharer_actor_id,rid)
                con.execute("INSERT OR IGNORE INTO organization_shared_quest_offers VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(oid,self.world_id,org['organization_instance_id'],quest_id,sharer_actor_id,rid,'pending',world_time,None,utc_now(),utc_now(),_json({})))
                out.append({'offer_id':oid,'recipient_actor_id':rid,'quest_id':quest_id})
        self._publish('quest_offer_shared',{'organization_instance_id':org['organization_instance_id'],'quest_id':quest_id,'recipients':recipients}); return out
    def eligible_group_quest_members(self, actor_id, quest_id=None, room_id=None):
        party=self.get_actor_party(actor_id)
        return [] if not party else [m['actor_id'] for m in self.get_members(party['organization_instance_id'],'active')]
    def award_group_kill_credit(self, actor_id, quest_service, event):
        credited=[]
        for aid in self.eligible_group_quest_members(actor_id):
            ev=dict(event); ev['actor_id']=aid; ev['event_id']=stable_id('groupquest',event.get('event_id',''),aid)
            if hasattr(quest_service,'handle_event'): quest_service.handle_event(ev)
            credited.append(aid)
        self._publish('group_quest_credit_awarded',{'source_actor_id':actor_id,'credited_actor_ids':credited}); return credited
    def create_subgroup(self, organization_id, name, subgroup_type='party', leader_actor_id='', maximum_members=None):
        org=self.get_organization(organization_id); sid=stable_id('osg',org['organization_instance_id'],name,uuid.uuid4().hex); now=utc_now()
        with self._con() as con:
            con.execute("INSERT INTO organization_subgroups VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,org['organization_instance_id'],name,subgroup_type,leader_actor_id,maximum_members,'active',now,now,_json({})))
            self._audit(con,org['organization_instance_id'],leader_actor_id,'subgroup_created','subgroup',sid,None,{'name':name})
        self._publish('organization_subgroup_created',{'subgroup_id':sid}); return {'subgroup_id':sid,'name':name}
    def set_relationship(self, source_organization_id, target_organization_id, relationship_type='neutral', value=0, status='active', *, world_time=0):
        src=self.get_organization(source_organization_id); tgt=self.get_organization(target_organization_id); rid=stable_id('orel',self.world_id,src['organization_instance_id'],tgt['organization_instance_id'],relationship_type); now=utc_now()
        with self._con() as con: con.execute("INSERT OR REPLACE INTO organization_relationships VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(rid,self.world_id,src['organization_instance_id'],tgt['organization_instance_id'],relationship_type,float(value),status,world_time,world_time,now,now,_json({})))
        self._publish('organization_relationship_changed',{'relationship_id':rid}); return {'relationship_id':rid}
    def materialize_seed(self, seed_id, actor_resolver=None, *, world_time=0):
        s=self.content.get('organization_seeds',seed_id)
        if not s or not s.get('enabled',True): raise ValueError('seed not found or disabled')
        leader=(actor_resolver(s.get('leader_actor_ref')) if actor_resolver and s.get('leader_actor_ref') else s.get('leader_actor_ref') or '')
        org=self.create_organization(s['organization_definition_id'],leader,s.get('instance_name'),world_time=world_time)
        for ref in s.get('member_refs',[]):
            aid=actor_resolver(ref) if actor_resolver else ref
            role=(s.get('role_assignments') or {}).get(ref) or (self.content.get('organization_definitions',s['organization_definition_id']) or {}).get('default_role_id') or 'member'
            try: self.add_member(org['organization_instance_id'],aid,role,'seed',world_time=world_time)
            except ValueError: pass
        return org
    def trace_organization(self, organization_id):
        org=self.get_organization(organization_id); oid=org['organization_instance_id'] if org else organization_id
        with self._con() as con:
            audit=[dict(r) for r in con.execute("SELECT * FROM organization_audit_events WHERE organization_instance_id=? ORDER BY created_at",(oid,))]
            inv=[dict(r) for r in con.execute("SELECT * FROM organization_invitations WHERE organization_instance_id=?",(oid,))]
            app=[dict(r) for r in con.execute("SELECT * FROM organization_applications WHERE organization_instance_id=?",(oid,))]
        return {'organization':org,'definition':self.content.get('organization_definitions',org['organization_definition_id']) if org else None,'memberships':self.get_members(oid),'invitations':inv,'applications':app,'audit':audit,'combat_participation':self.trace_group_combat(oid),'restart_state':'sqlite-authoritative'}
    get_organization_context=trace_organization
