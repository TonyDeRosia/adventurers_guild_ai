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
from .death_rewards import (CharacterXPService, alignment_after, death_penalty, npc_normal_xp, pve_glory, pvp_glory, pvp_group_xp, rare_kill_bonus)


class DeathState(StrEnum):
    ALIVE="ALIVE"; DEFEATED_PENDING_DEATH="DEFEATED_PENDING_DEATH"; DEATH_PROCESSING="DEATH_PROCESSING"; DEAD_PROCESSED="DEAD_PROCESSED"; DEAD_PROCESSED_PENDING_RESPAWN="DEAD_PROCESSED_PENDING_RESPAWN"; REWARDS_COMPLETED="REWARDS_COMPLETED"; REMOVED="REMOVED"

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
                 operations: dict[str, Callable[..., Any]] | None = None, publish: Callable[[str, dict[str, Any]], None] | None = None, xp_service: CharacterXPService | None = None, rng: Any | None = None, clock: Callable[[], float] | None = None):
        self.db_path=str(db_path); self.actor_lookup=actor_lookup or (lambda _id: None); self.operations=operations or {}; self.publish=publish or (lambda _n,_p: None); self.xp_service=xp_service or CharacterXPService(); self.rng=rng or random; self.clock=clock or __import__("time").time; self.init_schema()
    def init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS death_ledger(death_id TEXT PRIMARY KEY, world_id TEXT, victim_actor_id TEXT, life_generation TEXT, terminal_damage_event_id TEXT, status TEXT, immediate_source_actor_id TEXT, credited_killer_actor_id TEXT, corpse_instance_id TEXT, result_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, failure_stage TEXT)""")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS death_ledger_terminal_once ON death_ledger(world_id,victim_actor_id,life_generation,terminal_damage_event_id)")
            con.execute("CREATE TABLE IF NOT EXISTS death_reward_awards(death_id TEXT, recipient_id TEXT, award_type TEXT, payload_json TEXT NOT NULL, PRIMARY KEY(death_id,recipient_id,award_type))")
    def _event(self, name: str, req: DeathRequest, **data: Any) -> str:
        event_id=f"{name}:{req.death_id}"
        # Preserve the originating ability/damage identity on every Phase 20
        # lifecycle event without introducing a parallel event contract.
        linkage = {key: value for key, value in (req.source_metadata or {}).items()
                   if key in {"ability_request_id", "ability_id", "damage_result_id"}}
        self.publish(name, {"event_id":event_id,"death_id":req.death_id,
                            "victim_actor_id":req.victim_actor_id,
                            "world_id":req.world_id, "engagement_id":req.engagement_id,
                            "terminal_damage_event_id":req.terminal_damage_event_id,
                            **linkage, **data})
        return event_id
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

    # Phase 20B deliberately runs after the 20A foundation record.  Adapter callbacks
    # integrate the existing group, quest, corpse and transport services; this class
    # never reimplements their objective or transfer rules.
    def process_rewards(self, request: DeathRequest) -> DeathResult:
        with sqlite3.connect(self.db_path) as con:
            con.row_factory=sqlite3.Row
            row=con.execute("SELECT * FROM death_ledger WHERE death_id=?", (request.death_id,)).fetchone()
            if not row: raise ValueError("death must be claimed by Phase 20A before rewards")
            if row["status"] == DeathState.REWARDS_COMPLETED: return self._stored(row)
            if row["status"] not in {DeathState.REMOVED, DeathState.DEAD_PROCESSED, DeathState.DEAD_PROCESSED_PENDING_RESPAWN}:
                raise ValueError("death foundation is not complete")
            foundation=self._stored(row); credited=row["credited_killer_actor_id"]
        victim=self.actor_lookup(request.victim_actor_id); killer=self.actor_lookup(credited) if credited else None
        victim_is_npc=request.victim_actor_id.startswith("entity:") or _value(victim,"kind","").lower() in {"npc","entity","mobile"}
        # Snapshot was captured with 20A where available.  Its list is stable across retries.
        snap=request.source_metadata.get("group_snapshot", [])
        if not snap and credited: snap=[{"actor_id": credited, "room_id": request.room_id, "zone_id": request.source_metadata.get("zone_id"), "group_id": request.source_metadata.get("group_id")}]
        recipients=[]; seen=set()
        for member in snap:
            ident=str(member.get("actor_id") if isinstance(member,dict) else member)
            if ident and ident not in seen and _member_value(member,"room_id") == request.room_id:
                actor=self.actor_lookup(ident)
                if actor is not None and not _value(actor,"is_summoned_follower",False): recipients.append((ident,actor,member)); seen.add(ident)
        if credited and not recipients and killer is not None: recipients=[(credited,killer,{"actor_id":credited,"room_id":request.room_id})]
        event_ids=[]
        def emit(name: str, **data: Any) -> None: event_ids.append(self._event(name, request, credited_killer_actor_id=credited, room_id=request.room_id, zone_id=request.source_metadata.get("zone_id"), **data))
        def award(recipient: str, typ: str, payload: dict[str,Any]) -> bool:
            with sqlite3.connect(self.db_path) as con:
                try: con.execute("INSERT INTO death_reward_awards(death_id,recipient_id,award_type,payload_json) VALUES(?,?,?,?)",(request.death_id,recipient,typ,json.dumps(payload)))
                except sqlite3.IntegrityError: return False
            return True
        # Quest credit has wider (same-room OR same-zone) eligibility than XP.
        zone=request.source_metadata.get("zone_id")
        for member in snap:
            ident=str(_member_value(member,"actor_id") or "")
            if not ident or (_member_value(member,"room_id") != request.room_id and _member_value(member,"zone_id") != zone): continue
            if award(ident,"quest_credit",{"zone_id":zone,"room_id":request.room_id}):
                self._operation("grant_quest_credit", request, credited, recipient_id=ident, victim=victim, death_id=request.death_id, zone_id=zone, room_id=request.room_id)
                emit("death.quest_credit.granted", recipient_id=ident, group_id=_member_value(member,"group_id"))
        # Calculate and apply unmodified XP; CharacterXPService applies the global bonus once.
        normal_by_recipient={}
        if victim_is_npc:
            for ident, actor, member in recipients:
                normal=npc_normal_xp(int(_value(victim,"level",1)),int(_value(actor,"level",1)),int(_value(victim,"authored_bonus_xp",0)),self.xp_service.max_gain)
                normal_by_recipient[ident]=normal
                rare=rare_kill_bonus(normal, int(request.source_metadata.get("rare_live_count", 0)))
                if award(ident,"xp",{"normal":normal,"rare":rare}):
                    result=self.xp_service.apply(actor,normal); emit("death.reward.calculated",recipient_id=ident,base_amount=normal,bonus_amount=rare,final_amount=normal); emit("death.xp.granted",recipient_id=ident,before=result["before"],after=result["after"],final_amount=result["applied"])
                    if rare: result=self.xp_service.apply(actor,rare); emit("death.rare_bonus.granted",recipient_id=ident,base_amount=normal,bonus_amount=rare,final_amount=result["applied"])
                    before=int(_value(actor,"alignment",0)); after=alignment_after(before,int(_value(victim,"alignment",0))); _set_value(actor,"alignment",after); emit("death.alignment.changed",recipient_id=ident,before=before,after=after)
        else:
            total, share=pvp_group_xp(int(_value(victim,"current_exp",_value(victim,"exp",0))),len(recipients),self.xp_service.max_loss)
            for ident,actor,_ in recipients:
                if award(ident,"xp",{"normal":share,"rare":0,"total":total}):
                    result=self.xp_service.apply(actor,share); emit("death.xp.granted",recipient_id=ident,base_amount=share,final_amount=result["applied"])
                    before=int(_value(actor,"alignment",0)); after=alignment_after(before,int(_value(victim,"alignment",0))); _set_value(actor,"alignment",after); emit("death.alignment.changed",recipient_id=ident,before=before,after=after)
        # Primary glory remains solely with the credited player killer.
        if killer is not None and not _value(killer,"is_immortal",False):
            diff=abs(int(_value(victim,"level",1))-int(_value(killer,"level",1)))
            if victim_is_npc: base=self.rng.randint(15,25); glory=pve_glory(base,diff); cooldown=False
            else:
                now=float(self.clock()); previous=_value(killer,"last_pvp_glory_victim_id"); then=float(_value(killer,"last_pvp_glory_at",0) or 0); cooldown=previous == request.victim_actor_id and now-then < 600
                base=self.rng.randint(800,1200) if not cooldown else 0; glory=0 if cooldown else pvp_glory(base,diff)
            if award(credited,"glory",{"base":base,"amount":glory,"cooldown":cooldown}):
                if glory: _set_value(killer,"glory",int(_value(killer,"glory",0))+glory); _set_value(killer,"last_pvp_glory_victim_id",request.victim_actor_id) if not victim_is_npc else None; _set_value(killer,"last_pvp_glory_at",self.clock()) if not victim_is_npc else None
                emit("death.glory.granted",recipient_id=credited,base_amount=base,final_amount=glory,roll=base,cooldown_result=cooldown)
        if not victim_is_npc:
            # Bounty atomicity is delegated to an adapter when one exists; fallback mutates both in this unit of work.
            bounty=int(_value(victim,"bounty",0)); eligible=killer is not None and credited != request.victim_actor_id and not _value(killer,"is_immortal",False) and bounty > 0
            if eligible and award(credited,"bounty",{"amount":bounty}):
                outcome=self._operation("claim_bounty",request,credited,victim=victim,killer=killer,amount=bounty,death_id=request.death_id)
                if not outcome: _set_value(victim,"bounty",0); _set_value(killer,"gold",int(_value(killer,"gold",0))+bounty)
                emit("death.bounty.claimed",recipient_id=credited,final_amount=bounty)
            if not _value(victim,"is_immortal",False):
                threshold_fn=self.operations.get("next_level_threshold")
                threshold=threshold_fn(request, credited, victim=victim) if threshold_fn else _value(victim,"next_level_threshold",int(_value(victim,"current_exp",0)))
                if isinstance(threshold,dict): threshold=threshold.get("threshold", _value(victim,"next_level_threshold",int(_value(victim,"current_exp",0))))
                calc=death_penalty(int(_value(victim,"current_exp",_value(victim,"exp",0))),int(_value(victim,"level",1)),int(threshold),int(request.source_metadata.get("max_mortal_level",100)),self.xp_service.max_loss)
                if award(request.victim_actor_id,"death_penalty",calc):
                    result=self.xp_service.apply(victim,-calc["loss"]); emit("death.xp.penalty_applied",recipient_id=request.victim_actor_id,penalty_calculation=calc,before=result["before"],after=result["after"],final_amount=calc["loss"])
            if award(request.victim_actor_id,"criminal_flags",{}): self._operation("clear_criminal_flags",request,credited,victim=victim); emit("death.criminal_flags.cleared",recipient_id=request.victim_actor_id)
        for name,event in (("auto_split","death.auto_split.completed"),("auto_gold","death.auto_gold.completed"),("auto_loot","death.auto_loot.completed"),("auto_sacrifice","death.auto_sacrifice.completed")):
            if award(credited or "",name,{"corpse_id":foundation.corpse_instance_id}): self._operation(name,request,credited,corpse_instance_id=foundation.corpse_instance_id,victim_is_npc=victim_is_npc,death_id=request.death_id); emit(event,recipient_id=credited)
        if not victim_is_npc and award(request.victim_actor_id,"respawn",{}):
            outcome=self._operation("respawn_player",request,credited,victim=victim,death_id=request.death_id) or {}
            _set_value(victim,"hp",max(1,int(_value(victim,"hp",0)))); _set_value(victim,"position","RESTING"); _set_value(victim,"wait_state",0); _set_value(victim,"life_state","ALIVE")
            emit("death.player.respawned",recipient_id=request.victim_actor_id,respawn_room=outcome.get("room_id",request.source_metadata.get("temple_room_id")))
        self._operation("post_kill_hooks",request,credited,death_id=request.death_id)
        emit("death.rewards.completed"); emit("death.completed",stage="rewards")
        final=DeathResult(**{**asdict(foundation),"status":DeathState.REWARDS_COMPLETED,"event_ids":tuple(foundation.event_ids)+tuple(event_ids)})
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE death_ledger SET status=?, result_json=?, completed_at=CURRENT_TIMESTAMP WHERE death_id=?",(DeathState.REWARDS_COMPLETED,json.dumps(asdict(final)),request.death_id))
        return final

    def _operation(self, name: str, request: DeathRequest, credited: str | None, **kwargs: Any) -> dict[str,Any]:
        value=self.operations.get(name)
        if not value: return {}
        result=value(request, credited, **kwargs)
        return result if isinstance(result,dict) else {}

def _value(actor: Any, key: str, default: Any=None) -> Any:
    return actor.get(key,default) if isinstance(actor,dict) else getattr(actor,key,default)
def _set_value(actor: Any, key: str, value: Any) -> None:
    if isinstance(actor,dict): actor[key]=value
    else: setattr(actor,key,value)
def _member_value(member: Any, key: str) -> Any:
    return member.get(key) if isinstance(member,dict) else getattr(member,key,None)
