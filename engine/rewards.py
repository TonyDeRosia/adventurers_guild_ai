"""Phase 7A canonical reward, loot, corpse-inventory, and claim foundations.

The service in this module is intentionally small and conservative: all reward
sources resolve into persistent RewardPacket/RewardEntry rows, delivery is
idempotent through reward_delivery_events, and gameplay systems call this single
pipeline instead of rolling loot or mutating rewards directly.
"""
from __future__ import annotations

import hashlib, json, random, re, sqlite3, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
SOURCE_TYPES = {"combat","corpse","quest","exploration","container","event","harvest","gathering","profession","achievement_placeholder","admin","script","world","custom"}
RECIPIENT_TYPES = {"actor","character","party_placeholder","group_placeholder","room","corpse","container","world","custom"}
PACKET_STATUSES = {"pending","resolved","partially_delivered","delivered","failed","cancelled","expired"}
REWARD_TYPES = {"item","currency","experience","practice_sessions","training_sessions","skill_points","attribute_points","ability","ability_rank","effect","progression_modifier","reputation_placeholder","title","accolade","custom"}
ROLL_MODES = {"all","weighted_one","weighted_many","chance_each","guaranteed_plus_weighted","explicit_sequence","custom"}
ADVANCEMENT_CURRENCIES = {"practice_sessions","training_sessions","skill_points","attribute_points"}


def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v: Any, default: Any=None) -> Any:
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def safe_id(value: str) -> bool: return bool(value and SAFE_ID_RE.fullmatch(str(value)))
def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

