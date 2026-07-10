"""Phase 5E canonical modifier/effect/stat resolution services.

Small deterministic implementation layer that bridges SQLite item instances and
runtime effect instances into the existing Actor/Formula/Score architecture.
It intentionally does not implement combat execution.
"""
from __future__ import annotations

import ast, json, math, sqlite3, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_DOMAINS={"attribute","resource_base","resource_maximum","resource_regeneration","derived_stat","resistance","movement","carry","status","custom"}
SOURCE_TYPES={"equipment","effect","profile","species","race","class","profession","title","achievement","quest","environment","weather","terrain","injury","disease","consumable","builder","plugin","temporary","future_ability"}
OPERATIONS=("add","subtract","multiply","divide","percentage_increase","percentage_reduction","minimum","maximum","override","clamp")
STACKING_POLICIES={"unique","replace","refresh","stack","highest_only","lowest_only","independent"}

@dataclass(frozen=True)
class CanonicalModifier:
    modifier_id: str
    source_type: str
    source_id: str
    source_instance_id: str
    source_template_id: str
    owner_actor_id: str
    target_key: str
    target_domain: str
    operation: str
    value: float|int|list[Any]
    priority: int=100
    stacking_group: str=""
    stacking_policy: str="stack"
    condition_id: str=""
    condition_data: dict[str,Any]=field(default_factory=dict)
    active: bool=True
    visible: bool=True
    starts_at: str=""
    expires_at: str=""
    metadata: dict[str,Any]=field(default_factory=dict)

    def to_dict(self)->dict[str,Any]: return asdict(self)

@dataclass
class Resolution:
    key: str
    base_value: float
    final_value: float
    contributions: list[dict[str,Any]]
    formula_id: str=""
    trace: list[dict[str,Any]]=field(default_factory=list)


def safe_id(s:str)->bool:
    return bool(s) and all(c.isalnum() or c in "_-" for c in s)


def validate_modifier_decl(d:dict[str,Any])->list[str]:
    errors=[]
    if not safe_id(str(d.get("id") or d.get("modifier_id") or "")): errors.append("modifier id must be safe")
    if d.get("target_domain") not in TARGET_DOMAINS: errors.append("invalid target_domain")
    if not d.get("target_key"): errors.append("target_key required")
    if d.get("operation") not in OPERATIONS: errors.append("invalid operation")
    if d.get("stacking_policy","stack") not in STACKING_POLICIES: errors.append("invalid stacking_policy")
    try: int(d.get("priority",100))
    except Exception: errors.append("priority must be integer")
    if d.get("operation")!="clamp":
        try: float(d.get("value"))
        except Exception: errors.append("value must be numeric")
    return errors

class SafeExpression:
    funcs={"min":min,"max":max,"floor":math.floor,"ceil":math.ceil,"round":round,"abs":abs,"clamp":lambda x,a,b:max(a,min(x,b))}
    nodes=(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Constant,ast.Name,ast.Load,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.USub,ast.UAdd,ast.Call)
    def __init__(self, expression:str):
        self.expression=expression or "base"
        self.tree=ast.parse(self.expression, mode="eval")
        self.inputs=[]; self._validate(self.tree)
    def _validate(self,node):
        if not isinstance(node,self.nodes): raise ValueError(f"unsupported expression node: {type(node).__name__}")
        if isinstance(node,ast.Call):
            if not isinstance(node.func,ast.Name) or node.func.id not in self.funcs: raise ValueError("unsupported function")
        if isinstance(node,ast.Name) and node.id not in self.funcs and node.id not in self.inputs: self.inputs.append(node.id)
        for child in ast.iter_child_nodes(node): self._validate(child)
    def eval(self, variables:dict[str,Any])->float:
        def ev(n):
            if isinstance(n,ast.Expression): return ev(n.body)
            if isinstance(n,ast.Constant):
                if not isinstance(n.value,(int,float)): raise ValueError("only numeric constants allowed")
                return n.value
            if isinstance(n,ast.Name):
                if n.id in variables: return variables[n.id]
                raise ValueError(f"missing input {n.id}")
            if isinstance(n,ast.UnaryOp): return -ev(n.operand) if isinstance(n.op,ast.USub) else +ev(n.operand)
            if isinstance(n,ast.BinOp):
                a,b=ev(n.left),ev(n.right)
                if isinstance(n.op,ast.Add): v=a+b
                elif isinstance(n.op,ast.Sub): v=a-b
                elif isinstance(n.op,ast.Mult): v=a*b
                elif isinstance(n.op,ast.Div):
                    if b==0: raise ZeroDivisionError("division by zero")
                    v=a/b
                else: raise ValueError("bad operator")
                if not math.isfinite(float(v)): raise ValueError("non-finite result")
                return v
            if isinstance(n,ast.Call):
                v=self.funcs[n.func.id](*[ev(a) for a in n.args])
                if not math.isfinite(float(v)): raise ValueError("non-finite result")
                return v
            raise ValueError("unsupported expression")
        return float(ev(self.tree))

