"""Canonical Builder-authored NPC schedule service for Phase 12A.

The service selects activities only. Activity execution is dispatched to the
canonical runtime/services that already own movement, needs, training, economy,
crafting, gathering, and conversation behavior.
"""
from __future__ import annotations

import json
import sqlite3
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTIVITY_DISPATCH = {
    "sleep": "survival_needs", "wake": "survival_needs", "eat": "survival_needs", "drink": "survival_needs", "rest": "survival_needs",
    "gather": "gathering", "craft": "crafting", "cook": "crafting", "train": "training", "shop": "economy", "bank": "economy",
    "converse": "conversation", "patrol": "movement", "travel": "movement", "stand_guard": "movement", "visit_location": "movement", "return_home": "movement",
    "idle": "none", "work": "none",
}
SCHEDULE_SCHEMA = """
CREATE TABLE IF NOT EXISTS npc_schedule_runtime(npc_id TEXT PRIMARY KEY,world_id TEXT,schedule_id TEXT,current_entry_id TEXT,current_activity TEXT,current_target_room_id TEXT,status TEXT,interrupted INTEGER DEFAULT 0,resume_json TEXT,trace_json TEXT,last_world_day INTEGER,last_world_minute INTEGER,updated_at TEXT);
CREATE TABLE IF NOT EXISTS npc_activity_history(id INTEGER PRIMARY KEY AUTOINCREMENT,npc_id TEXT,world_id TEXT,schedule_id TEXT,entry_id TEXT,activity TEXT,target_room_id TEXT,from_room_id TEXT,to_room_id TEXT,transition TEXT,world_day INTEGER,world_minute INTEGER,created_at TEXT,metadata_json TEXT);
"""

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _loads(v: Any, d: Any):
    try: return json.loads(v) if v else deepcopy(d)
    except Exception: return deepcopy(d)
def _dump(v: Any) -> str: return json.dumps(v if v is not None else {}, sort_keys=True)
def _norm_activity(v: str) -> str: return str(v or "idle").strip().lower().replace(" ", "_").replace("-", "_")
def _minute(wt: dict[str, Any]) -> int: return int(wt.get("hour", 0))*60 + int(wt.get("minute", 0))

class ScheduleValidationError(ValueError): pass

def init_schedule_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as con: con.executescript(SCHEDULE_SCHEMA)

