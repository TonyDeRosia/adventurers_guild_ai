"""Canonical zone reset service for Smart MUD Phase 15A."""
from __future__ import annotations

from engine.equipment_slots import normalize_equipment_slot

import json, sqlite3, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

RESET_MODES={"always","when_empty","manual_only","never"}; COMMAND_TYPES={"SPAWN_ENTITY","SPAWN_ITEM","GIVE_ITEM","EQUIP_ITEM","PUT_ITEM","SET_EXIT_STATE"}; CONDITIONS={"always","if_previous_succeeded","if_previous_created","if_reference_exists","if_room_empty","if_zone_empty","if_count_below_limit"}; FAILURE_POLICIES={"continue","skip_dependents","abort_profile"}; MAX_SCOPES={"room","zone","world","template_global"}

def utcnow(): return datetime.now(timezone.utc).isoformat()
def _asdict(records):
    if isinstance(records, dict): return {str(k):v for k,v in records.items() if isinstance(v,dict)}
    return {str((r or {}).get('id')):r for r in (records or []) if isinstance(r,dict) and r.get('id')}

def init_zone_reset_schema(db_path: str|Path):
    p=Path(db_path); p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as c:
        c.executescript('''
CREATE TABLE IF NOT EXISTS zone_reset_runtime(world_id TEXT,zone_id TEXT,reset_profile_id TEXT PRIMARY KEY,last_attempted_reset TEXT,last_successful_reset TEXT,next_due_reset TEXT,reset_generation INTEGER DEFAULT 0,last_status TEXT,last_error TEXT,claim_token TEXT,claim_expires_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS zone_reset_runs(reset_run_id TEXT PRIMARY KEY,world_id TEXT,zone_id TEXT,reset_profile_id TEXT,world_generation INTEGER,definition_version TEXT,trigger TEXT,requested_by TEXT,started_at TEXT,completed_at TEXT,status TEXT,planned_action_count INTEGER,executed_action_count INTEGER,skipped_action_count INTEGER,failed_action_count INTEGER,created_entity_count INTEGER,created_item_count INTEGER,changed_exit_count INTEGER,result_summary TEXT);
CREATE TABLE IF NOT EXISTS zone_reset_action_results(id INTEGER PRIMARY KEY AUTOINCREMENT,reset_run_id TEXT,reset_command_id TEXT,command_type TEXT,status TEXT,reason TEXT,created_instance_ids TEXT,affected_instance_ids TEXT,started_at TEXT,completed_at TEXT,details TEXT);
CREATE INDEX IF NOT EXISTS idx_zone_reset_runtime_world_zone ON zone_reset_runtime(world_id,zone_id);
CREATE INDEX IF NOT EXISTS idx_zone_reset_runtime_next_due ON zone_reset_runtime(next_due_reset);
CREATE INDEX IF NOT EXISTS idx_zone_reset_runs_profile ON zone_reset_runs(reset_profile_id);
CREATE INDEX IF NOT EXISTS idx_zone_reset_runs_status ON zone_reset_runs(status);
CREATE INDEX IF NOT EXISTS idx_zone_reset_runs_started ON zone_reset_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_zone_reset_actions_run ON zone_reset_action_results(reset_run_id);
''')

@dataclass(frozen=True)
class ValidationResult:
    ok: bool; errors: list[str]=field(default_factory=list); warnings: list[str]=field(default_factory=list)
@dataclass(frozen=True)
class ResetPlan:
    profile_id: str; world_id: str; zone_id: str; world_generation: int; definition_version: str; actions: tuple[dict[str,Any],...]; profile: dict[str,Any]

