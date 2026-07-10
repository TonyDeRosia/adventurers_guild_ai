"""Phase 6E canonical progression services.

This module is deliberately data-driven: world JSON definitions describe species,
races, classes, tracks, professions, curves, and growth profiles while SQLite is
the runtime authority for actor progression state, XP history, currencies, and
progression grants.
"""
from __future__ import annotations

import json, math, re, sqlite3, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
CURRENCIES = {"practice_sessions", "training_sessions", "skill_points", "attribute_points", "talent_points_placeholder"}
COLLECTIONS = [
    "species_profiles","race_profiles","class_profiles","class_tracks","profession_profiles","experience_curves",
    "progression_profiles","attribute_growth_profiles","resource_growth_profiles","derived_stat_growth_profiles",
    "practice_gain_profiles","training_gain_profiles","skill_point_gain_profiles","remort_profiles","prestige_profiles",
    "experience_reward_profiles",
]

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v: Any, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default

def safe_id(value: str) -> bool: return bool(value and SAFE_ID_RE.match(str(value)))

def default_collection_item(collection: str, item_id: str, name: str = "") -> dict[str, Any]:
    base = {"id": item_id, "name": name or item_id.replace("_", " ").title(), "description": "", "tags": [], "plugin_data": {}, "version": 1}
    if collection == "species_profiles":
        base.update({"body_profile_id":"","default_combat_profile_id":"","default_behavior_profile_id":"","default_lifecycle_profile_id":"","default_resource_profile_id":"","default_resistance_profile_id":"","default_natural_weapon_profile_ids":[],"base_attributes":{},"attribute_modifiers":[],"resource_modifiers":[],"derived_stat_modifiers":[],"resistance_modifiers":[],"default_ability_loadout_id":"","granted_abilities":[],"immunities":[],"vulnerabilities":[],"languages":[],"movement_modes":["walk"],"size_category":"medium","age_rules":{}})
    elif collection == "race_profiles":
        base.update({"species_id":"humanoid","playable":True,"selectable":True,"minimum_age":0,"maximum_age":0,"default_height":"","default_weight":"","size_category_override":"","languages":[],"base_attribute_adjustments":{},"resource_adjustments":{},"derived_stat_modifiers":[],"resistance_modifiers":[],"granted_abilities":[],"granted_effects":[],"default_class_options":[],"restricted_class_ids":[],"default_profession_options":[],"body_profile_override":""})
    elif collection == "class_profiles":
        base.update({"class_type":"custom","playable":True,"selectable":True,"maximum_level":20,"primary_attribute_ids":[],"secondary_attribute_ids":[],"resource_profile_id":"","combat_profile_id":"","behavior_profile_id":"","ability_loadout_id":"","allowed_weapon_classes":[],"allowed_armor_classes":[],"starting_abilities":[],"level_ability_grants":{},"attribute_growth_profile_id":"","resource_growth_profile_id":"","derived_stat_growth_profile_id":"","experience_curve_id":"standard_adventurer_curve","practice_gain_profile_id":"","training_gain_profile_id":"","skill_point_gain_profile_id":"","advancement_requirements":[],"multiclass_rules":{"class_level_mode":"single_level","maximum_classes":1},"remort_rules":{}})
    elif collection == "class_tracks":
        base.update({"class_id":"","minimum_level":1,"requirements":[],"ability_grants":[],"modifier_grants":[],"resource_changes":[],"allowed_equipment_changes":[]})
    elif collection == "profession_profiles":
        base.update({"profession_type":"custom","maximum_rank":1,"experience_curve_id":"","rank_names":[],"granted_abilities":[],"modifier_grants":[],"resource_grants":[],"requirements":[]})
    elif collection == "experience_curves":
        base.update({"curve_type":"explicit_thresholds","maximum_level":20,"thresholds":{"1":0,"2":100},"formula_id":"","level_offset":0,"multiplier":100,"minimum_increment":1,"maximum_increment":0,"world_scaling_placeholder":{}})
    elif collection.endswith("growth_profiles") or collection in {"practice_gain_profiles","training_gain_profiles","skill_point_gain_profiles"}:
        base.update({"growth_mode":"fixed","per_level":{},"milestones":{},"formula_ids":{},"minimum_values":{},"maximum_values":{},"granted_attribute_points":0,"automatic_distribution":{},"manual_distribution_allowed":False,"resource_id":"","base_gain_per_level":0,"formula_id":"","minimum":0,"maximum":0,"refill_policy":"none","stat_grants":[],"formula_overrides":{}})
    elif collection in {"remort_profiles","prestige_profiles"}:
        base.update({"requirements":[],"reset_rules":{},"preserve_rules":{},"grants":[],"maximum_count":0})
    elif collection == "progression_profiles":
        base.update({"species_id":"humanoid","race_id":"human","primary_class_id":"adventurer","primary_class_track_id":"","profession_ids":[],"level":1,"experience":0,"progression_policy":"fixed","secondary_class_ids":[],"class_levels":{},"class_experience":{},"shared_character_level":True,"class_level_mode":"single_level"})
    elif collection == "experience_reward_profiles":
        base.update({"base_experience":0,"formula_id":"","level_difference_rules":{},"group_rules_placeholder":{},"maximum_reward":0,"minimum_reward":0,"eligible_source_types":["admin","custom"]})
    return base

