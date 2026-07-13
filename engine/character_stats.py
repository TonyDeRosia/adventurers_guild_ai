"""Canonical Phase 13C3-A character attributes, modifiers, and combat stats."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import json, math, sqlite3, hashlib
from engine.mud_state_store import utc_now
from engine.formulas import FormulaEngine

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

@dataclass(frozen=True)
class WeaponStatProjection:
    instance_id:str; template_id:str; name:str; minimum_damage:int; maximum_damage:int; damage_type:str; attack_speed:int; reach:int; range:int; hands:int; proficiency_id:str; modifiers:list[StatModifier]=field(default_factory=list)
@dataclass(frozen=True)
class EquipmentStatSnapshot:
    character_id:str; slots:dict[str,str]; equipped_instances:dict[str,dict[str,Any]]; resolved_templates:dict[str,dict[str,Any]]; weapon_instance:WeaponStatProjection|None; armor_instances:list[dict[str,Any]]; modifier_sources:list[dict[str,Any]]; total_weight:float; version:str

class CharacterAttributeService:
    migration_version='phase13c3a_v1'
    def __init__(self, state_store=None, world_id='shattered_realms', world_root:Path|None=None, event_bus=None):
        self.state_store=state_store; self.world_id=world_id; self.world_root=world_root or _world_root(world_id); self.event_bus=event_bus; self.reload_definitions()
    def reload_definitions(self):
        raw=_load_json(self.world_root/'attributes/attributes.json', {'attributes':[]}); self.definitions={a['attribute_id']:a for a in raw.get('attributes',raw if isinstance(raw,list) else []) if a.get('enabled',True)}
    def _runtime(self, context=None): return (context or {}).get('runtime') or getattr(self,'runtime',None)
    def _template_maps(self):
        maps=[]
        for folder,key in [('weapon_templates','weapon_templates'),('armor_templates','armor_templates'),('item_templates','item_templates')]:
            raw=_load_json(self.world_root/folder/f'{folder}.json', {})
            recs=(raw if isinstance(raw,list) else raw.get(key, []))
            maps.append({str(r.get('id') or r.get('template_id')):r for r in recs if isinstance(r,dict)})
        return maps
    def _item_modifiers(self,item,source_type='equipment'):
        out=[]; tmpl=item.get('template') or {}; plugin=item.get('plugin_data') or {}; decls=list(tmpl.get('modifiers') or [])+list(plugin.get('modifiers') or [])+list(plugin.get('enchantments',{}).get('modifiers',[]) if isinstance(plugin.get('enchantments'),dict) else [])
        for d in decls:
            target=d.get('target_stat') or d.get('target_key'); dom=d.get('target_domain','')
            if dom=='attribute': target=target
            elif dom=='derived_stat': target=f'derived.{target}'
            elif dom=='resistance': target=f'resistance.{target}'
            op=d.get('operation','add');
            if target and op in OPS:
                out.append(StatModifier(str(d.get('modifier_id') or d.get('id') or f"{item.get('instance_id')}:{target}"), source_type, str(item.get('instance_id') or item.get('template_id')), str(target), op, float(d.get('value',0)), int(d.get('priority',100)), str(d.get('stacking_group','')), str(d.get('stacking_rule') or d.get('stacking_policy','stack')), condition=d.get('condition') or d.get('condition_data') or {}, tags=list(d.get('tags') or []), metadata={'item_name':item.get('name'), 'slot':item.get('equipped_slot')}) )
        return out
    def equipment_snapshot(self, character, context=None):
        cid=_cid(character); rt=self._runtime(context); weapon_map, armor_map, item_map=self._template_maps(); items=[]
        if rt and hasattr(rt,'find_equipped_items'): items=list(rt.find_equipped_items(cid))
        elif self.state_store:
            with self.state_store.connect() as con:
                con.row_factory=sqlite3.Row

                cols={r[1] for r in con.execute('PRAGMA table_info(item_instances)')}
                if {'owner_type','owner_id','destroyed_at'}.issubset(cols):
                    rows=con.execute("SELECT * FROM item_instances WHERE owner_type='equipment' AND owner_id=? AND destroyed_at IS NULL",(cid,)).fetchall()
                    for r in rows: items.append(dict(r))
        slots={}; inst={}; templates={}; armor=[]; total=0.0; weapon=None; mods=[]
        for item in items:
            tid=str(item.get('template_id') or ''); tmpl=dict(item.get('template') or item_map.get(tid) or weapon_map.get(tid) or armor_map.get(tid) or {'id':tid,'name':tid})
            item={**item,'template':tmpl,'name':item.get('name') or tmpl.get('name') or tid}; slot=str(item.get('equipped_slot') or '')
            qty=int(item.get('stack_count') or item.get('quantity') or 1); weight=float(tmpl.get('weight',0) or 0)*qty; total+=weight
            slots[slot]=item.get('instance_id',tid); inst[item.get('instance_id',tid)]=item; templates[tid]=tmpl
            imods=self._item_modifiers(item); mods.extend(imods)
            if tid in weapon_map or tmpl.get('item_type')=='weapon' or tmpl.get('type')=='weapon':
                base=int(tmpl.get('base_damage') or tmpl.get('damage',0) or 0); weapon=WeaponStatProjection(str(item.get('instance_id') or tid),tid,str(tmpl.get('name') or tid),int(tmpl.get('min_damage',base)),int(tmpl.get('max_damage',base)),str((tmpl.get('damage_types') or ['physical'])[0]),int(tmpl.get('attack_speed',1) or 1),int(tmpl.get('reach',1) or 1),int(tmpl.get('range',0) or 0),len(tmpl.get('occupies_slots') or [slot]),str(tmpl.get('proficiency_id') or tmpl.get('weapon_class') or ''),imods)
            if tid in armor_map or tmpl.get('armor_value') is not None:
                armor.append({**item,'armor_value':int(tmpl.get('armor_value',0) or 0),'evasion_penalty':int(tmpl.get('evasion_penalty',0) or 0),'speed_penalty':int(tmpl.get('speed_penalty',0) or 0),'resistances':tmpl.get('resistances') or {}})
        version=hashlib.sha1(json.dumps({'slots':slots,'mods':[asdict(m) for m in mods],'weight':total},sort_keys=True,default=str).encode()).hexdigest()
        return EquipmentStatSnapshot(cid,slots,inst,templates,weapon,armor,mods,total,version)
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
                con.execute('CREATE TABLE IF NOT EXISTS character_attribute_migrations(world_id TEXT, character_id TEXT, migration_version TEXT, changed_attributes TEXT, migrated_at TEXT, PRIMARY KEY(world_id,character_id,migration_version))'); con.execute('INSERT OR REPLACE INTO character_attribute_migrations VALUES(?,?,?,?,?)',(self.world_id,cid,self.migration_version,json.dumps(changed),utc_now()))
        return changed
    def _rows(self,cid):
        if not self.state_store: return {}
        self.state_store.initialize();
        with self.state_store.connect() as con: return {r['attribute_id']:dict(r) for r in con.execute('SELECT * FROM character_attributes WHERE character_id=?',(cid,))}
    def collect_modifiers(self, character, context=None):
        mods=[]; context=context or {}; cid=_cid(character)
        eq=self.equipment_snapshot(character,context); mods.extend(eq.modifier_sources)
        rt=self._runtime(context)
        if rt:
            try:
                from engine.phase5e import RuntimeEffectService
                for cm in RuntimeEffectService(rt).get_effect_modifiers(cid):
                    target=cm.target_key if cm.target_domain=='attribute' else f"derived.{cm.target_key}" if cm.target_domain in {'derived_stat','movement','carry'} else f"resistance.{cm.target_key}" if cm.target_domain=='resistance' else f"resource.{cm.target_key}"
                    op={'percentage_increase':'percentage_add','percentage_reduction':'percentage_multiply','minimum':'set_minimum','maximum':'set_maximum'}.get(cm.operation,cm.operation)
                    if op in OPS: mods.append(StatModifier(cm.modifier_id,'affect',cm.source_instance_id,target,op,float(cm.value),cm.priority,cm.stacking_group,{'highest_only':'highest','lowest_only':'lowest'}.get(cm.stacking_policy,cm.stacking_policy),expires_at=cm.expires_at,condition=cm.condition_data,tags=[],metadata=cm.metadata))
            except Exception: pass
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
    def __init__(self, attribute_service:CharacterAttributeService): self.attribute_service=attribute_service; self.world_root=attribute_service.world_root; self.formula_engine=FormulaEngine(); self.reload_definitions()
    def reload_definitions(self):
        self.stat_defs={d['stat_id']:d for d in _load_json(self.world_root/'formulas/derived_stats.json',{}).get('derived_stats',[])}; self.formulas={f['formula_id']:f['expression'] for f in _load_json(self.world_root/'formulas/stat_formulas.json',{}).get('formulas',[])}; self.thresholds=_load_json(self.world_root/'formulas/derived_stats.json',{}).get('encumbrance_thresholds',{})
    def equipment_snapshot(self,ch,context=None): return self.attribute_service.equipment_snapshot(ch,context)
    def _weight(self,ch,context=None):
        eq=self.equipment_snapshot(ch,context); total=eq.total_weight; rt=(context or {}).get('runtime') or getattr(self.attribute_service,'runtime',None); cid=_cid(ch)
        seen=set()
        def item_weight(item, depth=0):
            iid=str(item.get('instance_id') or item.get('unique_id') or item.get('template_id'));
            if iid in seen or depth>16: return 0.0
            seen.add(iid); tmpl=item.get('template') or {}; qty=int(item.get('stack_count') or item.get('quantity') or 1); w=float(tmpl.get('weight', item.get('weight',0)) or 0)*qty
            reduction=float((tmpl.get('container') or {}).get('weight_reduction_percent',0) or 0)/100
            for child in (item.get('contents') or []): w += item_weight(child, depth+1)*(1-reduction)
            return w
        items=[]
        if rt and hasattr(rt,'find_inventory_items'): items=list(rt.find_inventory_items(cid))
        elif self.attribute_service.state_store:
            with self.attribute_service.state_store.connect() as con:
                con.row_factory=sqlite3.Row

                cols={r[1] for r in con.execute('PRAGMA table_info(item_instances)')}
                if {'owner_type','owner_id','destroyed_at'}.issubset(cols):
                    for r in con.execute("SELECT * FROM item_instances WHERE owner_type IN ('character','actor') AND owner_id=? AND destroyed_at IS NULL",(cid,)): items.append(dict(r))
        for i in items: total+=item_weight(i)
        if not items and not total:
            total=sum(float((i if isinstance(i,dict) else {}).get('weight', (i if isinstance(i,dict) else {}).get('state',{}).get('weight',0)) or 0)*int((i if isinstance(i,dict) else {}).get('quantity',1) or 1) for i in (getattr(ch,'inventory',[]) or []))
        return total
    def _variables(self,ch,attrs,extra=None,context=None):
        eq=self.equipment_snapshot(ch,context); armor=sum(int(i.get('armor_value',0) or 0) for i in eq.armor_instances); weapon=eq.weapon_instance
        v={k:a.final_value for k,a in attrs.items()}; v.update(level=int(getattr(ch,'level',1) or 1), equipment_armor=armor, inventory_weight=self._weight(ch,context), weapon_base_min=(weapon.minimum_damage if weapon else 0), weapon_base_max=(weapon.maximum_damage if weapon else 0)); v.update(extra or {}); return v
    def get_stat(self,ch,stat_id,context=None): return self.get_breakdown(ch,stat_id,context)['value']
    def get_breakdown(self,ch,stat_id,context=None):
        attrs=self.attribute_service.get_all_attributes(ch,context); vars=self._variables(ch,attrs,context=context); expr=self.formulas.get(self.stat_defs.get(stat_id,{}).get('formula_id',stat_id),'0')
        val=self.formula_engine.evaluate_expression(self.stat_defs.get(stat_id,{}).get('formula_id',stat_id), expr, vars).final_value; mods=[m for m in self.attribute_service.collect_modifiers(ch,context) if m.target_stat in {stat_id,'derived.'+stat_id}]; val,src=self.attribute_service._apply(val,mods); d=self.stat_defs.get(stat_id,{}); val=max(float(d.get('minimum_value',0)), min(float(d.get('maximum_value',100000)), val)); rounded=int(math.floor(val)) if d.get('rounding','floor')=='floor' else round(val)
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
        eq=self.equipment_snapshot(ch,context); mn=self.get_stat(ch,'weapon_damage_min',context); mx=self.get_stat(ch,'weapon_damage_max',context); return None if not eq.weapon_instance or mx<=0 else DamageProfile(mn,mx,eq.weapon_instance.damage_type,eq.weapon_instance.attack_speed,eq.weapon_instance.reach,eq.weapon_instance.range,eq.weapon_instance.name)
    def _source_version(self,ch,context=None):
        eq=self.equipment_snapshot(ch,context); mods=self.attribute_service.collect_modifiers(ch,context); payload={'migration':self.attribute_service.migration_version,'equipment':eq.version,'mods':[asdict(m) for m in mods],'formulas':self.formulas,'stat_defs':self.stat_defs}
        return hashlib.sha1(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()

    def synchronize_resources(self, ch, resources):
        events=[]
        mapping={'health':('hp','hp_current','max_health'),'mana':('mana','mana_current','max_mana'),'stamina':('stamina','stamina_current','max_stamina')}
        cid=_cid(ch)
        for key,(attr,current_col,max_key) in mapping.items():
            cur=int(getattr(ch,attr,getattr(ch,current_col,0)) or 0); maxv=int(resources[max_key]); new=min(cur,maxv)
            old_max=getattr(ch,'max_'+key,None)
            if old_max is not None and int(old_max)!=maxv: events.append(('resource_maximum_changed',{'character_id':cid,'resource':key,'old_max':int(old_max),'new_max':maxv}))
            setattr(ch,'max_'+key,maxv); setattr(ch,attr,new)
            if new!=cur: events.append(('resource_current_clamped',{'character_id':cid,'resource':key,'old_current':cur,'new_current':new,'maximum':maxv}))
        if self.attribute_service.state_store and events:
            try:
                with self.attribute_service.state_store.connect() as con:
                    cols={r[1] for r in con.execute('PRAGMA table_info(characters)')}
                    sets=[]; vals=[]
                    for col,val in [('hp_current',getattr(ch,'hp',0)),('mana_current',getattr(ch,'mana',0)),('stamina_current',getattr(ch,'stamina',0))]:
                        if col in cols: sets.append(f'{col}=?'); vals.append(val)
                    if sets: vals.append(cid); con.execute(f"UPDATE characters SET {','.join(sets)} WHERE id=?", vals)
            except Exception: pass
        bus=getattr(self.attribute_service,'event_bus',None)
        for name,payload in events:
            if bus and hasattr(bus,'publish'):
                try: bus.publish(name,payload)
                except Exception: pass
        return events
    def get_combat_snapshot(self,ch,context=None):
        attrs=self.attribute_service.get_all_attributes(ch,context); stat=lambda s:self.get_stat(ch,s,context); enc=self.get_encumbrance(ch,context)
        resources={'max_health':stat('max_health'),'max_mana':stat('max_mana'),'max_stamina':stat('max_stamina'),'health':min(int(getattr(ch,'hp',getattr(ch,'hp_current',0)) or 0),stat('max_health')),'mana':min(int(getattr(ch,'mana',0) or 0),stat('max_mana')),'stamina':min(int(getattr(ch,'stamina',0) or 0),stat('max_stamina'))}
        self.synchronize_resources(ch, resources)
        return CombatStatSnapshot(_cid(ch),attrs,resources,{'armor':stat('armor'),'evasion':stat('evasion'),'critical_avoidance':stat('critical_avoidance')},{'accuracy':stat('accuracy'),'hit_bonus':stat('hit_bonus'),'attack_power':stat('attack_power'),'damage_bonus':stat('damage_bonus'),'spell_power':stat('spell_power'),'healing_power':stat('healing_power')},{'physical_save':stat('physical_save'),'mental_save':stat('mental_save'),'magic_save':stat('magic_save')},self.get_resistances(ch,context),{'critical_melee':stat('critical_melee'),'critical_spell':stat('critical_spell'),'critical_heal':stat('critical_heal'),'critical_avoidance':stat('critical_avoidance')},self.get_damage_profile(ch,context),DamageProfile(stat('unarmed_damage_min'),stat('unarmed_damage_max'),'physical',stat('attack_speed'),1,0,'unarmed'),{'initiative':stat('initiative'),'attack_speed':stat('attack_speed'),'casting_speed':stat('casting_speed'),'recovery_speed':stat('recovery_speed'),'movement_speed':stat('movement_speed')},enc,context or {},self._source_version(ch,context))
