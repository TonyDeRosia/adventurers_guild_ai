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
class PrimaryStatValue:
    stat_id:str; semantic_role:str; label:str; short_label:str; base_value:int; permanent_component:float; equipment_component:float; effect_component:float; template_component:float; instance_component:float; situational_component:float; final_value:int; minimum:int; maximum:int; active:bool=True; inactive_reason:str=""; formula_or_aggregation:str="base+components"; source_versions:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class CombatStatValue:
    stat_id:str; label:str; value:Any; unit:str; display_format:str; display_group:str; display_order:int; active:bool; inactive_reason:str; minimum:Any; maximum:Any; base_component:float; attribute_component:float; equipment_component:float; effect_component:float; template_component:float; instance_component:float; situational_component:float; formula_id:str; formula_inputs:dict[str,Any]=field(default_factory=dict); source_versions:dict[str,Any]=field(default_factory=dict)
    def __str__(self): return str(self.value)
    def __int__(self):
        try: return int(self.value)
        except Exception: return 0
    def __float__(self):
        try: return float(self.value)
        except Exception: return 0.0
    def _coerce(self, other):
        try: return float(other.value)
        except Exception:
            try: return float(other)
            except Exception: return 0.0
    def __lt__(self, other): return float(self) < self._coerce(other)
    def __le__(self, other): return float(self) <= self._coerce(other)
    def __gt__(self, other): return float(self) > self._coerce(other)
    def __ge__(self, other): return float(self) >= self._coerce(other)
    def __eq__(self, other): return self.value == (getattr(other,'value',other))
@dataclass(frozen=True)
class ResistanceStatValue:
    resistance_id:str; label:str; value:float; unit:str; minimum:float; maximum:float; display_order:int; active:bool; inactive_reason:str; covered_damage_types:list[str]; base_component:float; equipment_component:float; effect_component:float; template_component:float; instance_component:float; formula_id:str; source_versions:dict[str,Any]=field(default_factory=dict)
    def __str__(self): return str(self.value)
    def __int__(self): return int(self.value)
    def __eq__(self, other): return self.value == (getattr(other,'value',other))
    def __lt__(self, other): return float(self.value) < float(getattr(other,'value',other))
    def __le__(self, other): return float(self.value) <= float(getattr(other,'value',other))
    def __gt__(self, other): return float(self.value) > float(getattr(other,'value',other))
    def __ge__(self, other): return float(self.value) >= float(getattr(other,'value',other))
@dataclass(frozen=True)
class NaturalWeaponProfile:
    profile_id:str; name:str; attack_kind:str; minimum_damage:int; maximum_damage:int; damage_type:str; attack_speed:int; reach:int; minimum_range:int; maximum_range:int; scaling_role:str; scaling_coefficient:float; can_critical:bool; critical_multiplier_policy:str; armor_applies:bool; resistance_applies:bool; source_template_id:str=""; source_body_profile_id:str=""; source_versions:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class DamageProfile:
    minimum_damage:int; maximum_damage:int; damage_type:str; attack_speed:int; reach:int; range:int; source:str