class ProgressionContent:
    def __init__(self, world_root: str | Path = "worlds/shattered_realms") -> None:
        self.world_root = Path(world_root); self.data={c:self._load(c) for c in COLLECTIONS}
    def _load(self, collection: str) -> dict[str, dict[str, Any]]:
        paths=[self.world_root/collection/f"{collection}.json", self.world_root/"builder"/f"{collection}.json"]
        for p in paths:
            if p.exists():
                raw=json.loads(p.read_text(encoding="utf-8"))
                items = raw.get(collection, raw) if isinstance(raw, dict) else raw
                if isinstance(items, list): return {str(i.get("id")): i for i in items if isinstance(i,dict) and i.get("id")}
                if isinstance(items, dict): return {str(k): (v|{"id":v.get("id",k)} if isinstance(v,dict) else {"id":k,"value":v}) for k,v in items.items()}
        return {}
    def get(self, collection: str, item_id: str|None) -> dict[str, Any] | None: return self.data.get(collection,{}).get(str(item_id or ""))
    def list(self, collection: str) -> list[dict[str, Any]]: return sorted(self.data.get(collection,{}).values(), key=lambda x: x.get("id",""))
    def validate(self) -> dict[str, list[str]]:
        errors=[]; warnings=[]
        for c, items in self.data.items():
            for item_id, item in items.items():
                if not safe_id(item_id): errors.append(f"{c}:{item_id}: unsafe id")
        for rid,r in self.data["race_profiles"].items():
            if r.get("species_id") and r.get("species_id") not in self.data["species_profiles"]: errors.append(f"race {rid} references unknown species {r.get('species_id')}")
            if r.get("playable") and not r.get("default_class_options"): warnings.append(f"playable race {rid} has no default class")
        for cid,c in self.data["class_profiles"].items():
            if int(c.get("maximum_level",1) or 1) < 1: errors.append(f"class {cid} has invalid maximum_level")
            curve=c.get("experience_curve_id")
            if curve and curve not in self.data["experience_curves"]: errors.append(f"class {cid} references unknown experience curve {curve}")
            if not c.get("starting_abilities"): warnings.append(f"class {cid} has no starting abilities")
        for xid,x in self.data["experience_curves"].items():
            try: thresholds=[(int(k), int(v)) for k,v in dict(x.get("thresholds",{})).items()]
            except Exception: errors.append(f"curve {xid} has invalid thresholds"); continue
            prev=-1
            for lvl,val in sorted(thresholds):
                if val < 0: errors.append(f"curve {xid} has negative threshold")
                if val <= prev: errors.append(f"curve {xid} thresholds must strictly increase")
                prev=val
        return {"errors": errors, "warnings": warnings}

