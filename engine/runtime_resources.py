"""Canonical runtime resource mutation service.

Normal gameplay code should route health, mana, stamina, movement, and future
numeric resource changes through RuntimeResourceService so live Actor state,
character persistence, stats rows, prompts, and events move in one direction.
"""
from __future__ import annotations

import json, sqlite3, uuid
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.actors import Actor

RESOURCES = ("health", "mana", "stamina", "movement")
OPS = {"damage", "healing", "cost", "regeneration", "set", "clamp", "maximum_changed"}
SAFE_META = {"action_id", "ability_id", "component_id", "source", "reason", "world_id", "room_id", "encounter_id", "round_id"}


def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _num(v: Any, default: int = 0) -> int:
    try: return int(float(v))
    except Exception: return default

@dataclass(frozen=True)
class ResourceMutationResult:
    ok: bool
    actor_id: str
    character_id: str
    resource: str
    operation: str
    before: int
    requested_amount: int
    applied_amount: int
    after: int
    maximum: int
    clamped: bool = False
    reason_code: str = "ok"
    persistence_version: int = 0
    events: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    expected_version: int | None = None

@dataclass(frozen=True)
class LifecycleTransitionResult:
    ok: bool
    actor_id: str
    previous_state: str
    new_state: str
    transition_type: str
    transition_id: str
    trigger_action_id: str = ""
    already_processed: bool = False
    corpse_created: bool = False
    respawn_scheduled: bool = False
    rewards_processed: bool = False
    combat_ended: bool = False
    events: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

