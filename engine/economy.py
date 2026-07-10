"""Phase 7B canonical economy foundations.

This module owns currency balances, immutable ledger rows, quotes,
transactions, shop stock, services, repair foundations, bank accounts, and
conversion helpers.  It deliberately stays conservative: all money movement is
integer minor units, every mutation appends ledger entries, and item movement is
performed through the runtime/store API when one is supplied.
"""
from __future__ import annotations

import hashlib, json, re, sqlite3, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
CURRENCY_TYPES = {"coin","token","faction_placeholder","profession_placeholder","event","premium_placeholder","custom"}
OWNER_TYPES = {"actor","character","account_placeholder","shop","organization_placeholder","bank_account","treasury_placeholder","custom"}
TRANSACTION_TYPES = {"purchase","sale","service","repair","deposit","withdrawal","conversion","refund","admin","custom"}
TRANSACTION_STATUSES = {"quoted","pending","committing","completed","partially_completed","failed","cancelled","refunded","expired"}
QUOTE_STATUSES = {"active","accepted","expired","cancelled","invalidated"}
LEDGER_OPERATIONS = {"credit","debit","hold","release","refund","deposit","withdrawal","purchase","sale","service_fee","repair_fee","conversion","admin_adjustment","custom"}


def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def _json(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True, ensure_ascii=False)
def _loads(v: Any, default: Any=None) -> Any:
    try: return json.loads(v) if v else ({} if default is None else default)
    except Exception: return {} if default is None else default
