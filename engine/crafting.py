"""Phase 7C canonical crafting, recipe, workstation, quality, and production foundation."""
from __future__ import annotations
import hashlib, json, re, sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from engine.rewards import RewardService, RewardSource, RewardRecipient
from engine.economy import EconomyService

SAFE_ID_RE=re.compile(r"^[A-Za-z0-9_.:-]+$")
RECIPE_TYPES={"craft","assemble","refine","process","cook","cooking","baking","roasting","boiling","grilling","smoking","drying","preserving","food_preparation","drink_preparation","brew","forge","smelt","tailor","leatherwork","woodwork","alchemy","salvage","disassemble","repair_material","enchant_placeholder","custom"}
SELECTION_MODES={"all_required","one_of","any_quantity","exact_quantity","tag_match","material_match","custom"}
TOOL_LOCATIONS={"equipped","carried","workstation","either","custom"}
JOB_STATUSES={"previewed","pending","reserved","in_progress","paused","completed","failed","cancelled","refunded"}
RESERVATION_STATUSES={"active","consumed","released","expired","cancelled"}

def utc_now(): return datetime.now(timezone.utc).isoformat()
def _json(v): return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v, default=None):
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def stable_id(prefix,*parts):
    raw="|".join(json.dumps(p,sort_keys=True,default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
def safe_id(v): return bool(v and SAFE_ID_RE.fullmatch(str(v)))

SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS workstation_runtime_state(workstation_state_id TEXT PRIMARY KEY,world_id TEXT,workstation_profile_id TEXT,feature_id TEXT,room_id TEXT,enabled INTEGER,condition_current INTEGER,condition_maximum INTEGER,active_job_count INTEGER,last_used_world_time INTEGER,owner_type TEXT,owner_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,workstation_profile_id,feature_id,room_id));
CREATE TABLE IF NOT EXISTS crafting_jobs(crafting_job_id TEXT PRIMARY KEY,world_id TEXT,recipe_id TEXT,owner_type TEXT,owner_id TEXT,actor_id TEXT,workstation_state_id TEXT,status TEXT,quantity INTEGER,batch_index INTEGER,started_world_time INTEGER,completes_world_time INTEGER,next_tick_world_time INTEGER,input_reservation_id TEXT,cost_transaction_id TEXT,quality_seed TEXT,result_reward_packet_id TEXT,failure_reason TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_crafting_jobs_actor ON crafting_jobs(world_id,actor_id,status);
CREATE TABLE IF NOT EXISTS crafting_input_reservations(reservation_id TEXT PRIMARY KEY,world_id TEXT,crafting_job_id TEXT,owner_actor_id TEXT,status TEXT,created_world_time INTEGER,expires_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS crafting_input_reservation_entries(reservation_entry_id TEXT PRIMARY KEY,reservation_id TEXT,item_instance_id TEXT,required_quantity INTEGER,reserved_quantity INTEGER,consume INTEGER,catalyst INTEGER,original_owner_type TEXT,original_owner_id TEXT,created_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_crafting_reserved_item ON crafting_input_reservation_entries(item_instance_id,reservation_id);
CREATE TABLE IF NOT EXISTS actor_profession_state(profession_state_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,profession_id TEXT,rank INTEGER,experience INTEGER,experience_to_next INTEGER,total_experience INTEGER,specialization_ids_json TEXT,active INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,actor_id,profession_id));
CREATE TABLE IF NOT EXISTS actor_recipe_knowledge(knowledge_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,recipe_id TEXT,source_type TEXT,source_id TEXT,learned_world_time INTEGER,active INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,actor_id,recipe_id,source_type,source_id));
CREATE TABLE IF NOT EXISTS craft_previews(preview_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,recipe_id TEXT,quantity INTEGER,workstation_state_id TEXT,eligible INTEGER,created_world_time INTEGER,created_at TEXT,preview_json TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS cooking_job_context(cooking_context_id TEXT PRIMARY KEY,crafting_job_id TEXT UNIQUE,recipe_id TEXT,cooking_method TEXT,workstation_instance_id TEXT,campfire_instance_id TEXT,heat_profile_id TEXT,fuel_reserved INTEGER,environment_snapshot_json TEXT,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS cooking_job_ingredients(ingredient_record_id TEXT PRIMARY KEY,crafting_job_id TEXT,item_instance_id TEXT,item_template_id TEXT,ingredient_profile_id TEXT,quantity INTEGER,quality_id TEXT,freshness_state TEXT,substitution_group_id TEXT,reserved_at TEXT,consumed_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS cooking_job_outputs(output_record_id TEXT PRIMARY KEY,crafting_job_id TEXT,item_instance_id TEXT,item_template_id TEXT,servings INTEGER,quality_id TEXT,freshness_profile_id TEXT,freshness_state TEXT,consumable_profile_id TEXT,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS cooking_fuel_reservations(fuel_reservation_id TEXT PRIMARY KEY,crafting_job_id TEXT UNIQUE,campfire_instance_id TEXT,fuel_amount INTEGER,status TEXT,created_at TEXT,metadata_json TEXT);
"""

def init_crafting_schema(db_path):
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA_SQL)
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_instances" in tables:
            cols={r[1] for r in con.execute("PRAGMA table_info(item_instances)")}
            for name,ddl in {"quality_profile_id":"TEXT","quality_score":"INTEGER","crafted_by_actor_id":"TEXT","crafted_from_recipe_id":"TEXT","crafting_job_id":"TEXT","craft_world_time":"INTEGER","batch_id":"TEXT","provenance_json":"TEXT","consumable_profile_id":"TEXT","portion_profile_id":"TEXT","freshness_created_world_time":"INTEGER","freshness_profile_id":"TEXT","servings_remaining":"INTEGER"}.items():
                if name not in cols: con.execute(f"ALTER TABLE item_instances ADD COLUMN {name} {ddl}")

class CraftingContent:
    collections=["recipe_definitions","workstation_profiles","production_profiles","item_quality_profiles","crafting_quality_profiles","ingredient_substitution_profiles","crafting_message_profiles","profession_experience_curves","profession_growth_profiles","cooking_ingredient_profiles","cooking_substitution_profiles","ingredient_preparation_profiles","cooking_serving_yield_profiles","cooking_consumable_output_profiles","food_nutrition_profiles","food_preservation_profiles","cooking_heat_profiles","cooking_failure_profiles","cooking_message_profiles","cooking_render_profiles","consumable_profiles","consumable_portion_profiles","food_freshness_profiles"]
    def __init__(self, world_root="worlds/shattered_realms"):
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}
    def _load(self,c):
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text(encoding="utf-8")); items=raw.get(c,raw) if isinstance(raw,dict) else raw
                if isinstance(items,list): return {str(x.get("id")):x for x in items if isinstance(x,dict) and x.get("id")}
                if isinstance(items,dict): return {str(k):(v|{"id":v.get("id",k)} if isinstance(v,dict) else {"id":k}) for k,v in items.items()}
        return {}
    def get(self,c,i): return self.data.get(c,{}).get(str(i or ""))
    def list(self,c): return sorted(self.data.get(c,{}).values(), key=lambda x:x.get("id",""))
    def validate(self, item_templates=None, professions=None, formulas=None):
        errors=[]; warnings=[]; item_templates=item_templates or set(); professions=professions or set(); formulas=formulas or set()
        for c,items in self.data.items():
            for iid,obj in items.items():
                if not safe_id(iid): errors.append(f"{c}:{iid}: unsafe id")
                if c=="recipe_definitions": self._validate_recipe(obj,errors,warnings,item_templates,professions,formulas)
                if c=="workstation_profiles": self._validate_workstation(obj,errors,warnings)
                if c=="production_profiles": self._validate_production(obj,errors,warnings,formulas)
                if c in {"item_quality_profiles","crafting_quality_profiles"}: self._validate_quality(c,obj,errors,warnings,formulas)
        return {"errors":errors,"warnings":warnings}
    def _validate_recipe(self,r,e,w,item_templates,professions,formulas):
        rid=r.get("id");
        if r.get("recipe_type","craft") not in RECIPE_TYPES: e.append(f"recipe {rid} invalid recipe_type")
        if professions and r.get("profession_id") and r.get("profession_id") not in professions: e.append(f"recipe {rid} invalid profession {r.get('profession_id')}")
        seen=set()
        for g in r.get("input_groups") or []:
            if g.get("id") in seen: e.append(f"recipe {rid} duplicate input group {g.get('id')}")
            seen.add(g.get("id"));
            if g.get("selection_mode","all_required") not in SELECTION_MODES: e.append(f"recipe {rid} invalid input selection")
            if int(g.get("minimum_entries",0) or 0)>int(g.get("maximum_entries",999999) or 999999): e.append(f"recipe {rid} impossible input group {g.get('id')}")
            for x in g.get("entries") or []:
                if item_templates and x.get("item_template_id") and x.get("item_template_id") not in item_templates: e.append(f"recipe {rid} invalid item {x.get('item_template_id')}")
        if not r.get("output_groups"): w.append(f"recipe {rid} has no output")
        if not r.get("input_groups"): w.append(f"recipe {rid} has no inputs")
        if r.get("production_profile_id") and not self.get("production_profiles",r.get("production_profile_id")): e.append(f"recipe {rid} invalid production profile")
        if r.get("workstation_profile_id") and not self.get("workstation_profiles",r.get("workstation_profile_id")): e.append(f"recipe {rid} invalid workstation")
        if r.get("quality_profile_id") and not self.get("crafting_quality_profiles",r.get("quality_profile_id")): e.append(f"recipe {rid} invalid quality profile")
        for t in r.get("tool_requirements") or []:
            if t.get("required_location","carried") not in TOOL_LOCATIONS: e.append(f"recipe {rid} invalid tool location")
    def _validate_workstation(self,x,e,w):
        if int(x.get("capacity",1) or 0)<0: e.append(f"workstation {x.get('id')} negative capacity")
        if not x.get("allowed_recipe_ids") and not x.get("allowed_recipe_types"): w.append(f"workstation {x.get('id')} has no recipes")
    def _validate_production(self,x,e,w,formulas):
        if int(x.get("base_duration",0) or 0)<0: e.append(f"production {x.get('id')} negative duration")
        if x.get("production_mode","instant")=="timed" and int(x.get("base_duration",0) or 0)==0: w.append(f"production {x.get('id')} has no duration but uses timed mode")
    def _validate_quality(self,c,x,e,w,formulas):
        if c=="item_quality_profiles" and int(x.get("minimum_score",0) or 0)>int(x.get("maximum_score",0) or 0): e.append(f"quality {x.get('id')} invalid bounds")
        last=None
        for tier in x.get("quality_tiers") or []:
            lo=int(tier.get("minimum_score",0)); hi=int(tier.get("maximum_score",lo))
            if hi<lo: e.append(f"quality {x.get('id')} invalid tier bounds")
            if last is not None and lo<=last: e.append(f"quality {x.get('id')} overlapping tiers")
            last=hi

@dataclass(frozen=True)
class CraftPreview:
    preview_id:str; actor_id:str; recipe_id:str; quantity:int; eligible:bool; details:dict[str,Any]=field(default_factory=dict)

class CraftingService:
    def __init__(self, db_path, world_id="shattered_realms", world_root=None, runtime=None, event_bus=None, reward_service=None, economy_service=None):
        self.db_path=Path(db_path); self.world_id=world_id; self.runtime=runtime; self.event_bus=event_bus or getattr(runtime,"event_bus",None); init_crafting_schema(self.db_path)
        self.content=CraftingContent(world_root or f"worlds/{world_id}"); self.economy=economy_service or EconomyService(self.db_path, world_id, world_root or f"worlds/{world_id}", self.event_bus, runtime); self.rewards=reward_service or RewardService(db_path=self.db_path, runtime=runtime, world_id=world_id)
    def publish(self,e,p):
        if self.event_bus and hasattr(self.event_bus,"publish"):
            try: self.event_bus.publish(e,p,source_system="crafting")
            except TypeError: self.event_bus.publish(e,p)
    def get_recipe(self, recipe_id): return self.content.get("recipe_definitions", recipe_id)
    def list_available_recipes(self, actor_id, context=None):
        return [r for r in self.content.list("recipe_definitions") if r.get("enabled",True) and self.actor_knows_recipe(actor_id,r["id"])]

    # Phase 11E cooking adapter APIs: these route through canonical crafting jobs.
    def list_cooking_recipes(self, actor_id, filters=None):
        filters=filters or {}
        out=[]
        for r in self.get_actor_recipes(actor_id):
            if self._is_cooking_recipe(r) and all(r.get(k)==v for k,v in filters.items() if v): out.append(r)
        return out
    def _is_cooking_recipe(self, r):
        return r.get("recipe_category") in {"cooking","baking","roasting","boiling","grilling","smoking","drying","preserving","food_preparation","drink_preparation"} or r.get("recipe_type") in {"cook","cooking","baking","roasting","boiling","smoking","drying","preserving"}
    def get_cooking_recipe(self, recipe_id):
        r=self.get_recipe(recipe_id); return r if r and self._is_cooking_recipe(r) else None
    def resolve_cooking_ingredients(self, actor_id, recipe_id, ingredient_item_ids=None):
        r=self.get_cooking_recipe(recipe_id);
        if not r: raise KeyError(recipe_id)
        return self.select_inputs(actor_id,r,1,ingredient_item_ids)
    def resolve_ingredient_substitutions(self, recipe_id, ingredient_item_ids=None):
        r=self.get_recipe(recipe_id) or {}; prof=self.content.get('cooking_substitution_profiles', r.get('ingredient_substitution_profile_id')) or {}
        return {'recipe_id':recipe_id,'profile_id':prof.get('id',''),'maximum_substitutions':prof.get('maximum_substitutions',0),'substitutions':[]}
    def resolve_campfire_workstation(self, actor_id, campfire_instance_id):
        surv=getattr(self.runtime,'survival_needs',None) if self.runtime else None
        row=surv.trace_campfire(campfire_instance_id) if surv and hasattr(surv,'trace_campfire') else {}
        if not row: return {'ok':False,'reason':'campfire_not_found'}
        room=getattr(surv,'_room_for_actor',lambda a: row.get('room_id'))(actor_id)
        if row.get('room_id')!=room: return {'ok':False,'reason':'campfire_wrong_room','campfire':row}
        if row.get('status')!='lit': return {'ok':False,'reason':'campfire_not_lit','campfire':row}
        return {'ok':True,'workstation_type':'campfire','campfire_instance_id':campfire_instance_id,'room_id':row.get('room_id'),'heat_available':True,'heat_level':50,'fuel_available':int(row.get('fuel_current') or 0),'quality_modifier':0,'tags':['campfire','cooking']}
    def resolve_cooking_workstation(self, actor_id, recipe_id, workstation_id=None):
        if workstation_id and str(workstation_id).startswith('campfire_'): return self.resolve_campfire_workstation(actor_id,workstation_id)
        return {'ok':True,'workstation_profile_id':workstation_id or (self.get_recipe(recipe_id) or {}).get('workstation_profile_id'),'workstation_type':workstation_id or 'generic'}
    def validate_cooking_requirements(self, actor_id, recipe_id, ingredient_item_ids=None, workstation_id=None):
        p=self.preview_cooking(actor_id,recipe_id,ingredient_item_ids,workstation_id); return {'ok':p.eligible,'details':p.details}
    def preview_cooking(self, actor_id, recipe_id, ingredient_item_ids=None, workstation_id=None):
        p=self.preview_recipe(actor_id,recipe_id,1,workstation_id,ingredient_item_ids)
        if not self.get_cooking_recipe(recipe_id): p.details.setdefault('warnings',[]).append('not a cooking recipe')
        p.details['cooking']= {'serving_yield_profile_id':p.details['recipe'].get('serving_yield_profile_id'),'consumable_output_profile_id':p.details['recipe'].get('consumable_output_profile_id'),'substitutions':self.resolve_ingredient_substitutions(recipe_id,ingredient_item_ids)}
        return p
    def start_cooking(self, actor_id, recipe_id, ingredient_item_ids=None, workstation_id=None):
        if not self.get_cooking_recipe(recipe_id): raise ValueError('not a cooking recipe')
        if workstation_id=='campfire':
            surv=getattr(self.runtime,'survival_needs',None) if self.runtime else None
            if surv:
                with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; row=con.execute("SELECT campfire_instance_id FROM campfire_instances WHERE status='lit' ORDER BY created_at DESC LIMIT 1").fetchone(); workstation_id=row['campfire_instance_id'] if row else workstation_id
        ctx=self.resolve_cooking_workstation(actor_id,recipe_id,workstation_id)
        if not ctx.get('ok',True): raise ValueError(ctx.get('reason','invalid workstation'))
        job=self.start_crafting(actor_id,recipe_id,1,workstation=workstation_id,explicit_instances=ingredient_item_ids)
        meta={'workstation_context':ctx}
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO cooking_job_context VALUES(?,?,?,?,?,?,?,?,?,?,?)",(stable_id('cookctx',job['crafting_job_id']),job['crafting_job_id'],recipe_id,(self.get_recipe(recipe_id) or {}).get('cooking_method',''),workstation_id or '',ctx.get('campfire_instance_id',''),(self.get_recipe(recipe_id) or {}).get('required_heat_profile_id',''),0,_json({}),utc_now(),_json(meta)))
        self.publish('cooking_started', {'crafting_job_id':job['crafting_job_id'],'actor_id':actor_id,'recipe_id':recipe_id})
        return job
    def complete_cooking(self, crafting_job_id):
        return self.complete_crafting_job(crafting_job_id)
    def interrupt_cooking(self, crafting_job_id, reason):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE crafting_jobs SET status='failed',failure_reason=?,updated_at=? WHERE crafting_job_id=? AND status!='completed'",(reason,utc_now(),crafting_job_id))
        self.publish('cooking_interrupted', {'crafting_job_id':crafting_job_id,'reason':reason}); return self.get_crafting_job(crafting_job_id)
    def preserve_food(self, actor_id, item_instance_id, preservation_profile_id='basic_smoking_or_drying'):
        prof=self.content.get('food_preservation_profiles',preservation_profile_id) or {};
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE item_instances SET freshness_profile_id=?,updated_at=? WHERE instance_id=? AND owner_id=?",(prof.get('output_freshness_profile_id') or 'preserved_food',utc_now(),item_instance_id,actor_id))
        self.publish('food_preserved', {'actor_id':actor_id,'item_instance_id':item_instance_id,'preservation_profile_id':preservation_profile_id}); return {'ok':True,'item_instance_id':item_instance_id,'preservation_profile_id':preservation_profile_id}
    def trace_cooking_job(self, crafting_job_id):
        tr=self.trace_crafting_job(crafting_job_id)
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; tr['cooking_context']=dict(con.execute("SELECT * FROM cooking_job_context WHERE crafting_job_id=?",(crafting_job_id,)).fetchone() or {}); tr['outputs']=[dict(r) for r in con.execute("SELECT * FROM cooking_job_outputs WHERE crafting_job_id=?",(crafting_job_id,))]
        return tr
    trace_cooking_quality=trace_cooking_job; trace_cooking_freshness=trace_cooking_job; trace_cooking_servings=trace_cooking_job

    def grant_recipe(self, actor_id, recipe_id, source_type="admin", source_id=None, world_time=0):
        kid=stable_id("rk",self.world_id,actor_id,recipe_id,source_type,source_id or ""); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO actor_recipe_knowledge VALUES(?,?,?,?,?,?,?,?,?,?,?)",(kid,self.world_id,actor_id,recipe_id,source_type,source_id or "",world_time,1,now,now,_json({})))
        self.publish("recipe_granted", {"actor_id":actor_id,"recipe_id":recipe_id}); return kid
    def revoke_recipe(self, actor_id, recipe_id, source_type=None):
        q="UPDATE actor_recipe_knowledge SET active=0,updated_at=? WHERE world_id=? AND actor_id=? AND recipe_id=?"; p=[utc_now(),self.world_id,actor_id,recipe_id]
        if source_type: q+=" AND source_type=?"; p.append(source_type)
        with sqlite3.connect(self.db_path) as con: con.execute(q,p)
        self.publish("recipe_revoked", {"actor_id":actor_id,"recipe_id":recipe_id}); return True
    def actor_knows_recipe(self, actor_id, recipe_id):
        r=self.get_recipe(recipe_id) or {}; 
        if r.get("visibility","known") in {"public","known","default"}: return True
        with sqlite3.connect(self.db_path) as con: return bool(con.execute("SELECT 1 FROM actor_recipe_knowledge WHERE world_id=? AND actor_id=? AND recipe_id=? AND active=1",(self.world_id,actor_id,recipe_id)).fetchone())
    def get_actor_recipes(self, actor_id): return [r for r in self.content.list("recipe_definitions") if self.actor_knows_recipe(actor_id,r["id"])]
    def get_actor_profession(self, actor_id, profession_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM actor_profession_state WHERE world_id=? AND actor_id=? AND profession_id=?",(self.world_id,actor_id,profession_id)).fetchone(); return dict(r) if r else None
    def grant_profession(self, actor_id, profession_id):
        pid=stable_id("prof",self.world_id,actor_id,profession_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO actor_profession_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,actor_id,profession_id,1,0,100,0,_json([]),1,now,now,_json({})))
        return self.get_actor_profession(actor_id,profession_id)
    def award_profession_experience(self, actor_id, profession_id, amount, source=None):
        self.grant_profession(actor_id,profession_id); amount=int(amount)
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_profession_state SET experience=experience+?,total_experience=total_experience+?,rank=1+((total_experience+?)/100),updated_at=? WHERE world_id=? AND actor_id=? AND profession_id=?",(amount,amount,amount,utc_now(),self.world_id,actor_id,profession_id))
        self.publish("profession_experience_awarded", {"actor_id":actor_id,"profession_id":profession_id,"amount":amount}); return self.get_actor_profession(actor_id,profession_id)
    def _inventory(self, actor_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row
            cols={r[1] for r in con.execute("PRAGMA table_info(item_instances)")}
            if "instance_id" not in cols: return []
            rows=con.execute("SELECT * FROM item_instances WHERE owner_type='actor' AND owner_id=? AND destroyed_at IS NULL",(actor_id,)).fetchall()
            return [dict(r) for r in rows]
    def _reserved(self):
        with sqlite3.connect(self.db_path) as con: return {r[0] for r in con.execute("SELECT e.item_instance_id FROM crafting_input_reservation_entries e JOIN crafting_input_reservations r ON r.reservation_id=e.reservation_id WHERE r.status='active'")}
    def select_inputs(self, actor_id, recipe, quantity=1, explicit_instances=None):
        items=self._inventory(actor_id); reserved=self._reserved(); selected=[]; missing=[]; rejected=[]; explicit=set(explicit_instances or [])
        for g in recipe.get("input_groups") or []:
            need=int(g.get("quantity",1) or 1)*int(quantity)
            entries=g.get("entries") or []
            candidates=[]
            for it in items:
                meta=_loads(it.get("plugin_data"))|_loads(it.get("custom_flags")); tags=set(meta.get("tags") or [])
                for en in entries:
                    reasons=[]
                    if it.get("instance_id") in reserved: reasons.append("reserved")
                    if it.get("equipped_slot") and not en.get("allow_equipped",False): reasons.append("equipped")
                    if meta.get("bound") and not en.get("allow_bound",False): reasons.append("bound")
                    if meta.get("protected") and not en.get("allow_bound",False): reasons.append("protected")
                    match=(en.get("item_template_id") and en.get("item_template_id")==it.get("template_id")) or (en.get("item_tag") and en.get("item_tag") in tags) or (en.get("item_type") and en.get("item_type")==meta.get("item_type")) or (en.get("material_profile_id") and en.get("material_profile_id")==meta.get("material_profile_id"))
                    if explicit and it.get("instance_id") not in explicit: match=False
                    if match and not reasons: candidates.append((en,it)); break
                    if match and reasons: rejected.append({"item_instance_id":it.get("instance_id"),"reasons":reasons})
            candidates=sorted(candidates,key=lambda ei:(0 if ei[0].get("item_template_id") else 1, int(ei[1].get("quality_score") or 0), int(ei[1].get("condition_current") or 100), ei[1].get("created_at") or "", ei[1].get("instance_id") or ""))
            take=candidates[:need]
            if len(take)<need: missing.append({"group_id":g.get("id"),"required":need,"available":len(take)})
            for en,it in take: selected.append({"group_id":g.get("id"),"entry_id":en.get("id"),"item_instance_id":it.get("instance_id"),"quantity":1,"consume":bool(g.get("consume",True)) and not bool(en.get("catalyst",False)),"catalyst":bool(en.get("catalyst",False)),"template_id":it.get("template_id")})
        return {"selected_inputs":selected,"missing_inputs":missing,"rejected_inputs":rejected}
    def preview_recipe(self, actor_id, recipe_id, quantity=1, workstation=None, explicit_instances=None, world_time=0):
        r=self.get_recipe(recipe_id); assert r, f"unknown recipe {recipe_id}"; prof=self.get_actor_profession(actor_id,r.get("profession_id")) if r.get("profession_id") else None
        checks=[]; eligible=bool(r.get("enabled",True)) and self.actor_knows_recipe(actor_id,recipe_id)
        if r.get("profession_id") and (not prof or int(prof.get("rank",0))<int(r.get("minimum_profession_rank",1) or 1)): eligible=False; checks.append("missing profession/rank")
        sel=self.select_inputs(actor_id,r,quantity,explicit_instances); eligible=eligible and not sel["missing_inputs"]
        prod=self.content.get("production_profiles",r.get("production_profile_id")) or {"production_mode":"instant","base_duration":0}
        details={"recipe":r,"profession_requirement":{"profession_id":r.get("profession_id"),"minimum_rank":r.get("minimum_profession_rank",0),"current":prof},"workstation":workstation or r.get("workstation_profile_id"),"duration":int(prod.get("base_duration",0) or 0)*int(quantity),"quality_range":self.quality_range(r),"profession_xp":int(r.get("profession_experience",0) or 0)*int(quantity),"currency_costs":r.get("currency_costs") or {},"resource_costs":r.get("resource_costs") or {},"expected_outputs":r.get("output_groups") or [],"possible_byproducts":r.get("byproduct_groups") or [],"warnings":checks + (["destructive salvage: selected items will be consumed"] if r.get("recipe_type") in {"salvage","disassemble"} else []), **sel}
        pid=stable_id("cp",self.world_id,actor_id,recipe_id,quantity,details,world_time)
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO craft_previews VALUES(?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,actor_id,recipe_id,int(quantity),workstation or "",1 if eligible else 0,world_time,utc_now(),_json(details),_json({})))
        return CraftPreview(pid,actor_id,recipe_id,int(quantity),eligible,details)
    def can_craft(self,*a,**k): return self.preview_recipe(*a,**k).eligible
    def quality_range(self, recipe):
        q=self.content.get("crafting_quality_profiles",recipe.get("quality_profile_id")) or {}; return {"minimum_quality":q.get("minimum_quality","common"),"maximum_quality":q.get("maximum_quality","common")}
    def resolve_quality(self, recipe, seed, profession_rank=0, ingredient_score=0, workstation_modifier=0):
        q=self.content.get("crafting_quality_profiles",recipe.get("quality_profile_id")) or {}; score=int(q.get("base_quality",50) or 50)+int(profession_rank)-int(q.get("recipe_difficulty",0) or 0)+int(ingredient_score)+int(workstation_modifier)
        score=max(int(q.get("minimum_score",0) or 0), min(int(q.get("maximum_score",100) or 100), score))
        tiers=q.get("quality_tiers") or []
        prof="common"
        for t in tiers:
            if int(t.get("minimum_score",0))<=score<=int(t.get("maximum_score",score)): prof=t.get("quality_profile_id") or t.get("id") or prof
        return {"quality_score":score,"quality_profile_id":prof,"seed":seed,"formula_id":q.get("quality_formula_id","phase7c_deterministic_quality")}
    def _reserve(self, job_id, actor_id, selected, world_time):
        rid=stable_id("res",self.world_id,job_id,selected); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO crafting_input_reservations VALUES(?,?,?,?,?,?,?,?,?,?)",(rid,self.world_id,job_id,actor_id,"active",world_time,None,now,now,_json({})))
            for s in selected:
                con.execute("INSERT OR IGNORE INTO crafting_input_reservation_entries VALUES(?,?,?,?,?,?,?,?,?,?,?)",(stable_id("rese",rid,s["item_instance_id"]),rid,s["item_instance_id"],s.get("quantity",1),s.get("quantity",1),1 if s.get("consume") else 0,1 if s.get("catalyst") else 0,"actor",actor_id,now,_json(s)))
        self.publish("craft_inputs_reserved", {"reservation_id":rid,"crafting_job_id":job_id}); return rid
    def start_crafting(self, actor_id, recipe_id=None, quantity=1, preview_id=None, workstation=None, world_time=0, explicit_instances=None):
        prev=self.preview_recipe(actor_id,recipe_id,quantity,workstation,explicit_instances,world_time=world_time) if not preview_id else self._load_preview(preview_id)
        if not prev.eligible: raise ValueError("crafting preview is not eligible")
        r=prev.details["recipe"]; seed=stable_id("qseed",self.world_id,actor_id,r["id"],quantity,world_time); jid=stable_id("cj",self.world_id,actor_id,r["id"],quantity,seed); dur=int(prev.details["duration"]); now=utc_now(); costs=r.get("currency_costs") or {}; txn=""
        if costs:
            txn=self.economy.create_transaction("service",buyer_type="actor",buyer_id=actor_id,total=costs,status="completed",metadata={"crafting_job_id":jid})
            for cur,amt in costs.items(): self.economy.debit_currency("actor",actor_id,cur,int(amt),transaction_id=txn,reason="crafting cost",source_type="crafting",source_id=jid)
            self.publish("craft_cost_paid", {"crafting_job_id":jid,"transaction_id":txn})
        rid=self._reserve(jid,actor_id,prev.details["selected_inputs"],world_time)
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO crafting_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(jid,self.world_id,r["id"],"actor",actor_id,actor_id,workstation or "","in_progress",int(quantity),0,world_time,world_time+dur,world_time+dur,rid,txn,seed,"","",now,now,_json({"recipe_version":r.get("version",1),"selected_inputs":prev.details["selected_inputs"]})))
        self.publish("craft_job_created", {"crafting_job_id":jid}); self.publish("craft_job_started", {"crafting_job_id":jid});
        if dur==0: self.complete_crafting_job(jid, world_time)
        return self.get_crafting_job(jid)
    def _load_preview(self,pid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM craft_previews WHERE preview_id=?",(pid,)).fetchone()
        if not r: raise KeyError(pid)
        return CraftPreview(r["preview_id"],r["actor_id"],r["recipe_id"],r["quantity"],bool(r["eligible"]),_loads(r["preview_json"]))
    def get_crafting_job(self, jid):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM crafting_jobs WHERE crafting_job_id=?",(jid,)).fetchone(); return dict(r) if r else None
    def list_actor_crafting_jobs(self, actor_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM crafting_jobs WHERE world_id=? AND actor_id=? ORDER BY created_at",(self.world_id,actor_id))]
    def list_workstation_jobs(self, workstation_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM crafting_jobs WHERE workstation_state_id=?",(workstation_id,))]
    def process_crafting_jobs(self, world_id=None, world_time=0):
        with sqlite3.connect(self.db_path) as con: ids=[r[0] for r in con.execute("SELECT crafting_job_id FROM crafting_jobs WHERE world_id=? AND status='in_progress' AND completes_world_time<=?",(world_id or self.world_id,world_time))]
        return [self.complete_crafting_job(i,world_time) for i in ids]
    def complete_crafting_job(self, jid, world_time=0):
        job=self.get_crafting_job(jid); 
        if not job or job["status"]=="completed": return job
        r=self.get_recipe(job["recipe_id"]); meta=_loads(job.get("metadata_json")); q=self.resolve_quality(r,job["quality_seed"])
        with sqlite3.connect(self.db_path) as con:
            for eid,iid in con.execute("SELECT reservation_entry_id,item_instance_id FROM crafting_input_reservation_entries WHERE reservation_id=? AND consume=1",(job["input_reservation_id"],)): con.execute("UPDATE item_instances SET destroyed_at=?,destroy_reason=?,updated_at=? WHERE instance_id=? AND destroyed_at IS NULL",(utc_now(),"crafting_consumed",utc_now(),iid))
            con.execute("UPDATE crafting_input_reservations SET status='consumed',updated_at=? WHERE reservation_id=?",(utc_now(),job["input_reservation_id"]))
        entries=[]
        for g in r.get("output_groups") or []:
            for e in g.get("entries") or []: entries.append({"id":e.get("id"),"reward_type":e.get("reward_type") or e.get("type") or "item","definition_id":e.get("definition_id") or e.get("item_template_id") or e.get("currency_id"),"item_template_id":e.get("item_template_id"),"quantity":int(e.get("quantity",1) or 1)*int(job["quantity"]),"metadata":{"crafting_job_id":jid,"quality":q}})
        rd={"id":stable_id("craft_reward",jid),"entries":entries,"delivery_policy":"default"}
        self.rewards.content.data.setdefault("reward_definitions",{})[rd["id"]]=rd
        packet=self.rewards.resolve_reward_definition(rd["id"], RewardSource("profession",r["id"],jid,self.world_id,world_time,{"crafting_job_id":jid}), RewardRecipient("actor",job["actor_id"]), seed=job["quality_seed"])
        self.rewards.deliver_reward_packet(packet["reward_packet_id"])
        with sqlite3.connect(self.db_path) as con:
            existing=con.execute("SELECT COUNT(*) FROM item_instances WHERE json_extract(custom_flags,'$.reward_packet_id')=? OR json_extract(custom_flags,'$.source_reward_packet_id')=?",(packet["reward_packet_id"],packet["reward_packet_id"])).fetchone()[0]
            if existing==0:
                for en in entries:
                    if en.get('reward_type')=='item':
                        for i in range(int(en.get('quantity',1) or 1)):
                            iid=stable_id('item', packet['reward_packet_id'], en.get('item_template_id'), i)
                            con.execute("INSERT OR IGNORE INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,stack_count,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,en.get('item_template_id') or en.get('definition_id'),'actor',job['actor_id'],'',1,utc_now(),utc_now(),_json({'reward_packet_id':packet['reward_packet_id']}),_json({})))
            con.execute("UPDATE item_instances SET quality_profile_id=?,quality_score=?,crafted_by_actor_id=?,crafted_from_recipe_id=?,crafting_job_id=?,craft_world_time=?,batch_id=?,provenance_json=? WHERE json_extract(custom_flags,'$.reward_packet_id')=? OR json_extract(custom_flags,'$.source_reward_packet_id')=?",(q["quality_profile_id"],q["quality_score"],job["actor_id"],r["id"],jid,world_time,jid,_json({"recipe_id":r["id"],"job_id":jid,"selected_inputs":meta.get("selected_inputs",[])}),packet["reward_packet_id"],packet["reward_packet_id"]))
            con.execute("UPDATE crafting_jobs SET status='completed',result_reward_packet_id=?,updated_at=? WHERE crafting_job_id=? AND status!='completed'",(packet["reward_packet_id"],utc_now(),jid))
        if r.get("profession_id") and r.get("profession_experience"): self.award_profession_experience(job["actor_id"],r["profession_id"],int(r.get("profession_experience") or 0)*int(job["quantity"]),{"crafting_job_id":jid})
        self.publish("craft_quality_resolved", {"crafting_job_id":jid,**q}); self.publish("craft_inputs_consumed", {"crafting_job_id":jid}); self.publish("craft_job_completed", {"crafting_job_id":jid,"reward_packet_id":packet["reward_packet_id"]});
        if self._is_cooking_recipe(r):
            self._finalize_cooking_outputs(jid, job, r, q, world_time)
        if r.get("recipe_type")=="salvage": self.publish("salvage_completed", {"crafting_job_id":jid})
        if r.get("recipe_type") in {"refine","process","smelt"}: self.publish("refining_completed", {"crafting_job_id":jid})
        return self.get_crafting_job(jid)

    def _finalize_cooking_outputs(self, jid, job, recipe, quality, world_time):
        sy=self.content.get('cooking_serving_yield_profiles', recipe.get('serving_yield_profile_id')) or {'base_servings':1,'minimum_servings':1,'maximum_servings':1}
        servings=max(0,min(int(sy.get('maximum_servings',sy.get('base_servings',1)) or 1), int(sy.get('base_servings',1) or 1)))
        co=self.content.get('cooking_consumable_output_profiles', recipe.get('consumable_output_profile_id')) or {}
        fresh=recipe.get('freshness_output_profile_id') or co.get('freshness_profile_id') or 'fresh_cooked_food'
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row
            rows=con.execute("SELECT instance_id,template_id FROM item_instances WHERE crafting_job_id=? AND destroyed_at IS NULL",(jid,)).fetchall()
            for row in rows:
                con.execute("UPDATE item_instances SET servings_remaining=?,freshness_created_world_time=?,freshness_profile_id=?,consumable_profile_id=?,portion_profile_id=?,updated_at=? WHERE instance_id=?",(servings,world_time,fresh,co.get('consumable_profile_id',''),co.get('portion_profile_id',''),utc_now(),row['instance_id']))
                con.execute("INSERT OR IGNORE INTO cooking_job_outputs VALUES(?,?,?,?,?,?,?,?,?,?,?)",(stable_id('cookout',jid,row['instance_id']),jid,row['instance_id'],row['template_id'],servings,quality.get('quality_profile_id'),fresh,'fresh',co.get('consumable_profile_id',''),utc_now(),_json({'serving_yield_profile_id':recipe.get('serving_yield_profile_id')})))
        self.publish('cooking_quality_resolved', {'crafting_job_id':jid, **quality}); self.publish('cooking_servings_resolved', {'crafting_job_id':jid,'servings':servings}); self.publish('cooking_freshness_resolved', {'crafting_job_id':jid,'freshness_profile_id':fresh}); self.publish('cooked_food_created', {'crafting_job_id':jid}); self.publish('cooking_completed', {'crafting_job_id':jid})

    def cancel_crafting(self, actor_id, crafting_job_id):
        job=self.get_crafting_job(crafting_job_id)
        if not job or job["actor_id"]!=actor_id: raise KeyError(crafting_job_id)
        if job["status"]=="completed": raise ValueError("completed jobs cannot be cancelled")
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE crafting_input_reservations SET status='released',updated_at=? WHERE reservation_id=? AND status='active'",(utc_now(),job["input_reservation_id"]))
            con.execute("UPDATE crafting_jobs SET status='cancelled',updated_at=? WHERE crafting_job_id=? AND status!='completed'",(utc_now(),crafting_job_id))
        self.publish("craft_inputs_released", {"crafting_job_id":crafting_job_id}); self.publish("craft_job_cancelled", {"crafting_job_id":crafting_job_id}); return self.get_crafting_job(crafting_job_id)
    def trace_recipe_preview(self,*a,**k): return self.preview_recipe(*a,**k).details
    def trace_crafting_job(self,jid):
        job=self.get_crafting_job(jid) or {}; return {"job":job,"recipe":self.get_recipe(job.get("recipe_id")),"reservation":job.get("input_reservation_id"),"idempotency":"completed jobs are ignored on repeat completion"}
    retry_crafting_job=lambda self,jid: self.get_crafting_job(jid)
    complete_job=complete_crafting_job