@dataclass(frozen=True)
class RewardSource:
    source_type: str
    source_id: str
    source_instance_id: str = ""
    world_id: str = "shattered_realms"
    world_time: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RewardRecipient:
    recipient_type: str
    recipient_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reward_packets(reward_packet_id TEXT PRIMARY KEY,world_id TEXT,source_type TEXT,source_id TEXT,source_instance_id TEXT,recipient_type TEXT,recipient_id TEXT,delivery_policy TEXT,status TEXT,resolution_seed TEXT,resolved_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_reward_packets_source ON reward_packets(world_id,source_type,source_id,source_instance_id);
CREATE INDEX IF NOT EXISTS idx_reward_packets_recipient ON reward_packets(recipient_type,recipient_id,status);
CREATE TABLE IF NOT EXISTS reward_entries(reward_entry_id TEXT PRIMARY KEY,reward_packet_id TEXT,reward_type TEXT,definition_id TEXT,quantity INTEGER,resolved_value_json TEXT,recipient_override_json TEXT,destination_override_json TEXT,delivery_status TEXT,failure_reason TEXT,source_rule_id TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_reward_entries_packet ON reward_entries(reward_packet_id,delivery_status);
CREATE TABLE IF NOT EXISTS reward_delivery_events(delivery_event_id TEXT PRIMARY KEY,reward_packet_id TEXT,reward_entry_id TEXT,recipient_type TEXT,recipient_id TEXT,destination_type TEXT,destination_id TEXT,operation TEXT,result TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reward_delivery_once ON reward_delivery_events(reward_entry_id,operation,result) WHERE result='delivered';
CREATE TABLE IF NOT EXISTS reward_claim_records(claim_id TEXT PRIMARY KEY,world_id TEXT,reward_definition_id TEXT,source_type TEXT,source_id TEXT,source_instance_id TEXT,recipient_type TEXT,recipient_id TEXT,repeat_key TEXT,claimed_at TEXT,expires_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reward_claim_repeat ON reward_claim_records(world_id,reward_definition_id,recipient_type,recipient_id,repeat_key);
CREATE TABLE IF NOT EXISTS loot_resolution_records(resolution_id TEXT PRIMARY KEY,world_id TEXT,loot_table_id TEXT,source_type TEXT,source_id TEXT,source_instance_id TEXT,resolution_seed TEXT,result_json TEXT,resolved_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS pending_reward_claims(claim_id TEXT PRIMARY KEY,reward_packet_id TEXT,recipient_type TEXT,recipient_id TEXT,expires_world_time INTEGER,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS actor_currency_balances(actor_id TEXT,currency_id TEXT,amount INTEGER,updated_at TEXT,PRIMARY KEY(actor_id,currency_id));
CREATE TABLE IF NOT EXISTS actor_currency_events(currency_event_id TEXT PRIMARY KEY,actor_id TEXT,currency_id TEXT,operation TEXT,amount INTEGER,source_json TEXT,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS corpse_inventory_state(corpse_id TEXT PRIMARY KEY,source_actor_id TEXT,source_spawn_id TEXT,source_population_id TEXT,room_id TEXT,owner_actor_id TEXT,loot_rights_policy TEXT,loot_table_id TEXT,treasure_group_id TEXT,generated_reward_packet_id TEXT,inventory_state TEXT,created_world_time INTEGER,decays_world_time INTEGER,looted_state TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS resource_node_state(node_instance_id TEXT PRIMARY KEY,profile_id TEXT,charges_remaining INTEGER,last_harvest_world_time INTEGER,next_regeneration_world_time INTEGER,status TEXT,metadata_json TEXT);
"""

class RewardContent:
    collections = ["reward_definitions","loot_tables","treasure_groups","death_loot_profiles","corpse_decay_profiles","resource_node_profiles","currency_profiles","reward_message_profiles","reward_eligibility_profiles","reward_delivery_profiles"]
    def __init__(self, world_root: str | Path = "worlds/shattered_realms") -> None:
        self.world_root = Path(world_root); self.data = {c:self._load(c) for c in self.collections}
    def _load(self, c: str) -> dict[str, dict[str, Any]]:
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text(encoding="utf-8")); items=raw.get(c, raw) if isinstance(raw,dict) else raw
                if isinstance(items, list): return {str(x.get("id")):x for x in items if isinstance(x,dict) and x.get("id")}
                if isinstance(items, dict): return {str(k):(v|{"id":v.get("id",k)} if isinstance(v,dict) else {"id":k}) for k,v in items.items()}
        return {}
    def get(self, c: str, i: str|None) -> dict[str, Any] | None: return self.data.get(c,{}).get(str(i or ""))
    def list(self, c: str) -> list[dict[str, Any]]: return sorted(self.data.get(c,{}).values(), key=lambda x:x.get("id",""))
    def validate(self, item_templates: set[str] | None = None) -> dict[str, list[str]]:
        errors=[]; warnings=[]; item_templates=item_templates or set()
        for c, items in self.data.items():
            for iid, item in items.items():
                if not safe_id(iid): errors.append(f"{c}:{iid}: unsafe id")
                if c=="reward_definitions": self._validate_reward(item, errors, warnings, item_templates)
                if c=="loot_tables": self._validate_loot(item, errors, warnings, item_templates)
        for tid in self.data["loot_tables"]: self._detect_cycle(tid, [], errors)
        return {"errors":errors,"warnings":warnings}
    def _validate_reward(self, r, errors, warnings, item_templates):
        seen=set(); entries=r.get("entries") or []
        if not entries: warnings.append(f"reward {r.get('id')} has no entries")
        for e in entries:
            eid=e.get("id") or e.get("reward_entry_id")
            if eid in seen: errors.append(f"reward {r.get('id')} duplicate entry {eid}")
            seen.add(eid); typ=e.get("reward_type") or e.get("type")
            if typ not in REWARD_TYPES: errors.append(f"reward {r.get('id')} unknown reward type {typ}")
            if typ=="item" and item_templates and (e.get("definition_id") or e.get("item_template_id")) not in item_templates: errors.append(f"reward {r.get('id')} unknown item {(e.get('definition_id') or e.get('item_template_id'))}")
            if int(e.get("quantity", e.get("amount",1)) or 1) < 0: errors.append(f"reward {r.get('id')} negative quantity")
    def _validate_loot(self, t, errors, warnings, item_templates):
        if t.get("roll_mode","all") not in ROLL_MODES: errors.append(f"loot {t.get('id')} invalid roll_mode")
        seen=set(); produces=False
        for e in t.get("entries") or []:
            if e.get("id") in seen: errors.append(f"loot {t.get('id')} duplicate entry {e.get('id')}")
            seen.add(e.get("id")); produces |= (e.get("reward_type","item")=="item")
            if float(e.get("chance",1) or 0) < 0 or float(e.get("chance",1) or 0) > 1: errors.append(f"loot {t.get('id')} invalid chance")
            if int(e.get("minimum_quantity",1) or 1) > int(e.get("maximum_quantity",e.get("minimum_quantity",1)) or 1): errors.append(f"loot {t.get('id')} invalid quantity bounds")
            if item_templates and e.get("item_template_id") and e.get("item_template_id") not in item_templates: errors.append(f"loot {t.get('id')} unknown item {e.get('item_template_id')}")
        if not produces: warnings.append(f"loot table {t.get('id')} never produces an item")
    def _detect_cycle(self, tid, stack, errors):
        if tid in stack: errors.append("loot table recursion cycle: "+" -> ".join(stack+[tid])); return
        t=self.get("loot_tables", tid) or {}
        for n in t.get("nested_table_ids") or []: self._detect_cycle(str(n), stack+[tid], errors)

class CurrencyService:
    def __init__(self, db_path: str | Path): self.db_path=Path(db_path); init_reward_schema(self.db_path)
    def award_currency(self, actor_id, currency_id, amount, source=None):
        amount=int(amount)
        if amount < 0: raise ValueError("currency award cannot be negative")
        eid=stable_id("cur", actor_id, currency_id, amount, source); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO actor_currency_events VALUES(?,?,?,?,?,?,?,?)",(eid,actor_id,currency_id,"award",amount,_json(source or {}),now,_json({})))
            if con.total_changes:
                con.execute("INSERT INTO actor_currency_balances VALUES(?,?,?,?) ON CONFLICT(actor_id,currency_id) DO UPDATE SET amount=amount+excluded.amount,updated_at=excluded.updated_at",(actor_id,currency_id,amount,now))
        return {"event_id":eid,"balance":self.get_currency_balance(actor_id,currency_id)}
    def remove_currency(self, actor_id, currency_id, amount, reason=None):
        bal=self.get_currency_balance(actor_id,currency_id); amount=int(amount)
        if amount<0 or bal<amount: raise ValueError("insufficient currency")
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_currency_balances SET amount=amount-?,updated_at=? WHERE actor_id=? AND currency_id=?",(amount,utc_now(),actor_id,currency_id))
    def get_currency_balance(self, actor_id, currency_id):
        with sqlite3.connect(self.db_path) as con:
            r=con.execute("SELECT amount FROM actor_currency_balances WHERE actor_id=? AND currency_id=?",(actor_id,currency_id)).fetchone(); return int(r[0]) if r else 0
    def get_currency_history(self, actor_id, currency_id=None):
        sql="SELECT * FROM actor_currency_events WHERE actor_id=?"+(" AND currency_id=?" if currency_id else "")+" ORDER BY created_at DESC"
        with sqlite3.connect(self.db_path) as con: return [dict(zip([c[0] for c in con.execute(sql,(actor_id,currency_id) if currency_id else (actor_id,)).description], r)) for r in con.execute(sql,(actor_id,currency_id) if currency_id else (actor_id,))]

def init_reward_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as con: con.executescript(SCHEMA_SQL)

class RewardService:
    def __init__(self, store: Any | None = None, *, db_path: str | Path | None = None, runtime: Any | None = None, content: RewardContent | None = None, world_id: str = "shattered_realms", event_bus: Any | None = None):
        self.store=store or getattr(runtime,"state_store",None); self.runtime=runtime; self.db_path=Path(db_path or getattr(self.store,"db_path",":memory:")); self.world_id=world_id or getattr(self.store,"world_id","shattered_realms"); self.content=content or RewardContent(Path("worlds")/self.world_id); self.event_bus=event_bus or getattr(runtime,"event_bus",None); init_reward_schema(self.db_path); self.currency=CurrencyService(self.db_path)
    def publish(self, name, payload):
        if self.event_bus: self.event_bus.publish(name, payload, source_system="rewards")
    def _seed(self, kind, ident, source, recipient, seed): return str(seed if seed is not None else stable_id("seed",kind,ident,source.__dict__,recipient.__dict__ if recipient else {}))
    def resolve_reward_definition(self, reward_definition_id, source, recipient, seed=None, context=None):
        source=self._source(source); recipient=self._recipient(recipient); rd=self.content.get("reward_definitions", reward_definition_id)
        if not rd: raise KeyError(f"unknown reward definition {reward_definition_id}")
        s=self._seed("reward", reward_definition_id, source, recipient, seed); pid=stable_id("rp", self.world_id,reward_definition_id,source.__dict__,recipient.__dict__,s); now=utc_now(); self.publish("reward_resolution_started", {"reward_packet_id":pid})
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO reward_packets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,source.source_type,source.source_id,source.source_instance_id,recipient.recipient_type,recipient.recipient_id,rd.get("delivery_policy","default"),"resolved",s,source.world_time,now,now,_json({"reward_definition_id":reward_definition_id,"eligibility_result":{"eligible":True},"trace":[]})))
            for e in rd.get("entries") or []: self._insert_entry(con,pid,e,reward_definition_id,e.get("id") or e.get("reward_entry_id"),s)
        self.publish("reward_resolved", {"reward_packet_id":pid}); return self.get_reward_packet(pid)
    def resolve_loot_table(self, loot_table_id, source, recipient=None, seed=None, context=None):
        source=self._source(source); recipient=self._recipient(recipient or {"recipient_type":"custom","recipient_id":""}); s=self._seed("loot",loot_table_id,source,recipient,seed); entries, trace = self._roll_table(loot_table_id, random.Random(s), [], context or {})
        pid=stable_id("rp", self.world_id,"loot",loot_table_id,source.__dict__,recipient.__dict__,s); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO reward_packets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,source.source_type,source.source_id,source.source_instance_id,recipient.recipient_type,recipient.recipient_id,"default","resolved",s,source.world_time,now,now,_json({"loot_table_id":loot_table_id,"trace":trace,"eligibility_result":{"eligible":True}})))
            for e in entries: self._insert_entry(con,pid,e, e.get("definition_id") or e.get("item_template_id") or loot_table_id, e.get("id"), s)
            con.execute("INSERT OR IGNORE INTO loot_resolution_records VALUES(?,?,?,?,?,?,?,?,?,?)",(stable_id("lr",loot_table_id,source.__dict__,s),self.world_id,loot_table_id,source.source_type,source.source_id,source.source_instance_id,s,_json(entries),now,_json({"trace":trace})))
        self.publish("loot_table_resolved", {"loot_table_id":loot_table_id,"reward_packet_id":pid}); return self.get_reward_packet(pid)
    def resolve_treasure_group(self, treasure_group_id, source, recipient=None, seed=None, context=None):
        tg=self.content.get("treasure_groups", treasure_group_id)
        if not tg: raise KeyError(f"unknown treasure group {treasure_group_id}")
        source=self._source(source); recipient=self._recipient(recipient or {"recipient_type":"custom","recipient_id":""}); s=self._seed("treasure",treasure_group_id,source,recipient,seed)
        all_entries=list(tg.get("guaranteed_rewards") or []); trace=[]
        for tid in tg.get("loot_table_ids") or []:
            entries,tr=self._roll_table(str(tid), random.Random(f"{s}:{tid}"), [], context or {}); all_entries+=entries; trace+=tr
        pid=stable_id("rp", self.world_id,"treasure",treasure_group_id,source.__dict__,recipient.__dict__,s); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO reward_packets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,source.source_type,source.source_id,source.source_instance_id,recipient.recipient_type,recipient.recipient_id,tg.get("delivery_policy","default"),"resolved",s,source.world_time,now,now,_json({"treasure_group_id":treasure_group_id,"trace":trace,"eligibility_result":{"eligible":True}})))
            for e in all_entries: self._insert_entry(con,pid,e,e.get("definition_id") or e.get("item_template_id") or treasure_group_id,e.get("id"),s)
        self.publish("treasure_group_resolved", {"treasure_group_id":treasure_group_id,"reward_packet_id":pid}); return self.get_reward_packet(pid)
    def _roll_table(self, tid, rng, stack, context):
        if tid in stack: raise ValueError("loot table recursion cycle: "+" -> ".join(stack+[tid]))
        t=self.content.get("loot_tables",tid)
        if not t: raise KeyError(f"unknown loot table {tid}")
        entries=sorted(t.get("entries") or [], key=lambda e:str(e.get("id",""))); mode=t.get("roll_mode","all"); out=[]; trace=[]
        guaranteed=[e for e in entries if e.get("guaranteed")]
        pool=[e for e in entries if not e.get("guaranteed")]
        def add(e, why):
            qmin=int(e.get("minimum_quantity", e.get("quantity",1)) or 1); qmax=int(e.get("maximum_quantity", qmin) or qmin); q=rng.randint(qmin,qmax) if qmax>qmin else qmin
            out.append({**e,"reward_type":e.get("reward_type","item"),"definition_id":e.get("definition_id") or e.get("item_template_id") or e.get("currency_id"),"quantity":q}); trace.append({"entry_id":e.get("id"),"selected":True,"reason":why,"quantity":q})
        if mode in {"all","explicit_sequence"}: [add(e,"all") for e in entries]
        elif mode=="chance_each":
            for e in entries:
                roll=rng.random(); ok=e.get("guaranteed") or roll <= float(e.get("chance",1) or 0); trace.append({"entry_id":e.get("id"),"roll":roll,"chance":e.get("chance",1),"selected":ok});
                if ok: add(e,"chance_each")
        else:
            [add(e,"guaranteed") for e in guaranteed]
            count=max(1,int(t.get("roll_count",1) or 1)) if mode in {"weighted_many","guaranteed_plus_weighted"} else 1
            for _ in range(count):
                total=sum(max(0,float(e.get("weight",1) or 0)) for e in pool)
                if total<=0: break
                pick=rng.random()*total; acc=0
                for e in pool:
                    acc+=max(0,float(e.get("weight",1) or 0))
                    if pick<=acc: add(e,"weighted"); break
        for nested in t.get("nested_table_ids") or []:
            ne,nt=self._roll_table(str(nested),rng,stack+[tid],context); out+=ne; trace+=nt
        return out, trace
    def _insert_entry(self, con, pid, e, definition_id, source_rule_id, seed):
        typ=e.get("reward_type") or e.get("type") or ("currency" if e.get("currency_id") else "item")
        eid=stable_id("re", pid, source_rule_id, typ, definition_id, e)
        qty=int(e.get("quantity", e.get("amount",1)) or 1)
        val={"item_template_id":e.get("item_template_id") or (definition_id if typ=="item" else ""),"currency_id":e.get("currency_id") or (definition_id if typ=="currency" else ""),"amount":e.get("amount",qty),"seed":seed, **dict(e.get("resolved_value") or {})}
        con.execute("INSERT OR IGNORE INTO reward_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,pid,typ,definition_id,qty,_json(val),_json(e.get("recipient_override")),_json(e.get("destination_override")),"pending","",source_rule_id or "",_json(e.get("metadata",{}))))
    def deliver_reward_packet(self, reward_packet_id):
        pkt=self.get_reward_packet(reward_packet_id)
        if not pkt or pkt["status"] in {"cancelled","expired"}: return pkt
        self.publish("reward_delivery_started", {"reward_packet_id":reward_packet_id}); results=[]
        for e in pkt["resolved_entries"]:
            if e["delivery_status"]=="delivered": continue
            results.append(self._deliver_entry(pkt,e))
        entries=self.get_reward_packet(reward_packet_id)["resolved_entries"]; status="delivered" if all(x["delivery_status"]=="delivered" for x in entries) else ("partially_delivered" if any(x["delivery_status"]=="delivered" for x in entries) else "failed")
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE reward_packets SET status=?,updated_at=? WHERE reward_packet_id=?",(status,utc_now(),reward_packet_id))
        self.publish("reward_packet_delivered" if status=="delivered" else "reward_packet_partially_delivered", {"reward_packet_id":reward_packet_id,"status":status}); return self.get_reward_packet(reward_packet_id)
    retry_reward_delivery = deliver_reward_packet
    def _deliver_entry(self,pkt,e):
        typ=e["reward_type"]; val=e["resolved_value"]; dest="actor_inventory"; did=pkt["recipient_id"]; result="delivered"; meta={}
        try:
            if typ=="item": meta=self._deliver_item(pkt,e); dest=meta.get("destination_type",dest); did=meta.get("destination_id",did); self.publish("item_reward_created", meta)
            elif typ=="currency": meta=self.currency.award_currency(pkt["recipient_id"], val.get("currency_id") or e["definition_id"], int(val.get("amount",e["quantity"])), {"reward_packet_id":pkt["reward_packet_id"],"reward_entry_id":e["reward_entry_id"]}); dest="actor_currency"; self.publish("currency_reward_awarded", meta)
            elif typ=="experience": meta=self._award_xp(pkt,e); dest="actor_progression"; self.publish("progression_reward_awarded", meta)
            elif typ in ADVANCEMENT_CURRENCIES: meta=self._grant_advancement(pkt,e,typ); dest="actor_progression"; self.publish("progression_reward_awarded", meta)
            elif typ in {"ability","ability_rank"}: meta=self._grant_ability(pkt,e,typ); dest="actor_progression"; self.publish("ability_reward_granted", meta)
            elif typ=="effect": meta={"placeholder":True,"effect_id":e["definition_id"]}; dest="actor_effects"; self.publish("effect_reward_applied", meta)
            elif typ in {"title","accolade"}: meta=self._grant_achievement_recognition(pkt,e,typ); dest="actor_achievements"; self.publish(f"{typ}_reward_granted", meta)
            else: raise ValueError(f"unsupported reward type {typ}")
        except Exception as ex:
            result="failed"; meta={"error":str(ex)}
        eid=stable_id("de", e["reward_entry_id"], "deliver")
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO reward_delivery_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,pkt["reward_packet_id"],e["reward_entry_id"],pkt["recipient_type"],pkt["recipient_id"],dest,did,"deliver",result,pkt.get("resolved_world_time"),utc_now(),_json(meta)))
            con.execute("UPDATE reward_entries SET delivery_status=?,failure_reason=? WHERE reward_entry_id=?",("delivered" if result=="delivered" else "failed", meta.get("error","") if result=="failed" else "", e["reward_entry_id"]))
        self.publish("reward_entry_delivered" if result=="delivered" else "reward_entry_failed", {"reward_entry_id":e["reward_entry_id"], **meta}); return meta
    def _deliver_item(self,pkt,e):
        val=e["resolved_value"]; template_id=val.get("item_template_id") or e["definition_id"]; qty=max(1,int(e["quantity"])); dest=e.get("destination_override") or {}; owner_type=dest.get("destination_type") or ("corpse" if pkt["recipient_type"]=="corpse" else "character"); owner_id=dest.get("destination_id") or pkt["recipient_id"]
        existing=self._created_items(e["reward_entry_id"])
        if existing: return {"created_item_ids":existing,"destination_type":owner_type,"destination_id":owner_id,"idempotent":True}
        created=[]
        if self.runtime and hasattr(self.runtime,"spawn_item"):
            tmpl=getattr(self.runtime,"item_templates",{}).get(template_id,{})
            n=1 if tmpl.get("stackable") else qty; stack=qty if tmpl.get("stackable") else 1
            for _ in range(n): created.append(self.runtime.spawn_item(template_id, owner_type if owner_type!="character" else "character", owner_id=owner_id, stack_count=stack, custom_flags={"reward_packet_id":pkt["reward_packet_id"],"reward_entry_id":e["reward_entry_id"]})["instance_id"])
        elif self.store and hasattr(self.store,"create_item_instance"):
            for i in range(qty):
                iid=stable_id("item", e["reward_entry_id"], i); self.store.create_item_instance(iid, template_id, current_owner=owner_id, flags=["reward"], creator="RewardService"); created.append(iid)
        else: raise RuntimeError("no canonical item instance API available")
        return {"created_item_ids":created,"destination_type":owner_type,"destination_id":owner_id}
    def _created_items(self, entry_id):
        out=[]
        with sqlite3.connect(self.db_path) as con:
            try: out += [r[0] for r in con.execute("SELECT instance_id FROM item_instances WHERE json_extract(custom_flags,'$.reward_entry_id')=? AND destroyed_at IS NULL",(entry_id,))]
            except Exception: pass
            try: out += [r[0] for r in con.execute("SELECT unique_id FROM item_instances WHERE flags_json LIKE ?",(f"%{entry_id}%",))]
            except Exception: pass
        return out
    def _award_xp(self,pkt,e):
        from engine.progression import ProgressionService
        return ProgressionService(self.store).award_experience(pkt["recipient_id"], int(e["quantity"]), "reward", pkt["reward_packet_id"], "reward packet")
    def _grant_advancement(self,pkt,e,currency):
        from engine.progression import ProgressionService
        return {"balance": ProgressionService(self.store).grant_currency(pkt["recipient_id"], currency, int(e["quantity"]), "reward", pkt["reward_packet_id"], "reward packet")}
    def _grant_ability(self,pkt,e,typ):
        from engine.progression import ProgressionService
        ps=ProgressionService(self.store); return ps.increase_ability_rank(pkt["recipient_id"], e["definition_id"]) if typ=="ability_rank" else ps.learn_ability(pkt["recipient_id"], e["definition_id"], {"source":"reward","reward_packet_id":pkt["reward_packet_id"]})
    def _grant_achievement_recognition(self,pkt,e,typ):
        from engine.achievements import AchievementService
        svc=AchievementService(self.db_path, world_id=self.world_id, event_bus=self.event_bus)
        if typ=="title":
            oid=svc.grant_title(pkt["recipient_id"], e["definition_id"], "reward", pkt["reward_packet_id"], pkt.get("resolved_world_time"))
            return {"actor_title_id":oid,"title_id":e["definition_id"]}
        oid=svc.grant_accolade(pkt["recipient_id"], e["definition_id"], "reward", pkt["reward_packet_id"], pkt.get("resolved_world_time"))
        return {"actor_accolade_id":oid,"accolade_id":e["definition_id"]}

    def cancel_reward_packet(self, reward_packet_id, reason=None):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE reward_packets SET status='cancelled',updated_at=?,metadata_json=json_set(COALESCE(metadata_json,'{}'),'$.cancel_reason',?) WHERE reward_packet_id=?",(utc_now(),reason or "",reward_packet_id))
        self.publish("reward_packet_cancelled", {"reward_packet_id":reward_packet_id,"reason":reason}); return self.get_reward_packet(reward_packet_id)
    def get_reward_packet(self, reward_packet_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM reward_packets WHERE reward_packet_id=?",(reward_packet_id,)).fetchone()
            if not r: return None
            pkt=dict(r); pkt["metadata"]=_loads(pkt.pop("metadata_json"),{}); pkt["eligibility_result"]=pkt["metadata"].get("eligibility_result",{})
            entries=[]
            for er in con.execute("SELECT * FROM reward_entries WHERE reward_packet_id=? ORDER BY reward_entry_id",(reward_packet_id,)):
                d=dict(er); d["resolved_value"]=_loads(d.pop("resolved_value_json"),{}); d["recipient_override"]=_loads(d.pop("recipient_override_json"),{}); d["destination_override"]=_loads(d.pop("destination_override_json"),{}); d["metadata"]=_loads(d.pop("metadata_json"),{}); entries.append(d)
            pkt["resolved_entries"]=entries; return pkt
    def trace_reward_resolution(self, reward_packet_id): return self.get_reward_packet(reward_packet_id)
    def trace_loot_table(self, loot_table_id, seed=None, context=None):
        entries, trace = self._roll_table(loot_table_id, random.Random(str(seed if seed is not None else stable_id("trace",loot_table_id))), [], context or {})
        return {"loot_table_id":loot_table_id,"seed":seed,"entries":entries,"trace":trace}
    def _source(self, x):
        if isinstance(x, RewardSource): return x
        return RewardSource(str(x.get("source_type","custom")), str(x.get("source_id","")), str(x.get("source_instance_id","")), str(x.get("world_id",self.world_id)), x.get("world_time"), dict(x.get("metadata",{})))
    def _recipient(self, x):
        if isinstance(x, RewardRecipient): return x
        return RewardRecipient(str(x.get("recipient_type","actor")), str(x.get("recipient_id","")), dict(x.get("metadata",{})))
