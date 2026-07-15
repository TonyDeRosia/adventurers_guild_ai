from __future__ import annotations
import ast, copy, hashlib, json, os, re, shutil, tempfile, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from engine.formulas import FormulaEngine

SAFE_ID_RE=re.compile(r'^[a-z0-9]+(?:_[a-z0-9]+)*$')
ROUNDINGS={'floor','ceil','round','none'}; BOOL_ON={'on','true','yes','1'}; BOOL_OFF={'off','false','no','0'}

def now(): return datetime.now(timezone.utc).isoformat()
def dump(obj): return json.dumps(obj, indent=2, sort_keys=True)+"\n"
def sha_bytes(b:bytes): return hashlib.sha256(b).hexdigest()
def read_json(path:Path, default):
    if not path.exists(): return copy.deepcopy(default)
    return json.loads(path.read_text(encoding='utf-8') or 'null') or copy.deepcopy(default)
def norm_hash(data): return sha_bytes(dump(data).encode())
def parse_bool(v):
    s=str(v).lower()
    if s in BOOL_ON: return True
    if s in BOOL_OFF: return False
    raise ValueError('expected on|off')
def parse_num(v):
    if str(v).lower()=='none': return None
    return float(v) if re.search(r'[.]', str(v)) else int(v)
def safe_id(v):
    if not SAFE_ID_RE.fullmatch(str(v)): raise ValueError('unsafe id: use lowercase letters, digits, single underscores, no edge underscores')
    return str(v)