class RuntimeResourceService:
    def __init__(self, runtime: Any | None = None, *, db_path: str | Path | None = None, event_bus: Any | None = None, world_id: str = "") -> None:
        self.runtime = runtime
        self.db_path = Path(db_path or getattr(getattr(runtime, "state_store", None), "db_path", "")) if (db_path or getattr(getattr(runtime, "state_store", None), "db_path", None)) else None
        self.event_bus = event_bus or getattr(runtime, "event_bus", None)
        self.world_id = world_id or getattr(runtime, "active_world_id", "") or ""
        if self.db_path: self.initialize()
        self._next_regeneration_monotonic = time.monotonic() + 6.0

    def initialize(self) -> None:
        if not self.db_path: return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as con:
            con.execute("CREATE TABLE IF NOT EXISTS actor_resource_versions(actor_id TEXT,resource TEXT,value INTEGER,maximum INTEGER,version INTEGER DEFAULT 0,updated_at TEXT,PRIMARY KEY(actor_id,resource))")
            con.execute("CREATE TABLE IF NOT EXISTS resource_mutation_requests(request_id TEXT PRIMARY KEY,actor_id TEXT,resource TEXT,operation TEXT,result_json TEXT,created_at TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS actor_lifecycle_transitions(actor_id TEXT,transition_type TEXT,transition_id TEXT,trigger_action_id TEXT,previous_state TEXT,new_state TEXT,processed_at TEXT,corpse_created INTEGER DEFAULT 0,respawn_scheduled INTEGER DEFAULT 0,rewards_processed INTEGER DEFAULT 0,combat_ended INTEGER DEFAULT 0,metadata_json TEXT,PRIMARY KEY(actor_id,transition_type,transition_id))")

    def _publish(self, name: str, payload: dict[str, Any]) -> None:
        if self.event_bus: self.event_bus.publish(name, payload, source_system="runtime_resources", world_id=payload.get("world_id") or self.world_id)

    def _cid(self, actor: Actor) -> str:
        return actor.actor_id.split(":", 1)[1] if actor.actor_id.startswith("character:") else ""

    def _sync_character(self, actor: Actor, resource: str, after: int, maximum: int, con: sqlite3.Connection | None = None) -> None:
        cid = self._cid(actor)
        if not cid or not self.db_path: return
        close = con is None
        con = con or sqlite3.connect(self.db_path)
        col = {"health":"hp_current", "mana":"mana_current", "stamina":"stamina_current"}.get(resource)
        if col:
            try:
                con.execute(f"UPDATE characters SET {col}=?,updated_at=? WHERE character_id=?", (after, _now(), cid))
            except sqlite3.OperationalError:
                pass
        try:
            con.execute("INSERT INTO character_stats(character_id,stat_name,stat_value) VALUES(?,?,?) ON CONFLICT(character_id,stat_name) DO UPDATE SET stat_value=excluded.stat_value", (cid, resource, after))
            con.execute("INSERT INTO character_stats(character_id,stat_name,stat_value) VALUES(?,?,?) ON CONFLICT(character_id,stat_name) DO UPDATE SET stat_value=excluded.stat_value", (cid, f"maximum_{resource}", maximum))
        except sqlite3.OperationalError:
            cols = {"health": ("hp", "max_hp"), "mana": ("mana", "max_mana"), "stamina": ("stamina", "max_stamina")}.get(resource)
            if cols:
                con.execute(f"UPDATE character_stats SET {cols[0]}=?,{cols[1]}=?,updated_at=CURRENT_TIMESTAMP WHERE character_id=?", (after, maximum, cid))
        if close: con.commit(); con.close()

    def _actor_ids(self, actor_or_character_id: Any) -> list[str]:
        aid = str(getattr(actor_or_character_id, "actor_id", actor_or_character_id) or "")
        out = [aid] if aid else []
        if aid.startswith("character:"):
            out.append(aid.split(":", 1)[1])
        elif aid and ":" not in aid:
            out.append("character:" + aid)
        return list(dict.fromkeys(out))

    def hydrate_character(self, character: Any) -> Any:
        """Overlay command-facing character resources from canonical resource rows.

        Generic character JSON may be loaded from an older command object.  This
        method makes RuntimeResourceService the read authority for current and
        maximum resources whenever actor_resource_versions contains a row.
        """
        if not self.db_path or character is None:
            return character
        ids = self._actor_ids(getattr(character, "id", ""))
        if not ids:
            return character
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(self.db_path) as con:
            rows = con.execute(
                f"SELECT actor_id,resource,value,maximum,version FROM actor_resource_versions WHERE actor_id IN ({placeholders})",
                ids,
            ).fetchall()
        for _aid, resource, value, maximum, version in rows:
            if resource == "health":
                setattr(character, "hp", _num(value, getattr(character, "hp", 0)))
                setattr(character, "max_hp", _num(maximum, getattr(character, "max_hp", 0)))
            elif resource == "mana":
                setattr(character, "mana", _num(value, getattr(character, "mana", 0)))
                setattr(character, "max_mana", _num(maximum, getattr(character, "max_mana", 0)))
            elif resource == "stamina":
                setattr(character, "stamina", _num(value, getattr(character, "stamina", 0)))
                setattr(character, "max_stamina", _num(maximum, getattr(character, "max_stamina", 0)))
            getattr(character, "actor_data", {}).setdefault("resource_versions", {})[str(resource)] = int(version or 0)
        return character

    def mutate(self, actor: Actor, resource: str, operation: str, amount: int = 0, *, maximum: int | None = None, action_id: str = "", metadata: dict[str, Any] | None = None, expected_version: int | None = None) -> ResourceMutationResult:
        resource = str(resource); operation = str(operation)
        meta = {str(k): v for k, v in (metadata or {}).items() if k in SAFE_META and isinstance(v, (str, int, float, bool, type(None)))}
        if action_id: meta["action_id"] = action_id
        before = _num(getattr(actor.resources, resource, 0)); maxv = _num(maximum if maximum is not None else getattr(actor.resources, f"maximum_{resource}", before), before)
        req = max(0, int(amount or 0)); cid = self._cid(actor)
        request_event = {"event":"resource_mutation_requested","action_id":action_id,"actor_id":actor.actor_id,"character_id":cid,"resource":resource,"operation":operation,"before":before,"requested_amount":req,"world_id":self.world_id,"room_id":getattr(actor.identity,"current_location","")}
        self._publish("resource_mutation_requested", request_event)
        if resource not in RESOURCES or operation not in OPS:
            ev = {**request_event, "event":"resource_mutation_denied", "reason_code":"unsupported_resource_or_operation"}; self._publish("resource_mutation_denied", ev)
            return ResourceMutationResult(False, actor.actor_id, cid, resource, operation, before, req, 0, before, maxv, False, "unsupported_resource_or_operation", 0, (request_event, ev), meta, expected_version)
        persisted_version = 0
        if self.db_path:
            with sqlite3.connect(self.db_path) as con:
                row = con.execute("SELECT value,maximum,version FROM actor_resource_versions WHERE actor_id=? AND resource=?", (actor.actor_id, resource)).fetchone()
                if row:
                    before = _num(row[0], before); maxv = _num(maximum if maximum is not None else row[1], maxv); persisted_version = int(row[2] or 0)
                    setattr(actor.resources, resource, before); setattr(actor.resources, f"maximum_{resource}", maxv)
        if expected_version is not None and int(expected_version) != int(persisted_version):
            ev = {**request_event, "event":"resource_mutation_denied", "before":before, "after":before, "maximum":maxv, "reason_code":"stale_resource_version", "expected_version":int(expected_version), "persistence_version":persisted_version}
            self._publish("resource_mutation_denied", ev)
            return ResourceMutationResult(False, actor.actor_id, cid, resource, operation, before, req, 0, before, maxv, False, "stale_resource_version", persisted_version, (request_event, ev), meta, expected_version)
        if operation in {"damage", "cost"}: after = max(0, before - req)
        elif operation in {"healing", "regeneration"}: after = min(maxv, before + req)
        elif operation == "set": after = max(0, min(maxv, req))
        elif operation in {"clamp", "maximum_changed"}: after = max(0, min(maxv, before))
        else: after = before
        applied = abs(after - before); clamped = after != (before + req if operation in {"healing","regeneration"} else before - req if operation in {"damage","cost"} else req if operation=="set" else before)
        version = persisted_version
        if after != before and self.db_path:
            with sqlite3.connect(self.db_path) as con:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute("SELECT version FROM actor_resource_versions WHERE actor_id=? AND resource=?", (actor.actor_id, resource)).fetchone()
                version = int(row[0] if row else 0) + 1
                con.execute("INSERT INTO actor_resource_versions(actor_id,resource,value,maximum,version,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(actor_id,resource) DO UPDATE SET value=excluded.value,maximum=excluded.maximum,version=actor_resource_versions.version+1,updated_at=excluded.updated_at", (actor.actor_id, resource, after, maxv, version, _now()))
                self._sync_character(actor, resource, after, maxv, con)
        setattr(actor.resources, resource, after); setattr(actor.resources, f"maximum_{resource}", maxv)
        evname = "resource_mutation_applied" if after != before else "resource_mutation_denied"
        if operation == "cost" and after != before: evname = "resource_cost_paid"
        if operation == "regeneration" and after != before: evname = "resource_regenerated"
        if operation in {"clamp","maximum_changed"}: evname = "resource_current_clamped" if clamped else "resource_maximum_changed"
        event = {**request_event, "event":evname, "after":after, "applied_amount":applied, "maximum":maxv, "reason_code":"ok" if after != before or operation in {"clamp","maximum_changed"} else "no_change"}
        self._publish(evname, event)
        res = ResourceMutationResult(True, actor.actor_id, cid, resource, operation, before, req, applied, after, maxv, clamped, event["reason_code"], version, (request_event, event), meta)
        if action_id and self.db_path:
            with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO resource_mutation_requests VALUES(?,?,?,?,?,?)", (action_id, actor.actor_id, resource, operation, json.dumps(asdict(res), default=str), _now()))
        return res

    def apply_damage(self, actor: Actor, amount: int, **kw: Any) -> ResourceMutationResult: return self.mutate(actor, "health", "damage", amount, **kw)
    def apply_healing(self, actor: Actor, amount: int, **kw: Any) -> ResourceMutationResult: return self.mutate(actor, "health", "healing", amount, **kw)
    def pay_cost(self, actor: Actor, resource: str, amount: int, **kw: Any) -> ResourceMutationResult: return self.mutate(actor, resource, "cost", amount, **kw)
    def regenerate(self, actor: Actor, resource: str, amount: int, **kw: Any) -> ResourceMutationResult: return self.mutate(actor, resource, "regeneration", amount, **kw)

    def process_due_regeneration(self, now_monotonic: float | None = None) -> int:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        if now < self._next_regeneration_monotonic:
            return 0
        self._next_regeneration_monotonic = now + 6.0
        rt = self.runtime
        if rt is None:
            return 0
        counters = getattr(rt, "performance_counters", {})
        counters["regeneration_pulses"] = counters.get("regeneration_pulses", 0) + 1
        actors = list(getattr(getattr(rt, "combat_runtime", None), "resident_actors", {}).values())
        processed = 0
        changes = 0
        for actor in actors:
            if getattr(actor, "lifecycle_state", "alive") == "dead" or _num(actor.resources.health) <= 0:
                continue
            processed += 1
            state = str(actor.combat_profile.get("combat_state") or getattr(actor, "position", "") or "standing").lower()
            mult = 4 if state == "sleeping" else 2 if state == "resting" else 1
            if state == "in_combat" or state == "fighting":
                mult = 0
            if mult <= 0:
                continue
            for resource in ("health", "mana", "stamina"):
                before = _num(getattr(actor.resources, resource, 0))
                maximum = _num(getattr(actor.resources, f"maximum_{resource}", before), before)
                after = min(maximum, before + mult)
                if after != before:
                    setattr(actor.resources, resource, after)
                    changes += 1
            if changes and actor.actor_id.startswith("character:"):
                cid = actor.actor_id.split(":", 1)[1]
                ch = getattr(rt, "active_characters", {}).get(cid)
                if ch:
                    ch.hp = actor.resources.health; ch.mana = actor.resources.mana; ch.stamina = actor.resources.stamina
                    if hasattr(rt, "mark_character_dirty"):
                        rt.mark_character_dirty(cid, "regeneration")
        counters["regeneration_actors_processed"] = counters.get("regeneration_actors_processed", 0) + processed
        counters["regeneration_resource_changes"] = counters.get("regeneration_resource_changes", 0) + changes
        return processed

    def evaluate_zero_health(self, actor: Actor, *, trigger_action_id: str = "") -> LifecycleTransitionResult:
        previous = str(getattr(actor, "lifecycle_state", "alive") or "alive")
        if _num(actor.resources.health) > 0:
            return LifecycleTransitionResult(False, actor.actor_id, previous, previous, "none", "", trigger_action_id, metadata={"reason":"health_above_zero"})
        tid = "death_" + uuid.uuid5(uuid.NAMESPACE_URL, f"{self.world_id}:{actor.actor_id}:health_zero").hex
        already = False
        if self.db_path:
            with sqlite3.connect(self.db_path) as con:
                cur = con.execute("INSERT OR IGNORE INTO actor_lifecycle_transitions(actor_id,transition_type,transition_id,trigger_action_id,previous_state,new_state,processed_at,metadata_json) VALUES(?,?,?,?,?,?,?,?)", (actor.actor_id,"death",tid,trigger_action_id,previous,"dead",_now(),"{}"))
                already = cur.rowcount == 0
        actor.lifecycle_state = "dead"; actor.combat_profile["combat_state"] = "dead"
        ev = {"event":"actor_died" if not already else "actor_death_already_processed", "actor_id":actor.actor_id, "transition_id":tid, "trigger_action_id":trigger_action_id, "world_id":self.world_id}
        self._publish(ev["event"], ev)
        return LifecycleTransitionResult(True, actor.actor_id, previous, "dead", "death", tid, trigger_action_id, already, events=(ev,))
