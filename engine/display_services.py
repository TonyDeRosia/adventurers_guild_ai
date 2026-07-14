"""Canonical display snapshot services for Smart MUD character UI.

Gameplay systems calculate values; these services only collect normalized,
player-visible values for display builders and prompt rendering.
"""
from __future__ import annotations

import logging, math, sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

from engine.mud_displays import CharacterDisplaySnapshot, AbilityDisplaySnapshot


@dataclass(frozen=True)
class CharacterWorthSnapshot:
    character_id: str = ""
    level: int = 1
    experience: int = 0
    experience_to_next_level: int = 0
    practice_points: int = 0
    training_points: int = 0
    quest_points: int = 0
    remort_count: int = 0
    currencies: dict[str, Any] = field(default_factory=dict)
    source_versions: dict[str, Any] = field(default_factory=dict)


def _field(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, Mapping) and obj.get(name) is not None:
            return obj.get(name)
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _natural_seconds(seconds: float | int | None) -> str:
    try: total = max(0, int(math.ceil(float(seconds or 0))))
    except Exception: total = 0
    if total <= 0: return "Ready"
    minutes, secs = divmod(total, 60); hours, minutes = divmod(minutes, 60)
    parts=[]
    if hours: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs or not parts: parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    return ", ".join(parts[:2])


class DisplayFormatters:
    @staticmethod
    def thousands(value: Any) -> str:
        try: return f"{int(value):,}"
        except Exception: return str(value)
    @staticmethod
    def signed(value: Any) -> str:
        try: return f"{int(value):+d}"
        except Exception: return str(value)
    @staticmethod
    def percent(value: Any) -> str:
        try: return f"{float(value):g}%"
        except Exception: return str(value)
    @staticmethod
    def duration(seconds: Any) -> str: return _natural_seconds(seconds)
    @staticmethod
    def weight(value: Any) -> str:
        try: return f"{float(value):g} lb"
        except Exception: return str(value)
    @staticmethod
    def age(years: Any) -> str:
        try: return f"{int(years)} years old"
        except Exception: return str(years) if years not in (None, "") else ""
    @staticmethod
    def currency(amount: Any, singular: str, plural: str | None = None) -> str:
        try: n=int(amount)
        except Exception: return f"{amount} {plural or singular}"
        return f"{n:,} {singular if n == 1 else (plural or singular + 's')}"


class LegacyCharacterDisplayAdapter:
    def field(self, obj: Any, *names: str, default: Any = None) -> Any:
        logger.warning("legacy_character_display_adapter_used names=%s", names)
        return _field(obj, *names, default=default)


class ProgressionDisplayAdapter:
    """Single compatibility boundary for progression display values."""
    def __init__(self, runtime: Any = None) -> None: self.runtime = runtime
    def snapshot(self, character: Any) -> dict[str, Any]:
        state = None
        rt = self.runtime
        if rt and hasattr(rt, "_progression_service"):
            try: state = rt._progression_service().get_actor_progression(str(_field(character, "id", "character_id", default="")))
            except Exception: state = None
        xp = _field(state, "experience", default=_field(character, "xp", "experience", default=0))
        level = _field(state, "level", default=_field(character, "level", default=None))
        direct_tnl = _field(character, "xp_to_next_level", "tnl", "experience_to_next_level", default=None)
        required = _field(state, "experience_to_next", default=_field(character, "next_level_xp", default=None))
        tnl = direct_tnl if direct_tnl is not None else (None if required is None else max(0, int(required or 0) - int(xp or 0)))
        percent = None
        if required not in (None, 0):
            try: percent = max(0, min(100, int((int(xp or 0) / int(required)) * 100)))
            except Exception: percent = None
        return {k:v for k,v in {
            "level": level, "xp": xp, "xp_required_next_level": required, "xp_to_next_level": tnl,
            "level_progress_percent": percent,
            "practice_points": _field(state, "practice_sessions", default=_field(character, "practice_points", default=None)),
            "training_points": _field(state, "training_sessions", default=_field(character, "training_points", default=None)),
            "quest_points": _field(character, "quest_points", default=None),
        }.items() if v is not None}


