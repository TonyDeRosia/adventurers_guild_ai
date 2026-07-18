"""Authoritative runtime heartbeat, world clock, and active effects."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import uuid

@dataclass
class HeartbeatConfig:
    pulses_per_second: int = 10
    pulses_per_tick: int = 75
    ticks_per_game_hour: int = 1
    game_hours_per_day: int = 24
    days_per_month: int = 30
    months_per_year: int = 12
    years: int = 1

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "HeartbeatConfig":
        d = dict(data or {})
        if "base_pulse_ms" in d and "pulses_per_second" not in d:
            d["pulses_per_second"] = max(1, int(round(1000 / max(1, int(d.get("base_pulse_ms") or 100)))))
        if "point_update_pulse_count" in d and "pulses_per_tick" not in d:
            d["pulses_per_tick"] = int(d.get("point_update_pulse_count") or 75)
        return cls(**{k: max(1, int(d.get(k, getattr(cls, k)))) for k in cls.__dataclass_fields__})

    @property
    def base_pulse_ms(self) -> int:
        return int(1000 / max(1, self.pulses_per_second))

@dataclass
class GameClock:
    config: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    total_ticks: int = 0
    year: int = 1
    month: int = 1
    day: int = 1
    hour: int = 6
    minute: int = 0

    def advance_tick(self) -> list[tuple[str, dict[str, Any]]]:
        events=[("world.minute", self.snapshot())]
        self.total_ticks += 1
        if self.total_ticks % self.config.ticks_per_game_hour == 0:
            old_hour = self.hour
            self.hour += 1; self.minute = 0
            if self.hour >= self.config.game_hours_per_day:
                self.hour = 0; self.day += 1; events.append(("world.day", self.snapshot()))
                if self.day > self.config.days_per_month:
                    self.day = 1; self.month += 1; events.append(("world.month", self.snapshot()))
                    if self.month > self.config.months_per_year:
                        self.month = 1; self.year += 1; events.append(("world.year", self.snapshot()))
            events.append(("world.hour", self.snapshot()))
            if old_hour != self.hour:
                if self.hour == 6: events.append(("world.dawn", {**self.snapshot(), "message":"The sun rises in the east."}))
                if self.hour == 18: events.append(("world.sunset", {**self.snapshot(), "message":"The night has begun."}))
        return events

    def snapshot(self) -> dict[str, Any]:
        return {"total_ticks":self.total_ticks,"year":self.year,"month":self.month,"day":self.day,"hour":self.hour,"minute":self.minute}

class ActiveEffectService:
    def __init__(self, runtime: Any): self.runtime = runtime
    def apply_effect(self, character: Any, *, name: str, duration_ticks: int | None = None, category: str = "Spell", source: str = "system", summary: str = "", modifiers: dict[str,int] | None = None, flags: list[str] | None = None, equipment: bool = False, permanent: bool = False, application_message: str = "", expiration_message: str = "") -> dict[str, Any]:
        effects = getattr(character, "affects", None) if isinstance(getattr(character, "affects", None), dict) else {}
        eid = "eff_" + uuid.uuid4().hex
        rec = {"id":eid,"effect_instance_id":eid,"name":name,"display_name":name,"source":source,"category":category.title(),"duration":None if permanent else int(duration_ticks or 0),"remaining":None if permanent else int(duration_ticks or 0),"remaining_ticks":None if permanent else int(duration_ticks or 0),"summary":summary,"modifiers":modifiers or {},"stat_modifiers":modifiers or {},"flags":flags or [],"equipment":equipment,"permanent":permanent,"application_message":application_message,"expiration_message":expiration_message,"stacking_policy":"independent","refresh_policy":"refresh"}
        effects[eid]=rec; character.affects=effects
        self.rebuild_derived_stats(character)
        if getattr(self.runtime, "event_bus", None): self.runtime.event_bus.publish("character.effect.applied", rec, source_system="active_effects", world_id=getattr(self.runtime,"active_world_id","") or "", character_id=getattr(character,"id", ""))
        if application_message and hasattr(self.runtime, "_enqueue_room_output"): self.runtime._enqueue_room_output(character.id, application_message, room_id=getattr(character,"room_id",""), category="effect")
        self._dirty(character, "effect_applied"); return rec
    def process_tick(self) -> int:
        expired=0
        for ch in list(getattr(self.runtime, "active_characters", {}).values()):
            effects = getattr(ch, "affects", {}) if isinstance(getattr(ch, "affects", {}), dict) else {}
            for eid, eff in list(effects.items()):
                if eff.get("permanent") or eff.get("equipment"): continue
                rem = eff.get("remaining_ticks", eff.get("remaining", eff.get("duration")))
                if rem is None: continue
                eff["remaining_ticks"] = eff["remaining"] = int(rem) - 1
                if eff["remaining_ticks"] <= 0:
                    effects.pop(eid, None); expired += 1
                    if getattr(self.runtime, "event_bus", None): self.runtime.event_bus.publish("character.effect.expired", eff, source_system="active_effects", world_id=getattr(self.runtime,"active_world_id","") or "", character_id=getattr(ch,"id", ""))
                    msg = eff.get("expiration_message")
                    if msg and hasattr(self.runtime, "_enqueue_room_output"): self.runtime._enqueue_room_output(ch.id, msg, room_id=getattr(ch,"room_id",""), category="effect")
            ch.affects = effects; self.rebuild_derived_stats(ch); self._dirty(ch, "effect_tick")
        return expired
    def rebuild_derived_stats(self, character: Any) -> dict[str, Any]:
        base = dict(getattr(character, "attributes", {}) or {})
        totals = dict(base)
        for eff in (getattr(character, "affects", {}) or {}).values():
            if isinstance(eff, dict):
                for k,v in (eff.get("stat_modifiers") or eff.get("modifiers") or {}).items(): totals[k]=int(totals.get(k,0) or 0)+int(v or 0)
        character.calculated_stats = {**dict(getattr(character,"calculated_stats",{}) or {}), "derived_from_effects": totals}
        return totals
    def _dirty(self, ch: Any, reason: str):
        if hasattr(self.runtime, "invalidate_character_projections"): self.runtime.invalidate_character_projections(ch.id, reason)
        if hasattr(self.runtime, "mark_character_dirty"): self.runtime.mark_character_dirty(ch.id, reason)

def format_duration(effect: dict[str, Any], pulses_per_tick: int = 1, pulses_per_second: int = 1) -> str:
    if effect.get("permanent") or effect.get("remaining") is None or effect.get("remaining_ticks") is None: return "permanent"
    seconds = max(0, int(effect.get("remaining_ticks") or 0) * max(1, int(pulses_per_tick)) // max(1, int(pulses_per_second)))
    if seconds < 60: return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60: return f"{minutes}m"
    return f"{minutes//60}h {minutes%60}m"
