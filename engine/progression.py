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
from typing import Any, Mapping

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
CURRENCIES = {"practice_sessions", "training_sessions", "skill_points", "attribute_points", "talent_points_placeholder"}

# Adventurer's Lair parity: canonical Shattered Realms Glory purchase costs.
# These are intentionally centralized so command handlers never hard-code them.
GLORY_PRACTICE_COST = 250
GLORY_TRAIN_COST = 600
TRAINING_ATTRIBUTE_CAP = 20
TRAINING_RESOURCE_SESSION_COST = 10
TRAINING_RESOURCE_BONUS = 10
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


class ProgressionIdentityError(ValueError):
    pass



def character_field(record: Any, *names: str, default: Any = None) -> Any:
    """Safely read character/actor fields from mappings, rows, and runtime objects."""
    if record is None:
        return default
    for name in names:
        if isinstance(record, Mapping):
            if name in record and record[name] is not None:
                return record[name]
        elif hasattr(record, name):
            value = getattr(record, name)
            if value is not None:
                return value
    data = getattr(record, "actor_data", None)
    if isinstance(data, Mapping):
        for name in names:
            if name in data and data[name] is not None:
                return data[name]
    return default


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
        character_record = actor_id if not isinstance(actor_id, str) else None
        actor_id = str(character_field(character_record, "id", "character_id", default=actor_id))
        existing=self.get_actor_progression(actor_id, actor_type)
        if existing: return existing
        defaults=defaults or {}; char=character_record or {}
        if actor_type=="player" and not char:
            try: char=self.store.load_character(actor_id) or {}
            except Exception: char={}
        prof=self.content.get("progression_profiles", profile_id) if profile_id else None
        now=utc_now()
        level=max(1,int(defaults.get("level", character_field(char,"level", default=(prof or {}).get("level",1))) or 1))
        xp=max(0,int(defaults.get("experience", character_field(char,"experience","xp", default=(prof or {}).get("experience",0))) or 0))
        species=defaults.get("species_id") or character_field(char,"species_id", default=None) or (prof or {}).get("species_id") or "humanoid"
        race=defaults.get("race_id") or character_field(char,"race_id", default=None) or (prof or {}).get("race_id") or "human"
        cls=defaults.get("primary_class_id") or character_field(char,"primary_class_id","class_id","profession", default=None) or (prof or {}).get("primary_class_id") or "adventurer"
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
    def purchase_session_with_glory(self, actor_id: str, session_currency: str, *, actor_type: str="player", source_id: str="guild_trainer") -> dict[str, Any]:
        """Atomically spend Glory and grant one practice/training session.

        The economy ledger and progression currency history are written in one
        SQLite transaction.  If the Glory debit cannot be applied, the session
        grant is not recorded.
        """
        if session_currency not in {"practice_sessions", "training_sessions"}:
            raise ValueError("unsupported glory purchase")
        cost = GLORY_PRACTICE_COST if session_currency == "practice_sessions" else GLORY_TRAIN_COST
        self.initialize_actor_progression(actor_id, actor_type=actor_type)
        from engine.economy import init_economy_schema, stable_id
        init_economy_schema(self.store.db_path)
        now = utc_now()
        bal_id = stable_id("bal", self.store.world_id, "actor", actor_id, "glory")
        txn = stable_id("txn", "glory_session_purchase", actor_id, session_currency, now)
        with self.store.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT OR IGNORE INTO actor_currency_balances VALUES(?,?,?,?,?,?,?,?,?)", (bal_id,self.store.world_id,"actor",actor_id,"glory",0,now,now,_json({})))
            row = con.execute("SELECT balance FROM actor_currency_balances WHERE balance_id=?", (bal_id,)).fetchone()
            before_glory = int(row["balance"] if hasattr(row, "keys") else row[0])
            if before_glory < cost:
                con.rollback()
                return {"ok": False, "reason": "insufficient_glory", "cost": cost, "glory": before_glory, "currency": session_currency}
            after_glory = before_glory - cost
            state = con.execute("SELECT * FROM actor_progression_state WHERE actor_id=? AND actor_type=?", (actor_id, actor_type)).fetchone()
            before_sessions = int(state[session_currency] if hasattr(state, "keys") else state[14 if session_currency=="training_sessions" else 13])
            after_sessions = before_sessions + 1
            con.execute("UPDATE actor_currency_balances SET balance=?,updated_at=? WHERE balance_id=?", (after_glory, now, bal_id))
            con.execute("INSERT INTO economy_ledger_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (stable_id("led", txn, 1, actor_id, "glory"), self.store.world_id, txn, 1, "actor", actor_id, "glory", "debit", cost, before_glory, after_glory, "guild", source_id, "glory_session_purchase", session_currency, f"buy {session_currency}", None, now, _json({"actor_type": actor_type})))
            con.execute(f"UPDATE actor_progression_state SET {session_currency}=?,updated_at=? WHERE actor_id=? AND actor_type=?", (after_sessions, now, actor_id, actor_type))
            con.execute("INSERT INTO actor_advancement_currency_events VALUES(?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), actor_id, session_currency, "grant", 1, "glory_purchase", source_id, f"buy {session_currency}", after_sessions, now, _json({"actor_type": actor_type, "glory_cost": cost, "glory_after": after_glory, "transaction_id": txn})))
        return {"ok": True, "cost": cost, "glory": after_glory, "currency": session_currency, "sessions": after_sessions}
    def learn_ability(self, actor_id: str, ability_id: str, source: dict[str,Any]|None=None, actor_type="player") -> dict[str,Any]:
        source=source or {}; self.initialize_actor_progression(actor_id,actor_type=actor_type)
        cost=int(source.get("practice_cost",0) or 0)
        if cost: self.spend_currency(actor_id,"practice_sessions",cost,f"learn {ability_id}",actor_type)
        now=utc_now()
        with self.store.connect() as con: con.execute("INSERT OR IGNORE INTO actor_ability_progression VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(actor_id,ability_id,1,int(source.get("maximum_rank", source.get("maximum_proficiency",100)) or 100),max(1,min(100,int(source.get("default_proficiency", source.get("proficiency",1)) or 1))),(self.get_actor_progression(actor_id,actor_type) or {}).get("level",1),source.get("class_id"),source.get("race_id"),source.get("profession_id"),source.get("track_id"),cost,int(source.get("training_cost",0) or 0),int(source.get("skill_point_cost",0) or 0),_json(source.get("requirements",[])),1,now,_json(source)))
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
    def progression_identity_snapshot(self, actor_id: str, actor_type: str="player", *, state: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return typed, validated canonical progression identity for displays."""
        s = state if state is not None else self.get_actor_progression(actor_id, actor_type)
        if not s:
            raise ProgressionIdentityError(f"progression_identity_missing actor_id={actor_id}")
        source_version = str(s.get("updated_at") or s.get("created_at") or "")
        species_id = str(s.get("species_id") or "")
        race_id = str(s.get("race_id") or "")
        class_id = str(s.get("primary_class_id") or "")
        track_id = str(s.get("primary_class_track_id") or "")
        species = self.content.get("species_profiles", species_id) if species_id else None
        race = self.content.get("race_profiles", race_id) if race_id else None
        cls = self.content.get("class_profiles", class_id) if class_id else None
        if species_id and not species: raise ProgressionIdentityError(f"invalid_progression_identity field=species_id id={species_id}")
        if not race: raise ProgressionIdentityError(f"invalid_progression_identity field=race_id id={race_id}")
        if not cls: raise ProgressionIdentityError(f"invalid_progression_identity field=primary_class_id id={class_id}")
        track = None
        if track_id:
            track = self.content.get("class_tracks", track_id)
            if not track: raise ProgressionIdentityError(f"invalid_progression_identity field=primary_class_track_id id={track_id}")
            if str(track.get("class_id") or "") != class_id:
                raise ProgressionIdentityError(f"invalid_progression_identity field=primary_class_track_id id={track_id} class_id={class_id}")
        display_class_name = str((track or {}).get("name") or cls.get("name") or "")
        return {
            "species_id": species_id, "species_name": str((species or {}).get("name") or ""),
            "race_id": race_id, "race_name": str(race.get("name") or ""),
            "primary_class_id": class_id, "primary_class_name": str(cls.get("name") or ""),
            "primary_class_track_id": track_id, "primary_class_track_name": str((track or {}).get("name") or ""),
            "display_class_name": display_class_name,
            "level": int(s.get("level") or 1), "experience": int(s.get("experience") or 0),
            "experience_to_next": int(s.get("experience_to_next") if s.get("experience_to_next") is not None else self.get_experience_to_next_value(class_id, int(s.get("level") or 1), int(s.get("experience") or 0))),
            "xp_to_next_level": int(s.get("experience_to_next") if s.get("experience_to_next") is not None else self.get_experience_to_next_value(class_id, int(s.get("level") or 1), int(s.get("experience") or 0))),
            "practice_sessions": int(s.get("practice_sessions") or 0), "training_sessions": int(s.get("training_sessions") or 0),
            "remort_count": int(s.get("remort_count") or 0), "source_version": source_version,
        }

    def repair_legacy_progression_identity(self, character: Any, actor_type: str="player", *, apply: bool = True) -> dict[str, Any]:
        """Idempotently repair missing canonical identity from legacy fields/default profile."""
        actor_id = str(character_field(character, "id", "character_id", default=""))
        if not actor_id: raise ProgressionIdentityError("missing actor id")
        existing = self.get_actor_progression(actor_id, actor_type)
        profile = self.content.get("progression_profiles", str(character_field(character, "progression_profile_id", default="player_starter"))) or self.content.get("progression_profiles", "player_starter") or {}
        def valid(coll, val): return str(val) if val and self.content.get(coll, str(val)) else ""
        race = valid("race_profiles", (existing or {}).get("race_id")) or valid("race_profiles", character_field(character,"race_id")) or valid("race_profiles", character_field(character,"race")) or valid("race_profiles", profile.get("race_id"))
        cls = valid("class_profiles", (existing or {}).get("primary_class_id")) or valid("class_profiles", character_field(character,"primary_class_id")) or valid("class_profiles", character_field(character,"class_id")) or valid("class_profiles", character_field(character,"character_class","char_class","profession")) or valid("class_profiles", profile.get("primary_class_id"))
        species = valid("species_profiles", (existing or {}).get("species_id")) or valid("species_profiles", character_field(character,"species_id")) or valid("species_profiles", (self.content.get("race_profiles", race) or {}).get("species_id")) or valid("species_profiles", profile.get("species_id"))
        track = valid("class_tracks", (existing or {}).get("primary_class_track_id")) or valid("class_tracks", character_field(character,"primary_class_track_id","class_track_id","track_id")) or valid("class_tracks", profile.get("primary_class_track_id"))
        if track and str((self.content.get("class_tracks", track) or {}).get("class_id") or "") != cls: raise ProgressionIdentityError(f"invalid_progression_identity field=primary_class_track_id id={track} class_id={cls}")
        if not race or not cls or not species: raise ProgressionIdentityError("no_valid_progression_identity_default")
        changes={}
        if not existing:
            if apply: self.initialize_actor_progression(character, actor_type=actor_type, defaults={"species_id":species,"race_id":race,"primary_class_id":cls,"primary_class_track_id":track,"attribute_points":30})
            existing = self.get_actor_progression(actor_id, actor_type) or {}
        for k,v in {"species_id":species,"race_id":race,"primary_class_id":cls,"primary_class_track_id":track}.items():
            if not (existing or {}).get(k) and v is not None: changes[k]=v
        metadata = dict((existing or {}).get("metadata") or {})
        metadata["legacy_identity_migration"]={"version":"score_identity_2026_07_14","selected_race_id":race,"selected_class_id":cls,"selected_track_id":track,"used_default": not any(character_field(character,*names) for names in (("race_id","race"),("primary_class_id","class_id","character_class","char_class","profession"))),"timestamp":utc_now()}
        if apply and (changes or "legacy_identity_migration" not in metadata):
            changes["metadata_json"] = metadata
            self.update_actor_progression(actor_id, changes, actor_type)
        final = self.get_actor_progression(actor_id, actor_type) or existing or {}
        return {"character_id": actor_id, "row_exists": bool(final), "changed_fields": sorted(changes), "proposed_race_id": race, "proposed_class_id": cls, "proposed_track_id": track, "definition_validation": "valid", "applied": bool(apply and changes), "state": final}

    def trace_ability_learning(self, actor_id, ability_id, actor_type="player"):
        with self.store.connect() as con: r=con.execute("SELECT * FROM actor_ability_progression WHERE actor_id=? AND ability_id=?",(actor_id,ability_id)).fetchone()
        return {"actor_id":actor_id,"ability_id":ability_id,"known":bool(r),"grant":dict(r) if r else None}
    def _practice_projection(self, row: Mapping[str, Any], intelligence: int=10) -> dict[str, Any]:
        meta = _loads(row.get("metadata_json") if isinstance(row, Mapping) else row["metadata_json"], {})
        ability_id = str(row.get("ability_id") if isinstance(row, Mapping) else row["ability_id"])
        display = str(meta.get("name") or meta.get("display_name") or ability_id.replace("_", " ").title())
        rank = int(row.get("rank", 1) if isinstance(row, Mapping) else row["rank"] or 1)
        maximum_rank = int(row.get("maximum_rank", 1) if isinstance(row, Mapping) else row["maximum_rank"] or 1)
        proficiency = int(row.get("proficiency", 1) if isinstance(row, Mapping) else row["proficiency"] or 1)
        cap = int(meta.get("practice_proficiency_cap") or meta.get("maximum_proficiency") or 75)
        gain = max(1, min(15, 5 + (int(intelligence)-10)//2))
        return {"ability_id": ability_id, "display_name": display, "ability_type": str(meta.get("ability_type") or meta.get("type") or "skill"), "current_rank": rank, "maximum_rank": maximum_rank, "current_proficiency": proficiency, "practice_proficiency_cap": cap, "required_level": int(meta.get("required_level") or row.get("learned_at_level", 1) if isinstance(row, Mapping) else 1), "source_class": row.get("source_class_id") if isinstance(row, Mapping) else row["source_class_id"], "source_class_track": row.get("source_track_id") if isinstance(row, Mapping) else row["source_track_id"], "source_race": row.get("source_race_id") if isinstance(row, Mapping) else row["source_race_id"], "source_profession": row.get("source_profession_id") if isinstance(row, Mapping) else row["source_profession_id"], "availability": "known", "practice_eligibility": proficiency < cap, "practice_cost": 1, "calculated_learning_gain": gain}
    def list_known_practice_abilities(self, actor_id: str, actor_type: str="player", *, intelligence: int=10) -> list[dict[str, Any]]:
        self.initialize_actor_progression(actor_id, actor_type=actor_type)
        with self.store.connect() as con:
            con.row_factory=sqlite3.Row
            return [self._practice_projection(dict(r), intelligence) for r in con.execute("SELECT * FROM actor_ability_progression WHERE actor_id=? AND active=1 ORDER BY ability_id",(actor_id,))]
    def resolve_practice_ability(self, actor_id: str, query: str, actor_type: str="player", *, intelligence: int=10) -> dict[str, Any]:
        q = " ".join(str(query).lower().replace("_"," ").split())
        rows = self.list_known_practice_abilities(actor_id, actor_type, intelligence=intelligence)
        def norm(s): return " ".join(str(s).lower().replace("_"," ").split())
        for a in rows:
            names = [norm(a["display_name"]), norm(a["ability_id"])]
            if q in names: return {"ok": True, "ability": a}
        matches = [a for a in rows if q and q in norm(a["display_name"]).split()]
        if not matches: matches = [a for a in rows if q and norm(a["display_name"]).startswith(q)]
        if len(matches) == 1: return {"ok": True, "ability": matches[0]}
        if len(matches) > 1: return {"ok": False, "ambiguous": [a["display_name"] for a in matches]}
        return {"ok": False, "reason": "unknown"}
    def practice_ability(self, actor_id: str, ability_id: str, actor_type: str="player", *, intelligence: int=10, trainer_ok: bool=False) -> dict[str, Any]:
        if not trainer_ok: return {"ok": False, "reason": "trainer_required"}
        state = self.initialize_actor_progression(actor_id, actor_type=actor_type)
        if int(state.get("practice_sessions",0) or 0) < 1: return {"ok": False, "reason": "insufficient_practice_sessions"}
        with self.store.connect() as con:
            con.row_factory=sqlite3.Row
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM actor_ability_progression WHERE actor_id=? AND ability_id=? AND active=1", (actor_id, ability_id)).fetchone()
            if not row: con.rollback(); return {"ok": False, "reason": "unknown"}
            proj = self._practice_projection(dict(row), intelligence)
            if int(proj["current_proficiency"]) >= int(proj["practice_proficiency_cap"]): con.rollback(); return {"ok": False, "reason": "at_cap", "projection": proj}
            before = int(proj["current_proficiency"]); new = min(int(proj["practice_proficiency_cap"]), before + int(proj["calculated_learning_gain"]))
            before_sessions = int(state.get("practice_sessions",0) or 0); after_sessions = before_sessions - 1; now=utc_now()
            con.execute("UPDATE actor_ability_progression SET proficiency=? WHERE actor_id=? AND ability_id=?", (new, actor_id, ability_id))
            con.execute("UPDATE actor_progression_state SET practice_sessions=?,updated_at=? WHERE actor_id=? AND actor_type=?", (after_sessions, now, actor_id, actor_type))
            con.execute("INSERT INTO actor_advancement_currency_events VALUES(?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), actor_id, "practice_sessions", "spend", 1, "practice", ability_id, f"practice {ability_id}", after_sessions, now, _json({"actor_type": actor_type, "before_proficiency": before, "after_proficiency": new})))
        return {"ok": True, "ability_id": ability_id, "before": before, "after": new, "sessions": after_sessions, "projection": {**proj, "current_proficiency": new}}
    def trace_actor_progression(self, actor_id, actor_type="player"):
        s=self.initialize_actor_progression(actor_id,actor_type=actor_type); return {"state":s,"species":self.content.get("species_profiles",s.get("species_id")),"race":self.content.get("race_profiles",s.get("race_id")),"class":self.content.get("class_profiles",s.get("primary_class_id")),"experience_to_next":self.get_experience_to_next(actor_id,actor_type),"history":self.get_experience_history(actor_id,5,actor_type)}
    def trace_experience_curve(self, curve_id, level): return {"curve_id":curve_id,"level":level,"threshold":self.get_experience_threshold(curve_id,int(level)),"curve":self.content.get("experience_curves",curve_id)}
    def trace_experience_award(self, actor_id, amount, source_type): return {"actor_id":actor_id,"amount":amount,"source_type":source_type,"valid":int(amount)>=0}
    def preview_level_up(self, actor_id, actor_type="player"): return {"can_level":self.can_actor_level(actor_id,actor_type),"next_level":int(self.initialize_actor_progression(actor_id,actor_type=actor_type).get("level",1))+1}
    def trace_level_up(self, actor_id, actor_type="player"): return {**self.preview_level_up(actor_id,actor_type),"state":self.get_actor_progression(actor_id,actor_type)}
