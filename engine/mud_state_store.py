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
    if safe.startswith("mud_"):
        parts = safe.split("_", 2)
        if len(parts) == 3 and parts[1] and parts[2]:
            return base / "saves" / "smart_mud" / parts[1] / f"{parts[2]}.sqlite"
    return base / "saves" / "smart_mud" / f"{safe}.sqlite"


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
            self._ensure_character_privilege_columns(con)
            self._ensure_v3_columns(con)
            con.execute("INSERT OR REPLACE INTO campaign_meta(key,value) VALUES(?,?)", ("campaign_id", self.campaign_id))
            if self.world_id:
                con.execute("INSERT OR REPLACE INTO campaign_meta(key,value) VALUES(?,?)", ("world_id", self.world_id))

    def _ensure_character_privilege_columns(self, con: sqlite3.Connection) -> None:
        existing = {r["name"] for r in con.execute("PRAGMA table_info(characters)")}
        for name, ddl in {"role": "TEXT DEFAULT 'player'", "immortal_level": "INTEGER DEFAULT 0", "builder_enabled": "INTEGER DEFAULT 0"}.items():
            if name not in existing:
                con.execute(f"ALTER TABLE characters ADD COLUMN {name} {ddl}")

    def _ensure_v3_columns(self, con: sqlite3.Connection) -> None:
        table_columns = {
            "npc_relationships": {"suspicion": "INTEGER DEFAULT 0", "friendship": "INTEGER DEFAULT 0", "debt": "INTEGER DEFAULT 0", "favor": "INTEGER DEFAULT 0"},
            "npc_memories": {"importance": "INTEGER DEFAULT 1", "emotion": "TEXT", "timestamp": "TEXT", "related_room": "TEXT", "related_npc": "TEXT", "expires": "TEXT", "player_id": "TEXT"},
            "room_items": {"item_instance_id": "TEXT"},
        }
        for table, columns in table_columns.items():
            existing = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
            for name, ddl in columns.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def admin_exists(self) -> bool:
        self.initialize()
        with self.connect() as con:
            row = con.execute("SELECT 1 FROM characters WHERE role='admin' LIMIT 1").fetchone()
            return bool(row)

    def promote_character(self, character_id: str, role: str = "admin", immortal_level: int = 100, builder_enabled: bool = True) -> None:
        self.initialize()
        with self.connect() as con:
            con.execute("UPDATE characters SET role=?, immortal_level=?, builder_enabled=?, updated_at=? WHERE character_id=?", (role, int(immortal_level), 1 if builder_enabled else 0, utc_now(), character_id))

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
        vals = (cid, self.campaign_id, data.get("world_id", self.world_id), data.get("name",""), data.get("race_id", data.get("race","")), data.get("class_id", data.get("class", data.get("char_class",""))), data.get("appearance",""), int(data.get("level",1) or 1), int(data.get("xp",0) or 0), data.get("current_room_id",""), int(data.get("hp_current", data.get("hp",0)) or 0), int(data.get("mana_current", data.get("mana", data.get("energy_or_mana",0))) or 0), int(data.get("stamina_current", data.get("stamina",0)) or 0), int(data.get("gold",0) or 0), data.get("created_at") or now, now, data.get("role", "player"), int(data.get("immortal_level", 0) or 0), 1 if data.get("builder_enabled") else 0)
        with self.connect() as con:
            con.execute("""INSERT INTO characters(character_id,campaign_id,world_id,name,race_id,class_id,appearance,level,xp,current_room_id,hp_current,mana_current,stamina_current,gold,created_at,updated_at,role,immortal_level,builder_enabled)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET campaign_id=excluded.campaign_id,world_id=excluded.world_id,name=excluded.name,race_id=excluded.race_id,class_id=excluded.class_id,appearance=excluded.appearance,level=excluded.level,xp=excluded.xp,current_room_id=excluded.current_room_id,hp_current=excluded.hp_current,mana_current=excluded.mana_current,stamina_current=excluded.stamina_current,gold=excluded.gold,updated_at=excluded.updated_at,role=excluded.role,immortal_level=excluded.immortal_level,builder_enabled=excluded.builder_enabled""", vals)

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

    def add_command_history(self, character_id: str, command_text: str, room_id: str = "", limit: int = 100) -> None:
        self.initialize()
        with self.connect() as con:
            con.execute(
                "INSERT INTO command_history(character_id,command_text,room_id,created_at) VALUES(?,?,?,?)",
                (character_id, command_text, room_id, utc_now()),
            )
            if limit > 0:
                con.execute(
                    "DELETE FROM command_history WHERE character_id=? AND id NOT IN (SELECT id FROM command_history WHERE character_id=? ORDER BY id DESC LIMIT ?)",
                    (character_id, character_id, int(limit)),
                )

    def load_command_history(self, character_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM command_history WHERE character_id=? ORDER BY id DESC LIMIT ?", (character_id, int(limit)))]
        return list(reversed(rows))

    def add_scrollback(self, character_id: str, entry_type: str, text: str, html: str = "", room_id: str = "", limit: int = 1000) -> None:
        self.initialize()
        with self.connect() as con:
            con.execute(
                "INSERT INTO mud_scrollback(character_id,entry_type,text,html,room_id,created_at) VALUES(?,?,?,?,?,?)",
                (character_id, entry_type, text, html, room_id, utc_now()),
            )
            if limit > 0:
                con.execute(
                    "DELETE FROM mud_scrollback WHERE character_id=? AND id NOT IN (SELECT id FROM mud_scrollback WHERE character_id=? ORDER BY id DESC LIMIT ?)",
                    (character_id, character_id, int(limit)),
                )

    def load_scrollback(self, character_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM mud_scrollback WHERE character_id=? ORDER BY id DESC LIMIT ?", (character_id, int(limit)))]
        return list(reversed(rows))

    def clear_scrollback(self, character_id: str) -> None:
        self.initialize()
        with self.connect() as con:
            con.execute("DELETE FROM mud_scrollback WHERE character_id=?", (character_id,))
    def load_npc_runtime(self,npc_id:str)->dict[str,Any]:
        row=self._one("SELECT * FROM npc_runtime WHERE npc_id=? AND campaign_id=?",(npc_id,self.campaign_id)) or {"npc_id":npc_id,"campaign_id":self.campaign_id,"world_id":self.world_id,"state_json":"{}"}; row["state"]=self._loads(row.get("state_json")); return row
    def save_npc_runtime(self,npc_id:str,state:dict[str,Any])->None:
        self.initialize(); now=utc_now();
        with self.connect() as con: con.execute("INSERT INTO npc_runtime VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(npc_id,campaign_id) DO UPDATE SET current_room_id=excluded.current_room_id,mood=excluded.mood,disposition=excluded.disposition,state_json=excluded.state_json,updated_at=excluded.updated_at", (npc_id,self.campaign_id,self.world_id,state.get("current_room_id"),state.get("mood"),state.get("disposition"),self._json(state),now))
    def load_relationship(self,npc_id:str,character_id:str)->dict[str,Any]:
        row=self._one("SELECT * FROM npc_relationships WHERE npc_id=? AND character_id=?",(npc_id,character_id)); return row or {"npc_id":npc_id,"character_id":character_id,"trust":50,"affection":0,"fear":0,"hostility":0,"respect":0,"suspicion":0,"friendship":0,"debt":0,"favor":0,"state_json":"{}"}
    def update_relationship(self,npc_id:str,character_id:str,deltas:dict[str,int])->dict[str,Any]:
        rel=self.load_relationship(npc_id,character_id); keys=("trust","affection","fear","hostility","respect","suspicion","friendship","debt","favor")
        for k in keys: rel[k]=max(0,min(100,int(rel.get(k,0) or 0)+int(deltas.get(k,0) or 0)))
        rel["last_interaction_at"]=utc_now(); self.initialize();
        with self.connect() as con: con.execute("INSERT INTO npc_relationships(npc_id,character_id,trust,affection,fear,hostility,respect,suspicion,friendship,debt,favor,last_interaction_at,state_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(npc_id,character_id) DO UPDATE SET trust=excluded.trust,affection=excluded.affection,fear=excluded.fear,hostility=excluded.hostility,respect=excluded.respect,suspicion=excluded.suspicion,friendship=excluded.friendship,debt=excluded.debt,favor=excluded.favor,last_interaction_at=excluded.last_interaction_at,state_json=excluded.state_json", (npc_id,character_id,*[rel[k] for k in keys],rel["last_interaction_at"],rel.get("state_json","{}")))
        return rel
    def add_npc_memory(self,npc_id:str,character_id:str,summary:str,memory_type:str="interaction",weight:int=1,tags:list[str]|None=None,emotion:str="",related_room:str="",related_npc:str="",expires:str|None=None,importance:int|None=None)->None:
        self.initialize(); now=utc_now(); importance = int(importance if importance is not None else weight)
        with self.connect() as con: con.execute("INSERT INTO npc_memories(npc_id,character_id,player_id,memory_type,summary,weight,importance,emotion,created_at,timestamp,last_recalled_at,tags_json,related_room,related_npc,expires) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (npc_id,character_id,character_id,memory_type,summary,int(weight),importance,emotion,now,now,None,self._json(tags or []),related_room,related_npc,expires))
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

    def list_tables(self) -> list[str]:
        self.initialize()
        with self.connect() as con:
            return [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]

    def upsert_account(self, account_id: str, username: str, email: str = "") -> None:
        self.initialize()
        with self.connect() as con:
            con.execute("INSERT INTO accounts(account_id,username,email,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET username=excluded.username,email=excluded.email,updated_at=excluded.updated_at", (account_id, username, email, utc_now(), utc_now()))

    def save_npc_template(self, template_id: str, data: dict[str, Any]) -> None:
        self.initialize()
        with self.connect() as con:
            con.execute("INSERT INTO npc_templates(template_id,world_id,name,template_json,loaded_at) VALUES(?,?,?,?,?) ON CONFLICT(template_id,world_id) DO UPDATE SET name=excluded.name,template_json=excluded.template_json", (template_id, data.get("world_id", self.world_id), data.get("name", template_id), self._json(data), utc_now()))

    def load_npc_template(self, template_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM npc_templates WHERE template_id=? AND world_id=?", (template_id, self.world_id)) or self._one("SELECT * FROM npc_templates WHERE template_id=?", (template_id,))
        if not row: return {}
        row["template"] = self._loads(row.get("template_json"))
        return row

    def save_npc_instance(self, instance_id: str, template_id: str, room_id: str, state: dict[str, Any] | None = None) -> None:
        self.initialize(); now=utc_now(); state=state or {}
        with self.connect() as con:
            con.execute("INSERT INTO npc_instances(instance_id,template_id,campaign_id,world_id,spawn_point,current_room_id,spawn_timer,death_time,corpse_id,killer,loot_generated,respawn_status,ai_state_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(instance_id) DO UPDATE SET current_room_id=excluded.current_room_id,death_time=excluded.death_time,corpse_id=excluded.corpse_id,killer=excluded.killer,loot_generated=excluded.loot_generated,respawn_status=excluded.respawn_status,ai_state_json=excluded.ai_state_json,updated_at=excluded.updated_at", (instance_id, template_id, self.campaign_id, self.world_id, state.get("spawn_point", room_id), room_id, state.get("spawn_timer"), state.get("death_time"), state.get("corpse_id"), state.get("killer"), self._json(state.get("loot_generated", [])), state.get("respawn_status", "alive"), self._json(state.get("ai_state", state)), now, now))
            con.execute("INSERT INTO npc_current_room(instance_id,room_id,updated_at) VALUES(?,?,?) ON CONFLICT(instance_id) DO UPDATE SET room_id=excluded.room_id,updated_at=excluded.updated_at", (instance_id, room_id, now))

    def load_npc_instance(self, instance_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM npc_instances WHERE instance_id=?", (instance_id,)) or {}
        if row: row["ai_state"] = self._loads(row.get("ai_state_json")); row["loot_generated_data"] = self._loads(row.get("loot_generated"), [])
        return row

    def create_item_instance(self, unique_id: str, template_id: str, current_owner: str = "", current_room: str = "", **kw: Any) -> None:
        self.initialize(); now=utc_now()
        with self.connect() as con:
            con.execute("INSERT INTO item_instances(unique_id,template_id,current_owner,current_room,durability,charges,quality,flags_json,custom_name,creator,created_date,last_modified) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(unique_id) DO UPDATE SET current_owner=excluded.current_owner,current_room=excluded.current_room,durability=excluded.durability,charges=excluded.charges,quality=excluded.quality,flags_json=excluded.flags_json,custom_name=excluded.custom_name,last_modified=excluded.last_modified", (unique_id, template_id, current_owner, current_room, int(kw.get("durability",100) or 100), int(kw.get("charges",0) or 0), kw.get("quality","normal"), self._json(kw.get("flags", [])), kw.get("custom_name",""), kw.get("creator",""), kw.get("created_date", now), now))

    def load_item_instance(self, unique_id: str) -> dict[str, Any]:
        row=self._one("SELECT * FROM item_instances WHERE unique_id=?", (unique_id,)) or {}
        if row: row["flags"] = self._loads(row.get("flags_json"), [])
        return row

    def create_corpse(self, corpse_id: str, room_id: str, owner: str = "", gold: int = 0, decay_seconds: int = 0, items: list[Any] | None = None) -> None:
        self.initialize(); now_dt=datetime.now(timezone.utc); decay=(now_dt+timedelta(seconds=decay_seconds)).isoformat() if decay_seconds else None
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO room_corpses(corpse_id,room_id,owner,gold,items_json,time_of_death,decay_at,state_json) VALUES(?,?,?,?,?,?,?,?)", (corpse_id, room_id, owner, int(gold or 0), self._json(items or []), now_dt.isoformat(), decay, "{}"))

    def load_persistent_corpses(self, room_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as con: return [{**dict(r), "items": self._loads(r["items_json"], [])} for r in con.execute("SELECT * FROM room_corpses WHERE room_id=? ORDER BY time_of_death DESC", (room_id,))]

    def save_world_state(self, key: str, value: Any) -> None:
        self.initialize()
        with self.connect() as con: con.execute("INSERT INTO world_state(campaign_id,key,value_json,updated_at) VALUES(?,?,?,?) ON CONFLICT(campaign_id,key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (self.campaign_id, key, self._json(value), utc_now()))

    def load_world_state(self, key: str, default: Any = None) -> Any:
        row=self._one("SELECT value_json FROM world_state WHERE campaign_id=? AND key=?", (self.campaign_id, key)); return self._loads(row.get("value_json") if row else None, default)

    def save_quest_state(self, character_id: str, quest_id: str, status: str, objectives: dict[str, Any] | None = None) -> None:
        self.initialize()
        with self.connect() as con: con.execute("INSERT INTO character_quests(character_id,quest_id,status,active_objectives_json,timers_json,reputation_json,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(character_id,quest_id) DO UPDATE SET status=excluded.status,active_objectives_json=excluded.active_objectives_json,updated_at=excluded.updated_at", (character_id, quest_id, status, self._json(objectives or {}), "{}", "{}", utc_now()))

    def load_quest_state(self, character_id: str, quest_id: str) -> dict[str, Any]:
        row=self._one("SELECT * FROM character_quests WHERE character_id=? AND quest_id=?", (character_id, quest_id)) or {}
        if row: row["active_objectives"] = self._loads(row.get("active_objectives_json"))
        return row

    def save_shop_inventory(self, shop_id: str, item_id: str, quantity: int, price: int, gold: int = 0) -> None:
        self.initialize()
        with self.connect() as con:
            con.execute("INSERT INTO shops(shop_id,campaign_id,gold,updated_at) VALUES(?,?,?,?) ON CONFLICT(shop_id,campaign_id) DO UPDATE SET gold=excluded.gold,updated_at=excluded.updated_at", (shop_id,self.campaign_id,int(gold or 0),utc_now()))
            con.execute("INSERT INTO shop_inventories(shop_id,item_id,quantity,price,restock_at,state_json) VALUES(?,?,?,?,?,?) ON CONFLICT(shop_id,item_id) DO UPDATE SET quantity=excluded.quantity,price=excluded.price", (shop_id,item_id,int(quantity),int(price),None,"{}"))

    def load_shop_inventory(self, shop_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM shop_inventories WHERE shop_id=? ORDER BY item_id", (shop_id,))]

    def build_ai_context(self, character_id: str, npc_id: str = "", room_id: str = "") -> dict[str, Any]:
        character = self.load_character(character_id)
        room_id = room_id or character.get("current_room_id", "")
        return {
            "player": character,
            "character": character,
            "current_room": self.load_room_runtime(room_id) if room_id else {},
            "nearby_players": self.load_room_players(room_id),
            "nearby_npcs": self.load_room_npcs(room_id),
            "npc_personality": self.load_npc_runtime(npc_id) if npc_id else {},
            "npc_relationships": self.load_relationship(npc_id, character_id) if npc_id else {},
            "npc_memories": self.recall_npc_memories(npc_id, character_id, 10) if npc_id else [],
            "current_conversation": self.load_recent_conversation(npc_id, character_id, 10) if npc_id else [],
            "faction_reputation": self.load_character_factions(character_id),
            "world_time": self.load_world_state("clock", {}),
            "weather": self.load_world_state("weather", {}),
            "active_quests": self.load_active_quests(character_id),
            "recent_room_events": self.load_room_events(room_id, 10),
            "relevant_world_lore": self.load_world_lore(room_id),
        }

    def load_room_players(self, room_id: str) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM room_players WHERE room_id=?", (room_id,))]
    def load_room_npcs(self, room_id: str) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM room_npcs WHERE room_id=?", (room_id,))]
    def load_room_events(self, room_id: str, limit: int = 10) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM room_events WHERE room_id=? ORDER BY created_at DESC LIMIT ?", (room_id, limit))]
    def load_character_factions(self, character_id: str) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM character_factions WHERE character_id=?", (character_id,))]
    def load_active_quests(self, character_id: str) -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM character_quests WHERE character_id=? AND status='active'", (character_id,))]
    def load_world_lore(self, subject_id: str = "") -> list[dict[str, Any]]:
        self.initialize();
        with self.connect() as con: return [dict(r) for r in con.execute("SELECT * FROM world_facts WHERE campaign_id=? AND (?='' OR subject_id=?) ORDER BY weight DESC,id DESC LIMIT 10", (self.campaign_id, subject_id, subject_id))]

    def clear(self)->None:
        if self.db_path.exists(): self.db_path.unlink()
        self.initialize()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaign_meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS characters(character_id TEXT PRIMARY KEY,campaign_id TEXT,world_id TEXT,name TEXT,race_id TEXT,class_id TEXT,appearance TEXT,level INTEGER,xp INTEGER,current_room_id TEXT,hp_current INTEGER,mana_current INTEGER,stamina_current INTEGER,gold INTEGER,created_at TEXT,updated_at TEXT,role TEXT DEFAULT 'player',immortal_level INTEGER DEFAULT 0,builder_enabled INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS character_stats(character_id TEXT,stat_name TEXT,stat_value INTEGER,PRIMARY KEY(character_id,stat_name));
CREATE TABLE IF NOT EXISTS character_abilities(character_id TEXT,ability_id TEXT,source TEXT,learned_at TEXT,PRIMARY KEY(character_id,ability_id));
CREATE TABLE IF NOT EXISTS character_inventory(id INTEGER PRIMARY KEY AUTOINCREMENT,character_id TEXT,item_id TEXT,quantity INTEGER,equipped_slot TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS command_history(id INTEGER PRIMARY KEY AUTOINCREMENT,character_id TEXT,command_text TEXT,room_id TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS mud_scrollback(id INTEGER PRIMARY KEY AUTOINCREMENT,character_id TEXT,entry_type TEXT,text TEXT,html TEXT,room_id TEXT,created_at TEXT);
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
CREATE TABLE IF NOT EXISTS accounts(account_id TEXT PRIMARY KEY,username TEXT,email TEXT,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS account_settings(account_id TEXT,key TEXT,value_json TEXT,PRIMARY KEY(account_id,key));
CREATE TABLE IF NOT EXISTS account_preferences(account_id TEXT,key TEXT,value_json TEXT,PRIMARY KEY(account_id,key));
CREATE TABLE IF NOT EXISTS account_permissions(account_id TEXT,permission TEXT,granted INTEGER,PRIMARY KEY(account_id,permission));
CREATE TABLE IF NOT EXISTS account_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id TEXT,event_type TEXT,summary TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS character_equipment(character_id TEXT,slot TEXT,item_instance_id TEXT,state_json TEXT,PRIMARY KEY(character_id,slot));
CREATE TABLE IF NOT EXISTS character_skills(character_id TEXT,skill_id TEXT,rank INTEGER,learned_at TEXT,PRIMARY KEY(character_id,skill_id));
CREATE TABLE IF NOT EXISTS character_spells(character_id TEXT,spell_id TEXT,rank INTEGER,learned_at TEXT,PRIMARY KEY(character_id,spell_id));
CREATE TABLE IF NOT EXISTS character_affects(character_id TEXT,affect_id TEXT,expires_at TEXT,state_json TEXT,PRIMARY KEY(character_id,affect_id));
CREATE TABLE IF NOT EXISTS character_prompt(character_id TEXT PRIMARY KEY,prompt_text TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS character_aliases(character_id TEXT,alias TEXT,command TEXT,PRIMARY KEY(character_id,alias));
CREATE TABLE IF NOT EXISTS character_hotkeys(character_id TEXT,hotkey TEXT,command TEXT,PRIMARY KEY(character_id,hotkey));
CREATE TABLE IF NOT EXISTS character_languages(character_id TEXT,language_id TEXT,proficiency INTEGER,PRIMARY KEY(character_id,language_id));
CREATE TABLE IF NOT EXISTS character_titles(character_id TEXT,title_id TEXT,active INTEGER,earned_at TEXT,PRIMARY KEY(character_id,title_id));
CREATE TABLE IF NOT EXISTS character_conditions(character_id TEXT,condition_id TEXT,value INTEGER,state_json TEXT,PRIMARY KEY(character_id,condition_id));
CREATE TABLE IF NOT EXISTS character_quests(character_id TEXT,quest_id TEXT,status TEXT,active_objectives_json TEXT,timers_json TEXT,reputation_json TEXT,updated_at TEXT,PRIMARY KEY(character_id,quest_id));
CREATE TABLE IF NOT EXISTS character_factions(character_id TEXT,faction_id TEXT,reputation INTEGER,standing TEXT,crime INTEGER,bounty INTEGER,title TEXT,updated_at TEXT,PRIMARY KEY(character_id,faction_id));
CREATE TABLE IF NOT EXISTS character_reputation(character_id TEXT,scope_id TEXT,reputation INTEGER,state_json TEXT,PRIMARY KEY(character_id,scope_id));
CREATE TABLE IF NOT EXISTS character_bank(character_id TEXT,currency TEXT,amount INTEGER,PRIMARY KEY(character_id,currency));
CREATE TABLE IF NOT EXISTS character_storage(character_id TEXT,storage_id TEXT,item_instance_id TEXT,quantity INTEGER,PRIMARY KEY(character_id,storage_id,item_instance_id));
CREATE TABLE IF NOT EXISTS character_cooldowns(character_id TEXT,cooldown_id TEXT,ready_at TEXT,PRIMARY KEY(character_id,cooldown_id));
CREATE TABLE IF NOT EXISTS character_known_locations(character_id TEXT,room_id TEXT,known_at TEXT,PRIMARY KEY(character_id,room_id));
CREATE TABLE IF NOT EXISTS character_settings(character_id TEXT,key TEXT,value_json TEXT,PRIMARY KEY(character_id,key));
CREATE TABLE IF NOT EXISTS npc_templates(template_id TEXT,world_id TEXT,name TEXT,template_json TEXT,loaded_at TEXT,PRIMARY KEY(template_id,world_id));
CREATE TABLE IF NOT EXISTS npc_instances(instance_id TEXT PRIMARY KEY,template_id TEXT,campaign_id TEXT,world_id TEXT,spawn_point TEXT,current_room_id TEXT,spawn_timer TEXT,death_time TEXT,corpse_id TEXT,killer TEXT,loot_generated TEXT,respawn_status TEXT,ai_state_json TEXT,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS npc_current_room(instance_id TEXT PRIMARY KEY,room_id TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS npc_health(instance_id TEXT PRIMARY KEY,hp_current INTEGER,hp_max INTEGER,updated_at TEXT);
CREATE TABLE IF NOT EXISTS npc_inventory(instance_id TEXT,item_instance_id TEXT,quantity INTEGER,PRIMARY KEY(instance_id,item_instance_id));
CREATE TABLE IF NOT EXISTS npc_equipment(instance_id TEXT,slot TEXT,item_instance_id TEXT,PRIMARY KEY(instance_id,slot));
CREATE TABLE IF NOT EXISTS npc_reputation(npc_id TEXT,scope_id TEXT,reputation INTEGER,PRIMARY KEY(npc_id,scope_id));
CREATE TABLE IF NOT EXISTS npc_schedule(npc_id TEXT,schedule_key TEXT,state_json TEXT,PRIMARY KEY(npc_id,schedule_key));
CREATE TABLE IF NOT EXISTS npc_goals(npc_id TEXT,goal_id TEXT,priority INTEGER,state_json TEXT,PRIMARY KEY(npc_id,goal_id));
CREATE TABLE IF NOT EXISTS npc_personality_state(npc_id TEXT PRIMARY KEY,state_json TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS npc_emotions(npc_id TEXT,emotion TEXT,intensity INTEGER,updated_at TEXT,PRIMARY KEY(npc_id,emotion));
CREATE TABLE IF NOT EXISTS npc_recent_events(npc_id TEXT,event_id TEXT,summary TEXT,created_at TEXT,PRIMARY KEY(npc_id,event_id));
CREATE TABLE IF NOT EXISTS npc_dialog_history(id INTEGER PRIMARY KEY AUTOINCREMENT,npc_id TEXT,player_id TEXT,text TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS npc_known_players(npc_id TEXT,player_id TEXT,state_json TEXT,PRIMARY KEY(npc_id,player_id));
CREATE TABLE IF NOT EXISTS npc_current_activity(npc_id TEXT PRIMARY KEY,activity TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS npc_flags(npc_id TEXT,flag TEXT,value INTEGER,PRIMARY KEY(npc_id,flag));
CREATE TABLE IF NOT EXISTS room_runtime(room_id TEXT PRIMARY KEY,campaign_id TEXT,world_id TEXT,state_json TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS room_corpses(corpse_id TEXT PRIMARY KEY,room_id TEXT,owner TEXT,gold INTEGER,items_json TEXT,time_of_death TEXT,decay_at TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS room_doors(room_id TEXT,exit_id TEXT,state TEXT,locked INTEGER,key_id TEXT,PRIMARY KEY(room_id,exit_id));
CREATE TABLE IF NOT EXISTS room_weather(room_id TEXT PRIMARY KEY,weather_json TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS room_lighting(room_id TEXT PRIMARY KEY,lighting_json TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS room_events(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT,event_type TEXT,summary TEXT,state_json TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS room_players(room_id TEXT,character_id TEXT,entered_at TEXT,PRIMARY KEY(room_id,character_id));
CREATE TABLE IF NOT EXISTS room_npcs(room_id TEXT,npc_instance_id TEXT,entered_at TEXT,PRIMARY KEY(room_id,npc_instance_id));
CREATE TABLE IF NOT EXISTS room_objects(room_id TEXT,object_id TEXT,state_json TEXT,PRIMARY KEY(room_id,object_id));
CREATE TABLE IF NOT EXISTS room_flags(room_id TEXT,flag TEXT,value INTEGER,PRIMARY KEY(room_id,flag));
CREATE TABLE IF NOT EXISTS room_variables(room_id TEXT,key TEXT,value_json TEXT,PRIMARY KEY(room_id,key));
CREATE TABLE IF NOT EXISTS room_reset_state(room_id TEXT PRIMARY KEY,last_reset_at TEXT,next_reset_at TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS item_instances(unique_id TEXT PRIMARY KEY,template_id TEXT,current_owner TEXT,current_room TEXT,durability INTEGER,charges INTEGER,quality TEXT,flags_json TEXT,custom_name TEXT,creator TEXT,created_date TEXT,last_modified TEXT);

CREATE TABLE IF NOT EXISTS actor_progression_state(progression_state_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,species_id TEXT,race_id TEXT,primary_class_id TEXT,primary_class_track_id TEXT,profession_ids_json TEXT,level INTEGER,experience INTEGER,experience_to_next INTEGER,total_experience INTEGER,practice_sessions INTEGER,training_sessions INTEGER,skill_points INTEGER,attribute_points INTEGER,talent_points_placeholder INTEGER,remort_count INTEGER,prestige_rank INTEGER,advancement_flags_json TEXT,last_level_at TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(actor_type,actor_id));
CREATE INDEX IF NOT EXISTS idx_actor_progression_actor ON actor_progression_state(actor_type,actor_id);
CREATE TABLE IF NOT EXISTS actor_experience_events(experience_event_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,source_type TEXT,source_id TEXT,amount INTEGER,base_amount INTEGER,modifier_amount INTEGER,final_amount INTEGER,reason TEXT,world_time TEXT,created_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_actor_xp_events_actor ON actor_experience_events(actor_type,actor_id,created_at);
CREATE TABLE IF NOT EXISTS actor_advancement_currency_events(event_id TEXT PRIMARY KEY,actor_id TEXT,currency_id TEXT,operation TEXT,amount INTEGER,source_type TEXT,source_id TEXT,reason TEXT,world_time TEXT,created_at TEXT,metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_actor_currency_events_actor ON actor_advancement_currency_events(actor_id,currency_id,created_at);
CREATE TABLE IF NOT EXISTS actor_progression_modifiers(grant_id TEXT PRIMARY KEY,actor_id TEXT,source_type TEXT,source_id TEXT,target_domain TEXT,target_key TEXT,operation TEXT,value INTEGER,level_granted INTEGER,active INTEGER,metadata_json TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_progression_mod_unique ON actor_progression_modifiers(actor_id,source_type,source_id,target_domain,target_key,level_granted);
CREATE TABLE IF NOT EXISTS actor_ability_progression(actor_id TEXT,ability_id TEXT,rank INTEGER,maximum_rank INTEGER,proficiency INTEGER,learned_at_level INTEGER,source_class_id TEXT,source_race_id TEXT,source_profession_id TEXT,source_track_id TEXT,practice_cost INTEGER,training_cost INTEGER,skill_point_cost INTEGER,requirements_json TEXT,active INTEGER,learned_at TEXT,metadata_json TEXT,PRIMARY KEY(actor_id,ability_id));
CREATE TABLE IF NOT EXISTS world_state(campaign_id TEXT,key TEXT,value_json TEXT,updated_at TEXT,PRIMARY KEY(campaign_id,key));
CREATE TABLE IF NOT EXISTS factions(faction_id TEXT PRIMARY KEY,name TEXT,state_json TEXT);
CREATE TABLE IF NOT EXISTS faction_alliances(faction_id TEXT,other_faction_id TEXT,standing INTEGER,state_json TEXT,PRIMARY KEY(faction_id,other_faction_id));
CREATE TABLE IF NOT EXISTS shops(shop_id TEXT,campaign_id TEXT,gold INTEGER,owner_id TEXT,reputation INTEGER,updated_at TEXT,PRIMARY KEY(shop_id,campaign_id));
CREATE TABLE IF NOT EXISTS shop_inventories(shop_id TEXT,item_id TEXT,quantity INTEGER,price INTEGER,restock_at TEXT,state_json TEXT,PRIMARY KEY(shop_id,item_id));
CREATE TABLE IF NOT EXISTS shop_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,shop_id TEXT,character_id TEXT,item_id TEXT,quantity INTEGER,price INTEGER,created_at TEXT);
CREATE TABLE IF NOT EXISTS price_history(id INTEGER PRIMARY KEY AUTOINCREMENT,shop_id TEXT,item_id TEXT,price INTEGER,created_at TEXT);
CREATE TABLE IF NOT EXISTS merchant_ownership(merchant_id TEXT,shop_id TEXT,share INTEGER,PRIMARY KEY(merchant_id,shop_id));
CREATE TABLE IF NOT EXISTS merchant_reputation(merchant_id TEXT,character_id TEXT,reputation INTEGER,PRIMARY KEY(merchant_id,character_id));
CREATE TABLE IF NOT EXISTS restock_timers(shop_id TEXT,item_id TEXT,restock_at TEXT,PRIMARY KEY(shop_id,item_id));
"""
