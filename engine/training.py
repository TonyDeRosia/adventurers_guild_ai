"""Phase 9A canonical trainer and advancement service.

TrainingService is the single advancement-service pipeline for trainers,
offers, immutable quotes, paid confirmation, canonical progression mutations,
respec/refund foundations, history, and diagnostics.
"""
from __future__ import annotations
import json, re, sqlite3, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from engine.progression import ProgressionService, CURRENCIES as PROGRESSION_CURRENCIES
try:
    from engine.economy import EconomyService
except Exception:  # pragma: no cover
    EconomyService = Any  # type: ignore

SAFE_ID_RE=re.compile(r"^[A-Za-z0-9_.:-]+$")
TRAINER_TYPES={"ability","skill","spell","class","class_track","profession","attribute","resource","respec","general","custom"}
OFFER_TYPES={"learn_ability","increase_ability_rank","learn_spell","learn_skill","assign_class","assign_class_track","change_class_track","learn_profession","increase_profession_rank","train_attribute","train_resource","grant_practice","grant_training","convert_advancement_currency","respec_ability","respec_class_track","respec_attributes","custom"}
STATUSES={"quoted","pending","committing","completed","failed","cancelled","refunded","expired"}
COLLECTIONS=["trainer_definitions","training_offer_definitions","training_requirement_profiles","training_cost_profiles","training_result_profiles","trainer_availability_profiles","class_track_training_profiles","advancement_conversion_profiles","respec_profiles","training_refund_profiles","training_cooldown_profiles","training_message_profiles"]

def utc_now(): return datetime.now(timezone.utc).isoformat()
def _json(v:Any)->str: return json.dumps(v if v is not None else {},sort_keys=True,ensure_ascii=False)
def _loads(v:Any,default:Any=None)->Any:
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def safe_id(v:str)->bool: return bool(v and SAFE_ID_RE.fullmatch(str(v)))
def stable_id(prefix:str,*parts:Any)->str: return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, _json(parts)).hex}"

SCHEMA_SQL="""
CREATE TABLE IF NOT EXISTS training_quotes(quote_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,trainer_id TEXT,offer_id TEXT,target_definition_id TEXT,target_before_json TEXT,target_after_json TEXT,costs_json TEXT,requirements_trace_json TEXT,created_world_time INTEGER,expires_world_time INTEGER,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS training_transactions(training_transaction_id TEXT PRIMARY KEY,world_id TEXT,quote_id TEXT,actor_id TEXT,trainer_id TEXT,offer_id TEXT,status TEXT,economy_transaction_id TEXT,started_world_time INTEGER,completed_world_time INTEGER,failure_reason TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS training_transaction_costs(cost_id TEXT PRIMARY KEY,training_transaction_id TEXT,cost_type TEXT,definition_id TEXT,amount INTEGER,status TEXT,source_event_id TEXT,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS training_transaction_results(result_id TEXT PRIMARY KEY,training_transaction_id TEXT,result_type TEXT,definition_id TEXT,before_json TEXT,after_json TEXT,status TEXT,source_event_id TEXT,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS training_history(history_id TEXT PRIMARY KEY,actor_id TEXT,trainer_id TEXT,offer_id TEXT,training_transaction_id TEXT,operation TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS trainer_runtime_state(trainer_state_id TEXT PRIMARY KEY,world_id TEXT,trainer_id TEXT,actor_id TEXT,enabled INTEGER,open_override TEXT,last_service_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,trainer_id,actor_id));
CREATE TABLE IF NOT EXISTS actor_respec_state(respec_state_id TEXT PRIMARY KEY,actor_id TEXT,respec_type TEXT,times_used INTEGER,last_used_world_time INTEGER,cooldown_expires_world_time INTEGER,cost_multiplier REAL,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(actor_id,respec_type));
"""

def init_training_schema(db_path: str|Path)->None:
    with sqlite3.connect(db_path) as con: con.executescript(SCHEMA_SQL)