class ScheduleService:
    def __init__(self, runtime: Any | None = None, *, db_path: str | Path | None = None, world_id: str = "", event_bus: Any | None = None) -> None:
        self.runtime = runtime; self.db_path = Path(db_path or getattr(getattr(runtime, "state_store", None), "db_path", ":memory:")); self.world_id = world_id or getattr(runtime, "active_world_id", "") or ""; self.event_bus = event_bus or getattr(runtime, "event_bus", None); init_schedule_schema(self.db_path)
    def schedules(self) -> dict[str, dict[str, Any]]:
        active = getattr(self.runtime, "active_world", None)
        records = list(getattr(active, "schedules", []) or [])
        root = Path("data/worlds") / (self.world_id or "shattered_realms") / "schedules"
        if root.exists():
            for p in sorted(root.glob("*.json")):
                data = json.loads(p.read_text(encoding="utf-8")); records.extend(data if isinstance(data, list) else [data])
        return {str(s.get("id")): s for s in records if isinstance(s, dict) and s.get("id")}
    def validate_schedule(self, schedule: dict[str, Any]) -> list[str]:
        errors=[]
        if not schedule.get("id"): errors.append("schedule missing id")
        if not isinstance(schedule.get("entries"), list) or not schedule.get("entries"): errors.append(f"schedule {schedule.get('id')} missing entries")
        for e in schedule.get("entries") or []:
            if not e.get("id"): errors.append(f"schedule {schedule.get('id')} entry missing id")
            act=_norm_activity(e.get("activity"));
            if act not in ACTIVITY_DISPATCH: errors.append(f"entry {e.get('id')} unsupported activity {act}")
            for k in ("start_time","end_time"):
                try: h,m=[int(x) for x in str(e.get(k,"00:00")).split(":",1)]; assert 0<=h<24 and 0<=m<60
                except Exception: errors.append(f"entry {e.get('id')} invalid {k}")
        return errors
    def validate_all(self) -> dict[str, Any]:
        errors=[]
        for s in self.schedules().values(): errors.extend(self.validate_schedule(s))
        return {"ok": not errors, "errors": errors}
    def actor_schedule_id(self, npc_id: str, actor: dict[str, Any] | None = None) -> str:
        actor = actor or (self.runtime.find_entity(npc_id) if self.runtime and hasattr(self.runtime,"find_entity") else {}) or {}
        st=actor.get("state") or {}; plug=actor.get("plugin_data") or {}
        return str(st.get("schedule_id") or plug.get("schedule_id") or (plug.get("simulation") or {}).get("schedule_id") or "")
    def world_time(self) -> dict[str, Any]:
        if self.runtime and hasattr(self.runtime,"get_world_time"): return self.runtime.get_world_time(self.world_id or getattr(self.runtime,"active_world_id", ""))
        return {"world_id": self.world_id, "day": 1, "hour": 6, "minute": 0}
    def select_activity(self, npc_id: str, world_time: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
        wt=world_time or self.world_time(); actor=(self.runtime.find_entity(npc_id) if self.runtime and hasattr(self.runtime,"find_entity") else {}) or {}; sched=self.schedules().get(self.actor_schedule_id(npc_id, actor), {})
        if sched and self.validate_schedule(sched): raise ScheduleValidationError("; ".join(self.validate_schedule(sched)))
        entries=list(sched.get("entries") or []); minute=_minute(wt); day=int(wt.get("day",1)); season=wt.get("season"); holiday=wt.get("holiday")
        def ok(e):
            if e.get("holiday") and e.get("holiday") != holiday: return False
            if e.get("season") and e.get("season") != season: return False
            if e.get("weekdays") and ((day-1)%7)+1 not in [int(x) for x in e.get("weekdays")]: return False
            cond=e.get("conditions") or {}; flags=(context or {}).get("flags", {})
            if any(flags.get(k) != v for k,v in cond.get("flags", {}).items()): return False
            sh,sm=[int(x) for x in str(e.get("start_time","00:00")).split(":",1)]; eh,em=[int(x) for x in str(e.get("end_time","23:59")).split(":",1)]; s=sh*60+sm; end=eh*60+em
            return (s <= minute < end) if end > s else (minute >= s or minute < end)
        pools=[e for e in entries if e.get("override") == "emergency" and ok(e)] or [e for e in entries if e.get("override") == "holiday" and ok(e)] or [e for e in entries if ok(e)]
        entry=sorted(pools, key=lambda e:(-int(e.get("priority",0)), str(e.get("id"))))[0] if pools else (sched.get("fallback") or {"id":"fallback","activity":"idle"})
        refs=(sched.get("location_refs") or {}) | (actor.get("plugin_data") or {}).get("location_refs", {})
        target=entry.get("target_room_id") or refs.get(str(entry.get("target_ref") or "")) or refs.get({"sleep":"home","return_home":"home","work":"workplace","stand_guard":"workplace","patrol":"preferred_patrol_route","train":"preferred_trainer","gather":"preferred_gathering_area"}.get(_norm_activity(entry.get("activity")),"")) or actor.get("room_id")
        return {"npc_id":npc_id,"world_id":wt.get("world_id",self.world_id),"schedule_id":sched.get("id",""),"entry_id":entry.get("id"),"activity":_norm_activity(entry.get("activity")),"target_room_id":target,"dispatch_service":ACTIVITY_DISPATCH.get(_norm_activity(entry.get("activity")),"none"),"world_time":wt,"entry":entry}
    def apply(self, npc_id: str, world_time: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
        sel=self.select_activity(npc_id, world_time, context); prev=self.runtime_state(npc_id); actor=(self.runtime.find_entity(npc_id) if self.runtime and hasattr(self.runtime,"find_entity") else {}) or {}; from_room=actor.get("room_id") or actor.get("current_room_id") or ""; to_room=from_room
        transition="continue" if prev.get("current_entry_id")==sel["entry_id"] and prev.get("current_activity")==sel["activity"] else "transition"
        if sel["dispatch_service"] == "movement" and sel.get("target_room_id") and sel["target_room_id"] != from_room: to_room=self._move_one_step(npc_id, from_room, sel["target_room_id"], sel)
        self._save_runtime(sel, transition); self._history(sel, from_room, to_room, transition)
        if self.event_bus: self.event_bus.publish("schedule_activity_selected", sel | {"transition": transition, "from_room_id": from_room, "to_room_id": to_room}, source_system="schedule", world_id=sel.get("world_id",""))
        return sel | {"transition":transition,"from_room_id":from_room,"to_room_id":to_room}
    def _move_one_step(self,npc_id,start,target,sel):
        path = self.runtime.find_room_path(start,target).get("path",[]) if self.runtime and hasattr(self.runtime,"find_room_path") else []
        if len(path)>1 and hasattr(self.runtime,"move_entity"): self.runtime.move_entity(npc_id,path[1],source_system="schedule",schedule_entry_id=sel.get("entry_id")); return path[1]
        return start
    def runtime_state(self,npc_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM npc_schedule_runtime WHERE npc_id=?",(npc_id,)).fetchone(); return dict(r) if r else {}
    def _save_runtime(self,sel,transition):
        wt=sel["world_time"]; trace={"last_selection":sel,"transition":transition}
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO npc_schedule_runtime VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(npc_id) DO UPDATE SET world_id=excluded.world_id,schedule_id=excluded.schedule_id,current_entry_id=excluded.current_entry_id,current_activity=excluded.current_activity,current_target_room_id=excluded.current_target_room_id,status=excluded.status,interrupted=0,trace_json=excluded.trace_json,last_world_day=excluded.last_world_day,last_world_minute=excluded.last_world_minute,updated_at=excluded.updated_at",(sel["npc_id"],sel.get("world_id",""),sel.get("schedule_id",""),sel.get("entry_id",""),sel.get("activity",""),sel.get("target_room_id",""),"active",0,"{}",_dump(trace),int(wt.get("day",1)),_minute(wt),_now()))
    def _history(self,sel,from_room,to_room,transition):
        wt=sel["world_time"]
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO npc_activity_history(npc_id,world_id,schedule_id,entry_id,activity,target_room_id,from_room_id,to_room_id,transition,world_day,world_minute,created_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sel["npc_id"],sel.get("world_id",""),sel.get("schedule_id",""),sel.get("entry_id",""),sel.get("activity",""),sel.get("target_room_id",""),from_room,to_room,transition,int(wt.get("day",1)),_minute(wt),_now(),_dump({"dispatch_service":sel.get("dispatch_service")})))
    def history(self,npc_id,limit=20):
        with sqlite3.connect(self.db_path) as con: con.row_factory=sqlite3.Row; return [dict(r) for r in con.execute("SELECT * FROM npc_activity_history WHERE npc_id=? ORDER BY id DESC LIMIT ?",(npc_id,int(limit)))]
    def interrupt(self,npc_id,reason=""):
        cur=self.runtime_state(npc_id)
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE npc_schedule_runtime SET interrupted=1,status='interrupted',resume_json=?,updated_at=? WHERE npc_id=?",(_dump(cur | {"reason":reason}),_now(),npc_id))
        return self.runtime_state(npc_id)
    def resume(self,npc_id):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE npc_schedule_runtime SET interrupted=0,status='active',updated_at=? WHERE npc_id=?",(_now(),npc_id))
        return self.runtime_state(npc_id)