class ZoneResetService:
    history_limit=500
    def __init__(self, runtime: Any|None=None, world_package: Any|None=None, db_path: str|Path|None=None, event_bus: Any|None=None, worlds_dir: str|Path='worlds'):
        self.runtime=runtime; self.world=world_package; self.worlds_dir=Path(worlds_dir); self.event_bus=event_bus or getattr(runtime,'event_bus',None); self.db_path=Path(db_path or getattr(getattr(runtime,'state_store',None),'db_path',':memory:')); init_zone_reset_schema(self.db_path); self._plan_cache={}; self._active_profiles=set(); self._active_zones=set()
    def _publish(self,name,payload):
        if self.event_bus: self.event_bus.publish(name, payload, source_system='zone_reset', world_id=payload.get('world_id',''))
    def _root(self, world_id): return self.worlds_dir/world_id
    def load_profiles(self, world_id: str) -> list[dict[str,Any]]:
        out=[]
        for rel in ('resets/resets.json','builder/resets.json'):
            p=self._root(world_id)/rel
            if p.exists():
                d=json.loads(p.read_text()); vals=d.values() if isinstance(d,dict) else d
                out += [self.normalize_profile(x, world_id) for x in vals if isinstance(x,dict)]
        return out
    def normalize_profile(self, p, world_id=''):
        p=dict(p); p['reset_profile_id']=str(p.get('reset_profile_id') or p.get('id') or ''); p['id']=p['reset_profile_id']; p['world_id']=str(p.get('world_id') or world_id);
        if 'empty_required' in p and not p.get('reset_mode'): p['reset_mode']='when_empty' if p.get('empty_required') else 'always'
        p.setdefault('reset_mode','manual_only'); p.setdefault('enabled',True); p.setdefault('priority',100); p.setdefault('reset_interval_seconds',None); p.setdefault('definition_version','1'); p.setdefault('commands',[]); p.setdefault('metadata',{})
        return p
    def _maps(self, world_id):
        root=self._root(world_id)
        def read(rel):
            p=root/rel
            if not p.exists(): return {}
            d=json.loads(p.read_text()); return _asdict((d.get('records') or d.get(Path(rel).parent.name) or d) if isinstance(d, dict) else d)
        rooms=read('rooms/rooms.json')|read('builder/rooms.json'); zones=read('zones/zones.json')|read('builder/zones.json'); items=read('items/items.json')|read('builder/item_templates.json'); ents=read('npcs/npcs.json')|read('builder/entity_templates.json')
        room_zone={}
        for zid,z in zones.items():
            for rid in z.get('room_ids') or []: room_zone[str(rid)]=zid
        for rid,r in rooms.items():
            if r.get('zone_id'): room_zone[rid]=str(r.get('zone_id'))
        return rooms,zones,items,ents,room_zone
    def validate_profile(self, profile):
        p=self.normalize_profile(profile, profile.get('world_id','')); errors=[]; warnings=[]; refs=set(); ids=set(); rooms,zones,items,ents,room_zone=self._maps(p.get('world_id',''))
        if not p['reset_profile_id']: errors.append('missing reset_profile_id')
        if not p.get('world_id'): errors.append('missing world_id')
        if not p.get('zone_id'): errors.append('missing zone_id')
        elif p['zone_id'] not in zones: errors.append(f"unknown zone {p['zone_id']}")
        if p.get('reset_mode') not in RESET_MODES: errors.append(f"invalid reset mode {p.get('reset_mode')}")
        iv=p.get('reset_interval_seconds')
        if iv is not None and int(iv) < 0: errors.append('invalid interval')
        last_order=-10**9
        for c in sorted(p.get('commands') or [], key=lambda x:(int(x.get('order',0)), str(x.get('reset_command_id') or x.get('id','')))):
            cid=str(c.get('reset_command_id') or c.get('id') or '')
            if not cid: errors.append('missing command id')
            if cid in ids: errors.append(f'duplicate command ID {cid}')
            ids.add(cid); typ=str(c.get('command_type','')).upper()
            if typ not in COMMAND_TYPES: errors.append(f'unknown command type {typ}')
            if str(c.get('failure_policy','continue')) not in FAILURE_POLICIES: errors.append(f'invalid failure policy {cid}')
            cond=c.get('condition') or {'type':'always'}; ct=cond.get('type') if isinstance(cond,dict) else str(cond)
            if ct not in CONDITIONS: errors.append(f'invalid condition {cid}')
            rr=c.get('result_reference')
            if rr:
                if rr in refs: errors.append(f'duplicate result reference {rr}')
                refs.add(rr)
            ref=c.get('target_reference') or c.get('container_reference') or (cond.get('reference') if isinstance(cond,dict) else None)
            if ref and ref not in refs: errors.append(f'invalid forward reference {cid}:{ref}')
            rid=c.get('room_id')
            if rid:
                if rid not in rooms: errors.append(f'unknown room {rid}')
                elif p.get('zone_id') and room_zone.get(str(rid)) != p.get('zone_id'): errors.append(f'room outside declared zone {rid}')
            if c.get('maximum_scope','room') not in MAX_SCOPES: errors.append(f'invalid maximum scope {cid}')
            if int(c.get('maximum_count',0) or 0) < 0: errors.append(f'negative maximum count {cid}')
            if typ=='SPAWN_ENTITY' and c.get('entity_template_id') not in ents: errors.append(f"unknown entity template {c.get('entity_template_id')}")
            if typ in {'SPAWN_ITEM','GIVE_ITEM','EQUIP_ITEM','PUT_ITEM'} and c.get('item_template_id') not in items: errors.append(f"unknown item template {c.get('item_template_id')}")
            if typ=='SET_EXIT_STATE' and not c.get('direction'): errors.append(f'unknown direction {cid}')
            if typ.startswith('SPAWN') and int(c.get('spawn_count',1) or 0) <= 0: errors.append(f'zero spawn count where invalid {cid}')
            last_order=int(c.get('order',0))
        if p.get('reset_mode')=='always': warnings.append('always mode may run while players are present')
        if p.get('reset_mode')=='manual_only' and p.get('reset_interval_seconds'): warnings.append('manual-only profile has an interval')
        return ValidationResult(not errors, errors, warnings)
    def compile_plan(self, profile, world_generation: int|None=None):
        p=self.normalize_profile(profile, profile.get('world_id','')); gen=int(world_generation if world_generation is not None else getattr(self.runtime,'world_generation',1)); key=(p['world_id'],p['reset_profile_id'],p.get('definition_version'),gen,json.dumps(p, sort_keys=True, default=str))
        if key in self._plan_cache: return self._plan_cache[key]
        v=self.validate_profile(p)
        if not v.ok: raise ValueError('; '.join(v.errors))
        acts=tuple(dict(c, command_type=str(c.get('command_type','')).upper(), failure_policy=c.get('failure_policy','continue'), condition=c.get('condition') or {'type':'always'}) for c in sorted(p.get('commands') or [], key=lambda x:(int(x.get('order',0)), str(x.get('reset_command_id') or x.get('id','')))))
        plan=ResetPlan(p['reset_profile_id'],p['world_id'],p['zone_id'],gen,str(p.get('definition_version','1')),acts,p)
        if len(self._plan_cache)>64: self._plan_cache.clear()
        self._plan_cache[key]=plan; return plan
    def invalidate_plan_cache(self): self._plan_cache.clear()
    def active_players_in_zone(self, world_id, zone_id):
        _,_,_,_,rz=self._maps(world_id); chars=getattr(self.runtime,'characters',{}) or getattr(self.runtime,'active_characters',{}) or {}
        return [c for c in chars.values() if rz.get(str(getattr(c,'room_id', c.get('room_id','') if isinstance(c,dict) else ''))) == zone_id]
    def _count(self, typ, template_id, scope, room_id, zone_id, world_id):
        table='entity_instances' if typ=='entity' else 'item_instances'; w="destroyed_at IS NULL AND template_id=?"; params=[template_id]
        if typ == 'entity':
            w += " AND owner_type='room' AND entity_type IN ('npc','mob')"
        if scope=='room': w += (' AND current_room_id=?' if typ=='entity' else ' AND room_id=? AND owner_type=\'room\''); params.append(room_id)
        elif scope=='zone':
            rz=self._maps(world_id)[4]; rooms=[r for r,z in rz.items() if z==zone_id] or ['']
            col='current_room_id' if typ=='entity' else 'room_id'; w += f" AND {col} IN ({','.join('?' for _ in rooms)})"; params+=rooms
        elif scope=='world': w += ' AND world_id=?'; params.append(world_id)
        with sqlite3.connect(self.db_path) as c:
            if typ != 'entity':
                return int(c.execute(f'SELECT COUNT(*) FROM {table} WHERE {w}', params).fetchone()[0])
            rows=c.execute(f'SELECT state FROM {table} WHERE {w}', params).fetchall()
        live=0
        for (raw_state,) in rows:
            try: state=json.loads(raw_state or '{}')
            except Exception: state={}
            if state.get('is_alive') is False or str(state.get('current_state') or '').lower() in {'dead','corpse','despawned','destroyed'}:
                continue
            live += 1
        return live
    def _condition_ok(self, cond, plan, cmd, prev, refs):
        ct=cond.get('type') if isinstance(cond,dict) else str(cond or 'always')
        if ct=='always': return True,''
        if ct=='if_previous_succeeded': return bool(prev and prev.get('status')=='succeeded'),'previous command did not succeed'
        if ct=='if_previous_created': return bool(prev and prev.get('created')),'previous command created nothing'
        if ct=='if_reference_exists': return bool(refs.get(cond.get('reference') or cmd.get('target_reference'))),'reference missing'
        if ct=='if_room_empty': return not self.active_players_in_room(cmd.get('room_id')),'room occupied'
        if ct=='if_zone_empty': return not self.active_players_in_zone(plan.world_id, plan.zone_id),'zone occupied'
        if ct=='if_count_below_limit':
            typ='entity' if cmd.get('entity_template_id') else 'item'; tid=cmd.get('entity_template_id') or cmd.get('item_template_id'); cur=self._count(typ,tid,cmd.get('maximum_scope','room'),cmd.get('room_id',''),plan.zone_id,plan.world_id); return cur < int(cmd.get('maximum_count',0) or 0), f'count {cur} >= maximum'
        return False,'invalid condition'
    def active_players_in_room(self, room_id):
        chars=getattr(self.runtime,'characters',{}) or getattr(self.runtime,'active_characters',{}) or {}; return [c for c in chars.values() if str(getattr(c,'room_id', c.get('room_id','') if isinstance(c,dict) else ''))==str(room_id)]
    def execute(self, profile_id, trigger='manual', requested_by='', force=False, preview=False):
        prof=next((p for p in self.load_profiles(getattr(self.runtime,'active_world_id','shattered_realms')) if p['reset_profile_id']==profile_id), None)
        if not prof: raise ValueError(f'unknown reset profile {profile_id}')
        plan=self.compile_plan(prof); return self.execute_plan(plan, trigger, requested_by, force, preview)
    def execute_plan(self, plan, trigger='manual', requested_by='', force=False, preview=False):
        p=plan.profile
        if not p.get('enabled',True): return {'status':'skipped','reason':'disabled'}
        if p['reset_mode']=='never' and not force: return {'status':'rejected','reason':'never mode'}
        if trigger=='automatic' and p['reset_mode'] in {'manual_only','never'}: return {'status':'skipped','reason':'manual only'}
        if trigger=='automatic' and p['reset_mode']=='when_empty' and self.active_players_in_zone(plan.world_id, plan.zone_id): return {'status':'skipped','reason':'zone occupied'}
        if plan.profile_id in self._active_profiles or plan.zone_id in self._active_zones: return {'status':'skipped','reason':'duplicate run prevented'}
        self._active_profiles.add(plan.profile_id); self._active_zones.add(plan.zone_id)
        run_id='preview_'+uuid.uuid4().hex if preview else 'zrun_'+uuid.uuid4().hex; started=utcnow(); results=[]; refs={}; prev=None; counts={'entities':0,'items':0,'exits':0,'failed':0,'skipped':0,'executed':0}
        self._publish('zone_reset_previewed' if preview else 'zone_reset_started', {'world_id':plan.world_id,'zone_id':plan.zone_id,'profile_id':plan.profile_id,'trigger':trigger,'status':'started','generation':plan.world_generation,'definition_version':plan.definition_version})
        try:
            for cmd in plan.actions:
                cid=cmd.get('reset_command_id') or cmd.get('id'); st=utcnow(); status='succeeded'; reason=''; created=[]; affected=[]
                ok, why = self._condition_ok(cmd.get('condition') or {'type':'always'}, plan, cmd, prev, refs)
                if not ok: status='skipped'; reason=why; counts['skipped']+=1
                else:
                    try:
                        if not preview: created, affected = self._apply(cmd, plan, refs)
                        else: created=[]; affected=[]
                        counts['executed']+=1; counts['entities']+=sum(1 for x in created if str(x).startswith(('entity_','ent_'))); counts['items']+=sum(1 for x in created if str(x).startswith('item_')); counts['exits']+=1 if cmd.get('command_type')=='SET_EXIT_STATE' and status=='succeeded' else 0
                    except Exception as exc:
                        status='failed'; reason=str(exc); counts['failed']+=1
                if cmd.get('result_reference') and (created or affected): refs[cmd['result_reference']]=created or affected
                rec={'reset_run_id':run_id,'reset_command_id':cid,'command_type':cmd.get('command_type'),'status':status,'reason':reason,'created_instance_ids':created,'affected_instance_ids':affected,'started_at':st,'completed_at':utcnow(),'details':{}}
                results.append(rec); prev={'status':status,'created':created}
                self._publish('zone_reset_action_'+('skipped' if status=='skipped' else 'failed' if status=='failed' else 'succeeded'), {'world_id':plan.world_id,'zone_id':plan.zone_id,'profile_id':plan.profile_id,'command_id':cid,'trigger':trigger,'status':status,'counts':counts,'reason':reason,'generation':plan.world_generation,'definition_version':plan.definition_version})
                if status=='failed' and cmd.get('failure_policy')=='abort_profile': break
            final='succeeded' if counts['failed']==0 else ('partial' if counts['executed'] else 'failed')
            completed=utcnow(); summary={'status':final, 'reset_run_id':run_id, **counts, 'results':results}
            if not preview: self._persist_run(plan, run_id, trigger, requested_by, started, completed, final, counts, results)
            self._publish('zone_reset_completed', {'world_id':plan.world_id,'zone_id':plan.zone_id,'profile_id':plan.profile_id,'trigger':trigger,'status':final,'counts':counts,'reason':'','generation':plan.world_generation,'definition_version':plan.definition_version})
            return summary
        finally:
            self._active_profiles.discard(plan.profile_id); self._active_zones.discard(plan.zone_id)
    def _apply(self, cmd, plan, refs):
        typ=cmd['command_type']; created=[]; affected=[]
        if typ=='SPAWN_ENTITY':
            cur=self._count('entity',cmd['entity_template_id'],cmd.get('maximum_scope','room'),cmd.get('room_id',''),plan.zone_id,plan.world_id); need=max(0, min(int(cmd.get('spawn_count',1)), int(cmd.get('maximum_count',1))-cur))

            for _ in range(need):
                state=dict(cmd.get('spawn_state') or {})
                state.setdefault('source_reset_profile_id', plan.profile_id)
                state.setdefault('source_spawn_id', cmd.get('canonical_spawn_id') or cmd.get('reset_command_id') or cmd.get('id'))
                state.setdefault('spawn_origin', cmd.get('room_id'))
                state.setdefault('lifecycle_id', 'life_'+uuid.uuid4().hex)
                created.append(self.runtime.spawn_entity(cmd['entity_template_id'], room_id=cmd['room_id'], state=state, flags=cmd.get('spawn_flags') or [], source_system='zone_reset')['entity_id'])
        elif typ=='SPAWN_ITEM':
            cur=self._count('item',cmd['item_template_id'],cmd.get('maximum_scope','room'),cmd.get('room_id',''),plan.zone_id,plan.world_id); need=max(0, min(int(cmd.get('spawn_count',1)), int(cmd.get('maximum_count',1))-cur))
            for _ in range(need): created.append(self.runtime.spawn_item(cmd['item_template_id'],'room',room_id=cmd['room_id'],stack_count=cmd.get('stack_count',1),custom_flags={'source_reset_profile_id':plan.profile_id})['instance_id'])
        elif typ in {'GIVE_ITEM','EQUIP_ITEM','PUT_ITEM'}:
            target=(refs.get(cmd.get('target_reference') or cmd.get('container_reference')) or [None])[0]
            if not target: raise ValueError('target reference missing')
            item=self.runtime.spawn_item(cmd['item_template_id'],'entity' if typ!='EQUIP_ITEM' else 'equipment',owner_id=target,equipped_slot=normalize_equipment_slot(cmd.get('equipment_slot')) if typ=='EQUIP_ITEM' else '',stack_count=cmd.get('stack_count',1),custom_flags={'source_reset_profile_id':plan.profile_id})
            created.append(item['instance_id']); affected.append(target)
        elif typ=='SET_EXIT_STATE':
            if hasattr(self.runtime,'set_exit_state'): self.runtime.set_exit_state(cmd['room_id'], cmd['direction'], {k:cmd.get(k) for k in ('closed','locked','pickproof','hidden','state_flags') if k in cmd})
            affected.append(f"{cmd['room_id']}:{cmd['direction']}")
        return created, affected
    def _persist_run(self, plan, run_id, trigger, requested_by, started, completed, status, counts, results):
        with sqlite3.connect(self.db_path) as c:
            c.execute('INSERT INTO zone_reset_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,plan.world_id,plan.zone_id,plan.profile_id,plan.world_generation,plan.definition_version,trigger,requested_by,started,completed,status,len(plan.actions),counts['executed'],counts['skipped'],counts['failed'],counts['entities'],counts['items'],counts['exits'],json.dumps({'status':status})))
            for r in results: c.execute('INSERT INTO zone_reset_action_results(reset_run_id,reset_command_id,command_type,status,reason,created_instance_ids,affected_instance_ids,started_at,completed_at,details) VALUES(?,?,?,?,?,?,?,?,?,?)',(run_id,r['reset_command_id'],r['command_type'],r['status'],r['reason'],json.dumps(r['created_instance_ids']),json.dumps(r['affected_instance_ids']),r['started_at'],r['completed_at'],json.dumps(r['details'])))
            c.execute('INSERT INTO zone_reset_runtime(world_id,zone_id,reset_profile_id,last_attempted_reset,last_successful_reset,next_due_reset,reset_generation,last_status,last_error,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(reset_profile_id) DO UPDATE SET last_attempted_reset=excluded.last_attempted_reset,last_successful_reset=excluded.last_successful_reset,reset_generation=zone_reset_runtime.reset_generation+1,last_status=excluded.last_status,last_error=excluded.last_error,updated_at=excluded.updated_at',(plan.world_id,plan.zone_id,plan.profile_id,completed,completed if status=='succeeded' else None,None,1,status,'' if status=='succeeded' else status,completed))
            rows=c.execute('SELECT reset_run_id FROM zone_reset_runs ORDER BY started_at DESC LIMIT -1 OFFSET ?', (self.history_limit,)).fetchall()
            for (rid,) in rows: c.execute('DELETE FROM zone_reset_action_results WHERE reset_run_id=?',(rid,)); c.execute('DELETE FROM zone_reset_runs WHERE reset_run_id=?',(rid,))
    def history(self, limit=20):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute('SELECT * FROM zone_reset_runs ORDER BY started_at DESC LIMIT ?', (limit,))]
    def trace(self, run_id):
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; return [dict(r) for r in c.execute('SELECT * FROM zone_reset_action_results WHERE reset_run_id=? ORDER BY id',(run_id,))]
    def due_profiles(self, world_id, now=None):
        return [p for p in self.load_profiles(world_id) if p.get('enabled',True) and p.get('reset_mode') in {'always','when_empty'} and p.get('reset_interval_seconds')]
    def tick(self, world_id):
        out=[]
        for p in self.due_profiles(world_id): out.append(self.execute_plan(self.compile_plan(p), trigger='automatic'))
        return out