class AttributeDisplaySource:
    def snapshot(self, c: Any) -> dict[str, Any]:
        raw = _field(c, "attributes", "ability_scores", default={}) or {}
        out={}
        for key, val in (raw.items() if isinstance(raw, Mapping) else []):
            if isinstance(val, Mapping):
                base = val.get("base")
                mods = {k:int(val.get(k) or 0) for k in ("permanent_modifier","equipment_modifier","effect_modifier","temporary_modifier") if val.get(k) is not None}
                total = val.get("total_modifier", val.get("modifier", sum(mods.values()) if mods else None))
                final = val.get("final", (int(base or 0)+int(total or 0) if base is not None and total is not None else None))
                out[str(key)] = {k:v for k,v in {"base":base, **mods, "total_modifier":total, "final":final}.items() if v is not None}
            elif val is not None: out[str(key)] = {"final": val}
        return out

class CombatDisplaySource:
    def __init__(self, runtime: Any=None) -> None: self.runtime=runtime
    def mechanic(self, key: str, value: Any, label: str, *, active: bool=True, inactive_reason: str="", unit: str="", display_format: str="number", source_version: str="") -> dict[str, Any]:
        return {"value": value, "label": label, "active": bool(active), "inactive_reason": inactive_reason, "unit": unit, "display_format": display_format, "source_version": source_version}
    def snapshot(self, c: Any) -> dict[str, Any]:
        stats = _field(c, "calculated_stats", "stats", default={}) or {}
        keys=("armor","evasion","accuracy","hit_bonus","damage_bonus","spell_saves","saves","resistances","critical_melee","critical_spell","critical_heal","weapon_damage_summary","unarmed_damage_summary")
        out={k:(stats.get(k) if isinstance(stats, Mapping) and k in stats else _field(c,k)) for k in keys if (isinstance(stats, Mapping) and k in stats) or _field(c,k) is not None}
        out.setdefault("mechanics", {})
        out["mechanics"].setdefault("parry", self.mechanic("parry", out.get("parry", 0), "Parry", active=False, inactive_reason="Parry is not an active combat mechanic in this ruleset yet."))
        out["mechanics"].setdefault("block", self.mechanic("block", out.get("block", 0), "Block", active=False, inactive_reason="Block is not an active combat mechanic in this ruleset yet."))
        return out

class CarryingDisplaySource:
    def __init__(self, runtime: Any=None) -> None: self.runtime=runtime
    def snapshot(self, c: Any) -> dict[str, Any]:
        cur=_field(c,"current_weight","carry_weight")
        cap=_field(c,"carry_capacity","maximum_weight","max_weight")
        item_count=_field(c,"item_count","inventory_count")
        return {k:v for k,v in {"current_weight":cur,"carry_capacity":cap,"item_count":item_count,"max_item_count":_field(c,"max_item_count"),"encumbrance_text":_field(c,"encumbrance_text","encumbrance","encumbrance_key")}.items() if v is not None}

class CurrencyDisplaySource:
    def __init__(self, runtime: Any=None) -> None: self.runtime=runtime
    def snapshot(self, c: Any) -> dict[str, Any]:
        actor_id=str(_field(c,"id","character_id", default=""))
        rt=self.runtime
        if rt and getattr(rt, "state_store", None):
            try:
                svc = rt._economy_service() if hasattr(rt, "_economy_service") else getattr(rt, "economy_service", None)
                if svc is None:
                    from engine.economy import EconomyService
                    svc=EconomyService(rt.state_store.db_path, getattr(rt,"active_world_id","") or "shattered_realms", getattr(getattr(rt,"active_world",None),"root",None), getattr(rt,"event_bus",None), rt)
                balances=svc.get_currency_balances("actor", actor_id)
                profiles={p.get("id"):p for p in svc.content.list("currency_profiles")}
                ordered=sorted(balances, key=lambda k:int((profiles.get(k) or {}).get("display_order", {"gold":10,"silver":20,"copper":30}.get(k,999)) or 999))
                return {k:balances[k] for k in ordered if k in profiles or k in {"gold","silver","copper"}}
            except Exception:
                logger.exception("currency_display_source_failed")
        cur=dict(_field(c,"currency", default={}) or {}) if isinstance(_field(c,"currency", default={}), Mapping) else {}
        for key in ("gold","silver","copper"):
            val=_field(c,key)
            if val is not None: cur.setdefault(key, val)
        return {k:v for k,v in cur.items() if v is not None and not str(k).startswith(("ledger", "premium"))}