@dataclass
class ProgressionService:
    store: Any
    content: ProgressionContent | None = None
    def __post_init__(self):
        self.content = self.content or ProgressionContent(Path("worlds")/(self.store.world_id or "shattered_realms"))
        self.store.initialize()
    def _state_id(self, actor_id: str, actor_type: str) -> str: return f"prog:{self.store.campaign_id}:{actor_type}:{actor_id}"
    def get_actor_progression(self, actor_id: str, actor_type: str="player") -> dict[str, Any] | None:
        with self.store.connect() as con:
            row=con.execute("SELECT * FROM actor_progression_state WHERE actor_id=? AND actor_type=?",(actor_id,actor_type)).fetchone()
            return self._row(row) if row else None
    def _row(self,row):
        d=dict(row)
        for k in ("profession_ids_json","advancement_flags_json","metadata_json"):
            d[k[:-5] if k.endswith("_json") else k]=_loads(d.get(k), [] if k=="profession_ids_json" else {})
        return d
    def initialize_actor_progression(self, actor_id: str, profile_id: str|None=None, actor_type: str="player", defaults: dict[str,Any]|None=None) -> dict[str,Any]:
        existing=self.get_actor_progression(actor_id, actor_type)
        if existing: return existing
        defaults=defaults or {}; char={}
        if actor_type=="player":
            try: char=self.store.load_character(actor_id) or {}
            except Exception: char={}
        prof=self.content.get("progression_profiles", profile_id) if profile_id else None
        now=utc_now(); level=max(1,int(defaults.get("level", char.get("level", (prof or {}).get("level",1))) or 1)); xp=max(0,int(defaults.get("experience", char.get("xp", (prof or {}).get("experience",0))) or 0))
        species=defaults.get("species_id") or (prof or {}).get("species_id") or "humanoid"
        race=defaults.get("race_id") or char.get("race_id") or (prof or {}).get("race_id") or "human"
        cls=defaults.get("primary_class_id") or char.get("class_id") or (prof or {}).get("primary_class_id") or "adventurer"
        sid=self._state_id(actor_id, actor_type)
        with self.store.connect() as con:
            con.execute("""INSERT OR IGNORE INTO actor_progression_state(progression_state_id,world_id,actor_type,actor_id,species_id,race_id,primary_class_id,primary_class_track_id,profession_ids_json,level,experience,experience_to_next,total_experience,practice_sessions,training_sessions,skill_points,attribute_points,talent_points_placeholder,remort_count,prestige_rank,advancement_flags_json,last_level_at,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(sid,self.store.world_id,actor_type,actor_id,species,race,cls,defaults.get("primary_class_track_id",(prof or {}).get("primary_class_track_id","")),_json(defaults.get("profession_ids",(prof or {}).get("profession_ids",[]))),level,xp,self.get_experience_to_next_value(cls, level, xp),xp,int(defaults.get("practice_sessions",0)),int(defaults.get("training_sessions",0)),int(defaults.get("skill_points",0)),int(defaults.get("attribute_points",0)),int(defaults.get("talent_points_placeholder",0)),0,0,_json({"migration":"initialized_or_conserved"}),None,now,now,_json({"profile_id":profile_id or "","secondary_class_ids":[],"class_levels":{cls:level},"class_experience":{cls:xp},"shared_character_level":True,"class_level_mode":"single_level"})))
        return self.get_actor_progression(actor_id, actor_type) or {}
    def update_actor_progression(self, actor_id: str, changes: dict[str,Any], actor_type: str="player") -> dict[str,Any]:
        self.initialize_actor_progression(actor_id, actor_type=actor_type); allowed={"species_id","race_id","primary_class_id","primary_class_track_id","level","experience","experience_to_next","total_experience","practice_sessions","training_sessions","skill_points","attribute_points","talent_points_placeholder","remort_count","prestige_rank","last_level_at","metadata_json","advancement_flags_json","profession_ids_json"}
        sets=[]; vals=[]
        for k,v in changes.items():
            if k in allowed: sets.append(f"{k}=?"); vals.append(_json(v) if k.endswith("_json") and not isinstance(v,str) else v)
        if sets:
            sets.append("updated_at=?"); vals.append(utc_now()); vals += [actor_id, actor_type]
            with self.store.connect() as con: con.execute(f"UPDATE actor_progression_state SET {','.join(sets)} WHERE actor_id=? AND actor_type=?", vals)
        return self.get_actor_progression(actor_id, actor_type) or {}
    def get_experience_threshold(self, curve_id: str, level: int) -> int:
        curve=self.content.get("experience_curves", curve_id) or default_collection_item("experience_curves", curve_id or "standard")
        max_level=int(curve.get("maximum_level",level) or level)
        level=max(1,min(int(level),max_level))
        thresholds={int(k):int(v) for k,v in dict(curve.get("thresholds",{})).items()}
        if curve.get("curve_type") in {"explicit_thresholds","hybrid"} and level in thresholds: return thresholds[level]
        base=max(thresholds.values() or [0]); mult=int(curve.get("multiplier",100) or 100); offset=int(curve.get("level_offset",0) or 0)
        val=max(base, int(((level+offset-1)**2)*mult)); return max(0,val)
    def get_experience_to_next_value(self, class_id: str, level: int, xp: int) -> int:
        cls=self.content.get("class_profiles", class_id) or {}; maxlvl=int(cls.get("maximum_level",20) or 20)
        if level>=maxlvl: return 0
        return max(0, self.get_experience_threshold(cls.get("experience_curve_id","standard_adventurer_curve"), level+1)-int(xp))
    def get_experience_to_next(self, actor_id: str, actor_type: str="player") -> int:
        s=self.initialize_actor_progression(actor_id, actor_type=actor_type); return self.get_experience_to_next_value(s.get("primary_class_id",""), int(s.get("level",1)), int(s.get("experience",0)))
    def award_experience(self, actor_id: str, amount: int, source_type: str="admin", source_id: str|None=None, reason: str|None=None, actor_type: str="player") -> dict[str,Any]:
        if int(amount) < 0: raise ValueError("XP awards cannot be negative")
        s=self.initialize_actor_progression(actor_id, actor_type=actor_type); final=int(amount); now=utc_now(); eid=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.store.campaign_id}:{actor_id}:{now}:{amount}:{source_type}"))
        newxp=int(s["experience"])+final
        with self.store.connect() as con:
            con.execute("INSERT INTO actor_experience_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,self.store.world_id,actor_type,actor_id,source_type,source_id,final,final,0,final,reason or "",None,now,_json({})))
        self.update_actor_progression(actor_id,{"experience":newxp,"total_experience":int(s.get("total_experience",0))+final,"experience_to_next":self.get_experience_to_next_value(s.get("primary_class_id",""),int(s.get("level",1)),newxp)},actor_type)
        levels=self.process_all_pending_levels(actor_id, actor_type)
        return {"event_id":eid,"amount":final,"levels_gained":levels,"state":self.get_actor_progression(actor_id,actor_type)}
    def remove_experience(self, actor_id: str, amount: int, reason: str|None=None, actor_type: str="player") -> dict[str,Any]:
        if int(amount)<0: raise ValueError("XP removal cannot be negative")
        s=self.initialize_actor_progression(actor_id, actor_type=actor_type); new=max(0,int(s["experience"])-int(amount)); return self.set_experience(actor_id,new,reason or "remove_experience",actor_type)
    def set_experience(self, actor_id: str, amount: int, reason: str|None=None, actor_type: str="player") -> dict[str,Any]:
        if int(amount)<0: raise ValueError("XP cannot be negative")
        s=self.initialize_actor_progression(actor_id, actor_type=actor_type); self.update_actor_progression(actor_id,{"experience":int(amount),"total_experience":max(int(s.get("total_experience",0)),int(amount)),"experience_to_next":self.get_experience_to_next_value(s.get("primary_class_id",""),int(s.get("level",1)),int(amount))},actor_type); return self.get_actor_progression(actor_id,actor_type) or {}
    def get_experience_history(self, actor_id: str, limit: int|None=None, actor_type: str="player") -> list[dict[str,Any]]:
        sql="SELECT * FROM actor_experience_events WHERE actor_id=? AND actor_type=? ORDER BY created_at DESC"+(" LIMIT ?" if limit else "")
        with self.store.connect() as con: return [dict(r) for r in con.execute(sql, (actor_id,actor_type,int(limit)) if limit else (actor_id,actor_type))]
    def can_actor_level(self, actor_id: str, actor_type: str="player") -> bool:
        s=self.initialize_actor_progression(actor_id, actor_type=actor_type); cls=self.content.get("class_profiles",s.get("primary_class_id")) or {}; return int(s["level"]) < int(cls.get("maximum_level",20) or 20) and self.get_experience_to_next_value(s.get("primary_class_id",""),int(s["level"]),int(s["experience"]))<=0
    def process_actor_level_up(self, actor_id: str, actor_type: str="player") -> bool:
        if not self.can_actor_level(actor_id,actor_type): return False
        s=self.get_actor_progression(actor_id,actor_type) or {}; newlvl=int(s["level"])+1; now=utc_now()
        self.update_actor_progression(actor_id,{"level":newlvl,"last_level_at":now},actor_type)
        # idempotent grant rows per actor/level/source/target
        self._grant_level_modifiers(actor_id, actor_type, s, newlvl)
        self._grant_currency(actor_id,"practice_sessions",1,"level_up",str(newlvl),"level up",actor_type)
        self._grant_currency(actor_id,"training_sessions",1,"level_up",str(newlvl),"level up",actor_type)
        self._grant_currency(actor_id,"skill_points",1,"level_up",str(newlvl),"level up",actor_type)
        st=self.get_actor_progression(actor_id,actor_type) or {}; self.update_actor_progression(actor_id,{"experience_to_next":self.get_experience_to_next_value(st.get("primary_class_id",""),newlvl,int(st.get("experience",0)))},actor_type)
        return True
    def process_all_pending_levels(self, actor_id: str, actor_type: str="player") -> int:
        n=0
        while self.process_actor_level_up(actor_id,actor_type): n+=1
        return n
    def _grant_level_modifiers(self, actor_id, actor_type, state, level):
        cls=self.content.get("class_profiles",state.get("primary_class_id")) or {}
        grants=[]
        ag=self.content.get("attribute_growth_profiles", cls.get("attribute_growth_profile_id")) or {}; rg=self.content.get("resource_growth_profiles", cls.get("resource_growth_profile_id")) or {}; dg=self.content.get("derived_stat_growth_profiles", cls.get("derived_stat_growth_profile_id")) or {}
        for k,v in dict(ag.get("per_level",{})).items(): grants.append(("attribute",k,v,"attribute_growth"))
        if rg.get("resource_id") and rg.get("base_gain_per_level",0): grants.append(("resource",rg.get("resource_id"),rg.get("base_gain_per_level"),"resource_growth"))
        for g in dg.get("stat_grants",[]) if isinstance(dg.get("stat_grants",[]),list) else []: grants.append(("derived_stat",g.get("stat_id",g.get("id","")),g.get("value",0),"derived_stat_growth"))
        with self.store.connect() as con:
            for dom,key,val,src in grants:
                gid=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{actor_id}:{src}:{level}:{dom}:{key}")); con.execute("INSERT OR IGNORE INTO actor_progression_modifiers VALUES(?,?,?,?,?,?,?,?,?,?,?)",(gid,actor_id,src,cls.get(src+"_profile_id",src),dom,key,"add",int(val or 0),level,1,_json({"actor_type":actor_type})))
    def _grant_currency(self, actor_id, currency, amount, source_type, source_id, reason, actor_type="player"):
        if currency not in CURRENCIES: raise ValueError("unknown advancement currency")
        s=self.initialize_actor_progression(actor_id,actor_type=actor_type); amount=int(amount)
        if amount<0: raise ValueError("currency amount cannot be negative")
        col=currency; new=int(s.get(col,0))+amount; eid=str(uuid.uuid4())
        with self.store.connect() as con: con.execute("INSERT INTO actor_advancement_currency_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",(eid,actor_id,currency,"grant",amount,source_type,source_id,reason,None,utc_now(),_json({"actor_type":actor_type})))
        self.update_actor_progression(actor_id,{col:new},actor_type); return new
    grant_currency=_grant_currency
    def spend_currency(self, actor_id, currency, amount, reason="", actor_type="player"):
        s=self.initialize_actor_progression(actor_id,actor_type=actor_type); amount=int(amount)
        if amount<0 or int(s.get(currency,0))<amount: raise ValueError("insufficient advancement currency")
        with self.store.connect() as con: con.execute("INSERT INTO actor_advancement_currency_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),actor_id,currency,"spend",amount,"ability",None,reason,None,utc_now(),_json({"actor_type":actor_type})))
        return self.update_actor_progression(actor_id,{currency:int(s.get(currency,0))-amount},actor_type)
    def learn_ability(self, actor_id: str, ability_id: str, source: dict[str,Any]|None=None, actor_type="player") -> dict[str,Any]:
        source=source or {}; self.initialize_actor_progression(actor_id,actor_type=actor_type)
        cost=int(source.get("practice_cost",0) or 0)
        if cost: self.spend_currency(actor_id,"practice_sessions",cost,f"learn {ability_id}",actor_type)
        now=utc_now()
        with self.store.connect() as con: con.execute("INSERT OR IGNORE INTO actor_ability_progression VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(actor_id,ability_id,1,int(source.get("maximum_rank",1) or 1),0,(self.get_actor_progression(actor_id,actor_type) or {}).get("level",1),source.get("class_id"),source.get("race_id"),source.get("profession_id"),source.get("track_id"),cost,int(source.get("training_cost",0) or 0),int(source.get("skill_point_cost",0) or 0),_json(source.get("requirements",[])),1,now,_json(source)))
        try: self.store.save_abilities(actor_id, list(set(self.store.load_abilities(actor_id)+[ability_id])))
        except Exception: pass
        return self.trace_ability_learning(actor_id,ability_id,actor_type)
    def increase_ability_rank(self, actor_id, ability_id, actor_type="player"):
        self.learn_ability(actor_id,ability_id,{},actor_type)
        with self.store.connect() as con:
            row=con.execute("SELECT rank,maximum_rank FROM actor_ability_progression WHERE actor_id=? AND ability_id=?",(actor_id,ability_id)).fetchone()
            if row and int(row["rank"]) < int(row["maximum_rank"]): con.execute("UPDATE actor_ability_progression SET rank=rank+1 WHERE actor_id=? AND ability_id=?",(actor_id,ability_id))
        return self.get_ability_rank(actor_id,ability_id)
    def get_ability_rank(self, actor_id, ability_id):
        with self.store.connect() as con:
            r=con.execute("SELECT rank FROM actor_ability_progression WHERE actor_id=? AND ability_id=?",(actor_id,ability_id)).fetchone(); return int(r["rank"]) if r else 0
    def trace_ability_learning(self, actor_id, ability_id, actor_type="player"):
        with self.store.connect() as con: r=con.execute("SELECT * FROM actor_ability_progression WHERE actor_id=? AND ability_id=?",(actor_id,ability_id)).fetchone()
        return {"actor_id":actor_id,"ability_id":ability_id,"known":bool(r),"grant":dict(r) if r else None}
    def trace_actor_progression(self, actor_id, actor_type="player"):
        s=self.initialize_actor_progression(actor_id,actor_type=actor_type); return {"state":s,"species":self.content.get("species_profiles",s.get("species_id")),"race":self.content.get("race_profiles",s.get("race_id")),"class":self.content.get("class_profiles",s.get("primary_class_id")),"experience_to_next":self.get_experience_to_next(actor_id,actor_type),"history":self.get_experience_history(actor_id,5,actor_type)}
    def trace_experience_curve(self, curve_id, level): return {"curve_id":curve_id,"level":level,"threshold":self.get_experience_threshold(curve_id,int(level)),"curve":self.content.get("experience_curves",curve_id)}
    def trace_experience_award(self, actor_id, amount, source_type): return {"actor_id":actor_id,"amount":amount,"source_type":source_type,"valid":int(amount)>=0}
    def preview_level_up(self, actor_id, actor_type="player"): return {"can_level":self.can_actor_level(actor_id,actor_type),"next_level":int(self.initialize_actor_progression(actor_id,actor_type=actor_type).get("level",1))+1}
    def trace_level_up(self, actor_id, actor_type="player"): return {**self.preview_level_up(actor_id,actor_type),"state":self.get_actor_progression(actor_id,actor_type)}