def write_atomic(path:Path, data:dict):
    path.parent.mkdir(parents=True, exist_ok=True); content=dump(data).encode(); fd,tmp=tempfile.mkstemp(dir=str(path.parent), prefix=path.name+'.', suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as f: f.write(content); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return sha_bytes(content)

@dataclass
class Issue:
    document:str; record_id:str; field:str; code:str; message:str
    def line(self): return f"{self.document}:{self.record_id}:{self.field}:{self.code}: {self.message}"

class BaseAdapter:
    name=''; live=''; draft=''; collection_key=''; id_key='id'; default_doc=None; map_collection=False
    def __init__(self, root:Path): self.root=Path(root)
    @property
    def live_path(self): return self.root/self.live
    @property
    def draft_path(self): return self.root/self.draft
    def default_document(self): return copy.deepcopy(self.default_doc or {self.collection_key: []})
    def load_draft(self): return read_json(self.draft_path, read_json(self.live_path, self.default_document()))
    def load_live(self): return read_json(self.live_path, self.default_document())
    def save_draft(self,data): self.normalize_doc(data); return write_atomic(self.draft_path,data)
    def recs(self,data):
        val=data.setdefault(self.collection_key, {} if self.map_collection else [])
        if isinstance(val,dict): return val
        return val
    def values(self,data):
        r=self.recs(data); return list(r.values()) if isinstance(r,dict) else list(r)
    def find(self,data,rid):
        r=self.recs(data)
        if isinstance(r,dict): return r.get(rid)
        return next((x for x in r if str(x.get(self.id_key) or x.get('id'))==rid),None)
    def put(self,data,rec):
        r=self.recs(data); rid=rec.get(self.id_key) or rec.get('id')
        if isinstance(r,dict): r[rid]=rec
        else:
            for i,x in enumerate(r):
                if str(x.get(self.id_key) or x.get('id'))==rid: r[i]=rec; break
            else: r.append(rec)
    def remove(self,data,rid):
        r=self.recs(data)
        if isinstance(r,dict): r.pop(rid,None)
        else: data[self.collection_key]=[x for x in r if str(x.get(self.id_key) or x.get('id'))!=rid]
    def normalize_doc(self,data):
        vals=self.values(data)
        for r in vals: self.normalize_record(r)
        if not isinstance(self.recs(data),dict): data[self.collection_key]=sorted(vals,key=lambda r:(r.get('display_order', r.get('order',9999)), r.get(self.id_key) or r.get('id','')))
    def normalize_record(self,r):
        rid=safe_id(r.get(self.id_key) or r.get('id')); r[self.id_key]=rid
        if self.id_key!='id': r.setdefault('id',rid)
        for k in ('tags','variables'): 
            if k in r: r[k]=sorted(set(map(str,r.get(k) or [])))
    def default_record(self,rid): return {self.id_key:safe_id(rid),'id':rid,'name':rid.replace('_',' ').title(),'enabled':False,'tags':[]}
    def validate_record(self,r,ctx=None): return []
    def validate_doc(self,data,ctx=None):
        issues=[]; ids=[]
        for r in self.values(data):
            rid=str(r.get(self.id_key) or r.get('id','')); ids.append(rid)
            if not SAFE_ID_RE.fullmatch(rid): issues.append(Issue(self.name,rid,self.id_key,'unsafe_id','ID violates safe identifier policy'))
            issues += self.validate_record(r,ctx)
        if len(ids)!=len(set(ids)): issues.append(Issue(self.name,'*',self.id_key,'duplicate_id','Duplicate record IDs'))
        return issues
    def preview(self,r): return dump(r)

class AttributeDocumentAdapter(BaseAdapter):
    name='attributes'; live='attributes/attributes.json'; draft='builder/attributes/attributes.json'; collection_key='attributes'; id_key='attribute_id'
    def default_record(self,rid):
        r=super().default_record(rid); r.update(short_name=rid[:3].upper(),description='',default_value=10,minimum_value=1,maximum_value=30,creation_minimum=1,creation_maximum=18,display_group='custom',display_order=999,semantic_role='custom',player_visible=True,npc_visible=True,enabled=False); return r
    def validate_record(self,r,ctx=None):
        e=[]; rid=r.get('attribute_id','')
        try:
            mn,d,ma=int(r.get('minimum_value')),int(r.get('default_value')),int(r.get('maximum_value')); cmn,cma=int(r.get('creation_minimum')),int(r.get('creation_maximum'))
            if not (mn<=d<=ma): e.append(Issue(self.name,rid,'default_value','range','minimum <= default <= maximum required'))
            if not (mn<=cmn<=cma<=ma): e.append(Issue(self.name,rid,'creation_minimum','creation_range','creation range must fit min/max'))
            int(r.get('display_order'))
        except Exception as ex: e.append(Issue(self.name,rid,'numeric','invalid_number',str(ex)))
        if len(r.get('tags',[])) != len(set(r.get('tags',[]))): e.append(Issue(self.name,rid,'tags','duplicate','tags must be unique'))
        return e
class FormulaDocumentAdapter(BaseAdapter):
    name='formulas'; live='formulas/stat_formulas.json'; draft='builder/formulas/stat_formulas.json'; collection_key='formulas'; id_key='formula_id'
    def default_record(self,rid): r=super().default_record(rid); r.update(expression='0',description='',variables=['strength','dexterity','constitution','intelligence','wisdom','charisma','level','equipment_armor','inventory_weight','weapon_base_min','weapon_base_max'],minimum=None,maximum=None,rounding='none'); return r
    def validate_record(self,r,ctx=None):
        e=[]; rid=r.get('formula_id',''); expr=r.get('expression','0'); vars=set(r.get('variables') or [])
        try:
            tree=ast.parse(expr,mode='eval'); names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}-set(FormulaEngine._EXPR_FUNCS)
            if ('variables' in r) and not names.issubset(vars): e.append(Issue(self.name,rid,'variables','undeclared_variable','expression variables not declared: '+','.join(sorted(names-vars))))
            FormulaEngine().evaluate_expression(rid,expr,{v:1 for v in vars})
        except Exception as ex: e.append(Issue(self.name,rid,'expression','invalid_expression',str(ex)))
        if r.get('rounding','none') not in ROUNDINGS: e.append(Issue(self.name,rid,'rounding','invalid','unsupported rounding'))
        if r.get('minimum') is not None and r.get('maximum') is not None and float(r['minimum'])>float(r['maximum']): e.append(Issue(self.name,rid,'minimum','range','minimum exceeds maximum'))
        return e
class StatDefinitionDocumentAdapter(BaseAdapter):
    name='statdefs'; live='formulas/derived_stats.json'; draft='builder/formulas/derived_stats.json'; collection_key='derived_stats'; id_key='stat_id'
    def default_record(self,rid): r=super().default_record(rid); r.update(short_name=rid[:12].upper(),description='',formula_id='',minimum_value=0,maximum_value=100000,rounding='floor',display_format='number',display_group='custom',display_order=999,semantic_role='custom',player_visible=True); return r
    def validate_record(self,r,ctx=None):
        e=[]; rid=r.get('stat_id','')
        if r.get('rounding','floor') not in ROUNDINGS: e.append(Issue(self.name,rid,'rounding','invalid','unsupported rounding'))
        if r.get('display_format','number') not in {'number','percent','rating','text','custom'}: e.append(Issue(self.name,rid,'display_format','invalid','unsupported display format'))
        try:
            if float(r.get('minimum_value',0))>float(r.get('maximum_value',0)): e.append(Issue(self.name,rid,'minimum_value','range','minimum exceeds maximum'))
            int(r.get('display_order',0))
        except Exception as ex: e.append(Issue(self.name,rid,'numeric','invalid_number',str(ex)))
        if ctx and r.get('formula_id') and r.get('formula_id') not in ctx.get('formula_ids',set()): e.append(Issue(self.name,rid,'formula_id','missing_reference','formula does not exist'))
        return e