class SurvivalDisplaySource:
    def snapshot(self, c: Any) -> dict[str, Any]: return {k:_field(c,k) for k in ("posture","hunger","thirst","fatigue","exposure","active_combat","status_conditions") if _field(c,k) not in (None,"")}
class EffectDisplaySource:
    def snapshot(self, c: Any) -> list[dict[str, Any]]:
        raw=_field(c,"effects","affects", default=[]) or []; items = raw.values() if isinstance(raw, Mapping) else raw; out=[]
        for e in items:
            d=dict(e) if isinstance(e, Mapping) else {"name":str(e)}
            if d.get("hidden") or d.get("secret") or d.get("admin_only"): continue
            out.append(d)
        return out
class TimeDisplaySource:
    def snapshot(self, svc: Any, c: Any) -> dict[str, Any]:
        return {k:v for k,v in {"play_time": svc._natural_duration(_field(c,"played_seconds","play_seconds")), "last_login": svc._natural_last_login(_field(c,"last_login","last_login_at"))}.items() if v}


class CharacterDisplaySnapshotService:
    def __init__(self, runtime: Any = None) -> None:
        self.runtime = runtime
        self._snapshot_cache: dict[tuple[Any, ...], CharacterDisplaySnapshot] = {}
        self._worth_cache: dict[tuple[Any, ...], CharacterWorthSnapshot] = {}
        self.last_cache_hit = False
        self.progression = ProgressionDisplayAdapter(runtime)
        self.attributes = AttributeDisplaySource()
        self.combat = CombatDisplaySource(runtime)
        self.carrying = CarryingDisplaySource(runtime)
        self.currency = CurrencyDisplaySource(runtime)
        self.survival = SurvivalDisplaySource()
        self.effects = EffectDisplaySource()
        self.time_source = TimeDisplaySource()

    def _version_key(self, character: Any, *, worth: bool = False) -> tuple[Any, ...]:
        actor_data = _field(character, "actor_data", default={}) or {}
        versions = actor_data.get("source_versions", {}) if isinstance(actor_data, Mapping) else {}
        pieces = [
            _field(character, "id", "character_id", default=""),
            getattr(self.runtime, "active_world_id", "") if self.runtime else "",
            _field(character, "level", default=1), _field(character, "xp", "experience", default=0),
            _field(character, "gold", default=0), _field(character, "room_id", "current_room_id", default=""),
            len(_field(character, "inventory", default=[]) or []), len(_field(character, "equipment", default=[]) or []),
            len(_field(character, "effects", "affects", default=[]) or []),
            repr(sorted((versions or {}).items())) if isinstance(versions, Mapping) else repr(versions),
        ]
        if worth:
            return tuple(pieces[:5] + [pieces[-1]])
        return tuple(pieces)

    def invalidate(self, character_id: str | None = None) -> None:
        if not character_id:
            self._snapshot_cache.clear(); self._worth_cache.clear(); return
        self._snapshot_cache = {k:v for k,v in self._snapshot_cache.items() if str(k[0]) != str(character_id)}
        self._worth_cache = {k:v for k,v in self._worth_cache.items() if str(k[0]) != str(character_id)}

    def build_snapshot(self, character: Any) -> CharacterDisplaySnapshot:
        key = self._version_key(character)
        cached = self._snapshot_cache.get(key)
        if cached is not None:
            self.last_cache_hit = True
            return cached
        self.last_cache_hit = False
        if self.runtime is not None:
            getattr(self.runtime, "performance_counters", {}).setdefault("display_snapshot_builds", 0)
            self.runtime.performance_counters["display_snapshot_builds"] += 1
        prog = self.progression.snapshot(character)
        rt = self.runtime
        canonical_snapshot = None
        combat_service = getattr(rt, "combat_stat_service", None) if rt else None
        if combat_service is not None:
            try:
                canonical_snapshot = combat_service.get_combat_snapshot(character, {"runtime": rt})
            except Exception:
                logger.exception("canonical_combat_snapshot_failed")
        attrs = self._canonical_attributes(canonical_snapshot) if canonical_snapshot is not None else self.attributes.snapshot(character)
        combat = self._canonical_combat(canonical_snapshot) if canonical_snapshot is not None else self.combat.snapshot(character)
        carrying = self._canonical_carrying(canonical_snapshot) if canonical_snapshot is not None else self.carrying.snapshot(character)
        currency = self.currency.snapshot(character)
        identity={k:v for k,v in {
                "character_id": _field(character,"id","character_id"), "display_name": _field(character,"name","display_name", default="Adventurer"),
                "title": _field(character,"title"), "race_name": _field(character,"race_name","race"), "class_name": _field(character,"class_name","character_class","char_class"),
                "level": prog.get("level"), "alignment": _field(character,"alignment"), "age": self._natural_age(character), "birthday": _field(character,"birthday"),
            }.items() if v not in (None, "")}
        resources={}
        combat_sections = {
            "offense": combat.get("offense", {k: combat.get(k) for k in ("accuracy","hit_bonus","attack_power","damage_bonus","spell_power","healing_power") if k in combat}),
            "defense": combat.get("defense", {k: combat.get(k) for k in ("armor","evasion","critical_avoidance") if k in combat}),
            "saves": combat.get("saves", combat.get("spell_saves", {})) or {},
            "resistances": combat.get("resistances", {}) or {},
            "criticals": combat.get("criticals", {k: combat.get(k) for k in ("critical_melee","critical_spell","critical_heal","critical_damage") if k in combat}),
            "mechanics": combat.get("mechanics", {}),
        }
        snapshot = CharacterDisplaySnapshot(
            schema_version="phase13c3-b.snapshot.v1",
            snapshot_version="phase13c3-b.snapshot.v1",
            character_id=str(identity.get("character_id") or ""),
            generated_at=datetime.now(timezone.utc).isoformat(),
            identity=identity,
            title=str(identity.get("title") or ""),
            race={"name": identity.get("race_name"), "availability": "available" if identity.get("race_name") else "unavailable"},
            character_class={"name": identity.get("class_name"), "availability": "available" if identity.get("class_name") else "unsupported"},
            level=int(prog.get("level") or identity.get("level") or 1),
            alignment=str(identity.get("alignment") or ""),
            age={"display": identity.get("age"), "birthday": identity.get("birthday")},
            location={"room_id": _field(character, "room_id", "current_room_id"), "room_name": _field(character, "room_name")},
            resources=resources,
            progression=prog, attributes=attrs, combat=combat, carrying=carrying, currency=currency,
            offense=combat_sections["offense"], defense=combat_sections["defense"], saves=combat_sections["saves"], resistances=combat_sections["resistances"], criticals=combat_sections["criticals"],
            weapon_profile=combat.get("weapon_profile", {}) if isinstance(combat.get("weapon_profile", {}), Mapping) else (combat.get("weapon_damage_summary", {}) if isinstance(combat.get("weapon_damage_summary", {}), Mapping) else {"summary": combat.get("weapon_damage_summary", "")}),
            unarmed_profile=combat.get("unarmed_profile", {}) if isinstance(combat.get("unarmed_profile", {}), Mapping) else (combat.get("unarmed_damage_summary", {}) if isinstance(combat.get("unarmed_damage_summary", {}), Mapping) else {"summary": combat.get("unarmed_damage_summary", "")}),
            speed=combat.get("speed", {k: combat.get(k) for k in ("initiative","attack_speed","casting_speed","movement_speed","recovery_speed") if k in combat}),
            encumbrance={k: carrying.get(k) for k in ("encumbrance_text","encumbrance_state","encumbrance_percent") if k in carrying},
            survival=self.survival.snapshot(character),
            conditions=list(_field(character, "conditions", "status_conditions", default=[]) or []),
            time=self.time_source.snapshot(self, character),
            effects=self.effects.snapshot(character), inventory=list(_field(character,"inventory", default=[]) or []), equipment=list(_field(character,"equipment", default=[]) or []),
            active_affects=self.effects.snapshot(character),
            mechanics=combat_sections["mechanics"],
            source_versions=self._source_versions(canonical_snapshot, combat, prog),
        )
        self._snapshot_cache[key] = snapshot
        return snapshot

    def build_worth_snapshot(self, character: Any) -> CharacterWorthSnapshot:
        key = self._version_key(character, worth=True)
        cached = self._worth_cache.get(key)
        if cached is not None:
            self.last_cache_hit = True
            return cached
        self.last_cache_hit = False
        prog = self.progression.snapshot(character)
        currency = self.currency.snapshot(character)
        snap = CharacterWorthSnapshot(
            character_id=str(_field(character, "id", "character_id", default="")),
            level=int(prog.get("level") or _field(character, "level", default=1) or 1),
            experience=int(prog.get("xp") or 0),
            experience_to_next_level=int(prog.get("xp_to_next_level") or 0),
            practice_points=int(prog.get("practice_points") or 0),
            training_points=int(prog.get("training_points") or 0),
            quest_points=int(prog.get("quest_points") or 0),
            remort_count=int(_field(character, "remort_count", default=0) or 0),
            currencies=currency,
            source_versions={"progression": str(prog.get("source_version") or "progression-display-adapter"), "currency": "currency-display-source"},
        )
        self._worth_cache[key] = snap
        return snap


    def _stat_entry(self, stat_id: str, label: str, value: Any, source_version: str, *, order: int = 0, unit: str = "") -> dict[str, Any]:
        return {"stat_id": stat_id, "label": label, "value": value, "display_order": order, "unit": unit, "active": True, "source_version": source_version}

    def _canonical_attributes(self, snap: Any) -> dict[str, Any]:
        out={}
        for i,(sid,a) in enumerate((getattr(snap, "attributes", {}) or {}).items()):
            out[sid]={"stat_id": sid, "label": getattr(a, "name", sid.replace("_"," ").title()), "short_label": getattr(a, "short_name", sid[:3].upper()), "base": getattr(a,"base_value",0), "permanent_modifier": getattr(a,"permanent_modifier",0), "equipment_modifier": getattr(a,"equipment_modifier",0), "effect_modifier": getattr(a,"affect_modifier",0), "temporary_modifier": getattr(a,"temporary_modifier",0), "final": getattr(a,"final_value",0), "value": getattr(a,"final_value",0), "minimum": getattr(a,"minimum_value",0), "maximum": getattr(a,"maximum_value",0), "display_order": i*10+10, "active": True, "source_version": getattr(snap,"source_version","")}
        return out

    def _canonical_combat(self, snap: Any) -> dict[str, Any]:
        if snap is None: return {}
        sv=getattr(snap,"source_version","")
        def entries(mapping):
            return {k:self._stat_entry(k, k.replace("_"," ").title(), v, sv, order=i*10+10) for i,(k,v) in enumerate((mapping or {}).items())}
        weapon=getattr(snap,"weapon_profile",None); unarmed=getattr(snap,"unarmed_profile",None)
        def prof(p):
            return {} if not p else {"name": getattr(p,"source", ""), "weapon_name": getattr(p,"source", ""), "minimum_damage": getattr(p,"minimum_damage",0), "maximum_damage": getattr(p,"maximum_damage",0), "damage_type": getattr(p,"damage_type", "physical"), "attack_speed": getattr(p,"attack_speed",0), "reach": getattr(p,"reach",0), "range": getattr(p,"range",0), "active": True, "source_version": sv}
        return {"offense": entries(getattr(snap,"offense",{})), "defense": entries(getattr(snap,"defense",{})), "saves": entries(getattr(snap,"saves",{})), "resistances": {k:self._stat_entry(k,k.replace("_"," ").title(),v,sv,order=i*10+10,unit="percentage") for i,(k,v) in enumerate((getattr(snap,"resistances",{}) or {}).items())}, "criticals": entries(getattr(snap,"critical",{})), "speed": entries(getattr(snap,"speed",{})), "weapon_profile": prof(weapon), "unarmed_profile": prof(unarmed), "mechanics": {"parry":{"label":"Parry","value":0,"active":False,"inactive_reason":"Parry is not an active combat mechanic in this ruleset yet."}, "block":{"label":"Block","value":0,"active":False,"inactive_reason":"Block is not an active combat mechanic in this ruleset yet."}}, "source_version": sv}

    def _canonical_carrying(self, snap: Any) -> dict[str, Any]:
        sv=getattr(snap,"source_version","")
        c=dict(getattr(snap,"carrying",{}) or {})
        if not c: return {}
        return {"current_weight":{"label":"Current Weight","value":c.get("current_carry_weight"),"unit":"lb","display_order":10,"source_version":sv}, "carry_capacity":{"label":"Capacity","value":c.get("carry_capacity"),"unit":"lb","display_order":20,"source_version":sv}, "encumbrance_percent":{"label":"Encumbrance","value":c.get("encumbrance_percent"),"unit":"percentage","display_order":30,"source_version":sv}, "encumbrance_state":{"label":"State","value":str(c.get("encumbrance_state","unburdened")).title(),"display_order":40,"source_version":sv}}

    def _source_versions(self, snap: Any, combat: Mapping[str, Any], prog: Mapping[str, Any]) -> dict[str, Any]:
        sv=getattr(snap,"source_version","") or combat.get("source_version") or "legacy-display-adapter"
        return {"snapshot": "phase13c3-b.snapshot.v1", "attributes": sv, "combat": sv, "equipment": sv, "effects": sv, "resources": sv, "progression": str(prog.get("source_version") or "progression-display-adapter"), "definitions": sv, "location": "character-location-fields"}

    def _attributes(self, c: Any) -> dict[str, Any]:
        raw = _field(c, "attributes", "ability_scores", default={}) or {}
        out={}
        for key, val in (raw.items() if isinstance(raw, Mapping) else []):
            if isinstance(val, Mapping):
                out[str(key)] = {k:int(val.get(k) or 0) for k in ("base","permanent_modifier","equipment_modifier","effect_modifier","temporary_modifier","modifier","final") if val.get(k) is not None}
            elif val is not None: out[str(key)] = {"final": val}
        return out

    def _combat(self, c: Any) -> dict[str, Any]:
        stats = _field(c, "calculated_stats", "stats", default={}) or {}
        keys=("armor","evasion","accuracy","hit_bonus","damage_bonus","spell_saves","saves","resistances","critical_melee","critical_spell","critical_heal","weapon_damage_summary","unarmed_damage_summary")
        return {k:(stats.get(k) if isinstance(stats, Mapping) and k in stats else _field(c,k)) for k in keys if (isinstance(stats, Mapping) and k in stats) or _field(c,k) is not None}

    def _carrying(self, c: Any) -> dict[str, Any]:
        cur=_field(c,"current_weight","carry_weight")
        cap=_field(c,"carry_capacity","maximum_weight","max_weight")
        item_count=_field(c,"item_count","inventory_count")
        return {k:v for k,v in {"current_weight":cur,"carry_capacity":cap,"item_count":item_count,"max_item_count":_field(c,"max_item_count"),"encumbrance_text":_field(c,"encumbrance_text","encumbrance","encumbrance_key")}.items() if v is not None}

    def _currency(self, c: Any) -> dict[str, Any]:
        cur=dict(_field(c,"currency", default={}) or {}) if isinstance(_field(c,"currency", default={}), Mapping) else {}
        for key in ("gold","silver","copper"):
            val=_field(c,key)
            if val is not None: cur.setdefault(key, val)
        return {k:v for k,v in cur.items() if v is not None and not str(k).startswith(("ledger", "premium"))}

    def _visible_effects(self, c: Any) -> list[dict[str, Any]]:
        raw=_field(c,"effects","affects", default=[]) or []
        items = raw.values() if isinstance(raw, Mapping) else raw
        out=[]
        for e in items:
            d=dict(e) if isinstance(e, Mapping) else {"name":str(e)}
            if d.get("hidden") or d.get("secret") or d.get("admin_only"): continue
            out.append(d)
        return out

    def _natural_duration(self, seconds: Any) -> str:
        if seconds is None: return ""
        try: total=int(seconds)
        except Exception: return str(seconds)
        days, rem=divmod(total, 86400); hours=rem//3600
        return ", ".join([p for p in (f"{days} day{'s' if days!=1 else ''}" if days else "", f"{hours} hour{'s' if hours!=1 else ''}" if hours else "") if p]) or "0 hours"
    def _natural_age(self, c: Any) -> Any: return _field(c,"age")
    def _natural_last_login(self, value: Any) -> str:
        if not value: return ""
        return str(value).replace("T", " ").split("+")[0]