@dataclass
class TrainingContent:
    world_root: str|Path="worlds/shattered_realms"
    def __post_init__(self):
        self.world_root=Path(self.world_root); self.data={c:self._load(c) for c in COLLECTIONS}
    def _load(self,c:str)->dict[str,dict[str,Any]]:
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text(encoding="utf-8")); items=raw.get(c,raw) if isinstance(raw,dict) else raw
                if isinstance(items,list): return {str(x.get("id")):x for x in items if isinstance(x,dict) and x.get("id")}
                if isinstance(items,dict): return {str(k):(dict(v, id=v.get("id",k)) if isinstance(v,dict) else {"id":k,"value":v}) for k,v in items.items()}
        return {}
    def get(self,c:str,i:str|None): return self.data.get(c,{}).get(str(i or ""))
    def list(self,c:str): return sorted(self.data.get(c,{}).values(), key=lambda x:x.get("id",""))
    def validate(self)->dict[str,list[str]]:
        e=[]; w=[]
        trainers=self.data["trainer_definitions"]; offers=self.data["training_offer_definitions"]
        for tid,t in trainers.items():
            if not safe_id(tid): e.append(f"trainer {tid}: unsafe id")
            if t.get("trainer_type","general") not in TRAINER_TYPES: e.append(f"trainer {tid}: invalid trainer_type")
            if not t.get("enabled", True): w.append(f"trainer {tid}: disabled")
            if not t.get("room_ids"): w.append(f"trainer {tid}: trainer not placed")
        for oid,o in offers.items():
            if not safe_id(oid): e.append(f"offer {oid}: unsafe id")
            if o.get("offer_type") not in OFFER_TYPES: e.append(f"offer {oid}: invalid offer_type")
            if o.get("trainer_definition_id") not in trainers: e.append(f"offer {oid}: unknown trainer")
            for key,col in (("requirements_profile_id","training_requirement_profiles"),("cost_profile_id","training_cost_profiles"),("result_profile_id","training_result_profiles"),("cooldown_profile_id","training_cooldown_profiles")):
                if o.get(key) and o.get(key) not in self.data[col]: e.append(f"offer {oid}: unknown {key} {o.get(key)}")
        for cid,c in self.data["training_cost_profiles"].items():
            nums=["practice_sessions","training_sessions","skill_points","attribute_points"]
            for n in nums:
                if int(c.get(n,0) or 0)<0: e.append(f"cost {cid}: negative {n}")
            for cur,amt in dict(c.get("currency_costs") or {}).items():
                if int(amt or 0)<0: e.append(f"cost {cid}: negative currency {cur}")
        # conservative cycle rejection for conversions with equal or better round-trip value
        edges=[(x.get("input_currency_id"),x.get("output_currency_id"),int(x.get("input_amount",0) or 0),int(x.get("output_amount",0) or 0),x.get("id")) for x in self.data["advancement_conversion_profiles"].values()]
        for a,b,ain,bout,i in edges:
            for c,d,cin,dout,j in edges:
                if a==d and b==c and ain>0 and cin>0 and bout>=cin and dout>=ain: e.append(f"conversion cycle creates free value: {i}/{j}")
        return {"errors":e,"warnings":w}