class ResistanceDocumentAdapter(StatDefinitionDocumentAdapter):
    name='resistances'; collection_key='resistance_types'; id_key='id'
    def recs(self,data):
        self.values(data); return data[self.collection_key]
    def values(self,data):
        val=data.setdefault(self.collection_key,[])
        if val and isinstance(val[0],str): data[self.collection_key]=[{'id':x,'name':x.title(),'unit':'percentage','minimum_value':0,'maximum_value':100,'display_order':i,'enabled':True,'player_visible':True} for i,x in enumerate(val)]
        return data[self.collection_key]
    def default_record(self,rid): return {'id':safe_id(rid),'name':rid.title(),'description':'','unit':'percentage','minimum_value':0,'maximum_value':100,'display_order':999,'enabled':False,'player_visible':True,'tags':[]}
    def validate_record(self,r,ctx=None):
        e=[]; rid=r.get('id','')
        if r.get('unit') not in {'percentage','rating','flat','custom'}: e.append(Issue(self.name,rid,'unit','invalid','invalid unit'))
        try:
            if float(r.get('minimum_value',0))>float(r.get('maximum_value',0)): e.append(Issue(self.name,rid,'minimum_value','range','minimum exceeds maximum'))
            int(r.get('display_order',0))
        except Exception as ex: e.append(Issue(self.name,rid,'numeric','invalid_number',str(ex)))
        return e

    def normalize_doc(self,data):
        self.values(data)
        super().normalize_doc(data)
class EncumbranceDocumentAdapter(BaseAdapter):
    name='encumbrance'; live='formulas/derived_stats.json'; draft='builder/formulas/derived_stats.json'; collection_key='encumbrance_thresholds'; id_key='id'; map_collection=True
    def values(self,data):
        m=data.setdefault(self.collection_key,{})
        if isinstance(m,dict): return [{'id':k,'name':k.title(),'threshold_percent':v,'display_order':i,'penalties':{}} for i,(k,v) in enumerate(sorted(m.items(), key=lambda kv:kv[1]))]
        return m
    def normalize_doc(self,data): data[self.collection_key]={r['id']:r.get('threshold_percent',r.get('percent',0)) for r in sorted(self.values(data),key=lambda r:(r.get('threshold_percent',0),r['id']))}
    def find(self,data,rid): return next((r for r in self.values(data) if r['id']==rid),None)
    def put(self,data,rec):
        vals=[r for r in self.values(data) if r['id']!=rec['id']]; vals.append(rec); data[self.collection_key]=vals
    def remove(self,data,rid): data[self.collection_key]=[r for r in self.values(data) if r['id']!=rid]
    def default_record(self,rid): return {'id':safe_id(rid),'name':rid.title(),'threshold_percent':0,'display_order':999,'description':'','penalties':{}}
    def validate_doc(self,data,ctx=None):
        e=super().validate_doc(data,ctx); vals=self.values(data); 
        if not any(r['id']=='unburdened' and float(r.get('threshold_percent',0))==0 for r in vals): e.append(Issue(self.name,'unburdened','threshold_percent','baseline_required','baseline unburdened at 0 required'))
        if any(float(r.get('threshold_percent',0))<0 for r in vals): e.append(Issue(self.name,'*','threshold_percent','negative','thresholds must be nonnegative'))
        return e
class PostureDocumentAdapter(BaseAdapter):
    name='postures'; live='combat/postures.json'; draft='builder/combat/postures.json'; collection_key='postures'; id_key='posture_id'
    fields={'attack_accuracy_modifier','defense_evasion_modifier','critical_modifier','damage_taken_modifier'}; required={'standing','dead'}
    def default_record(self,rid): r=super().default_record(rid); r.update(description='',attack_accuracy_modifier=0,defense_evasion_modifier=0,critical_modifier=0,damage_taken_modifier=0,attack_allowed=False,cast_allowed=False,movement_allowed=False,automatic_hit_against=False,wake_on_damage=False); return r