@dataclass(frozen=True)
class ActorStatInput:
    actor_id:str; actor_type:str; world_id:str; template_id:str|None; spawn_definition_id:str|None; instance_id:str|None; character_id:str|None; level:int; primary_attribute_bases:dict[str,int]; permanent_modifiers:list[StatModifier]=field(default_factory=list); equipment_snapshot:Any=None; effect_snapshot:list[Any]=field(default_factory=list); template_modifiers:list[StatModifier]=field(default_factory=list); instance_modifiers:list[StatModifier]=field(default_factory=list); situational_modifiers:list[StatModifier]=field(default_factory=list); resistance_profile:dict[str,Any]=field(default_factory=dict); body_profile:dict[str,Any]=field(default_factory=dict); combat_profile:dict[str,Any]=field(default_factory=dict); natural_weapon_profiles:list[NaturalWeaponProfile]=field(default_factory=list); resource_projection:dict[str,Any]=field(default_factory=dict); source_versions:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class CombatStatSnapshot:
    schema_version:str; snapshot_id:str; actor_id:str; actor_type:str; world_id:str; template_id:str|None; instance_id:str|None; level:int; primary_stats:dict[str,PrimaryStatValue]; offense:dict[str,CombatStatValue]; defense:dict[str,CombatStatValue]; criticals:dict[str,CombatStatValue]; saves:dict[str,CombatStatValue]; resistances:dict[str,ResistanceStatValue]; speed:dict[str,CombatStatValue]; weapon_profile:DamageProfile|None; unarmed_profile:DamageProfile; natural_weapon_profiles:list[NaturalWeaponProfile]; resource_maxima:dict[str,CombatStatValue]; carrying:dict[str,CombatStatValue]; encumbrance:dict[str,CombatStatValue]; mechanics:dict[str,Any]; source_versions:dict[str,Any]; generated_at:str
    @property
    def character_id(self): return self.actor_id
    @property
    def attributes(self): return self.primary_stats
    @property
    def resources(self): return {k:v.value for k,v in self.resource_maxima.items()}
    @property
    def critical(self): return self.criticals
    @property
    def source_version(self): return self.source_versions.get('snapshot','')

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
            row=rows.get(aid,{})
            legacy=getattr(character,'attributes',None) or (getattr(character,'actor_data',{}) or {}).get('attributes',{})
            legacy_val=legacy.get(aid) if isinstance(legacy,dict) else None
            base=int(row.get('base_value', legacy_val if legacy_val is not None else d.get('default_value',10))); perm=int(row.get('permanent_modifier',0)); rel=[m for m in mods if m.target_stat in {aid, 'attribute.'+aid}]; v,src=self._apply(base+perm, rel); final=max(int(d.get('minimum_value',1)), min(int(d.get('maximum_value',30)), int(math.floor(v))))
            sums={k:sum((m.value if m.operation=='add' else -m.value if m.operation=='subtract' else 0) for m in rel if m.source_type==k) for k in ['equipment','affect','temporary','situational']}
            out[aid]=CalculatedAttribute(aid,d.get('name',aid.title()),base,perm,sums['equipment'],sums['affect'],sums['temporary'],sums['situational'],final,int(d.get('minimum_value',1)),int(d.get('maximum_value',30)),src)
        return out
    def get_attribute(self, character, attribute_id, context=None): return self.get_all_attributes(character,context).get(attribute_id)
    def get_breakdown(self, character, attribute_id, context=None): return self.get_attribute(character,attribute_id,context)

class PlayerStatInputAdapter:
    def __init__(self, service): self.service=service
    def build(self, actor, context=None):
        attrs=self.service.attribute_service.get_all_attributes(actor,context)
        return ActorStatInput(_cid(actor),'player',self.service.attribute_service.world_id,None,None,None,_cid(actor),int(getattr(actor,'level',1) or 1),{k:v.base_value for k,v in attrs.items()},equipment_snapshot=self.service.equipment_snapshot(actor,context),resistance_profile=getattr(actor,'resistance_profile',None) or getattr(actor,'resistances',None) or {},resource_projection={'health':getattr(actor,'hp',getattr(actor,'hp_current',0))},source_versions={'adapter':'player'})
class EntityTemplateStatInputAdapter:
    def __init__(self, service): self.service=service
    def build(self, template, context=None):
        t=template if isinstance(template,dict) else getattr(template,'template',{}) or getattr(template,'definition',{}) or {}
        tid=str(t.get('id') or t.get('template_id') or getattr(template,'template_id',''))
        role=str(t.get('combat_role') or t.get('role') or 'balanced'); level=int(t.get('level') or getattr(template,'level',1) or 1)
        bases=dict(t.get('attributes') or t.get('primary_attributes') or {}) or self.service.project_legacy_template_attributes(tid,level,role,t)
        nws=self.service.resolve_natural_weapons_from_data(t, {'template':tid})
        return ActorStatInput(tid or 'template','npc',self.service.attribute_service.world_id,tid,None,None,None,level,{k:int(v) for k,v in bases.items()},resistance_profile=t.get('resistances') or t.get('resistance_profile') or {},body_profile=t.get('body_profile') or {},combat_profile=t.get('combat_profile') or {},natural_weapon_profiles=nws,source_versions={'adapter':'entity_template','migration':self.service.legacy_template_hash(t)})
