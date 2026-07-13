"""Canonical Phase 13C3-A character attributes, modifiers, and combat stats."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import ast, json, math, sqlite3
from engine.mud_state_store import utc_now

OPS={"add","subtract","multiply","percentage_add","percentage_multiply","set_minimum","set_maximum","override"}
STACK={"stack","highest","lowest","replace","unique_by_source","unique_by_group"}
@dataclass(frozen=True)
class StatModifier:
    modifier_id:str; source_type:str; source_id:str; target_stat:str; operation:str; value:float; priority:int=100; stacking_group:str=""; stacking_rule:str="stack"; duration:Any=None; expires_at:str|None=None; condition:dict[str,Any]=field(default_factory=dict); tags:list[str]=field(default_factory=list); metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class CalculatedAttribute:
    attribute_id:str; name:str; base_value:int; permanent_modifier:int; equipment_modifier:float; affect_modifier:float; temporary_modifier:float; situational_modifier:float; final_value:int; minimum_value:int; maximum_value:int; sources:list[dict[str,Any]]=field(default_factory=list)
@dataclass(frozen=True)
class DamageProfile:
    minimum_damage:int; maximum_damage:int; damage_type:str; attack_speed:int; reach:int; range:int; source:str
@dataclass(frozen=True)
class CombatStatSnapshot:
    character_id:str; attributes:dict[str,CalculatedAttribute]; resources:dict[str,int]; defense:dict[str,Any]; offense:dict[str,Any]; saves:dict[str,Any]; resistances:dict[str,Any]; critical:dict[str,Any]; weapon_profile:DamageProfile|None; unarmed_profile:DamageProfile; speed:dict[str,Any]; carrying:dict[str,Any]; context:dict[str,Any]; source_version:str

def _load_json(p:Path, default):
    try: return json.loads(p.read_text())
    except Exception: return default

def _cid(ch:Any)->str: return str(getattr(ch,'id',getattr(ch,'character_id','player_1')))
def _world_root(world_id='shattered_realms')->Path: return Path('worlds')/(world_id or 'shattered_realms')
def _allowed_metadata(d): return d if isinstance(d,dict) else {}

class SafeFormula:
    ALLOWED=(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Constant,ast.Name,ast.Load,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.FloorDiv,ast.Mod,ast.Pow,ast.USub,ast.IfExp,ast.Compare,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.BoolOp,ast.And,ast.Or)
    def eval(self, expr:str, variables:dict[str,Any])->float:
        tree=ast.parse(expr or '0', mode='eval')
        for n in ast.walk(tree):
            if not isinstance(n,self.ALLOWED): raise ValueError('unsafe formula node')
            if isinstance(n,ast.Name) and n.id not in variables: variables[n.id]=0
        return float(eval(compile(tree,'<formula>','eval'), {'__builtins__':{}}, variables))

class CharacterAttributeService:
    migration_version='phase13c3a_v1'
    def __init__(self, state_store=None, world_id='shattered_realms', world_root:Path|None=None, event_bus=None):
        self.state_store=state_store; self.world_id=world_id; self.world_root=world_root or _world_root(world_id); self.event_bus=event_bus; self.reload_definitions()
    def reload_definitions(self):
        raw=_load_json(self.world_root/'attributes/attributes.json', {'attributes':[]}); self.definitions={a['attribute_id']:a for a in raw.get('attributes',raw if isinstance(raw,list) else []) if a.get('enabled',True)}
    def migrate_character(self, character):
        cid=_cid(character); con=getattr(self.state_store,'connect',lambda:None)() if self.state_store else None
        legacy=getattr(character,'attributes',None) or (getattr(character,'actor_data',{}) or {}).get('attributes',{})
        changed=[]
        if con:
            with con:
                for aid,d in self.definitions.items():
                    row=con.execute('SELECT * FROM character_attributes WHERE character_id=? AND attribute_id=?',(cid,aid)).fetchone()
                    if row: continue
                    val=legacy.get(aid, d.get('default_value',10)) if isinstance(legacy,dict) else d.get('default_value',10)
                    try: val=int(val)
                    except Exception: val=int(d.get('default_value',10))
                    val=max(int(d.get('minimum_value',1)), min(int(d.get('maximum_value',30)), val))
                    con.execute('INSERT OR IGNORE INTO character_attributes VALUES(?,?,?,?,?,?,?,?)',(cid,aid,val,0,utc_now(),utc_now(),'migration:'+self.migration_version,'{}')); changed.append(aid)
                con.execute('INSERT OR REPLACE INTO campaign_meta(key,value) VALUES(?,?)',('character_attributes_migration_version',self.migration_version))
        return changed
    def _rows(self,cid):
        if not self.state_store: return {}
        self.state_store.initialize();
        with self.state_store.connect() as con: return {r['attribute_id']:dict(r) for r in con.execute('SELECT * FROM character_attributes WHERE character_id=?',(cid,))}
    def collect_modifiers(self, character, context=None):
        mods=[]; context=context or {}; inv=getattr(character,'inventory',[]) or []
        for item in inv:
            st=item if isinstance(item,dict) else {}; equipped=st.get('equipped_slot') or st.get('equipped') or st.get('slot') if st.get('equipped',False) else st.get('equipped_slot')
            if not equipped: continue
            for m in st.get('modifiers',[]) or st.get('state',{}).get('modifiers',[]):
                target=m.get('target_key') or m.get('target_stat'); op=m.get('operation','add');
                if target and op in OPS: mods.append(StatModifier(m.get('id',f"item_{target}"),'equipment',st.get('item_id',st.get('id','item')),target,op,float(m.get('value',0)),int(m.get('priority',100)),m.get('stacking_group',''),m.get('stacking_rule',m.get('stacking_policy','stack'))))
        for m in (context.get('modifiers') or []): mods.append(m if isinstance(m,StatModifier) else StatModifier(**m))
        return mods
    def _stack(self, mods):
        out=[]; groups={}
        for m in sorted(mods,key=lambda x:(x.priority,x.modifier_id)):
            if m.stacking_rule=='stack': out.append(m)
            else: groups.setdefault((m.stacking_group or m.target_stat, m.source_id if m.stacking_rule=='unique_by_source' else ''),[]).append(m)
        for ms in groups.values():
            rule=ms[-1].stacking_rule; out.append(max(ms,key=lambda m:m.value) if rule=='highest' else min(ms,key=lambda m:m.value) if rule=='lowest' else ms[-1])
        return sorted(out,key=lambda x:(x.priority,x.modifier_id))
    def _apply(self, base, mods):
        v=base; lo=None; hi=None; src=[]
        for m in self._stack(mods):
            b=v; op=m.operation
            if op=='add': v+=m.value
            elif op=='subtract': v-=m.value
            elif op=='multiply': v*=m.value
            elif op=='percentage_add': v*=1+m.value/100
            elif op=='percentage_multiply': v*=m.value/100
            elif op=='set_minimum': lo=m.value if lo is None else max(lo,m.value)
            elif op=='set_maximum': hi=m.value if hi is None else min(hi,m.value)
            elif op=='override': v=m.value
            src.append({**asdict(m),'before':b,'after':v})
        if lo is not None: v=max(v,lo)
        if hi is not None: v=min(v,hi)
        return v,src
    def get_all_attributes(self, character, context=None):
        self.migrate_character(character); rows=self._rows(_cid(character)); mods=self.collect_modifiers(character,context); out={}
        for aid,d in sorted(self.definitions.items(), key=lambda kv:kv[1].get('display_order',99)):
            row=rows.get(aid,{}); base=int(row.get('base_value',d.get('default_value',10))); perm=int(row.get('permanent_modifier',0)); rel=[m for m in mods if m.target_stat in {aid, 'attribute.'+aid}]; v,src=self._apply(base+perm, rel); final=max(int(d.get('minimum_value',1)), min(int(d.get('maximum_value',30)), int(math.floor(v))))
            sums={k:sum((m.value if m.operation=='add' else -m.value if m.operation=='subtract' else 0) for m in rel if m.source_type==k) for k in ['equipment','affect','temporary','situational']}
            out[aid]=CalculatedAttribute(aid,d.get('name',aid.title()),base,perm,sums['equipment'],sums['affect'],sums['temporary'],sums['situational'],final,int(d.get('minimum_value',1)),int(d.get('maximum_value',30)),src)
        return out
    def get_attribute(self, character, attribute_id, context=None): return self.get_all_attributes(character,context).get(attribute_id)
    def get_breakdown(self, character, attribute_id, context=None): return self.get_attribute(character,attribute_id,context)

class CombatStatService:
    def __init__(self, attribute_service:CharacterAttributeService): self.attribute_service=attribute_service; self.world_root=attribute_service.world_root; self.reload_definitions()
    def reload_definitions(self):
        self.stat_defs={d['stat_id']:d for d in _load_json(self.world_root/'formulas/derived_stats.json',{}).get('derived_stats',[])}; self.formulas={f['formula_id']:f['expression'] for f in _load_json(self.world_root/'formulas/stat_formulas.json',{}).get('formulas',[])}; self.thresholds=_load_json(self.world_root/'formulas/derived_stats.json',{}).get('encumbrance_thresholds',{})
    def _weight(self,ch): return sum(float((i if isinstance(i,dict) else {}).get('weight', (i if isinstance(i,dict) else {}).get('state',{}).get('weight',0)) or 0)*int((i if isinstance(i,dict) else {}).get('quantity',1) or 1) for i in (getattr(ch,'inventory',[]) or []))
    def _variables(self,ch,attrs,extra=None):
        v={k:a.final_value for k,a in attrs.items()}; v.update(level=int(getattr(ch,'level',1) or 1), equipment_armor=0, inventory_weight=self._weight(ch), weapon_base_min=0, weapon_base_max=0); v.update(extra or {}); return v
    def get_stat(self,ch,stat_id,context=None): return self.get_breakdown(ch,stat_id,context)['value']
    def get_breakdown(self,ch,stat_id,context=None):
        attrs=self.attribute_service.get_all_attributes(ch,context); vars=self._variables(ch,attrs); expr=self.formulas.get(self.stat_defs.get(stat_id,{}).get('formula_id',stat_id),'0')
        val=SafeFormula().eval(expr, vars); mods=[m for m in self.attribute_service.collect_modifiers(ch,context) if m.target_stat in {stat_id,'derived.'+stat_id}]; val,src=self.attribute_service._apply(val,mods); d=self.stat_defs.get(stat_id,{}); val=max(float(d.get('minimum_value',0)), min(float(d.get('maximum_value',100000)), val)); rounded=int(math.floor(val)) if d.get('rounding','floor')=='floor' else round(val)
        return {'stat_id':stat_id,'value':rounded,'formula':expr,'inputs':vars,'modifiers':src,'rounding':d.get('rounding','floor'),'clamping':[d.get('minimum_value',0),d.get('maximum_value',100000)]}
    def get_resistances(self,ch,context=None):
        mods=self.attribute_service.collect_modifiers(ch,context); out={t:0 for t in _load_json(self.world_root/'formulas/derived_stats.json',{}).get('resistance_types',[])}
        for t in list(out): out[t]=int(self.attribute_service._apply(0,[m for m in mods if m.target_stat in {f'resistance.{t}',t+'_resistance'}])[0])
        return out
    def get_encumbrance(self,ch,context=None):
        weight=self.get_stat(ch,'current_carry_weight',context); cap=max(1,self.get_stat(ch,'carry_capacity',context)); pct=int(weight/cap*100); state='unburdened'
        for name,thr in sorted(self.thresholds.items(), key=lambda kv:kv[1]):
            if pct>=thr: state=name
        return {'current_carry_weight':weight,'carry_capacity':cap,'encumbrance_percent':pct,'encumbrance_state':state}
    def get_damage_profile(self,ch,context=None):
        mn=self.get_stat(ch,'weapon_damage_min',context); mx=self.get_stat(ch,'weapon_damage_max',context); return None if mx<=0 else DamageProfile(mn,mx,'physical',self.get_stat(ch,'attack_speed',context),1,0,'weapon')
    def get_combat_snapshot(self,ch,context=None):
        attrs=self.attribute_service.get_all_attributes(ch,context); stat=lambda s:self.get_stat(ch,s,context); enc=self.get_encumbrance(ch,context)
        resources={'max_health':stat('max_health'),'max_mana':stat('max_mana'),'max_stamina':stat('max_stamina'),'health':min(int(getattr(ch,'hp',getattr(ch,'hp_current',0)) or 0),stat('max_health')),'mana':min(int(getattr(ch,'mana',0) or 0),stat('max_mana')),'stamina':min(int(getattr(ch,'stamina',0) or 0),stat('max_stamina'))}
        return CombatStatSnapshot(_cid(ch),attrs,resources,{'armor':stat('armor'),'evasion':stat('evasion'),'critical_avoidance':stat('critical_avoidance')},{'accuracy':stat('accuracy'),'hit_bonus':stat('hit_bonus'),'attack_power':stat('attack_power'),'damage_bonus':stat('damage_bonus'),'spell_power':stat('spell_power'),'healing_power':stat('healing_power')},{'physical_save':stat('physical_save'),'mental_save':stat('mental_save'),'magic_save':stat('magic_save')},self.get_resistances(ch,context),{'critical_melee':stat('critical_melee'),'critical_spell':stat('critical_spell'),'critical_heal':stat('critical_heal'),'critical_avoidance':stat('critical_avoidance')},self.get_damage_profile(ch,context),DamageProfile(stat('unarmed_damage_min'),stat('unarmed_damage_max'),'physical',stat('attack_speed'),1,0,'unarmed'),{'initiative':stat('initiative'),'attack_speed':stat('attack_speed'),'casting_speed':stat('casting_speed'),'recovery_speed':stat('recovery_speed'),'movement_speed':stat('movement_speed')},enc,context or {},self.attribute_service.migration_version)