class RangeRulesDocumentAdapter(BaseAdapter):
    name='range_rules'; live='combat/range_rules.json'; draft='builder/combat/range_rules.json'; collection_key='range_rules'; id_key='id'; map_collection=True
    allowed={'melee_reach_default':int,'ranged_minimum_range':int,'ranged_maximum_range':int,'spell_range':int,'distance_penalty_formula_id':str,'out_of_range_behavior':str,'point_blank_behavior':str,'point_blank_penalty':int,'line_of_sight_required':bool}
    def default_document(self): return {'range_rules':{'melee_reach_default':1,'ranged_minimum_range':2,'ranged_maximum_range':8,'spell_range':6,'distance_penalty_formula_id':'','out_of_range_behavior':'miss_with_reason','point_blank_behavior':'allowed_with_penalty','point_blank_penalty':0,'line_of_sight_required':True}}
    def normalize_doc(self,data):
        return None
    def validate_doc(self,data,ctx=None):
        rr=data.get('range_rules',{}); e=[]
        for k in rr:
            if k not in self.allowed: e.append(Issue(self.name,'range_rules',k,'unknown_field','unknown range field'))
        if rr.get('ranged_minimum_range',0)>rr.get('ranged_maximum_range',0): e.append(Issue(self.name,'range_rules','ranged_minimum_range','range','minimum exceeds maximum'))
        if rr.get('distance_penalty_formula_id') and ctx and rr.get('distance_penalty_formula_id') not in ctx.get('formula_ids',set()): e.append(Issue(self.name,'range_rules','distance_penalty_formula_id','missing_reference','formula missing'))
        return e
class CombatMessageDocumentAdapter(BaseAdapter):
    name='combat_messages'; live='combat/combat_messages.json'; draft='builder/combat/combat_messages.json'; collection_key='messages'; id_key='message_id'
    placeholders={'attacker','defender','damage','result','weapon','attack'}; condition_fields={'result','attack_type','damage_type','critical'}
    def default_record(self,rid): r=super().default_record(rid); r.update(attacker='{attacker} attacks {defender}.',defender='{attacker} attacks you.',observer='{attacker} attacks {defender}.',conditions={},tags=[]); return r
    def validate_record(self,r,ctx=None):
        e=[]; rid=r.get('message_id','')
        for f in ('attacker','defender','observer'):
            s=str(r.get(f,''));
            if '<' in s or '>' in s: e.append(Issue(self.name,rid,f,'unsafe_markup','HTML markup is not allowed'))
            for p in re.findall(r'{([^}]+)}',s):
                if p not in self.placeholders: e.append(Issue(self.name,rid,f,'unsafe_placeholder',f'unsupported placeholder {p}'))
        for c in (r.get('conditions') or {}):
            if c not in self.condition_fields: e.append(Issue(self.name,rid,'conditions','unknown_condition',c))
        return e
ADAPTERS=[AttributeDocumentAdapter,FormulaDocumentAdapter,StatDefinitionDocumentAdapter,ResistanceDocumentAdapter,EncumbranceDocumentAdapter,PostureDocumentAdapter,RangeRulesDocumentAdapter,CombatMessageDocumentAdapter]

class StatCombatPublishValidator:
    def __init__(self,root:Path): self.root=Path(root); self.adapters=[c(self.root) for c in ADAPTERS]
    def load_all(self): return {a.name:a.load_draft() for a in self.adapters}
    def graph(self,docs):
        formulas={r['formula_id'] for r in FormulaDocumentAdapter(self.root).values(docs['formulas'])}; stats={r['stat_id'] for r in StatDefinitionDocumentAdapter(self.root).values(docs['statdefs'])}; attrs={r['attribute_id'] for r in AttributeDocumentAdapter(self.root).values(docs['attributes'])}
        refs=[]
        for r in StatDefinitionDocumentAdapter(self.root).values(docs['statdefs']): refs.append(('statdef',r['stat_id'],'formula',r.get('formula_id','')))
        rr=docs['range_rules'].get('range_rules',{}); refs.append(('range_rules','range_rules','formula',rr.get('distance_penalty_formula_id','')))
        return {'formula_ids':formulas,'stat_ids':stats,'attribute_ids':attrs,'references':refs}
    def validate(self):
        docs=self.load_all(); ctx=self.graph(docs); errors=[]; warnings=[]
        for a in self.adapters: errors += a.validate_doc(docs[a.name], ctx)
        return {'ok':not errors,'errors':errors,'warnings':warnings,'graph':ctx,'docs':docs}
    def deletion_errors(self, kind, rid):
        v=self.validate(); errs=[]
        target='formula' if kind in {'formula','formulas'} else kind
        for src,sid,tgt,tid in v['graph']['references']:
            if tgt==target and tid==rid: errs.append(Issue(kind,rid,'delete','referenced',f'referenced by {src}:{sid}'))
        return errs