BASELINE_FORMULAS={
 "attribute_effective_v1":{"name":"Attribute Effective v1","expression":"base + modifier_total"},
 "resource_maximum_health_v1":{"name":"Health Maximum v1","expression":"base + constitution * 5 + modifier_total","minimum":1},
 "resource_maximum_mana_v1":{"name":"Mana Maximum v1","expression":"base + intelligence * 3 + wisdom * 2 + modifier_total","minimum":0},
 "resource_maximum_stamina_v1":{"name":"Stamina Maximum v1","expression":"base + constitution * 3 + strength * 2 + modifier_total","minimum":0},
 "attack_rating_v1":{"name":"Attack Rating v1","expression":"strength + dexterity + modifier_total"},
 "attack_power_v1":{"name":"Attack Power v1","expression":"strength * 2 + modifier_total"},
 "accuracy_v1":{"name":"Accuracy v1","expression":"dexterity + modifier_total"},
 "armor_rating_v1":{"name":"Armor Rating v1","expression":"base + modifier_total"},
 "evasion_rating_v1":{"name":"Evasion Rating v1","expression":"dexterity + modifier_total"},
 "spell_power_v1":{"name":"Spell Power v1","expression":"intelligence * 2 + modifier_total"},
 "healing_power_v1":{"name":"Healing Power v1","expression":"wisdom * 2 + modifier_total"},
 "critical_chance_v1":{"name":"Critical Chance v1","expression":"clamp(5 + dexterity / 5 + modifier_total, 0, 100)"},
 "critical_damage_v1":{"name":"Critical Damage v1","expression":"150 + modifier_total"},
 "initiative_v1":{"name":"Initiative v1","expression":"dexterity + wisdom + modifier_total"},
 "carry_capacity_v1":{"name":"Carry Capacity v1","expression":"strength * 10 + modifier_total"},
 "encumbrance_v1":{"name":"Encumbrance v1","expression":"carry_weight - carry_capacity"},
 "physical_resistance_v1":{"name":"Physical Resistance v1","expression":"base + modifier_total","minimum":0,"maximum":100},
 "magic_resistance_v1":{"name":"Magic Resistance v1","expression":"base + modifier_total","minimum":0,"maximum":100},
}

def ensure_effect_schema(db_path:Path)->None:
    with sqlite3.connect(db_path) as con:
        con.executescript("""
CREATE TABLE IF NOT EXISTS actor_effect_instances(effect_instance_id TEXT PRIMARY KEY,world_id TEXT,effect_template_id TEXT,target_actor_type TEXT,target_actor_id TEXT,source_actor_type TEXT,source_actor_id TEXT,source_ability_id TEXT,source_item_instance_id TEXT,category TEXT,disposition TEXT,visibility TEXT,stack_group TEXT,stack_count INTEGER,maximum_stacks INTEGER,started_world_time INTEGER,expires_world_time INTEGER,remaining_duration INTEGER,next_tick_world_time INTEGER,active INTEGER,suspended INTEGER,removal_reason TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_actor_effect_target ON actor_effect_instances(target_actor_type,target_actor_id,active);
CREATE INDEX IF NOT EXISTS idx_actor_effect_source ON actor_effect_instances(source_actor_type,source_actor_id);
CREATE INDEX IF NOT EXISTS idx_actor_effect_template ON actor_effect_instances(effect_template_id);
CREATE INDEX IF NOT EXISTS idx_actor_effect_expire ON actor_effect_instances(world_id,expires_world_time,active);
""")