class AbilityDisplaySnapshotService:
    def __init__(self, execution_service: Any) -> None: self.execution_service = execution_service
    def list_snapshots(self, character: Any, family: str = "abilities") -> list[AbilityDisplaySnapshot]:
        svc=self.execution_service; actor_id=str(_field(character,"id","character_id", default=""))
        if hasattr(svc, "actor_from_character"): svc.actor_from_character(character)
        rows = svc.get_actor_abilities(actor_id) if svc else []
        out=[]
        for row in rows:
            kind=str(row.get("ability_type") or "ability")
            if family == "skills" and kind == "spell": continue
            if family == "spells" and kind != "spell": continue
            aid=str(row.get("id") or row.get("ability_id") or "")
            validation = svc.validate_ability_use(actor_id, aid, target=None, preview=True) if hasattr(svc,"validate_ability_use") else svc.trace_ability(actor_id, aid, None)
            state = validation.get("availability") or ("READY" if validation.get("ok") else "UNKNOWN")
            out.append(AbilityDisplaySnapshot(ability_id=aid, display_name=str(row.get("name") or aid.replace("_"," ").title()), ability_kind=kind, category=str(row.get("category") or row.get("school") or "General"), rank=int(row.get("proficiency") or row.get("rank") or 1), maximum_rank=int(row.get("maximum_proficiency") or row.get("maximum_rank") or 100), description=str(row.get("description") or ""), resource_costs=tuple(row.get("costs") or ()), cooldown_remaining=validation.get("cooldown_remaining_text"), target_mode=str((row.get("targeting") or {}).get("mode") or "self"), availability=state.lower(), availability_reason_code=str(validation.get("reason_code") or state).lower(), availability_text=str(validation.get("message") or state.replace("_", " ").title()), passive=(kind == "passive"), usage_syntax=str(row.get("usage") or f"use {aid}")))
        return out


def ability_snapshots_as_rows(snaps: list[AbilityDisplaySnapshot]) -> list[dict[str, Any]]:
    return [{"id":s.ability_id,"name":s.display_name,"ability_type":s.ability_kind,"category":s.category,"rank":s.rank,"maximum_rank":s.maximum_rank,"description":s.description,"costs":list(s.resource_costs),"status_text":s.availability_text,"availability_text":s.availability_text,"passive":s.passive,"cooldown_remaining":s.cooldown_remaining} for s in snaps]

__all__ = ["CharacterWorthSnapshot", "CharacterDisplaySnapshotService", "AbilityDisplaySnapshotService", "ProgressionDisplayAdapter", "AttributeDisplaySource", "CombatDisplaySource", "CarryingDisplaySource", "CurrencyDisplaySource", "SurvivalDisplaySource", "EffectDisplaySource", "TimeDisplaySource", "LegacyCharacterDisplayAdapter", "DisplayFormatters", "ability_snapshots_as_rows", "_natural_seconds"]
