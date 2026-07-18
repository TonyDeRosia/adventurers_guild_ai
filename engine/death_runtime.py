"""Canonical, idempotent death-foundation runtime (Phase 20A).

The service is deliberately small and adapter-driven: the runtime supplies the
canonical corpse/item/extraction operations while this module owns claiming,
attribution, stored random outcomes, and the durable ledger.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import json, sqlite3, uuid
import random
from pathlib import Path
from typing import Any, Callable


class DeathState(StrEnum):
    ALIVE="ALIVE"; DEFEATED_PENDING_DEATH="DEFEATED_PENDING_DEATH"; DEATH_PROCESSING="DEATH_PROCESSING"; DEAD_PROCESSED="DEAD_PROCESSED"; REMOVED="REMOVED"

@dataclass(frozen=True)
class DeathRequest:
    death_id: str; world_id: str; room_id: str; victim_actor_id: str
    immediate_source_actor_id: str | None = None; damage_source_id: str = ""; damage_type: str = ""
    attack_or_ability_id: str = ""; engagement_id: str = ""; terminal_damage_event_id: str = ""
    hp_before: int = 0; hp_after: int = 0; victim_position: str = "DEAD"; timestamp_or_tick: str = ""
    source_metadata: dict[str, Any] = field(default_factory=dict); optional_explicit_reward_owner: str | None = None

@dataclass(frozen=True)
class DeathTriggerResult:
    handled: bool = False; suppress_default_death_cry: bool = False; optional_warning: str = ""

@dataclass(frozen=True)
class DeathResult:
    death_id: str; status: str; victim_actor_id: str; immediate_source_actor_id: str | None = None
    credited_killer_actor_id: str | None = None; corpse_instance_id: str | None = None; victim_removed: bool = False
    transferred_item_ids: tuple[str, ...] = (); npc_gold_result: dict[str, Any] = field(default_factory=dict)
    loot_roll_results: tuple[dict[str, Any], ...] = (); event_ids: tuple[str, ...] = (); warnings: tuple[str, ...] = (); failure_stage: str = ""


class DeathRuntimeService:
    """One death path with a SQLite atomic claim and resumable result record.

    ``operations`` is a canonical-runtime adapter.  Supported callbacks are
    ``cleanup_combat``, ``create_corpse``, ``transfer_belongings``,
    ``resolve_gold``, ``roll_loot``, ``extract_npc`` and ``emit_cry``.  Each
    receives the request/result context and may return a mapping.
    """
    def __init__(self, db_path: str | Path, *, actor_lookup: Callable[[str], Any | None] | None = None,
                 operations: dict[str, Callable[..., Any]] | None = None, publish: Callable[[str, dict[str, Any]], None] | None = None):
        self.db_path=str(db_path); self.actor_lookup=actor_lookup or (lambda _id: None); self.operations=operations or {}; self.publish=publish or (lambda _n,_p: None); self.init_schema()
    def init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS death_ledger(death_id TEXT PRIMARY KEY, world_id TEXT, victim_actor_id TEXT, life_generation TEXT, terminal_damage_event_id TEXT, status TEXT, immediate_source_actor_id TEXT, credited_killer_actor_id TEXT, corpse_instance_id TEXT, result_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, failure_stage TEXT)""")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS death_ledger_terminal_once ON death_ledger(world_id,victim_actor_id,life_generation,terminal_damage_event_id)")
    def _event(self, name: str, req: DeathRequest, **data: Any) -> str:
        event_id=f"{name}:{req.death_id}"; self.publish(name, {"event_id":event_id,"death_id":req.death_id,"victim_actor_id":req.victim_actor_id,**data}); return event_id
    def resolve_credited_killer(self, source_id: str | None, explicit: str | None = None) -> str | None:
        if explicit: return explicit
        if not source_id: return None
        current=source_id; visited=set()
        for _ in range(20):
            if current in visited: break
            visited.add(current); actor=self.actor_lookup(current)
            if actor is None: break
            kind=str(getattr(actor,"kind", "") or (actor.get("kind","") if isinstance(actor,dict) else "")).lower()
            if kind in {"player","character"} or current.startswith("character:"): return current
            master=getattr(actor,"master_id", None) or (actor.get("master_id") if isinstance(actor,dict) else None) or (actor.get("owner_id") if isinstance(actor,dict) else None)
            if not master: break
            current=str(master)
        return source_id
    @staticmethod
    def resolve_npc_gold(gold_min: int | float, gold_max: int | float, current_gold: int | float, *, rng: Any | None = None) -> dict[str, Any]:
        """Normalize authored ranges and make the inclusive gold result explicit."""
        lo=max(0, int(gold_min or 0)); hi=max(0, int(gold_max or 0)); hi=max(lo, hi)
        if lo or hi:
            amount=lo if lo == hi else (rng or random).randint(lo, hi); source="range"
        else: amount=max(0, int(current_gold or 0)); source="current_gold"
        return {"amount":amount,"gold_min":lo,"gold_max":hi,"source":source}
    @staticmethod
    def roll_npc_loot(entries: list[dict[str, Any]], *, rng: Any | None = None, item_exists: Callable[[str], bool] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
        """Roll each authored entry once; callers persist this return in the ledger."""
        randomizer=rng or random; exists=item_exists or (lambda _id: True); rolls=[]; warnings=[]
        for entry in entries:
            definition=str(entry.get("item_definition_id") or entry.get("item_id") or "")
            chance=max(0, min(100, int(entry.get("chance_percentage", entry.get("chance", 0)) or 0)))
            roll=None if chance <= 0 else randomizer.randint(1,100); dropped=bool(roll is not None and roll <= chance)
            if dropped and not exists(definition): warnings.append(f"missing loot item definition: {definition}"); dropped=False
            rolls.append({"item_definition_id":definition,"chance":chance,"roll":roll,"dropped":dropped})
        return rolls, warnings
    def _stored(self, row: sqlite3.Row) -> DeathResult:
        data=json.loads(row["result_json"] or "{}")
        return DeathResult(**data) if data else DeathResult(row["death_id"], row["status"], row["victim_actor_id"])
    def process_death(self, request: DeathRequest) -> DeathResult:
        self._event("death.requested", request)
        generation=str(request.source_metadata.get("life_generation") or request.source_metadata.get("spawn_generation") or "0")
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row; con.execute("BEGIN IMMEDIATE")
            row=con.execute("SELECT * FROM death_ledger WHERE death_id=?",(request.death_id,)).fetchone()
            if row:
                result=self._stored(row); self._event("death.duplicate_ignored",request,status=row["status"]); return result
            try:
                con.execute("INSERT INTO death_ledger(death_id,world_id,victim_actor_id,life_generation,terminal_damage_event_id,status,immediate_source_actor_id,result_json) VALUES(?,?,?,?,?,?,?,?)",(request.death_id,request.world_id,request.victim_actor_id,generation,request.terminal_damage_event_id,DeathState.DEATH_PROCESSING,request.immediate_source_actor_id,""))
            except sqlite3.IntegrityError:
                row=con.execute("SELECT * FROM death_ledger WHERE world_id=? AND victim_actor_id=? AND life_generation=? AND terminal_damage_event_id=?",(request.world_id,request.victim_actor_id,generation,request.terminal_damage_event_id)).fetchone()
                self._event("death.duplicate_ignored",request,status=row["status"]); return self._stored(row)
        events=[self._event("death.claimed",request)]
        warnings=[]; credited=self.resolve_credited_killer(request.immediate_source_actor_id,request.optional_explicit_reward_owner); events.append(self._event("death.attribution.resolved",request,credited_killer_actor_id=credited))
        def call(name: str, **kw: Any) -> dict[str,Any]:
            fn=self.operations.get(name); value=fn(request, credited, **kw) if fn else {}; return value if isinstance(value,dict) else {}
        try:
            call("cleanup_combat"); events.append(self._event("death.combat.cleaned",request))
            hook=call("trigger"); suppress=bool(hook.get("suppress_default_death_cry")); warnings.extend([str(hook["warning"])] if hook.get("warning") else [])
            if not suppress: call("emit_cry"); events.append(self._event("death.cry.emitted",request))
            corpse=call("create_corpse"); corpse_id=corpse.get("corpse_instance_id") or corpse.get("entity_id"); events.append(self._event("death.corpse.created",request,corpse_instance_id=corpse_id))
            transferred=tuple(call("transfer_belongings",corpse_instance_id=corpse_id).get("item_ids",()))
            events.append(self._event("death.item.transferred",request,item_ids=transferred))
            gold=call("resolve_gold",corpse_instance_id=corpse_id); events.append(self._event("death.gold.resolved",request,result=gold))
            loot=tuple(call("roll_loot",corpse_instance_id=corpse_id).get("rolls",())); events.append(self._event("death.loot.rolled",request,rolls=loot))
            removed=False
            if request.victim_actor_id.startswith("entity:"):
                call("extract_npc",corpse_instance_id=corpse_id); removed=True; events.append(self._event("death.npc.extracted",request))
            else: events.append(self._event("death.player.pending_respawn",request))
            status=DeathState.REMOVED if removed else DeathState.DEAD_PROCESSED
            result=DeathResult(request.death_id,status,request.victim_actor_id,request.immediate_source_actor_id,credited,corpse_id,removed,transferred,gold,loot,tuple(events),tuple(warnings))
            with sqlite3.connect(self.db_path) as con: con.execute("UPDATE death_ledger SET status=?,credited_killer_actor_id=?,corpse_instance_id=?,result_json=?,completed_at=CURRENT_TIMESTAMP WHERE death_id=?",(status,credited,corpse_id,json.dumps(asdict(result)),request.death_id))
            self._event("death.foundation.completed",request,status=status); return result
        except Exception as exc:
            result=DeathResult(request.death_id,"FAILED",request.victim_actor_id,request.immediate_source_actor_id,credited,warnings=tuple(warnings+[str(exc)]),failure_stage="processing")
            with sqlite3.connect(self.db_path) as con: con.execute("UPDATE death_ledger SET status='DEATH_PROCESSING',result_json=?,failure_stage=? WHERE death_id=?",(json.dumps(asdict(result)),"processing",request.death_id))
            self._event("death.failed",request,error=str(exc)); return result