class EquipmentModifierBridge:
    def __init__(self,runtime:Any): self.runtime=runtime
    def get_equipped_item_instances(self,actor_id:str): return list(self.runtime.find_equipped_items(actor_id))
    def resolve_item_instance_modifiers(self,item_instance_id:str):
        item=self.runtime.find_item(item_instance_id); return [] if not item or item.get('owner_type')!='equipment' else self._mods(item)
    def get_equipment_modifiers(self,actor_id:str):
        mods=[]
        for item in sorted(self.get_equipped_item_instances(actor_id), key=lambda i:(slot_sort(i.get('equipped_slot')), i.get('instance_id',''))): mods.extend(self._mods(item))
        return mods
    def _mods(self,item):
        t=item.get('template') or {}; decls=list(t.get('modifiers') or [])
        overrides=((item.get('plugin_data') or {}).get('modifier_overrides') or {})
        out=[]
        for d in decls:
            d={**d, **(overrides.get(d.get('id')) or {})}
            if validate_modifier_decl(d): continue
            out.append(CanonicalModifier(str(d.get('id')), 'equipment', item['instance_id'], item['instance_id'], item['template_id'], item['owner_id'], str(d['target_key']), str(d['target_domain']), str(d['operation']), d.get('value'), int(d.get('priority',100)), str(d.get('stacking_group') or f"equipment:{item['equipped_slot']}:{d['target_key']}"), str(d.get('stacking_policy','stack')), visible=bool(d.get('visible',True)), metadata={'slot':item.get('equipped_slot'),'item_name':item.get('name')}))
        return out

def slot_sort(slot):
    order={s:i for i,s in enumerate(['head','face','neck','shoulders','back','chest','arms','wrists','hands','finger_left','finger_right','waist','legs','feet','primary_weapon','secondary_weapon','shield','quiver','accessory_1','accessory_2','main_hand','off_hand','both_hands'])}
    return order.get(slot or '',999)