class StatCombatPublisher:
    targets=[('attributes','builder/attributes/attributes.json','attributes/attributes.json'),('formulas','builder/formulas/stat_formulas.json','formulas/stat_formulas.json'),('statdefs','builder/formulas/derived_stats.json','formulas/derived_stats.json'),('postures','builder/combat/postures.json','combat/postures.json'),('range_rules','builder/combat/range_rules.json','combat/range_rules.json'),('combat_messages','builder/combat/combat_messages.json','combat/combat_messages.json')]
    def __init__(self,root:Path,event_bus=None,runtime=None): self.root=Path(root); self.event_bus=event_bus; self.runtime=runtime
    def hashes(self): return {n:{'draft':sha_bytes((self.root/d).read_bytes()) if (self.root/d).exists() else None,'published':sha_bytes((self.root/t).read_bytes()) if (self.root/t).exists() else None} for n,d,t in self.targets}
    def preview(self):
        val=StatCombatPublishValidator(self.root).validate(); h=self.hashes(); changed=[n for n,x in h.items() if x['draft'] and x['draft']!=x['published']]
        return val,h,changed
    def publish(self, actor='unknown', inject=None):
        val,h,changed=self.preview()
        if not val['ok']: return {'ok':False,'published':False,'errors':val['errors'],'message':'validation failed'}
        pid='stats-'+uuid.uuid4().hex[:12]; stage=self.root/'builder'/'staging'/pid; stage.mkdir(parents=True,exist_ok=True)
        manifest={'publish_id':pid,'world_id':self.root.name,'actor_id':actor,'timestamp':now(),'files':[],'old_hashes':h,'validation_errors':[],'warnings':[w.__dict__ for w in val['warnings']],'activation_plan':'hot_reload_or_restart_required'}
        backups=[]; completed=[]
        try:
            for n,d,t in self.targets:
                src=self.root/d
                if not src.exists(): continue
                data=json.loads(src.read_text(encoding='utf-8') or '{}'); staged=stage/t; staged.parent.mkdir(parents=True,exist_ok=True); sh=write_atomic(staged,data); json.loads(staged.read_text())
                manifest['files'].append({'document':n,'draft_path':d,'target_path':t,'staged_hash':sh,'new_hash':sh})
            if inject=='before_replacement': raise RuntimeError('injected before replacement')
            for i,f in enumerate(manifest['files']):
                dp=self.root/f['target_path']; dp.parent.mkdir(parents=True,exist_ok=True); old=dp.read_bytes() if dp.exists() else None; backups.append((dp,old)); data=(stage/f['target_path']).read_bytes();
                fd,tmp=tempfile.mkstemp(dir=str(dp.parent),prefix=dp.name+'.',suffix='.tmp')
                with os.fdopen(fd,'wb') as out: out.write(data); out.flush(); os.fsync(out.fileno())
                os.replace(tmp,dp); completed.append(dp)
                if inject==f'after_replacement_{i}' or inject=='after_replacement': raise RuntimeError('injected after replacement')
            if inject=='before_reload': raise RuntimeError('injected before reload')
        except Exception as ex:
            rb=[]
            for dp,old in reversed(backups):
                if old is None:
                    if dp.exists(): dp.unlink(); rb.append((str(dp),None))
                else:
                    dp.write_bytes(old); rb.append((str(dp),sha_bytes(old)))
            manifest.update(status='failed',error=str(ex),rollback=rb); self._audit(manifest)
            return {'ok':False,'published':False,'rollback':rb,'manifest':manifest,'message':str(ex)}
        active=False; restart=False; reload_error=None
        try:
            if inject=='during_reload': raise RuntimeError('injected during reload')
            rt=self.runtime
            if rt and getattr(rt,'attribute_service',None): rt.attribute_service.reload_definitions(); active=True
            if rt and getattr(rt,'combat_stat_service',None): rt.combat_stat_service.reload_definitions(); active=True
            if rt and getattr(rt,'combat_runtime',None): rt.combat_runtime.refresh_content(); active=True
            if active and self.event_bus: self.event_bus.publish('stat_definitions_reloaded', {'publish_id':pid,'world_id':self.root.name,'changed_document_ids':changed}, source_system='builder')
            if not active: restart=True
        except Exception as ex:
            reload_error=str(ex); restart=True; active=False
        manifest.update(status='published',published=True,active_runtime=active,restart_required=restart,reload_error=reload_error); self._audit(manifest); shutil.rmtree(stage,ignore_errors=True)
        return {'ok':True,'published':True,'active_runtime':active,'restart_required':restart,'manifest':manifest,'changed':changed}
    def _audit(self,m):
        p=self.root/'builder'/'audit'/'stats_publish_manifests.jsonl'; p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('a',encoding='utf-8') as f: f.write(json.dumps(m,sort_keys=True,default=str)+'\n')