def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
def safe_id(v: str) -> bool: return bool(v and SAFE_ID_RE.fullmatch(str(v)))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS actor_currency_balances(balance_id TEXT PRIMARY KEY,world_id TEXT,owner_type TEXT,owner_id TEXT,currency_id TEXT,balance INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,owner_type,owner_id,currency_id));
CREATE INDEX IF NOT EXISTS idx_actor_currency_owner ON actor_currency_balances(world_id,owner_type,owner_id);
CREATE TABLE IF NOT EXISTS economy_ledger_entries(ledger_entry_id TEXT PRIMARY KEY,world_id TEXT,transaction_id TEXT,entry_sequence INTEGER,owner_type TEXT,owner_id TEXT,currency_id TEXT,operation TEXT,amount INTEGER,balance_before INTEGER,balance_after INTEGER,counterparty_type TEXT,counterparty_id TEXT,source_type TEXT,source_id TEXT,reason TEXT,world_time INTEGER,created_at TEXT,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_economy_ledger_idempotent ON economy_ledger_entries(transaction_id,entry_sequence,owner_type,owner_id,currency_id,operation,amount);
CREATE INDEX IF NOT EXISTS idx_economy_ledger_owner ON economy_ledger_entries(owner_type,owner_id,currency_id,created_at);
CREATE TABLE IF NOT EXISTS economy_transactions(transaction_id TEXT PRIMARY KEY,world_id TEXT,transaction_type TEXT,buyer_type TEXT,buyer_id TEXT,seller_type TEXT,seller_id TEXT,shop_id TEXT,service_provider_id TEXT,status TEXT,quote_id TEXT,subtotal_json TEXT,fees_json TEXT,discounts_json TEXT,total_json TEXT,delivery_status TEXT,failure_reason TEXT,started_world_time INTEGER,completed_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS economy_price_quotes(quote_id TEXT PRIMARY KEY,world_id TEXT,quote_type TEXT,buyer_id TEXT,seller_id TEXT,shop_id TEXT,offer_id TEXT,item_instance_id TEXT,item_template_id TEXT,service_id TEXT,quantity INTEGER,currency_cost_json TEXT,base_price_json TEXT,modifier_trace_json TEXT,created_world_time INTEGER,expires_world_time INTEGER,status TEXT,created_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS shop_runtime_state(shop_state_id TEXT PRIMARY KEY,world_id TEXT,shop_id TEXT,enabled INTEGER,open_override TEXT,last_restock_world_time INTEGER,next_restock_world_time INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,shop_id));
CREATE TABLE IF NOT EXISTS shop_stock_entries(stock_entry_id TEXT PRIMARY KEY,world_id TEXT,shop_id TEXT,stock_definition_id TEXT,item_template_id TEXT,item_instance_id TEXT,quantity INTEGER,reserved_quantity INTEGER,available INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,shop_id,stock_definition_id,item_instance_id));
CREATE TABLE IF NOT EXISTS shop_buyback_entries(buyback_entry_id TEXT PRIMARY KEY,world_id TEXT,shop_id TEXT,seller_actor_id TEXT,item_instance_id TEXT,sale_transaction_id TEXT,buyback_price_json TEXT,expires_world_time INTEGER,available INTEGER,created_at TEXT,updated_at TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS bank_accounts(bank_account_id TEXT PRIMARY KEY,world_id TEXT,owner_type TEXT,owner_id TEXT,bank_profile_id TEXT,status TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(world_id,owner_type,owner_id,bank_profile_id));
CREATE TABLE IF NOT EXISTS bank_account_balances(balance_id TEXT PRIMARY KEY,bank_account_id TEXT,currency_id TEXT,balance INTEGER,created_at TEXT,updated_at TEXT,UNIQUE(bank_account_id,currency_id));
CREATE TABLE IF NOT EXISTS bank_transactions(bank_transaction_id TEXT PRIMARY KEY,bank_account_id TEXT,transaction_id TEXT,operation TEXT,currency_id TEXT,amount INTEGER,balance_before INTEGER,balance_after INTEGER,world_time INTEGER,created_at TEXT,metadata_json TEXT);
"""

def init_economy_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA_SQL)
        # normalize existing runtime item table for repair foundations
        cols = {r[1] for r in con.execute("PRAGMA table_info(item_instances)").fetchall()}
        for name, ddl in {"condition_current":"INTEGER DEFAULT 100","condition_maximum":"INTEGER DEFAULT 100","broken":"INTEGER DEFAULT 0","repair_count":"INTEGER DEFAULT 0","last_repaired_at":"TEXT","condition_metadata":"TEXT"}.items():
            if "item_instances" in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] and name not in cols:
                con.execute(f"ALTER TABLE item_instances ADD COLUMN {name} {ddl}")

class EconomyContent:
    collections = ["currency_profiles","shop_definitions","shop_stock_profiles","shop_buy_policies","shop_sell_policies","pricing_profiles","service_definitions","repair_profiles","bank_profiles","shop_restock_profiles","economy_message_profiles","economy_eligibility_profiles"]
    def __init__(self, world_root: str | Path="worlds/shattered_realms"):
        self.world_root=Path(world_root); self.data={c:self._load(c) for c in self.collections}
    def _load(self,c):
        for p in (self.world_root/c/f"{c}.json", self.world_root/"builder"/f"{c}.json"):
            if p.exists():
                raw=json.loads(p.read_text()); items=raw.get(c, raw) if isinstance(raw,dict) else raw
                if isinstance(items,list): return {str(x.get("id")):x for x in items if isinstance(x,dict) and x.get("id")}
                if isinstance(items,dict): return {str(k):(v|{"id":v.get("id",k)} if isinstance(v,dict) else {"id":k}) for k,v in items.items()}
        return {}
    def get(self,c,i): return self.data.get(c,{}).get(str(i or ""))
    def list(self,c): return sorted(self.data.get(c,{}).values(), key=lambda x:x.get("id",""))
    def validate(self, item_templates:set[str]|None=None):
        errors=[]; warnings=[]; item_templates=item_templates or set()
        for c, items in self.data.items():
            seen=set()
            for iid,item in items.items():
                if not safe_id(iid): errors.append(f"{c}:{iid}: unsafe id")
                if iid in seen: errors.append(f"{c}: duplicate id {iid}")
                seen.add(iid)
                if c=="currency_profiles":
                    if item.get("currency_type","coin") not in CURRENCY_TYPES: errors.append(f"currency {iid} invalid type")
                    if int(item.get("precision",0) or 0) < 0: errors.append(f"currency {iid} invalid precision")
                    if item.get("maximum_balance") not in (None,"") and int(item.get("maximum_balance")) < int(item.get("minimum_balance",0) or 0): errors.append(f"currency {iid} invalid bounds")
                    if iid not in {"gold","silver","copper"}: warnings.append(f"currency {iid} may be unused")
                if c=="shop_stock_profiles":
                    if item.get("stock_mode","infinite_template") not in {"infinite_template","finite_template","runtime_inventory","hybrid","custom"}: errors.append(f"stock {iid} invalid stock_mode")
                    if not item.get("entries"): warnings.append(f"stock {iid} has no entries")
                    for e in item.get("entries") or []:
                        if item_templates and e.get("item_template_id") and e.get("item_template_id") not in item_templates: errors.append(f"stock {iid} unknown item {e.get('item_template_id')}")
                        if int(e.get("quantity",0) or 0) < 0: errors.append(f"stock {iid} invalid quantity")
                if c=="pricing_profiles":
                    if item.get("rounding_policy","currency_precision") not in {"down","up","nearest","currency_precision","custom"}: errors.append(f"pricing {iid} invalid rounding")
                    if int(item.get("minimum_price",0) or 0) < 0: errors.append(f"pricing {iid} negative minimum")
                if c=="bank_profiles" and not item.get("room_ids") and not item.get("provider_actor_ids"): warnings.append(f"bank {iid} has no assigned room/provider")
        return {"errors":errors,"warnings":warnings}

@dataclass(frozen=True)
class PriceQuote:
    quote_id:str; quote_type:str; total:dict[str,int]; status:str="active"; trace:dict[str,Any]=field(default_factory=dict)

class EconomyService:
    def __init__(self, db_path: str | Path, world_id: str="shattered_realms", world_root: str | Path|None=None, event_bus: Any=None, runtime: Any=None):
        self.db_path=Path(db_path); self.world_id=world_id; self.event_bus=event_bus; self.runtime=runtime; init_economy_schema(self.db_path); self.content=EconomyContent(world_root or f"worlds/{world_id}")
    def publish(self,event,payload):
        if self.event_bus and hasattr(self.event_bus,"publish"):
            try: self.event_bus.publish(event,payload,source_system="economy")
            except TypeError: self.event_bus.publish(event,payload)
    def _balance_row(self, con, owner_type, owner_id, currency_id):
        now=utc_now(); bid=stable_id("bal",self.world_id,owner_type,owner_id,currency_id)
        con.execute("INSERT OR IGNORE INTO actor_currency_balances VALUES(?,?,?,?,?,?,?,?,?)",(bid,self.world_id,owner_type,owner_id,currency_id,0,now,now,_json({})))
        return con.execute("SELECT * FROM actor_currency_balances WHERE balance_id=?",(bid,)).fetchone()
    def get_currency_balance(self, owner_type, owner_id, currency_id):
        with sqlite3.connect(self.db_path) as con:
            return int(self._balance_row(con,owner_type,owner_id,currency_id)[5] or 0)
    def get_currency_balances(self, owner_type, owner_id):
        with sqlite3.connect(self.db_path) as con:
            return {r[4]:int(r[5] or 0) for r in con.execute("SELECT * FROM actor_currency_balances WHERE world_id=? AND owner_type=? AND owner_id=?",(self.world_id,owner_type,owner_id))}
    def _ledger(self, con, transaction_id, seq, owner_type, owner_id, currency_id, operation, amount, before, after, counterparty_type="", counterparty_id="", source_type="", source_id="", reason="", world_time=None, metadata=None):
        lid=stable_id("led",transaction_id,seq,owner_type,owner_id,currency_id,operation,amount,before,after); now=utc_now()
        con.execute("INSERT OR IGNORE INTO economy_ledger_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(lid,self.world_id,transaction_id,int(seq),owner_type,owner_id,currency_id,operation,int(amount),int(before),int(after),counterparty_type,counterparty_id,source_type,source_id,reason,world_time,now,_json(metadata or {})))
        return lid
    def _mutate(self, con, owner_type, owner_id, currency_id, delta, operation, transaction_id=None, seq=1, **kw):
        row=self._balance_row(con,owner_type,owner_id,currency_id); before=int(row[5] or 0); after=before+int(delta)
        profile=self.content.get("currency_profiles",currency_id) or {}
        if after < int(profile.get("minimum_balance",0) or 0) and not bool(profile.get("allow_negative",False)): raise ValueError("insufficient funds")
        if profile.get("maximum_balance") not in (None,"") and after > int(profile.get("maximum_balance")): raise ValueError("maximum balance exceeded")
        con.execute("UPDATE actor_currency_balances SET balance=?,updated_at=? WHERE balance_id=?",(after,utc_now(),row[0]))
        tid=transaction_id or stable_id("txn",operation,owner_type,owner_id,currency_id,delta,kw.get("source_id",""))
        self._ledger(con,tid,seq,owner_type,owner_id,currency_id,operation,abs(int(delta)),before,after,**kw)
        self.publish("currency_balance_changed", {"owner_type":owner_type,"owner_id":owner_id,"currency_id":currency_id,"balance_before":before,"balance_after":after,"transaction_id":tid})
        self.publish("currency_credited" if delta>=0 else "currency_debited", {"owner_id":owner_id,"currency_id":currency_id,"amount":abs(int(delta))})
        return after
    def credit_currency(self, owner_type, owner_id, currency_id, amount, **kw):
        with sqlite3.connect(self.db_path) as con: return self._mutate(con,owner_type,owner_id,currency_id,int(amount),kw.pop("operation","credit"),**kw)
    def debit_currency(self, owner_type, owner_id, currency_id, amount, **kw):
        with sqlite3.connect(self.db_path) as con: return self._mutate(con,owner_type,owner_id,currency_id,-int(amount),kw.pop("operation","debit"),**kw)
    def set_currency_balance(self, owner_type, owner_id, currency_id, amount, reason="set", **kw):
        with sqlite3.connect(self.db_path) as con:
            before=self.get_currency_balance(owner_type,owner_id,currency_id); return self._mutate(con,owner_type,owner_id,currency_id,int(amount)-before,"admin_adjustment",reason=reason,**kw)
    def transfer_currency(self, from_type, from_id, to_type, to_id, currency_id, amount, transaction_id=None, reason="transfer", **kw):
        tid=transaction_id or stable_id("txn","transfer",from_type,from_id,to_type,to_id,currency_id,amount,reason); amt=int(amount)
        with sqlite3.connect(self.db_path) as con:
            self._mutate(con,from_type,from_id,currency_id,-amt,"debit",tid,1,counterparty_type=to_type,counterparty_id=to_id,reason=reason,**kw)
            self._mutate(con,to_type,to_id,currency_id,amt,"credit",tid,2,counterparty_type=from_type,counterparty_id=from_id,reason=reason,**kw)
        self.publish("currency_transferred", {"transaction_id":tid,"currency_id":currency_id,"amount":amt,"from_id":from_id,"to_id":to_id}); return tid
    def trace_currency_balance(self, owner_type, owner_id, currency_id=None, limit=50):
        q="SELECT * FROM economy_ledger_entries WHERE owner_type=? AND owner_id=?"; p=[owner_type,owner_id]
        if currency_id: q+=" AND currency_id=?"; p.append(currency_id)
        q+=" ORDER BY created_at DESC, entry_sequence DESC LIMIT ?"; p.append(int(limit))
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute(q,p)]
    def create_transaction(self, transaction_type, buyer_type="", buyer_id="", seller_type="", seller_id="", total=None, quote_id="", status="pending", **kw):
        if transaction_type not in TRANSACTION_TYPES: raise ValueError("invalid transaction type")
        tid=kw.pop("transaction_id", stable_id("txn",transaction_type,buyer_type,buyer_id,seller_type,seller_id,quote_id,total,kw)); now=utc_now()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO economy_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,self.world_id,transaction_type,buyer_type,buyer_id,seller_type,seller_id,kw.get("shop_id",""),kw.get("service_provider_id",""),status,quote_id,_json(total or {}),_json(kw.get("fees",{})),_json(kw.get("discounts",{})),_json(total or {}),kw.get("delivery_status","pending"),"",kw.get("world_time"),None,now,now,_json(kw.get("metadata",{}))))
        self.publish("economy_transaction_started", {"transaction_id":tid,"transaction_type":transaction_type}); return tid
    def complete_transaction(self, transaction_id, status="completed", failure_reason=""):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE economy_transactions SET status=?,failure_reason=?,completed_world_time=COALESCE(completed_world_time,0),updated_at=? WHERE transaction_id=? AND status!='completed'",(status,failure_reason,utc_now(),transaction_id))
        self.publish("economy_transaction_completed" if status=="completed" else "economy_transaction_failed", {"transaction_id":transaction_id,"status":status,"failure_reason":failure_reason})
    def get_transaction(self, transaction_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM economy_transactions WHERE transaction_id=?",(transaction_id,)).fetchone(); return dict(r) if r else None
    def quote_price(self, quote_type, buyer_id="", seller_id="", shop_id="", offer_id="", item_instance_id="", item_template_id="", service_id="", quantity=1, base_price=None, currency_id="gold", expires_world_time=60, formula_id=None, modifiers=None, **kw):
        qty=max(1,int(quantity)); base=int((base_price or {currency_id:0}).get(currency_id, base_price if isinstance(base_price,int) else 0) or 0); mods=modifiers or {}; price=base*qty
        if "markup" in mods: price = price * (100 + int(mods["markup"])) // 100
        if "markdown" in mods: price = price * max(0,100 - int(mods["markdown"])) // 100
        minimum=int(mods.get("minimum_price",0) or 0); maximum=mods.get("maximum_price")
        if price < minimum: price=minimum
        if maximum not in (None,""): price=min(price,int(maximum))
        qid=stable_id("quote",self.world_id,quote_type,buyer_id,seller_id,shop_id,offer_id,item_instance_id,item_template_id,service_id,qty,price,kw.get("world_time",0)); now=utc_now(); trace={"formula_id":formula_id or f"{quote_type}_price_v1","inputs":{"base_price":base,"quantity":qty},"modifiers":mods,"final":price,"formula_engine":"FormulaEngine"}
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO economy_price_quotes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(qid,self.world_id,quote_type,buyer_id,seller_id,shop_id,offer_id,item_instance_id,item_template_id,service_id,qty,_json({currency_id:price}),_json({currency_id:base}),_json(trace),kw.get("world_time",0),expires_world_time,"active",now,_json(kw.get("metadata",{}))))
        self.publish("economy_quote_created", {"quote_id":qid,"quote_type":quote_type,"total":{currency_id:price}}); return PriceQuote(qid,quote_type,{currency_id:price},"active",trace)
    def get_quote(self, quote_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM economy_price_quotes WHERE quote_id=?",(quote_id,)).fetchone(); return dict(r) if r else None
    def cancel_quote(self, actor_id, quote_id):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE economy_price_quotes SET status='cancelled' WHERE quote_id=? AND status='active'",(quote_id,)); return True
    cancel_sale_quote = cancel_quote
    def initialize_shop_stock(self, shop_id, stock_profile_id=None):
        shop=self.content.get("shop_definitions",shop_id) or {}; sp=self.content.get("shop_stock_profiles", stock_profile_id or shop.get("stock_profile_id")) or {}; now=utc_now(); sid=stable_id("shopstate",self.world_id,shop_id)
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO shop_runtime_state VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,shop_id,1,"",0,0,now,now,_json({})))
            for e in sp.get("entries") or []:
                eid=stable_id("stock",self.world_id,shop_id,e.get("id"),e.get("item_template_id"),"")
                con.execute("INSERT OR IGNORE INTO shop_stock_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,self.world_id,shop_id,e.get("id"),e.get("item_template_id",""),"",int(e.get("quantity",0) or 0),0,1,now,now,_json(e)))
        return self.list_shop_stock(shop_id)
    def list_shop_stock(self, shop_id):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM shop_stock_entries WHERE world_id=? AND shop_id=? AND available=1 ORDER BY stock_definition_id",(self.world_id,shop_id))]
    def reserve_stock(self, shop_id, stock_entry_id, quantity=1):
        qty=int(quantity)
        with sqlite3.connect(self.db_path) as con:
            r=con.execute("SELECT quantity,reserved_quantity FROM shop_stock_entries WHERE stock_entry_id=?",(stock_entry_id,)).fetchone()
            if not r or int(r[0])-int(r[1]) < qty: raise ValueError("stock unavailable")
            con.execute("UPDATE shop_stock_entries SET reserved_quantity=reserved_quantity+?,updated_at=? WHERE stock_entry_id=?",(qty,utc_now(),stock_entry_id))
        self.publish("shop_stock_reserved", {"shop_id":shop_id,"stock_entry_id":stock_entry_id,"quantity":qty}); return True
    def release_stock(self, shop_id, stock_entry_id, quantity=1):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE shop_stock_entries SET reserved_quantity=MAX(0,reserved_quantity-?),updated_at=? WHERE stock_entry_id=?",(int(quantity),utc_now(),stock_entry_id))
        self.publish("shop_stock_released", {"shop_id":shop_id,"stock_entry_id":stock_entry_id}); return True
    def quote_purchase(self, actor_id, shop_id, offer, quantity=1):
        self.initialize_shop_stock(shop_id); stock=offer if isinstance(offer,dict) else next((s for s in self.list_shop_stock(shop_id) if s["stock_definition_id"]==str(offer) or s["item_template_id"]==str(offer) or s["stock_entry_id"]==str(offer)), None)
        if not stock: raise ValueError("unknown offer")
        self.reserve_stock(shop_id, stock["stock_entry_id"], quantity)
        price=_loads(stock.get("metadata_json"),{}).get("price_override") or {"gold":10}
        return self.quote_price("purchase", buyer_id=actor_id, seller_id=shop_id, shop_id=shop_id, offer_id=stock["stock_definition_id"], item_template_id=stock["item_template_id"], quantity=quantity, base_price=price, currency_id=next(iter(price)))
    def confirm_purchase(self, actor_id, quote_id):
        q=self.get_quote(quote_id); 
        if not q or q["status"]!="active": return self.get_transaction(stable_id("txn","purchase",actor_id,quote_id))
        total=_loads(q["currency_cost_json"]); currency,amount=next(iter(total.items())); tid=self.create_transaction("purchase","actor",actor_id,"shop",q["shop_id"],total,quote_id,shop_id=q["shop_id"])
        try:
            self.transfer_currency("actor",actor_id,"shop",q["shop_id"],currency,int(amount),tid,"purchase")
            if self.runtime and hasattr(self.runtime,"spawn_item"): self.runtime.spawn_item(q["item_template_id"],"character",actor_id,custom_flags={"economy_transaction_id":tid})
            with sqlite3.connect(self.db_path) as con: con.execute("UPDATE economy_price_quotes SET status='accepted' WHERE quote_id=?",(quote_id,)); con.execute("UPDATE shop_stock_entries SET quantity=MAX(0,quantity-?),reserved_quantity=MAX(0,reserved_quantity-?),updated_at=? WHERE shop_id=? AND stock_definition_id=?",(q["quantity"],q["quantity"],utc_now(),q["shop_id"],q["offer_id"]))
            self.complete_transaction(tid); self.publish("shop_item_purchased", {"transaction_id":tid,"actor_id":actor_id,"shop_id":q["shop_id"]}); return self.get_transaction(tid)
        except Exception as e:
            self.complete_transaction(tid,"failed",str(e)); raise
    def quote_sale(self, actor_id, shop_id, item_instance_id, quantity=1):
        return self.quote_price("sale", buyer_id=shop_id, seller_id=actor_id, shop_id=shop_id, item_instance_id=item_instance_id, quantity=quantity, base_price={"gold":5}, currency_id="gold", formula_id="shop_sell_price_v1")
    def confirm_sale(self, actor_id, quote_id):
        q=self.get_quote(quote_id); total=_loads(q["currency_cost_json"]); currency,amount=next(iter(total.items())); tid=self.create_transaction("sale","shop",q["shop_id"],"actor",actor_id,total,quote_id,shop_id=q["shop_id"])
        if self.runtime and hasattr(self.runtime,"transfer_item"): self.runtime.transfer_item(q["item_instance_id"], to_owner=("shop",q["shop_id"]), reason="sale")
        self.credit_currency("actor",actor_id,currency,int(amount),transaction_id=tid,operation="sale",counterparty_type="shop",counterparty_id=q["shop_id"],reason="sale")
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE economy_price_quotes SET status='accepted' WHERE quote_id=?",(quote_id,)); con.execute("INSERT OR IGNORE INTO shop_buyback_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(stable_id("buyback",q["shop_id"],actor_id,q["item_instance_id"],tid),self.world_id,q["shop_id"],actor_id,q["item_instance_id"],tid,q["currency_cost_json"],0,1,utc_now(),utc_now(),_json({})))
        self.complete_transaction(tid); self.publish("shop_item_sold", {"transaction_id":tid}); self.publish("shop_buyback_created", {"transaction_id":tid}); return self.get_transaction(tid)
    def ensure_bank_account(self, owner_type, owner_id, bank_profile_id="default_bank"):
        bid=stable_id("bank",self.world_id,owner_type,owner_id,bank_profile_id); now=utc_now()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO bank_accounts VALUES(?,?,?,?,?,?,?,?,?)",(bid,self.world_id,owner_type,owner_id,bank_profile_id,"active",now,now,_json({})))
        self.publish("bank_account_created", {"bank_account_id":bid,"owner_id":owner_id}); return bid
    def _bank_bal(self, con, bank_account_id, currency_id):
        bid=stable_id("bbal",bank_account_id,currency_id); now=utc_now(); con.execute("INSERT OR IGNORE INTO bank_account_balances VALUES(?,?,?,?,?,?)",(bid,bank_account_id,currency_id,0,now,now)); return con.execute("SELECT balance FROM bank_account_balances WHERE balance_id=?",(bid,)).fetchone()[0]
    def deposit(self, actor_id, amount, currency_id, bank_profile_id="default_bank"):
        acct=self.ensure_bank_account("actor",actor_id,bank_profile_id); tid=self.create_transaction("deposit","actor",actor_id,"bank_account",acct,{currency_id:int(amount)})
        with sqlite3.connect(self.db_path) as con:
            self._mutate(con,"actor",actor_id,currency_id,-int(amount),"deposit",tid,1,counterparty_type="bank_account",counterparty_id=acct,reason="deposit")
            before=int(self._bank_bal(con,acct,currency_id)); after=before+int(amount); con.execute("UPDATE bank_account_balances SET balance=?,updated_at=? WHERE bank_account_id=? AND currency_id=?",(after,utc_now(),acct,currency_id)); con.execute("INSERT OR IGNORE INTO bank_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?)",(stable_id("btxn",tid),acct,tid,"deposit",currency_id,int(amount),before,after,0,utc_now(),_json({})))
        self.complete_transaction(tid); self.publish("bank_deposit_completed", {"transaction_id":tid}); return tid
    def withdraw(self, actor_id, amount, currency_id, bank_profile_id="default_bank"):
        acct=self.ensure_bank_account("actor",actor_id,bank_profile_id); tid=self.create_transaction("withdrawal","bank_account",acct,"actor",actor_id,{currency_id:int(amount)})
        with sqlite3.connect(self.db_path) as con:
            before=int(self._bank_bal(con,acct,currency_id));
            if before < int(amount): raise ValueError("insufficient bank funds")
            after=before-int(amount); con.execute("UPDATE bank_account_balances SET balance=?,updated_at=? WHERE bank_account_id=? AND currency_id=?",(after,utc_now(),acct,currency_id)); con.execute("INSERT OR IGNORE INTO bank_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?)",(stable_id("btxn",tid),acct,tid,"withdrawal",currency_id,int(amount),before,after,0,utc_now(),_json({})))
            self._mutate(con,"actor",actor_id,currency_id,int(amount),"withdrawal",tid,1,counterparty_type="bank_account",counterparty_id=acct,reason="withdrawal")
        self.complete_transaction(tid); self.publish("bank_withdrawal_completed", {"transaction_id":tid}); return tid
    def bank_balance(self, actor_id, currency_id, bank_profile_id="default_bank"):
        acct=self.ensure_bank_account("actor",actor_id,bank_profile_id)
        with sqlite3.connect(self.db_path) as con: return int(self._bank_bal(con,acct,currency_id))
    def convert_currency(self, actor_id, amount, from_currency, to_currency):
        fp=self.content.get("currency_profiles",from_currency) or {}; tp=self.content.get("currency_profiles",to_currency) or {}
        if fp.get("conversion_group") != tp.get("conversion_group") or not fp.get("conversion_group"): raise ValueError("incompatible currencies")
        received=int(int(amount)*int(fp.get("conversion_rate",1))/int(tp.get("conversion_rate",1)))
        tid=self.create_transaction("conversion","actor",actor_id,"actor",actor_id,{from_currency:int(amount),to_currency:received})
        self.debit_currency("actor",actor_id,from_currency,int(amount),transaction_id=tid,operation="conversion",reason="conversion")
        self.credit_currency("actor",actor_id,to_currency,received,transaction_id=tid,operation="conversion",seq=2,reason="conversion")
        self.complete_transaction(tid); self.publish("currency_converted", {"transaction_id":tid,"received":received}); return {"transaction_id":tid,"received":received,"currency_id":to_currency}
    def identify_item(self, item):
        tmpl=item.get("template",{}) if isinstance(item,dict) else {}; return {"name": item.get("name") if isinstance(item,dict) else str(item), "template_id": item.get("template_id") if isinstance(item,dict) else "", "type": tmpl.get("item_type") or tmpl.get("type"), "value": tmpl.get("value",0), "condition": item.get("condition") if isinstance(item,dict) else None}
    def repair_item_condition(self, item_instance_id, owner_id, restore_to=100):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE item_instances SET condition_current=?,broken=0,repair_count=COALESCE(repair_count,0)+1,last_repaired_at=?,condition_metadata=? WHERE instance_id=?",(int(restore_to),utc_now(),_json({"source":"economy_repair"}),item_instance_id))
        self.publish("item_repaired", {"item_instance_id":item_instance_id}); return True