class RuntimeEffectService:
    def __init__(self,runtime:Any): self.runtime=runtime; ensure_effect_schema(runtime.state_store.db_path)
    def templates(self): return {e['id']:e for e in getattr(self.runtime.active_world,'effect_templates',[]) or []}
    def apply_effect(self,target_actor_id,effect_template_id,source_actor_id=None,source_ability_id=None,source_item_instance_id=None,duration=None,stacks=1,metadata=None):
        t=self.templates()[effect_template_id]; now=int(getattr(self.runtime,'world_time',0) or 0); maxs=int(t.get('maximum_stacks',1) or 1); policy=t.get('stacking_policy','unique'); group=t.get('stack_group') or effect_template_id
        existing=[e for e in self.get_active_effects(target_actor_id, viewer='admin') if e['stack_group']==group and policy!='independent']
        if existing and policy in {'unique','refresh','replace','stack','highest_only','lowest_only'}:
            e=existing[0]
            if policy=='stack': self.set_effect_stacks(e['effect_instance_id'], min(maxs, int(e['stack_count'])+int(stacks or 1))); return self.get_effect(e['effect_instance_id'])
            self.refresh_effect(e['effect_instance_id'], duration); return self.get_effect(e['effect_instance_id'])
        eid=f"effect_{uuid.uuid4().hex}"; dur=duration if duration is not None else t.get('default_duration'); exp=(now+int(dur)) if t.get('duration_policy')=='timed' and dur is not None else None; ts=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.execute("INSERT INTO actor_effect_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,self.runtime.active_world_id or '',effect_template_id,'character',target_actor_id,'character',source_actor_id or '',source_ability_id or '',source_item_instance_id or '',t.get('category','buff'),t.get('disposition','neutral'),t.get('visibility','public'),group,min(maxs,int(stacks or 1)),maxs,now,exp,dur,None,1,0,'',ts,ts,json.dumps(metadata or {})))
        return self.get_effect(eid)
    def get_effect(self,eid):
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute('SELECT * FROM actor_effect_instances WHERE effect_instance_id=?',(eid,)).fetchone(); return dict(r) if r else None
    def get_active_effects(self,target_actor_id,viewer=None):
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.row_factory=sqlite3.Row; rows=[dict(r) for r in con.execute("SELECT * FROM actor_effect_instances WHERE target_actor_id=? AND active=1 AND suspended=0 ORDER BY started_world_time,effect_instance_id",(target_actor_id,))]
        if viewer not in {'admin','builder'}: rows=[r for r in rows if r.get('visibility') not in {'admin','builder','hidden'}]
        return rows
    def refresh_effect(self,eid,duration=None):
        e=self.get_effect(eid); t=self.templates().get(e['effect_template_id'],{}) if e else {}; dur=duration if duration is not None else t.get('default_duration'); now=int(getattr(self.runtime,'world_time',0) or 0); exp=now+int(dur) if dur is not None and t.get('duration_policy')=='timed' else e.get('expires_world_time')
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.execute('UPDATE actor_effect_instances SET remaining_duration=?,expires_world_time=?,updated_at=? WHERE effect_instance_id=?',(dur,exp,datetime.now(timezone.utc).isoformat(),eid))
    def set_effect_stacks(self,eid,stacks):
        e=self.get_effect(eid); stacks=max(1,min(int(e.get('maximum_stacks') or 1),int(stacks)))
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.execute('UPDATE actor_effect_instances SET stack_count=?,updated_at=? WHERE effect_instance_id=?',(stacks,datetime.now(timezone.utc).isoformat(),eid))
    def remove_effect(self,eid,reason=None):
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.execute('UPDATE actor_effect_instances SET active=0,removal_reason=?,updated_at=? WHERE effect_instance_id=?',(reason or 'removed',datetime.now(timezone.utc).isoformat(),eid))
    def get_effect_modifiers(self,target_actor_id):
        out=[]; templates=self.templates()
        for e in self.get_active_effects(target_actor_id, viewer='admin'):
            t=templates.get(e['effect_template_id'],{})
            decls=[]
            for k,dom in [('attribute_modifiers','attribute'),('resource_modifiers','resource_maximum'),('derived_stat_modifiers','derived_stat'),('resistance_modifiers','resistance')]:
                for d in t.get(k,[]) or []: decls.append({**d,'target_domain':d.get('target_domain',dom)})
            for d in decls:
                if validate_modifier_decl(d): continue
                out.append(CanonicalModifier(str(d.get('id')), 'effect', e['effect_instance_id'], e['effect_instance_id'], e['effect_template_id'], e['target_actor_id'], str(d['target_key']), str(d['target_domain']), str(d['operation']), float(d.get('value',0))*int(e.get('stack_count') or 1), int(d.get('priority',100)), str(d.get('stacking_group') or e.get('stack_group') or d['id']), str(d.get('stacking_policy',t.get('stacking_policy','stack'))), active=bool(e.get('active')), visible=t.get('visibility','public') not in {'hidden'}, starts_at=str(e.get('started_world_time') or ''), expires_at=str(e.get('expires_world_time') or ''), metadata={'effect_name':t.get('name'),'stacks':e.get('stack_count')}))
        return out
    def expire_effects(self,world_id,world_time):
        with sqlite3.connect(self.runtime.state_store.db_path) as con: con.execute("UPDATE actor_effect_instances SET active=0,removal_reason='expired',updated_at=? WHERE world_id=? AND active=1 AND expires_world_time IS NOT NULL AND expires_world_time<=?",(datetime.now(timezone.utc).isoformat(),world_id,int(world_time)))

def apply_modifiers(base:float, modifiers:list[CanonicalModifier]):
    trace=[]; active=[]; inactive=[]
    grouped={}
    for m in modifiers: grouped.setdefault((m.target_domain,m.target_key,m.stacking_group or m.modifier_id),[]).append(m)
    for mods in grouped.values():
        mods=sorted(mods,key=lambda m:(m.priority,m.modifier_id,m.source_instance_id))
        pol=mods[-1].stacking_policy
        winners=mods if pol in {'stack','independent','refresh'} else [max(mods,key=lambda m:(m.value,m.priority,m.modifier_id))] if pol=='highest_only' else [min(mods,key=lambda m:(m.value,m.priority,m.modifier_id))] if pol=='lowest_only' else [mods[-1]]
        active += winners; inactive += [m for m in mods if m not in winners]
    value=base
    for ops in [('add','subtract'),('multiply','divide'),('percentage_increase','percentage_reduction'),('minimum','maximum'),('override',),('clamp',)]:
        mods=sorted([m for m in active if m.operation in ops], key=lambda m:(m.priority,m.modifier_id,m.source_instance_id))
        if ops==('override',) and mods: mods=[mods[-1]]
        for m in mods:
            before=value; v=m.value
            if m.operation=='add': value+=float(v)
            elif m.operation=='subtract': value-=float(v)
            elif m.operation=='multiply': value*=float(v)
            elif m.operation=='divide':
                if float(v)==0: raise ZeroDivisionError('modifier division by zero')
                value/=float(v)
            elif m.operation=='percentage_increase': value*=1+float(v)/100
            elif m.operation=='percentage_reduction': value*=1-float(v)/100
            elif m.operation=='minimum': value=min(value,float(v))
            elif m.operation=='maximum': value=max(value,float(v))
            elif m.operation=='override': value=float(v)
            elif m.operation=='clamp': value=max(float(v[0]),min(value,float(v[1])))
            if not math.isfinite(value): raise ValueError('non-finite modifier result')
            trace.append({'modifier_id':m.modifier_id,'operation':m.operation,'before':before,'after':value,'source_instance_id':m.source_instance_id})
    for m in inactive: trace.append({'modifier_id':m.modifier_id,'active':False,'reason':'lost stacking/priority resolution','source_instance_id':m.source_instance_id})
    return value, [m.to_dict() for m in active], trace

def actor_modifiers(runtime, actor_id):
    mods=EquipmentModifierBridge(runtime).get_equipment_modifiers(actor_id)
    try: mods += RuntimeEffectService(runtime).get_effect_modifiers(actor_id)
    except Exception: pass
    return sorted(mods,key=lambda m:(m.target_domain,m.target_key,m.priority,m.modifier_id,m.source_instance_id))

def resolve_actor_value(runtime, actor, key, domain='derived_stat', base=0, formula_id=None):
    mods=[m for m in actor_modifiers(runtime, actor.actor_id) if m.target_domain==domain and m.target_key==key]
    mod_total, contrib, trace=apply_modifiers(0.0,mods)
    attrs={k:float(v or 0) for k,v in getattr(actor,'attributes',{}).items()}; vars={**attrs,'base':float(base or 0),'modifier_total':mod_total,'carry_weight':0,'carry_capacity':0}
    fid=formula_id or {'attack_power':'attack_power_v1','attack_rating':'attack_rating_v1','armor_rating':'armor_rating_v1','armor':'armor_rating_v1','critical_chance':'critical_chance_v1','critical_damage':'critical_damage_v1','initiative':'initiative_v1','spell_power':'spell_power_v1','healing_power':'healing_power_v1','carry_capacity':'carry_capacity_v1'}.get(key)
    if fid and fid in BASELINE_FORMULAS:
        f=BASELINE_FORMULAS[fid]; val=SafeExpression(f['expression']).eval(vars); val=max(float(f.get('minimum',-1e18)),min(val,float(f.get('maximum',1e18))))
    else: val=float(base or 0)+mod_total
    return Resolution(key,float(base or 0),val,contrib,fid or '',trace)
