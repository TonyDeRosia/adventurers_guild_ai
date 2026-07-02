"""SQLite persistence for MUD V2 runtime state and NPC memory."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mud_state_db_path(campaign_id: str, user_data_dir: Path | None = None, saves_dir: Path | None = None) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", campaign_id or "campaign").strip("._") or "campaign"
    base = Path(user_data_dir) if user_data_dir else (Path(saves_dir).parent if saves_dir else Path(".") / "user_data")
    return base / "saves" / "mud_v2" / f"{safe}.sqlite"


class MUDStateStore:
    def __init__(self, campaign_id: str, world_id: str = "", db_path: Path | None = None, user_data_dir: Path | None = None, saves_dir: Path | None = None) -> None:
        self.campaign_id = campaign_id
        self.world_id = world_id
        self.db_path = Path(db_path) if db_path is not None else mud_state_db_path(campaign_id, user_data_dir, saves_dir)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def initialize(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA_SQL)
            con.execute("INSERT OR REPLACE INTO campaign_meta(key,value) VALUES(?,?)", ("campaign_id", self.campaign_id))
            if self.world_id:
                con.execute("INSERT OR REPLACE INTO campaign_meta(key,value) VALUES(?,?)", ("world_id", self.world_id))

    def _json(self, value: Any) -> str: return json.dumps(value if value is not None else {}, ensure_ascii=False)
    def _loads(self, value: Any, default: Any = None) -> Any:
        try: return json.loads(value) if value else ({} if default is None else default)
        except Exception: return {} if default is None else default
    def _one(self, sql: str, args: tuple[Any, ...]) -> dict[str, Any] | None:
        self.initialize()
        with self.connect() as con:
            row = con.execute(sql, args).fetchone()
            return dict(row) if row else None

    def save_character(self, character: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self.initialize(); data = {**(character or {}), **kwargs}; now = utc_now()
        cid = str(data.get("character_id") or data.get("id") or "player_1")
        vals = (cid, self.campaign_id, data.get("world_id", self.world_id), data.get("name",""), data.get("race_id", data.get("race","")), data.get("class_id", data.get("class", data.get("char_class",""))), data.get("appearance",""), int(data.get("level",1) or 1), int(data.get("xp",0) or 0), data.get("current_room_id",""), int(data.get("hp_current", data.get("hp",0)) or 0), int(data.get("mana_current", data.get("mana", data.get("energy_or_mana",0))) or 0), int(data.get("stamina_current", data.get("stamina",0)) or 0), int(data.get("gold",0) or 0), data.get("created_at") or now, now)
        with self.connect() as con:
            con.execute("""INSERT INTO characters(character_id,campaign_id,world_id,name,race_id,class_id,appearance,level,xp,current_room_id,hp_current,mana_current,stamina_current,gold,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET campaign_id=excluded.campaign_id,world_id=excluded.world_id,name=excluded.name,race_id=excluded.race_id,class_id=excluded.class_id,appearance=excluded.appearance,level=excluded.level,xp=excluded.xp,current_room_id=excluded.current_room_id,hp_current=excluded.hp_current,mana_current=excluded.mana_current,stamina_current=excluded.stamina_current,gold=excluded.gold,updated_at=excluded.updated_at""", vals)

    def load_character(self, character_id: str) -> dict[str, Any]: return self._one("SELECT * FROM characters WHERE character_id=?", (character_id,)) or {}
    def save_character_stats(self, character_id: str, stats: dict[str, Any]) -> None:
        self.initialize();
        with self.connect() as con:
            con.execute("DELETE FROM character_stats WHERE character_id=?", (character_id,)); con.executemany("INSERT INTO character_stats VALUES(?,?,?)", [(character_id,k,int(v or 0)) for k,v in stats.items()])
    def load_character_stats(self, character_id: str) -> dict[str, int]:
        self.initialize();
        with self.connect() as con: return {r["stat_name"]: int(r["stat_value"]) for r in con.execute("SELECT stat_name,stat_value FROM character_stats WHERE character_id=?", (character_id,))}
    def save_abilities(self, character_id: str, ability_ids: list[Any]) -> None:
        self.initialize(); now=utc_now()
        with self.connect() as con:
            con.execute("DELETE FROM character_abilities WHERE character_id=?", (character_id,)); con.executemany("INSERT OR REPLACE INTO character_abilities VALUES(?,?,?,?)", [(character_id, str(a.get("id", a.get("name")) if isinstance(a,dict) else a), "starting", now) for a in ability_ids])
    def load_abilities(self, character_id: str) -> list[str]:
        self.initialize();
        with self.connect() as con: return [r["ability_id"] for r in con.execute("SELECT ability_id FROM character_abilities WHERE character_id=? ORDER BY learned_at,ability_id", (character_id,))]
    def save_inventory(self, character_id: str, entries: list[Any]) -> None:
        self.initialize();
        with self.connect() as con:
            con.execute("DELETE FROM character_inventory WHERE character_id=?", (character_id,))
            for e in entries:
                d=e if isinstance(e,dict) else {"item_id":str(e),"quantity":1}; con.execute("INSERT INTO character_inventory(character_id,item_id,quantity,equipped_slot,state_json) VALUES(?,?,?,?,?)", (character_id,d.get("item_id",d.get("id",d.get("name",""))),int(d.get("quantity",1) or 1),d.get("equipped_slot"),self._json(d.get("state", d))))
    def load_inventory(self, character_id: str) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [{**dict(r), "state": self._loads(r["state_json"])} for r in con.execute("SELECT * FROM character_inventory WHERE character_id=? ORDER BY id", (character_id,))]
    def mark_room_visited(self, room_id: str) -> None:
        self.initialize(); now=utc_now()
        with self.connect() as con: con.execute("INSERT INTO rooms_runtime(room_id,campaign_id,world_id,visited_count,last_visited_at,state_json) VALUES(?,?,?,?,?,?) ON CONFLICT(room_id) DO UPDATE SET visited_count=visited_count+1,last_visited_at=excluded.last_visited_at", (room_id,self.campaign_id,self.world_id,1,now,"{}"))
    def load_room_runtime(self, room_id: str) -> dict[str, Any]:
        row=self._one("SELECT * FROM rooms_runtime WHERE room_id=?", (room_id,)) or {"room_id":room_id,"campaign_id":self.campaign_id,"world_id":self.world_id,"visited_count":0,"state_json":"{}"}; row["state"]=self._loads(row.get("state_json")); return row
    def save_room_runtime(self, room_id: str, state: dict[str, Any]) -> None:
        self.initialize(); now=utc_now();
        with self.connect() as con: con.execute("INSERT INTO rooms_runtime VALUES(?,?,?,?,?,?) ON CONFLICT(room_id) DO UPDATE SET state_json=excluded.state_json,last_visited_at=excluded.last_visited_at", (room_id,self.campaign_id,self.world_id,int(state.get("visited_count",0) or 0),now,self._json(state)))
    def add_room_item(self, room_id: str, item_id: str, quantity: int, state: dict[str, Any] | None=None) -> None:
        self.initialize();
        with self.connect() as con: con.execute("INSERT INTO room_items(room_id,item_id,quantity,state_json) VALUES(?,?,?,?)", (room_id,item_id,quantity,self._json(state)))
    def load_room_items(self, room_id: str) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [{**dict(r),"state":self._loads(r["state_json"])} for r in con.execute("SELECT * FROM room_items WHERE room_id=?", (room_id,))]
    def load_npc_runtime(self,npc_id:str)->dict[str,Any]:
        row=self._one("SELECT * FROM npc_runtime WHERE npc_id=? AND campaign_id=?",(npc_id,self.campaign_id)) or {"npc_id":npc_id,"campaign_id":self.campaign_id,"world_id":self.world_id,"state_json":"{}"}; row["state"]=self._loads(row.get("state_json")); return row
    def save_npc_runtime(self,npc_id:str,state:dict[str,Any])->None:
        self.initialize(); now=utc_now();
        with self.connect() as con: con.execute("INSERT INTO npc_runtime VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(npc_id,campaign_id) DO UPDATE SET current_room_id=excluded.current_room_id,mood=excluded.mood,disposition=excluded.disposition,state_json=excluded.state_json,updated_at=excluded.updated_at", (npc_id,self.campaign_id,self.world_id,state.get("current_room_id"),state.get("mood"),state.get("disposition"),self._json(state),now))
    def load_relationship(self,npc_id:str,character_id:str)->dict[str,Any]:
        row=self._one("SELECT * FROM npc_relationships WHERE npc_id=? AND character_id=?",(npc_id,character_id)); return row or {"npc_id":npc_id,"character_id":character_id,"trust":50,"affection":0,"annoyance":0,"fear":0,"hostility":0,"respect":0,"romance":0,"state_json":"{}"}
    def update_relationship(self,npc_id:str,character_id:str,deltas:dict[str,int])->dict[str,Any]:
        rel=self.load_relationship(npc_id,character_id); keys=("trust","affection","annoyance","fear","hostility","respect","romance")
        for k in keys: rel[k]=max(0,min(100,int(rel.get(k,0) or 0)+int(deltas.get(k,0) or 0)))
        rel["last_interaction_at"]=utc_now(); self.initialize();
        with self.connect() as con: con.execute("INSERT INTO npc_relationships VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(npc_id,character_id) DO UPDATE SET trust=excluded.trust,affection=excluded.affection,annoyance=excluded.annoyance,fear=excluded.fear,hostility=excluded.hostility,respect=excluded.respect,romance=excluded.romance,last_interaction_at=excluded.last_interaction_at,state_json=excluded.state_json", (npc_id,character_id,*[rel[k] for k in keys],rel["last_interaction_at"],rel.get("state_json","{}")))
        return rel
    def add_npc_memory(self,npc_id:str,character_id:str,summary:str,memory_type:str="interaction",weight:int=1,tags:list[str]|None=None)->None:
        self.initialize();
        with self.connect() as con: con.execute("INSERT INTO npc_memories(npc_id,character_id,memory_type,summary,weight,created_at,last_recalled_at,tags_json) VALUES(?,?,?,?,?,?,?,?)", (npc_id,character_id,memory_type,summary,int(weight),utc_now(),None,self._json(tags or [])))
    def recall_npc_memories(self,npc_id:str,character_id:str,limit:int=5)->list[dict[str,Any]]:
        self.initialize(); now=utc_now();
        with self.connect() as con:
            rows=[dict(r) for r in con.execute("SELECT * FROM npc_memories WHERE npc_id=? AND character_id=? ORDER BY weight DESC, id DESC LIMIT ?",(npc_id,character_id,limit))]; con.execute("UPDATE npc_memories SET last_recalled_at=? WHERE npc_id=? AND character_id=?",(now,npc_id,character_id)); return [{**r,"tags":self._loads(r.get("tags_json"), [])} for r in rows]

    def _row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row: return None
        data = dict(row)
        if "state_json" in data: data["state"] = self._loads(data.get("state_json"))
        return data

    def upsert_mob_spawn(self, spawn: dict[str, Any]) -> None:
        self.initialize(); sid=str(spawn.get("spawn_id") or "")
        if not sid: return
        with self.connect() as con:
            con.execute("""INSERT INTO mob_spawns(spawn_id,campaign_id,world_id,npc_id,room_id,max_alive,respawn_enabled,respawn_delay_seconds,respawn_mode,next_respawn_at,state_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(spawn_id,campaign_id) DO UPDATE SET world_id=excluded.world_id,npc_id=excluded.npc_id,room_id=excluded.room_id,max_alive=excluded.max_alive,respawn_enabled=excluded.respawn_enabled,respawn_delay_seconds=excluded.respawn_delay_seconds,respawn_mode=excluded.respawn_mode,state_json=excluded.state_json""", (sid,self.campaign_id,spawn.get("world_id",self.world_id),spawn.get("npc_id") or spawn.get("mob_id"),spawn.get("room_id"),int(spawn.get("max_alive",1) or 1),1 if spawn.get("respawn_enabled") else 0,int(spawn.get("respawn_delay_seconds",0) or 0),spawn.get("respawn_mode","normal"),spawn.get("next_respawn_at"),self._json(spawn)))

    def spawn_mobs_for_room(self, room_id: str, spawn_defs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        self.initialize()
        for spawn in spawn_defs or []:
            if str(spawn.get("room_id") or spawn.get("default_room_id") or "") == room_id:
                data={**spawn, "room_id": room_id, "npc_id": spawn.get("npc_id") or spawn.get("mob_id") or spawn.get("id"), "spawn_id": spawn.get("spawn_id") or f"spawn_{spawn.get('id')}"}
                self.upsert_mob_spawn(data)
        with self.connect() as con:
            rows=[dict(r) for r in con.execute("SELECT * FROM mob_spawns WHERE campaign_id=? AND room_id=?", (self.campaign_id, room_id))]
            for sp in rows:
                alive=con.execute("SELECT COUNT(*) c FROM mob_instances WHERE spawn_id=? AND campaign_id=? AND status='alive'", (sp["spawn_id"], self.campaign_id)).fetchone()["c"]
                for _ in range(max(0, int(sp["max_alive"] or 1)-int(alive or 0))):
                    con.execute("INSERT INTO mob_instances(instance_id,spawn_id,npc_id,campaign_id,room_id,hp_current,status,state_json) VALUES(?,?,?,?,?,?,?,?)", (f'{sp["spawn_id"]}:{utc_now()}',sp["spawn_id"],sp["npc_id"],self.campaign_id,room_id,0,"alive","{}"))
        return self.load_alive_mobs(room_id)

    def load_alive_mobs(self, room_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as con: return [self._row(r) for r in con.execute("SELECT * FROM mob_instances WHERE campaign_id=? AND room_id=? AND status='alive' ORDER BY instance_id", (self.campaign_id, room_id))]

    def mark_mob_dead(self, instance_id: str, killed_by_character_id: str = "", cause: str = "combat", summary: str = "") -> dict[str, Any]:
        self.initialize(); now=utc_now()
        with self.connect() as con:
            inst=dict(con.execute("SELECT * FROM mob_instances WHERE instance_id=? AND campaign_id=?", (instance_id,self.campaign_id)).fetchone() or {})
            if not inst: return {}
            sp=dict(con.execute("SELECT * FROM mob_spawns WHERE spawn_id=? AND campaign_id=?", (inst["spawn_id"],self.campaign_id)).fetchone() or {})
            state=self._loads(sp.get("state_json")); corpse_seconds=int(state.get("corpse_decay_seconds", 0) or 0)
            corpse=(datetime.now(timezone.utc)+timedelta(seconds=corpse_seconds)).isoformat() if corpse_seconds else None
            con.execute("UPDATE mob_instances SET status='dead',killed_by_character_id=?,killed_at=?,corpse_expires_at=? WHERE instance_id=? AND campaign_id=?", (killed_by_character_id,now,corpse,instance_id,self.campaign_id))
            con.execute("INSERT INTO death_log(campaign_id,character_id,npc_id,instance_id,room_id,cause,summary,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.campaign_id,killed_by_character_id,inst.get("npc_id",""),instance_id,inst.get("room_id",""),cause,summary,now))
            if sp and int(sp.get("respawn_enabled") or 0) and sp.get("respawn_mode") != "story_permanent":
                due=(datetime.now(timezone.utc)+timedelta(seconds=int(sp.get("respawn_delay_seconds") or 0))).isoformat()
                con.execute("UPDATE mob_spawns SET next_respawn_at=? WHERE spawn_id=? AND campaign_id=?", (due,sp["spawn_id"],self.campaign_id))
            return self._row(con.execute("SELECT * FROM mob_instances WHERE instance_id=?", (instance_id,)).fetchone()) or {}

    def schedule_respawn(self, spawn_id: str) -> None:
        self.initialize()
        with self.connect() as con:
            sp=con.execute("SELECT * FROM mob_spawns WHERE spawn_id=? AND campaign_id=?", (spawn_id,self.campaign_id)).fetchone()
            if not sp: return
            due=(datetime.now(timezone.utc)+timedelta(seconds=int(sp["respawn_delay_seconds"] or 0))).isoformat()
            con.execute("UPDATE mob_spawns SET next_respawn_at=? WHERE spawn_id=? AND campaign_id=?", (due,spawn_id,self.campaign_id))

    def process_due_respawns(self, now: str | None = None) -> list[dict[str, Any]]:
        self.initialize(); now=now or utc_now(); made=[]
        with self.connect() as con:
            for sp in con.execute("SELECT * FROM mob_spawns WHERE campaign_id=? AND respawn_enabled=1 AND respawn_mode!='story_permanent' AND next_respawn_at IS NOT NULL AND next_respawn_at<=?", (self.campaign_id, now)):
                alive=con.execute("SELECT COUNT(*) c FROM mob_instances WHERE spawn_id=? AND campaign_id=? AND status='alive'", (sp["spawn_id"],self.campaign_id)).fetchone()["c"]
                if int(alive or 0) < int(sp["max_alive"] or 1):
                    iid=f'{sp["spawn_id"]}:{utc_now()}'; con.execute("INSERT INTO mob_instances(instance_id,spawn_id,npc_id,campaign_id,room_id,hp_current,status,state_json) VALUES(?,?,?,?,?,?,?,?)", (iid,sp["spawn_id"],sp["npc_id"],self.campaign_id,sp["room_id"],0,"alive","{}")); made.append({"instance_id":iid,"spawn_id":sp["spawn_id"],"npc_id":sp["npc_id"],"room_id":sp["room_id"]})
                con.execute("UPDATE mob_spawns SET next_respawn_at=NULL WHERE spawn_id=? AND campaign_id=?", (sp["spawn_id"],self.campaign_id))
        return made

    def load_corpses(self, room_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as con: return [self._row(r) for r in con.execute("SELECT * FROM mob_instances WHERE campaign_id=? AND room_id=? AND status='dead' AND corpse_expires_at IS NOT NULL ORDER BY killed_at DESC", (self.campaign_id, room_id))]

    def decay_expired_corpses(self, now: str | None = None) -> int:
        self.initialize(); now=now or utc_now()
        with self.connect() as con:
            cur=con.execute("UPDATE mob_instances SET status='despawned' WHERE campaign_id=? AND status='dead' AND corpse_expires_at IS NOT NULL AND corpse_expires_at<=?", (self.campaign_id, now)); return int(cur.rowcount or 0)

    def log_death(self, character_id: str = "", npc_id: str = "", instance_id: str = "", room_id: str = "", cause: str = "", summary: str = "") -> None:
        self.initialize()
        with self.connect() as con: con.execute("INSERT INTO death_log(campaign_id,character_id,npc_id,instance_id,room_id,cause,summary,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.campaign_id,character_id,npc_id,instance_id,room_id,cause,summary,utc_now()))

    def recall_kill_history(self, npc_id: str | None = None, character_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        self.initialize(); clauses=["campaign_id=?"]; args=[self.campaign_id]
        if npc_id: clauses.append("npc_id=?"); args.append(npc_id)
        if character_id: clauses.append("character_id=?"); args.append(character_id)
        with self.connect() as con: return [dict(r) for r in con.execute(f"SELECT * FROM death_log WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?", (*args, limit))]

    def load_respawn_timers(self, room_id: str | None = None) -> list[dict[str, Any]]:
        self.initialize(); sql="SELECT * FROM mob_spawns WHERE campaign_id=? AND next_respawn_at IS NOT NULL"; args=[self.campaign_id]
        if room_id: sql += " AND room_id=?"; args.append(room_id)
        with self.connect() as con: return [self._row(r) for r in con.execute(sql, args)]

    def log_event(self, campaign_id:str|None=None, character_id:str="", room_id:str="", actor_id:str="", event_type:str="event", summary:str="", data:dict[str,Any]|None=None, **kw:Any)->None:
        self.initialize();
        with self.connect() as con: con.execute("INSERT INTO event_log(campaign_id,character_id,room_id,actor_id,event_type,summary,data_json,created_at) VALUES(?,?,?,?,?,?,?,?)", (campaign_id or self.campaign_id, character_id, room_id, actor_id, event_type, summary, self._json(data or kw), utc_now()))
    def log_conversation(self,campaign_id:str|None=None,character_id:str="",npc_id:str="",room_id:str="",speaker:str="player",text:str="",**kw:Any)->None:
        self.initialize();
        with self.connect() as con: con.execute("INSERT INTO conversation_log(campaign_id,character_id,npc_id,room_id,speaker,text,created_at) VALUES(?,?,?,?,?,?,?)", (campaign_id or self.campaign_id,character_id,npc_id,room_id,speaker,text,utc_now()))
    def load_recent_events(self,campaign_id:str|None=None,limit:int=10)->list[dict[str,Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM event_log WHERE campaign_id=? ORDER BY id DESC LIMIT ?",(campaign_id or self.campaign_id,limit))]
    def load_recent_conversation(self,npc_id:str,character_id:str,limit:int=10)->list[dict[str,Any]]:
        self.initialize();
        with self.connect() as con: return list(reversed([dict(r) for r in con.execute("SELECT * FROM conversation_log WHERE npc_id=? AND character_id=? ORDER BY id DESC LIMIT ?",(npc_id,character_id,limit))]))
    def load_reputation(self,faction_id:str,character_id:str)->dict[str,Any]: return self._one("SELECT * FROM faction_reputation WHERE faction_id=? AND character_id=?",(faction_id,character_id)) or {"faction_id":faction_id,"character_id":character_id,"reputation":0,"state_json":"{}"}
    def update_reputation(self,faction_id:str,character_id:str,delta:int)->dict[str,Any]:
        rep=self.load_reputation(faction_id,character_id); rep["reputation"]=max(-100,min(100,int(rep.get("reputation",0) or 0)+int(delta or 0))); self.initialize();
        with self.connect() as con: con.execute("INSERT INTO faction_reputation VALUES(?,?,?,?) ON CONFLICT(faction_id,character_id) DO UPDATE SET reputation=excluded.reputation,state_json=excluded.state_json",(faction_id,character_id,rep["reputation"],rep.get("state_json","{}"))); return rep
    def clear(self)->None:
        if self.db_path.exists(): self.db_path.unlink()
        self.initialize()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaign_meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS characters(character_id TEXT PRIMARY KEY,campaign_id TEXT,world_id TEXT,name TEXT,race_id TEXT,class_id TEXT,appearance TEXT,level INTEGER,xp INTEGER,current_room_id TEXT,hp_current INTEGER,mana_current INTEGER,stamina_current INTEGER,gold INTEGER,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS character_stats(character_id TEXT,stat_name TEXT,stat_value INTEGER,PRIMARY KEY(character_id,stat_name));
CREATE TABLE IF NOT EXISTS character_abilities(character_id TEXT,ability_id TEXT,source TEXT,learned_at TEXT,PRIMARY KEY(character_id,ability_id));
CREATE TABLE IF NOT EXISTS character_inventory(id INTEGER PRIMARY KEY AUTOINCREMENT,character_id TEXT,item_id TEXT,quantity INTEGER,equipped_slot TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS rooms_runtime(room_id TEXT PRIMARY KEY,campaign_id TEXT,world_id TEXT,visited_count INTEGER,last_visited_at TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS room_items(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT,item_id TEXT,quantity INTEGER,state_json TEXT);
CREATE TABLE IF NOT EXISTS npc_runtime(npc_id TEXT,campaign_id TEXT,world_id TEXT,current_room_id TEXT,mood TEXT,disposition TEXT,state_json TEXT,updated_at TEXT,PRIMARY KEY(npc_id,campaign_id));
CREATE TABLE IF NOT EXISTS npc_relationships(npc_id TEXT,character_id TEXT,trust INTEGER,affection INTEGER,annoyance INTEGER,fear INTEGER,hostility INTEGER,respect INTEGER,romance INTEGER,last_interaction_at TEXT,state_json TEXT,PRIMARY KEY(npc_id,character_id));
CREATE TABLE IF NOT EXISTS npc_memories(id INTEGER PRIMARY KEY AUTOINCREMENT,npc_id TEXT,character_id TEXT,memory_type TEXT,summary TEXT,weight INTEGER,created_at TEXT,last_recalled_at TEXT,tags_json TEXT);
CREATE TABLE IF NOT EXISTS faction_reputation(faction_id TEXT,character_id TEXT,reputation INTEGER,state_json TEXT,PRIMARY KEY(faction_id,character_id));
CREATE TABLE IF NOT EXISTS quests_runtime(quest_id TEXT,character_id TEXT,status TEXT,objective_state_json TEXT,updated_at TEXT,PRIMARY KEY(quest_id,character_id));
CREATE TABLE IF NOT EXISTS event_log(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,character_id TEXT,room_id TEXT,actor_id TEXT,event_type TEXT,summary TEXT,data_json TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS conversation_log(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,character_id TEXT,npc_id TEXT,room_id TEXT,speaker TEXT,text TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS world_facts(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,fact_type TEXT,subject_id TEXT,summary TEXT,weight INTEGER,data_json TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS mob_spawns(spawn_id TEXT,campaign_id TEXT,world_id TEXT,npc_id TEXT,room_id TEXT,max_alive INTEGER,respawn_enabled INTEGER,respawn_delay_seconds INTEGER,respawn_mode TEXT,next_respawn_at TEXT,state_json TEXT,PRIMARY KEY(spawn_id,campaign_id));
CREATE TABLE IF NOT EXISTS mob_instances(instance_id TEXT PRIMARY KEY,spawn_id TEXT,npc_id TEXT,campaign_id TEXT,room_id TEXT,hp_current INTEGER,status TEXT,killed_by_character_id TEXT,killed_at TEXT,corpse_expires_at TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS object_spawns(spawn_id TEXT,campaign_id TEXT,item_id TEXT,room_id TEXT,max_count INTEGER,respawn_enabled INTEGER,respawn_delay_seconds INTEGER,next_respawn_at TEXT,state_json TEXT,PRIMARY KEY(spawn_id,campaign_id));
CREATE TABLE IF NOT EXISTS death_log(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,character_id TEXT,npc_id TEXT,instance_id TEXT,room_id TEXT,cause TEXT,summary TEXT,created_at TEXT);
"""