class EntityInstanceStatInputAdapter:
    def __init__(self, service): self.service=service
    def build(self, actor, context=None):
        t=getattr(actor,'template',None) or getattr(actor,'definition',None) or {}
        base=EntityTemplateStatInputAdapter(self.service).build(t or {},context)
        overrides=getattr(actor,'stat_overrides',None) or getattr(actor,'instance_modifiers',None) or {}
        attrs={**base.primary_attribute_bases, **{k:int(v) for k,v in (overrides.get('attributes',{}) if isinstance(overrides,dict) else {}).items()}}
        return ActorStatInput(_cid(actor),getattr(actor,'actor_type','mob'),self.service.attribute_service.world_id,base.template_id,getattr(actor,'spawn_definition_id',None),getattr(actor,'instance_id',None),None,int(getattr(actor,'level',base.level) or base.level),attrs,resistance_profile={**base.resistance_profile, **(getattr(actor,'resistances',{}) or {})},body_profile=base.body_profile,combat_profile=base.combat_profile,natural_weapon_profiles=self.service.resolve_natural_weapons_from_data(getattr(actor,'combat_profile',{}) or t or {}, {'template':base.template_id}) or base.natural_weapon_profiles,source_versions={**base.source_versions,'adapter':'entity_instance'})
class ActorRuntimeStatInputAdapter(EntityInstanceStatInputAdapter): pass