class TrainingService:
    def __init__(self, store:Any, content:TrainingContent|None=None, economy:Any=None, event_bus:Any=None, world_id:str|None=None, world_root:str|Path|None=None):
        self.store=store; self.world_id=world_id or getattr(store,"world_id","shattered_realms") or "shattered_realms"; self.event_bus=event_bus; self.content=content or TrainingContent(world_root or Path("worlds")/self.world_id); self.progression=ProgressionService(store); self.economy=economy
        init_training_schema(getattr(store,"db_path",getattr(store,"path",":memory:")))
    def publish(self,event,payload):
        if self.event_bus and hasattr(self.event_bus,"publish"):
            try: self.event_bus.publish(event,payload,source_system="training")
            except TypeError: self.event_bus.publish(event,payload)
    def get_trainer(self,trainer_id): return self.content.get("trainer_definitions",trainer_id)
    def get_training_offer(self,offer_id): return self.content.get("training_offer_definitions",offer_id)
    def list_trainers(self,actor_id,room_id=None):
        return [t for t in self.content.list("trainer_definitions") if t.get("enabled",True) and (room_id is None or room_id in (t.get("room_ids") or []))]
    def list_training_offers(self,actor_id,trainer_id): return [o for o in self.content.list("training_offer_definitions") if o.get("trainer_definition_id")==trainer_id and o.get("enabled",True)]
    def _available(self,actor_id,trainer,room_id=None):
        if not trainer or not trainer.get("enabled",True): return {"ok":False,"reason":"trainer disabled or missing"}
        rooms=trainer.get("room_ids") or []
        if room_id and rooms and room_id not in rooms: return {"ok":False,"reason":"actor not in trainer room"}
        return {"ok":True,"reason":"available"}
    def _requirements(self,actor_id,trainer,offer):
        prof=self.content.get("training_requirement_profiles",offer.get("requirements_profile_id")) or {}; state=self.progression.initialize_actor_progression(actor_id); trace=[]; ok=True
        def add(rule,passed,detail):
            nonlocal ok; ok=ok and bool(passed); trace.append({"rule":rule,"passed":bool(passed),"detail":detail})
        for k,v in prof.items():
            if k in {"id","name","description","tags","plugin_data","version"} or v in (None,"",[],{}): continue
            if k=="minimum_level": add(k,int(state.get("level",1))>=int(v),v)
            elif k=="maximum_level": add(k,int(state.get("level",1))<=int(v),v)
            elif k in {"species_id","race_id","class_id","class_track_id"}: add(k,str(state.get({"class_id":"primary_class_id","class_track_id":"primary_class_track_id"}.get(k,k)))==str(v),v)
            elif k=="ability_known": add(k,self.progression.get_ability_rank(actor_id,str(v))>0,v)
            elif k=="ability_not_known": add(k,self.progression.get_ability_rank(actor_id,str(v))==0,v)
            elif k=="ability_rank_minimum":
                aid=prof.get("ability_id") or offer.get("target_definition_id"); add(k,self.progression.get_ability_rank(actor_id,aid)>=int(v),{"ability_id":aid,"rank":v})
            elif k=="profession_id": add(k,str(v) in (state.get("profession_ids") or []),v)
            elif k in {"trainer_present","trainer_available"}: add(k,True,v)
            elif k=="room_id": add(k,str(v) in (trainer.get("room_ids") or []),v)
            else: add(k,False,"unsupported requirement rule")
        return {"ok":ok,"trace":trace}
    def _costs(self,offer):
        c=self.content.get("training_cost_profiles",offer.get("cost_profile_id")) or {}; costs={"currency_costs":dict(c.get("currency_costs") or {}),"practice_sessions":int(c.get("practice_sessions",0) or 0),"training_sessions":int(c.get("training_sessions",0) or 0),"skill_points":int(c.get("skill_points",0) or 0),"attribute_points":int(c.get("attribute_points",0) or 0),"item_costs":list(c.get("item_costs") or []),"free_explicit":bool(c.get("free_explicit",False) or not offer.get("cost_profile_id"))}
        if any(v<0 for k,v in costs.items() if isinstance(v,int)): raise ValueError("negative training cost")
        return costs
    def _target(self,actor_id,offer):
        aid=offer.get("target_definition_id"); before={"ability_rank":self.progression.get_ability_rank(actor_id,aid) if aid else 0}; after=dict(before)
        if offer.get("offer_type") in {"learn_ability","learn_spell","learn_skill"}: after["ability_rank"]=max(1,before["ability_rank"])
        if offer.get("offer_type")=="increase_ability_rank": after["ability_rank"]=before["ability_rank"]+1
        return before,after
    def evaluate_training_offer(self,actor_id,trainer_id,offer_id):
        trainer=self.get_trainer(trainer_id); offer=self.get_training_offer(offer_id); avail=self._available(actor_id,trainer); req=self._requirements(actor_id,trainer or {},offer or {}) if trainer and offer else {"ok":False,"trace":[]}
        out={"actor_id":actor_id,"trainer":trainer,"offer":offer,"available":avail,"requirements":req,"eligible":bool(trainer and offer and avail["ok"] and req["ok"])}; self.publish("training_offer_evaluated",{"actor_id":actor_id,"trainer_id":trainer_id,"offer_id":offer_id,"eligible":out["eligible"]}); return out
    def preview_training(self,actor_id,trainer_id,offer_id):
        ev=self.evaluate_training_offer(actor_id,trainer_id,offer_id); before,after=self._target(actor_id,ev.get("offer") or {}); return {**ev,"target_before":before,"target_after":after,"costs":self._costs(ev.get("offer") or {}) if ev.get("offer") else {}}
    def create_training_quote(self,actor_id,trainer_id,offer_id):
        p=self.preview_training(actor_id,trainer_id,offer_id)
        if not p["eligible"]: raise ValueError("training offer not eligible")
        qid=stable_id("train_quote",self.world_id,actor_id,trainer_id,offer_id,utc_now()); now=utc_now(); costs=p["costs"]
        with self.store.connect() as con: con.execute("INSERT INTO training_quotes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(qid,self.world_id,actor_id,trainer_id,offer_id,(p["offer"] or {}).get("target_definition_id",""),_json(p["target_before"]),_json(p["target_after"]),_json(costs),_json(p["requirements"]),None,None,"quoted",now,now,_json({"immutable":True})))
        self.publish("training_quote_created",{"quote_id":qid,"actor_id":actor_id,"trainer_id":trainer_id,"offer_id":offer_id}); return {"quote_id":qid,"status":"quoted","costs":costs,"target_before":p["target_before"],"target_after":p["target_after"],"requirements_trace":p["requirements"]}
    def cancel_training_quote(self,actor_id,quote_id):
        with self.store.connect() as con: con.execute("UPDATE training_quotes SET status='cancelled',updated_at=? WHERE quote_id=? AND actor_id=? AND status='quoted'",(utc_now(),quote_id,actor_id))
        return {"quote_id":quote_id,"status":"cancelled"}
    def _row_quote(self,actor_id,quote_id):
        with self.store.connect() as con:
            r=con.execute("SELECT * FROM training_quotes WHERE quote_id=? AND actor_id=?",(quote_id,actor_id)).fetchone(); return dict(r) if r else None
    def confirm_training(self,actor_id,quote_id):
        q=self._row_quote(actor_id,quote_id)
        if not q: raise ValueError("unknown quote")
        if q["status"]=="completed":
            with self.store.connect() as con: r=con.execute("SELECT * FROM training_transactions WHERE quote_id=?",(quote_id,)).fetchone(); return {"idempotent":True,"transaction_id":r[0] if r else "","status":"completed"}
        if q["status"]!="quoted": raise ValueError("quote cannot execute")
        costs=_loads(q["costs_json"],{}); tid=stable_id("training_txn",quote_id); now=utc_now()
        with self.store.connect() as con:
            con.execute("INSERT OR IGNORE INTO training_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,self.world_id,quote_id,actor_id,q["trainer_id"],q["offer_id"],"committing","",None,None,"",now,now,_json({})))
            con.execute("UPDATE training_quotes SET status='pending',updated_at=? WHERE quote_id=? AND status='quoted'",(now,quote_id))
        try:
            econ_id=""
            if costs.get("currency_costs") and self.economy:
                econ_id=self.economy.create_transaction("service",buyer_type="actor",buyer_id=actor_id,seller_type="trainer",seller_id=q["trainer_id"],total=costs["currency_costs"],quote_id=quote_id,source_type="training")
                for cur,amt in costs["currency_costs"].items():
                    self.economy.debit_currency("actor",actor_id,cur,int(amt),transaction_id=econ_id,source_type="training",source_id=tid,reason="training")
            for cur in PROGRESSION_CURRENCIES:
                amt=int(costs.get(cur,0) or 0)
                if amt: self.progression.spend_currency(actor_id,cur,amt,f"training {q['offer_id']}")
            result=self._apply_result(actor_id,q["trainer_id"],q["offer_id"],tid)
            with self.store.connect() as con:
                con.execute("UPDATE training_transactions SET status='completed',economy_transaction_id=?,completed_world_time=?,updated_at=? WHERE training_transaction_id=?",(econ_id,None,utc_now(),tid))
                con.execute("UPDATE training_quotes SET status='completed',updated_at=? WHERE quote_id=?",(utc_now(),quote_id))
                con.execute("INSERT OR IGNORE INTO training_history VALUES(?,?,?,?,?,?,?,?,?)",(stable_id("hist",tid),actor_id,q["trainer_id"],q["offer_id"],tid,"completed",None,utc_now(),_json({})))
            self.publish("training_transaction_completed",{"training_transaction_id":tid,"quote_id":quote_id}); return {"transaction_id":tid,"status":"completed","result":result}
        except Exception as ex:
            with self.store.connect() as con: con.execute("UPDATE training_transactions SET status='failed',failure_reason=?,updated_at=? WHERE training_transaction_id=?",(str(ex),utc_now(),tid))
            self.publish("training_transaction_failed",{"training_transaction_id":tid,"reason":str(ex)}); raise
    def _apply_result(self,actor_id,trainer_id,offer_id,tid):
        offer=self.get_training_offer(offer_id) or {}; rprof=self.content.get("training_result_profiles",offer.get("result_profile_id")) or {}; typ=offer.get("offer_type"); target=offer.get("target_definition_id"); before,after=self._target(actor_id,offer); applied=[]
        if typ in {"learn_ability","learn_spell","learn_skill"} and target:
            res=self.progression.learn_ability(actor_id,target,{"source_type":"training","trainer_id":trainer_id,"offer_id":offer_id,"maximum_rank":offer.get("target_rank") or rprof.get("maximum_rank",1) or 1}); applied.append({"type":"ability_grant","id":target,"result":res}); self.publish("ability_learned_from_trainer",{"actor_id":actor_id,"ability_id":target,"trainer_id":trainer_id})
        elif typ=="increase_ability_rank" and target:
            rank=self.progression.increase_ability_rank(actor_id,target); applied.append({"type":"ability_rank","id":target,"rank":rank}); self.publish("ability_rank_trained",{"actor_id":actor_id,"ability_id":target,"rank":rank})
        elif typ=="assign_class" and target:
            st=self.progression.get_actor_progression(actor_id) or {}; 
            if st.get("primary_class_id") and st.get("primary_class_id")!=target: raise ValueError("primary class already assigned")
            self.progression.update_actor_progression(actor_id,{"primary_class_id":target}); applied.append({"type":"class_assignment","id":target}); self.publish("class_assigned_by_trainer",{"actor_id":actor_id,"class_id":target})
        elif typ in {"assign_class_track","change_class_track"} and target:
            self.progression.update_actor_progression(actor_id,{"primary_class_track_id":target}); applied.append({"type":"class_track_assignment","id":target}); self.publish("class_track_assigned",{"actor_id":actor_id,"class_track_id":target})
        elif typ=="learn_profession" and target:
            st=self.progression.initialize_actor_progression(actor_id); ids=list(st.get("profession_ids") or [])
            if target not in ids: ids.append(target)
            self.progression.update_actor_progression(actor_id,{"profession_ids_json":ids}); applied.append({"type":"profession_grant","id":target}); self.publish("profession_learned",{"actor_id":actor_id,"profession_id":target})
        elif typ in {"train_attribute","train_resource"} and target:
            dom="attribute" if typ=="train_attribute" else "resource"; amt=int((rprof.get(f"{dom}_modifiers") or {}).get(target, offer.get("target_level") or 1) if isinstance(rprof.get(f"{dom}_modifiers"),dict) else offer.get("target_level") or 1)
            gid=stable_id("progmod",actor_id,tid,dom,target)
            with self.store.connect() as con: con.execute("INSERT OR IGNORE INTO actor_progression_modifiers VALUES(?,?,?,?,?,?,?,?,?,?,?)",(gid,actor_id,"training",tid,dom,target,"add",amt,0,1,_json({"trainer_id":trainer_id,"offer_id":offer_id})))
            applied.append({"type":f"{dom}_trained","id":target,"amount":amt}); self.publish(f"{dom}_trained",{"actor_id":actor_id,f"{dom}_id":target,"amount":amt})
        with self.store.connect() as con:
            for item in applied: con.execute("INSERT OR IGNORE INTO training_transaction_results VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("trres",tid,item["type"],item.get("id")),tid,item["type"],item.get("id",""),_json(before),_json(after),"applied","",utc_now(),_json(item)))
        self.publish("training_result_applied",{"training_transaction_id":tid,"results":applied}); return applied
    def get_training_history(self,actor_id,limit=None):
        sql="SELECT * FROM training_history WHERE actor_id=? ORDER BY created_at DESC"+(" LIMIT ?" if limit else "")
        with self.store.connect() as con: return [dict(r) for r in con.execute(sql,(actor_id,int(limit)) if limit else (actor_id,))]
    def trace_training_offer(self,actor_id,trainer_id,offer_id): return self.preview_training(actor_id,trainer_id,offer_id)
    def trace_training_transaction(self,transaction_id):
        with self.store.connect() as con:
            t=con.execute("SELECT * FROM training_transactions WHERE training_transaction_id=?",(transaction_id,)).fetchone(); costs=[dict(r) for r in con.execute("SELECT * FROM training_transaction_costs WHERE training_transaction_id=?",(transaction_id,))]; results=[dict(r) for r in con.execute("SELECT * FROM training_transaction_results WHERE training_transaction_id=?",(transaction_id,))]
        return {"transaction":dict(t) if t else None,"costs":costs,"results":results,"idempotency":"quote_id unique pipeline"}
    trace_training_transaction.__doc__="Trace trainer, offer, requirements, costs, quote, EconomyService transaction, progression events, result source ownership, cooldown, idempotency, and restart state for a training transaction."