class CombatStatService:
    schema_version='phase13c3-b3.combat-snapshot.v1'
    inactive_speed_reason='Combat rounds do not currently use initiative ordering or speed-based timing.'
    semantic_roles={'physical_power':'strength','agility':'dexterity','endurance':'constitution','intellect':'intelligence','willpower':'wisdom','presence':'charisma'}
    active_secondary={'accuracy','hit_bonus','attack_power','damage_bonus','spell_power','healing_power','armor','evasion','critical_avoidance','critical_melee','critical_spell','critical_heal','critical_damage','physical_save','mental_save','magic_save','max_health','max_mana','max_stamina','carry_capacity','current_carry_weight','encumbrance_percent'}
    def __init__(self, attribute_service:CharacterAttributeService): self.attribute_service=attribute_service; self.world_root=attribute_service.world_root; self.formula_engine=FormulaEngine(); self.reload_definitions()
    def reload_definitions(self):
        raw=_load_json(self.world_root/'formulas/derived_stats.json',{}); self.stat_defs={d['stat_id']:d for d in raw.get('derived_stats',[])}; self.formulas={f['formula_id']:f['expression'] for f in _load_json(self.world_root/'formulas/stat_formulas.json',{}).get('formulas',[])}; self.thresholds=raw.get('encumbrance_thresholds',{}); self.resistance_defs={str(r.get('id')):r for r in _load_json(self.world_root/'resistance_profiles/resistance_profiles.json',[])}; self.validate_semantic_roles()
    def validate_semantic_roles(self):
        seen={}
        for aid,d in self.attribute_service.definitions.items():
            role=d.get('semantic_role')
            if role:
                if role in seen and seen[role]!=aid: raise ValueError(f'ambiguous semantic role {role}')
                seen[role]=aid
        missing=[r for r in self.semantic_roles if r not in seen]
        if missing: raise ValueError(f'missing semantic roles: {missing}')
        self.semantic_roles=seen
    def equipment_snapshot(self,ch,context=None): return self.attribute_service.equipment_snapshot(ch,context)
    def build_actor_stat_input(self, actor_or_character, context=None):
        if isinstance(actor_or_character,ActorStatInput): return actor_or_character
        if isinstance(actor_or_character,dict) and ('template_id' in actor_or_character or 'combat_profile' in actor_or_character or 'natural_weapons' in actor_or_character or 'natural_attacks' in actor_or_character or 'combat_role' in actor_or_character): return EntityTemplateStatInputAdapter(self).build(actor_or_character,context)
        if getattr(actor_or_character,'template',None) or getattr(actor_or_character,'actor_type',None) in {'npc','mob','summon','pet','follower','temporary','environment'}: return ActorRuntimeStatInputAdapter(self).build(actor_or_character,context)
        return PlayerStatInputAdapter(self).build(actor_or_character,context)
    def project_legacy_template_attributes(self, tid, level, role, template):
        base=10+min(10,max(0,level//3)); vals={k:base for k in self.attribute_service.definitions}; shifts={'brute':('strength','constitution'),'skirmisher':('dexterity','strength'),'caster':('intelligence','wisdom'),'healer':('wisdom','charisma'),'leader':('charisma','wisdom'),'balanced':('strength','dexterity')}.get(role,('strength','constitution'))
        for i,a in enumerate(shifts): vals[a]=min(30,base+(3-i))
        if template.get('accuracy'): vals['dexterity']=min(30,vals.get('dexterity',base)+int(template.get('accuracy',0))//10)
        return vals
    def legacy_template_hash(self,t): return hashlib.sha1(json.dumps(t,sort_keys=True,default=str).encode()).hexdigest() if isinstance(t,dict) else ''
    def resolve_natural_weapons_from_data(self,data,versions=None):
        raw=data.get('natural_weapons') or data.get('natural_attacks') or data.get('attacks') or [] if isinstance(data,dict) else []
        if isinstance(raw,dict): raw=list(raw.values())
        out=[]
        for i,w in enumerate(raw or []):
            if not isinstance(w,dict): continue
            out.append(NaturalWeaponProfile(str(w.get('id') or f'natural_{i}'),str(w.get('name') or w.get('attack') or 'Natural Attack'),str(w.get('attack_kind') or 'melee'),int(w.get('minimum_damage') or w.get('min_damage') or w.get('damage_min') or 1),int(w.get('maximum_damage') or w.get('max_damage') or w.get('damage_max') or w.get('damage') or 2),str(w.get('damage_type') or 'physical'),int(w.get('attack_speed') or 100),int(w.get('reach') or 1),int(w.get('minimum_range') or 0),int(w.get('maximum_range') or w.get('range') or 0),str(w.get('scaling_role') or 'physical_power'),float(w.get('scaling_coefficient') or 0),bool(w.get('can_critical',True)),str(w.get('critical_multiplier_policy') or 'actor_stat'),bool(w.get('armor_applies',True)),bool(w.get('resistance_applies',True)),str((versions or {}).get('template','')),str((versions or {}).get('body','')),versions or {}))
        return out
    def _weight(self,ch,context=None):
        eq=self.equipment_snapshot(ch,context); total=getattr(eq,'total_weight',0.0); return total+sum(float((i if isinstance(i,dict) else {}).get('weight',0) or 0)*int((i if isinstance(i,dict) else {}).get('quantity',1) or 1) for i in (getattr(ch,'inventory',[]) or []))
    def _variables(self,ch,attrs,extra=None,context=None):
        eq=self.equipment_snapshot(ch,context); armor=sum(int(i.get('armor_value',0) or 0) for i in getattr(eq,'armor_instances',[])); weapon=getattr(eq,'weapon_instance',None)
        v={k:getattr(a,'final_value',a) for k,a in attrs.items()}
        for role,aid in self.semantic_roles.items(): v[role]=v.get(aid,10)
        v.update(level=int(getattr(ch,'level',1) or 1), equipment_armor=armor, inventory_weight=self._weight(ch,context), weapon_base_min=(weapon.minimum_damage if weapon else 0), weapon_base_max=(weapon.maximum_damage if weapon else 0)); v.update(extra or {}); return v
    def get_stat(self,ch,stat_id,context=None): return self.get_breakdown(ch,stat_id,context)['value']
    def get_breakdown(self,ch,stat_id,context=None):
        attrs=self.attribute_service.get_all_attributes(ch,context) if not isinstance(ch,ActorStatInput) else {k:v for k,v in ch.primary_attribute_bases.items()}; vars=self._variables(ch,attrs,context=context); d=self.stat_defs.get(stat_id,{}); fid=d.get('formula_id',stat_id); expr=self.formulas.get(fid,'0')
        val=self.formula_engine.evaluate_expression(fid, expr, vars).final_value; mods=[m for m in self.attribute_service.collect_modifiers(ch,context) if m.target_stat in {stat_id,'derived.'+stat_id}] if not isinstance(ch,ActorStatInput) else []
        val,src=self.attribute_service._apply(val,mods); val=max(float(d.get('minimum_value',0)), min(float(d.get('maximum_value',100000)), val)); rounded=int(math.floor(val)) if d.get('rounding','floor')=='floor' else round(val)
        return {'stat_id':stat_id,'value':rounded,'formula':expr,'formula_id':fid,'inputs':vars,'modifiers':src,'rounding':d.get('rounding','floor'),'clamping':[d.get('minimum_value',0),d.get('maximum_value',100000)]}
    def _combat_value(self,ch,stat_id,context=None, *, value=None, active=None, reason=''):
        d=self.stat_defs.get(stat_id,{}); bd=self.get_breakdown(ch,stat_id,context) if value is None and stat_id in self.stat_defs else {'value':value,'formula_id':'','inputs':{}}
        active = (stat_id in self.active_secondary) if active is None else active
        return CombatStatValue(stat_id,d.get('name',stat_id.replace('_',' ').title()),bd['value'],'multiplier' if stat_id=='critical_damage' else ('lb' if 'weight' in stat_id or 'capacity' in stat_id else ('percent' if stat_id.endswith('percent') else 'rating')),d.get('display_format','number'),d.get('display_group','combat'),int(d.get('display_order',999)),bool(active),'' if active else reason,float(d.get('minimum_value',0)),float(d.get('maximum_value',100000)),float(d.get('base_value',0)),0,0,0,0,0,0,bd.get('formula_id',''),bd.get('inputs',{}),{'snapshot':self._source_version(ch,context)})
    def get_resistances(self,ch,context=None): return {k:v.value for k,v in self.get_resistance_values(ch,context).items()}
    def get_resistance_values(self,ch,context=None):
        mods=self.attribute_service.collect_modifiers(ch,context) if not isinstance(ch,ActorStatInput) else []; profile=getattr(ch,'resistance_profile',None) or getattr(ch,'resistances',None) or {}; out={}
        ids=list(self.resistance_defs) or _load_json(self.world_root/'formulas/derived_stats.json',{}).get('resistance_types',[])
        for i,t in enumerate(ids):
            d=self.resistance_defs.get(t,{}); base=float((profile or {}).get(t,d.get('base',0)) or 0); val=self.attribute_service._apply(base,[m for m in mods if m.target_stat in {f'resistance.{t}',t+'_resistance'}])[0]
            out[t]=ResistanceStatValue(t,d.get('display_name',t.title()),val,str(d.get('unit') or 'percent'),float(d.get('minimum',0)),float(d.get('maximum',100)),i*10+10,True,'',[t],base,0,0,0,0,str(d.get('formula_id','')),{'snapshot':self._source_version(ch,context)})
        return out
    def get_encumbrance(self,ch,context=None):
        weight=self.get_stat(ch,'current_carry_weight',context); cap=max(1,self.get_stat(ch,'carry_capacity',context)); pct=int(weight/cap*100); state='unburdened'
        for name,thr in sorted(self.thresholds.items(), key=lambda kv:kv[1]):
            if pct>=thr: state=name
        return {'current_carry_weight':weight,'carry_capacity':cap,'encumbrance_percent':pct,'encumbrance_state':state}
    def get_damage_profile(self,ch,context=None):
        eq=self.equipment_snapshot(ch,context); mn=self.get_stat(ch,'weapon_damage_min',context); mx=self.get_stat(ch,'weapon_damage_max',context); return None if not getattr(eq,'weapon_instance',None) or mx<=0 else DamageProfile(mn,mx,eq.weapon_instance.damage_type,eq.weapon_instance.attack_speed,eq.weapon_instance.reach,eq.weapon_instance.range,eq.weapon_instance.name)
    def _source_version(self,ch,context=None):
        payload={'migration':self.attribute_service.migration_version,'formulas':self.formulas,'stat_defs':self.stat_defs,'actor':_cid(ch)}; return hashlib.sha1(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    def synchronize_resources(self,ch,resources): return self.refresh_actor_maxima(ch,'legacy_synchronize_resources',resources)
    def refresh_actor_maxima(self,ch,reason,resources=None):
        resources=resources or {'max_health':self.get_stat(ch,'max_health'),'max_mana':self.get_stat(ch,'max_mana'),'max_stamina':self.get_stat(ch,'max_stamina')}; events=[]
        for key,attr in [('health','hp'),('mana','mana'),('stamina','stamina')]:
            maxv=int(resources.get('max_'+key,0)); cur=int(getattr(ch,attr,0) or 0); setattr(ch,'max_'+key,maxv); 
            if cur>maxv: setattr(ch,attr,maxv); events.append(('resource_current_clamped',{'reason':reason,'resource':key,'old_current':cur,'new_current':maxv}))
        return events
    def get_combat_snapshot(self,ch,context=None):
        attrs=self.attribute_service.get_all_attributes(ch,context); sv=self._source_version(ch,context); primary={}
        for sid,a in attrs.items():
            d=self.attribute_service.definitions.get(sid,{})
            primary[sid]=PrimaryStatValue(sid,d.get('semantic_role',''),getattr(a,'name',sid.title()),d.get('short_name',sid[:3].upper()),a.base_value,a.permanent_modifier,a.equipment_modifier,a.affect_modifier,0,0,a.situational_modifier,a.final_value,a.minimum_value,a.maximum_value,True,'','base+components',{'snapshot':sv})
        offense={k:self._combat_value(ch,k,context) for k in ['accuracy','hit_bonus','attack_power','damage_bonus','spell_power','healing_power']}
        defense={k:self._combat_value(ch,k,context) for k in ['armor','evasion','critical_avoidance']}
        crit={k:self._combat_value(ch,k,context) for k in ['critical_melee','critical_spell','critical_heal','critical_avoidance','critical_damage']}
        saves={k:self._combat_value(ch,k,context) for k in ['physical_save','mental_save','magic_save']}
        speed={k:self._combat_value(ch,k,context,active=False,reason=self.inactive_speed_reason) for k in ['initiative','attack_speed','casting_speed','recovery_speed','movement_speed']}
        maxima={k:self._combat_value(ch,k,context) for k in ['max_health','max_mana','max_stamina']}
        enc=self.get_encumbrance(ch,context); carrying={k:self._combat_value(ch,k,context,value=v) for k,v in enc.items() if k!='encumbrance_state'}; encvals={**carrying,'encumbrance_state':self._combat_value(ch,'encumbrance_state',context,value=enc['encumbrance_state'],active=True)}
        resources={**maxima,'health':self._combat_value(ch,'health',context,value=int(getattr(ch,'hp',getattr(ch,'hp_current',0)) or 0),active=True),'mana':self._combat_value(ch,'mana',context,value=int(getattr(ch,'mana',0) or 0),active=True),'stamina':self._combat_value(ch,'stamina',context,value=int(getattr(ch,'stamina',0) or 0),active=True)}
        unarmed=DamageProfile(self.get_stat(ch,'unarmed_damage_min',context),self.get_stat(ch,'unarmed_damage_max',context),'physical',100,1,0,'unarmed')
        nw=getattr(self.build_actor_stat_input(ch,context),'natural_weapon_profiles',[])
        weapon=self.get_damage_profile(ch,context)
        if not weapon and nw: weapon=DamageProfile(nw[0].minimum_damage,nw[0].maximum_damage,nw[0].damage_type,nw[0].attack_speed,nw[0].reach,nw[0].maximum_range,nw[0].name)
        return CombatStatSnapshot(self.schema_version,hashlib.sha1((sv+utc_now()).encode()).hexdigest(),_cid(ch),getattr(ch,'actor_type','player'),self.attribute_service.world_id,getattr(ch,'template_id',None),getattr(ch,'instance_id',None),int(getattr(ch,'level',1) or 1),primary,offense,defense,crit,saves,self.get_resistance_values(ch,context),speed,weapon,unarmed,nw,resources,carrying,encvals,{'presence':{'active_attribute':True,'combat_consumed':False,'current_consumers':[]}}, {'snapshot':sv,'attributes':sv,'combat':sv,'equipment':sv,'effects':sv,'templates':sv,'instances':sv,'definitions':sv}, utc_now())
