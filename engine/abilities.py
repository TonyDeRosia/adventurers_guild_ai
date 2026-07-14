"""Canonical Phase 6C Ability architecture.

One data-driven pipeline owns skills, spells, heals, buffs, debuffs, natural
attacks, monster powers, item abilities, passives, and future AI-selected
runtime actions.  The implementation is deliberately deterministic and built on
Actor resources, CombatEngine damage, a canonical HealingEvent, effect-instance
persistence, world-time cooldowns, and EventBus publishing.
"""
from __future__ import annotations

import json, math, re, sqlite3, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.actors import Actor, ActorRegistry, actor_from_runtime_character
from engine.combat import CombatEngine, DamageEvent
from engine.runtime_resources import RuntimeResourceService
from engine.combat_equipment import CombatContentRegistry

ABILITY_TYPES = {"skill","spell","technique","heal","buff","debuff","utility","defensive","movement","racial","profession","monster","natural","item","passive","administrative","custom"}
TARGET_MODES = {"self","single_actor","single_enemy","single_ally","single_any","current_target","room_enemy","room_ally","room_all","room","direction","item","equipped_item","corpse","none","custom"}
ACTIVATION_TYPES = {"instant","cast","channel","charged","passive","toggle","custom"}
COST_TYPES = {"flat","formula","percentage_current","percentage_maximum","all_current","custom"}
CONSUME_ON = {"start","completion","success","hit","effect_application"}
REFUNDS = {"none","full_on_interrupt","partial_on_interrupt","full_on_failure","custom"}
CAST_STATES = {"pending","casting","channeling","completed","interrupted","failed","cancelled"}
STATE_CHANGES = {"stunned","sleeping","resting","standing","fleeing","incapacitated","unconscious"}
SAFE_ID = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
MESSAGE_KEYS = {"start_self","start_target","start_room","complete_self","complete_target","complete_room","fail_self","fail_target","fail_room","interrupt_self","interrupt_target","interrupt_room","hit_self","hit_target","hit_room","miss_self","miss_target","miss_room","heal_self","heal_target","heal_room","effect_self","effect_target","effect_room"}
PLACEHOLDERS = {"actor","target","ability","weapon","damage","healing","damage_type","effect","resource","cost","stacks","item","amount","duration","room"}


def now() -> str: return datetime.now(timezone.utc).isoformat()
def jdump(v: Any) -> str: return json.dumps(v or {}, sort_keys=True)
def jload(v: Any, default: Any=None) -> Any:
    try: return json.loads(v) if isinstance(v, str) and v else (v if v is not None else (default if default is not None else {}))
    except Exception: return default if default is not None else {}
def num(v: Any, default: float=0) -> float:
    try:
        n = float(v)
        return n if math.isfinite(n) else default
    except Exception: return default

PHASE14A_OPERATIONS = {
    "deal_damage","heal","modify_resource","apply_affect","remove_affect","apply_condition","remove_condition","modify_stat",
    "grant_resistance","grant_immunity","grant_vulnerability","damage_over_time","healing_over_time","resource_over_time",
    "dispel","cleanse","send_message","trigger_ability","set_cooldown","reduce_cooldown","teleport","recall","move_target",
}
PHASE14B_RESERVED_OPERATIONS = {"aura","stance","transform","summon","dismiss_summon","create_item","destroy_item","alter_item","create_room_effect","remove_room_effect"}
TARGET_KINDS = {"self","single_actor","single_enemy","single_ally","group","room_allies","room_enemies","room_all","area","single_item","inventory_item","equipped_item","room_item","room","exit","direction","location","no_target"}
STACKING_POLICIES = {"stack","refresh_duration","replace","highest","lowest","unique","unique_by_source","unique_by_ability","unique_by_tag","increase_stacks","increase_intensity","independent_instances"}
DURATION_POLICIES = {"instant","rounds","world_ticks","world_minutes","real_time","until_logout","until_death","until_room_change","until_combat_ends","permanent","while_equipped","while_source_exists"}

@dataclass(frozen=True)
class TargetingDefinition:
    target_kind: str = "self"; allowed_actor_types: tuple[str, ...] = (); self_allowed: bool = True; friendly_allowed: bool = True; hostile_allowed: bool = True
    dead_allowed: bool = False; defeated_allowed: bool = False; same_room_required: bool = True; same_area_allowed: bool = False
    minimum_range: int = 0; maximum_range: int = 0; maximum_targets: int = 1; area_shape: str = ""; group_policy: str = ""
    line_of_sight: bool = False; visibility_required: bool = True; required_tags: tuple[str, ...] = (); forbidden_tags: tuple[str, ...] = (); empty_target_policy: str = "deny"

@dataclass(frozen=True)
class AbilityCostDefinition:
    resource: str = "mana"; operation: str = "spend"; flat_amount: int = 0; formula_id: str = ""; percentage_current: float = 0; percentage_maximum: float = 0
    minimum_cost: int = 0; maximum_cost: int = 0; pay_timing: str = "start"; refund_policy: str = "none"; failure_consumes: bool = False; interrupt_refund_percent: int = 100

@dataclass(frozen=True)
class AbilityEffectDefinition:
    effect_id: str; operation: str; target_selector: str = "target"; timing: str = "success"; formula_id: str = ""; base_value: int = 0; coefficient: float = 1.0
    resource: str = ""; damage_type: str = ""; save_definition: dict[str, Any] = field(default_factory=dict); duration: dict[str, Any] = field(default_factory=dict)
    tick_interval: int = 0; stacking: dict[str, Any] = field(default_factory=dict); conditions: list[str] = field(default_factory=list); tags: list[str] = field(default_factory=list)
    messages: dict[str, str] = field(default_factory=dict); parameters: dict[str, Any] = field(default_factory=dict); custom_hook_id: str = ""; source_version: str = "1"

@dataclass(frozen=True)
class RuntimeEffectInstance:
    effect_instance_id: str; definition_id: str; source_ability_id: str = ""; source_actor_id: str = ""; source_item_id: str = ""; target_actor_id: str = ""; target_item_id: str = ""; target_room_id: str = ""
    applied_at: int = 0; expires_at: int | None = None; duration_domain: str = "world_minutes"; next_tick_at: int | None = None; tick_interval: int = 0
    stacks: int = 1; intensity: int = 1; state: str = "active"; tags: tuple[str, ...] = (); modifiers: tuple[dict[str, Any], ...] = (); origin_action_id: str = ""; source_versions: dict[str, Any] = field(default_factory=dict); metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class AbilityUseRequest:
    action_id: str; actor_id: str; ability_id: str; command_form: str = "cast"; raw_target: Any = None; resolved_targets: tuple[dict[str, Any], ...] = (); source_type: str = "learned"; source_id: str = ""; world_id: str = ""; room_id: str = ""; context: dict[str, Any] = field(default_factory=dict); requested_at: str = field(default_factory=now); metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ActorAbilityProficiency:
    actor_id: str; ability_id: str; learned: bool = True; proficiency: int = 1; maximum_proficiency: int = 100; practice_progress: int = 0; mastery_rank: str = "novice"; uses: int = 0; successes: int = 0; failures: int = 0; last_used: str = ""; source: str = "learned"; version: int = 1

class AbilityEffectOperationRegistry:
    def __init__(self):
        self.operations = set(PHASE14A_OPERATIONS)
        self.reserved = set(PHASE14B_RESERVED_OPERATIONS)
    def validate(self, operation: str) -> None:
        if operation not in self.operations:
            raise ValueError(f"Unknown ability effect operation: {operation}")
    def is_reserved(self, operation: str) -> bool: return operation in self.reserved

class AbilityAvailabilityService:
    def __init__(self, service: "AbilityExecutionService"):
        self.service = service
    def resolve_actor_abilities(self, actor_id: str) -> list[dict[str, Any]]:
        rows=[]
        for row in self.service.get_actor_abilities(actor_id):
            rows.append({"ability": row, "availability_state": "active" if row.get("enabled", True) else "inactive", "source_type": (row.get("grants") or [{}])[0].get("source_type", row.get("source", "learned")), "source_id": (row.get("grants") or [{}])[0].get("source_id", ""), "proficiency": row.get("proficiency", 1), "hidden": row.get("visibility") == "hidden", "visible": row.get("visibility") != "hidden", "active": row.get("enabled", True), "denial_reason": ""})
        actor=self.service.actors.get(actor_id)
        for aid in (getattr(actor, "plugin_data", {}) or {}).get("npc_ability_ids", []) if actor else []:
            if aid in self.service.registry.abilities and not any(r["ability"].get("id")==aid for r in rows):
                ab=self.service.registry.abilities[aid]
                rows.append({"ability": ab.to_dict(), "availability_state": "active", "source_type": "NPC template", "source_id": actor_id, "proficiency": int((getattr(actor,"plugin_data",{}) or {}).get("proficiency", 50)), "hidden": False, "visible": True, "active": True, "denial_reason": ""})
        return rows


@dataclass
class AbilityDefinition:
    id: str; name: str = ""; short_name: str = ""; description: str = ""; ability_type: str = "custom"
    school: str = ""; category: str = ""; tags: list[str] = field(default_factory=list); enabled: bool = True; visibility: str = "normal"
    source_types: list[str] = field(default_factory=list); requirements: dict[str, Any] = field(default_factory=dict); targeting: dict[str, Any] = field(default_factory=dict)
    costs: list[dict[str, Any]] = field(default_factory=list); cooldowns: dict[str, Any] = field(default_factory=dict); timing: dict[str, Any] = field(default_factory=dict)
    range: dict[str, Any] = field(default_factory=dict); formulas: dict[str, Any] = field(default_factory=dict); damage_components: list[dict[str, Any]] = field(default_factory=list)
    healing_components: list[dict[str, Any]] = field(default_factory=list); effects_applied: list[dict[str, Any]] = field(default_factory=list); effects_removed: list[dict[str, Any]] = field(default_factory=list)
    movement_components: list[dict[str, Any]] = field(default_factory=list); state_requirements: dict[str, Any] = field(default_factory=dict); state_changes: list[dict[str, Any]] = field(default_factory=list)
    interrupt_rules: dict[str, Any] = field(default_factory=dict); messages: dict[str, str] = field(default_factory=dict); ai_hints: dict[str, Any] = field(default_factory=dict)
    plugin_data: dict[str, Any] = field(default_factory=dict); version: str = "1.0.0"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AbilityDefinition":
        data = {k: raw.get(k) for k in cls.__dataclass_fields__ if k in raw}; data.setdefault("name", raw.get("name") or raw.get("id", "")); return cls(**data)
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    @property
    def activation_type(self) -> str: return str((self.timing or {}).get("activation_type") or "instant")

@dataclass
class AbilityLoadout:
    id: str; name: str = ""; description: str = ""; ability_ids: list[str] = field(default_factory=list); priority_order: list[str] = field(default_factory=list)
    default_auto_attack: str = ""; default_defensive_ability: str = ""; default_heal_ability: str = ""; default_escape_ability: str = ""; spellup_priority: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list); plugin_data: dict[str, Any] = field(default_factory=dict)
    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AbilityLoadout": return cls(**{k: raw.get(k) for k in cls.__dataclass_fields__ if k in raw})

@dataclass
class HealingEvent:
    event_id: str; world_id: str; source_actor_id: str; target_actor_id: str; ability_id: str|None; cast_id: str|None; component_id: str|None
    base_amount: int; formula_id: str|None; critical: bool; critical_profile_id: str|None; modifiers: dict[str, Any]; final_amount: int; overheal: int; world_time: int; trace: list[dict[str, Any]]; metadata: dict[str, Any]

@dataclass(frozen=True)
class AbilityUseResult:
    ok: bool
    ability_id: str = ""
    ability_name: str = ""
    reason_code: str = ""
    player_message: str = ""
    actor_id: str = ""
    target_id: str = ""
    resource_changes: list[dict[str, Any]] = field(default_factory=list)
    cooldown_started: bool = False
    effects_applied: list[dict[str, Any]] = field(default_factory=list)
    proficiency_before: int | None = None
    proficiency_after: int | None = None
    proficiency_increased: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

class AbilityRuntimeGateway:
    """One public runtime entry point for player ability use."""

    def __init__(self, service: "AbilityExecutionService", runtime: Any | None = None):
        self.service = service
        self.runtime = runtime or getattr(service, "runtime", None)

    def execute(self, character_id: str, ability_query: str, target_query: Any=None, invocation_context: dict[str, Any] | None=None) -> AbilityUseResult:
        actor = self.service.actor_registry.get(character_id)
        if actor is None:
            self.service._log_missing_actor(character_id, ability_query, invocation_context or {})
            return AbilityUseResult(False, reason_code="actor_registration_missing", player_message="Your character is not ready to use abilities yet. Please re-enter the world.", actor_id=character_id)
        resolved = self.resolve_ability(actor.actor_id, ability_query) or self.resolve_ability(character_id, ability_query)
        if not resolved:
            return AbilityUseResult(False, reason_code="unknown_ability", player_message="Unknown ability.", actor_id=character_id)
        ab = self.service.registry.abilities[resolved]
        before = self.service._proficiency(actor.actor_id, resolved)
        res = self.service.start_ability(actor.actor_id, resolved, target_query or "self")
        after = self.service._proficiency(actor.actor_id, resolved)
        return AbilityUseResult(
            ok=bool(res.get("ok")), ability_id=resolved, ability_name=ab.name, reason_code=str(res.get("reason_code") or ("ok" if res.get("ok") else "blocked")),
            player_message=str(res.get("message") or self.service._ability_success_message(resolved) or "Ability activated."), actor_id=actor.actor_id,
            target_id=str(target_query or ""), resource_changes=list(res.get("resource_changes") or []), cooldown_started=bool(res.get("cooldown_started")),
            effects_applied=list(res.get("effect_events") or []), proficiency_before=before, proficiency_after=after, proficiency_increased=after is not None and before is not None and after > before,
            events=list(res.get("events") or []), metadata={k: v for k, v in (res.get("metadata") or {}).items() if k in {"effect_type", "room_id"}},
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        value = re.sub(r"\s+", " ", str(query or "").lower().replace("_", " ")).strip()
        return re.sub(r"^(use|cast|perform|invoke)\s+", "", value).strip()

    def resolve_ability(self, actor_id: str, query: str) -> str:
        q = self._normalize_query(query)
        learned = {str(r["id"]) for r in self.service.get_actor_abilities(actor_id)}
        matches: list[str] = []
        for aid, ab in self.service.registry.abilities.items():
            if aid not in learned:
                continue
            pdata = ab.plugin_data or {}
            aliases = pdata.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            candidates = {
                self._normalize_query(aid),
                self._normalize_query(aid.replace("_", " ")),
                self._normalize_query(str(ab.name)),
                self._normalize_query(str(ab.short_name)),
                self._normalize_query(str(pdata.get("command") or "")),
                self._normalize_query(str(pdata.get("usage") or "")),
            } | {self._normalize_query(str(a)) for a in aliases}
            if q and q in {c for c in candidates if c}:
                matches.append(aid)
        unique = sorted(set(matches))
        return unique[0] if len(unique) == 1 else ""

class AbilityRegistry:
    def __init__(self, package: Any|None=None, records: dict[str, list[dict[str, Any]]]|None=None):
        records = records or {}
        get = lambda n: list(records.get(n) or getattr(package, n, []) or [])
        self.abilities = {a.id: a for a in (AbilityDefinition.from_dict(x) for x in get("abilities") if isinstance(x, dict) and x.get("id"))}
        self.loadouts = {l.id: l for l in (AbilityLoadout.from_dict(x) for x in get("ability_loadouts") if isinstance(x, dict) and x.get("id"))}
        self.schools = {str(x.get("id")) for x in get("ability_schools") if x.get("id")}
        self.categories = {str(x.get("id")) for x in get("ability_categories") if x.get("id")}
        self.cooldown_groups = {str(x.get("id")) for x in get("cooldown_groups") if x.get("id")}
        self.effect_templates = {str(x.get("id")) for x in get("effect_templates") if x.get("id")}
        self.resource_ids = {str(x.get("id")) for x in get("resource_profiles") if x.get("id")} | {"health","mana","stamina","movement"}
        self.damage_profiles = {str(x.get("id")) for x in get("damage_profiles") if x.get("id")}
        self.formulas = {str(x.get("id")) for x in get("combat_formulas") if x.get("id")} | {"flat","base","minor_heal_formula","power_strike_damage","spell_power","healing_power"}
        self.effect_operations = AbilityEffectOperationRegistry()
    def validate_ability(self, a: AbilityDefinition) -> tuple[list[str], list[str]]:
        errors=[]; warnings=[]
        if not SAFE_ID.fullmatch(a.id): errors.append(f"ability ID unsafe: {a.id}")
        if a.ability_type not in ABILITY_TYPES: errors.append(f"ability {a.id} has unknown type: {a.ability_type}")
        mode=str((a.targeting or {}).get("mode") or "self");
        if mode not in TARGET_MODES: errors.append(f"ability {a.id} invalid target mode: {mode}")
        if a.activation_type not in ACTIVATION_TYPES: errors.append(f"ability {a.id} invalid activation type: {a.activation_type}")
        ids=[]
        for bucket,name in ((a.damage_components,"damage"),(a.healing_components,"healing"),(a.effects_applied,"effect")):
            for c in bucket:
                cid=str(c.get("id") or c.get("component_id") or c.get("application_id") or "")
                if cid in ids: errors.append(f"ability {a.id} duplicate component ID: {cid}")
                ids.append(cid)
        for c in a.costs:
            if str(c.get("resource_id")) not in self.resource_ids: errors.append(f"ability {a.id} invalid resource: {c.get('resource_id')}")
            if str(c.get("cost_type","flat")) not in COST_TYPES: errors.append(f"ability {a.id} invalid cost type")
            if num(c.get("amount",0)) < 0 or num(c.get("percentage",0)) < 0: errors.append(f"ability {a.id} negative cost")
        for c in a.damage_components:
            if c.get("damage_profile_id") and str(c.get("damage_profile_id")) not in self.damage_profiles: errors.append(f"ability {a.id} invalid damage profile: {c.get('damage_profile_id')}")
        for c in a.effects_applied:
            if c.get("effect_template_id") and str(c.get("effect_template_id")) not in self.effect_templates: errors.append(f"ability {a.id} invalid effect template: {c.get('effect_template_id')}")
        for key,msg in (a.messages or {}).items():
            if key not in MESSAGE_KEYS: errors.append(f"ability {a.id} invalid message key: {key}")
            for ph in re.findall(r"{([^{}]+)}", str(msg)):
                if ph not in PLACEHOLDERS: errors.append(f"ability {a.id} invalid message placeholder: {ph}")
        if a.ability_type == "passive" and (a.costs or a.damage_components or a.healing_components or a.activation_type not in {"passive","instant"}): errors.append(f"ability {a.id} passive/active contradiction")
        if "spellup_eligible" in (a.tags or []) and (a.damage_components or a.ability_type in {"debuff","monster","natural"}): errors.append(f"ability {a.id} harmful ability tagged spellup_eligible")
        for eff in (a.plugin_data or {}).get("canonical_effects", []) or []:
            op=str(eff.get("operation") or "")
            if op not in self.effect_operations.operations: errors.append(f"ability {a.id} unknown operation: {op}")
            if eff.get("duration", {}).get("amount", 0) is not None and num(eff.get("duration", {}).get("amount", 0)) < 0: errors.append(f"ability {a.id} negative duration")
            st=str((eff.get("stacking") or {}).get("policy") or "unique")
            if st not in STACKING_POLICIES: errors.append(f"ability {a.id} invalid stacking: {st}")
            for key,msg in (eff.get("messages") or {}).items():
                for ph in re.findall(r"{([^{}]+)}", str(msg)):
                    if ph not in PLACEHOLDERS: errors.append(f"ability {a.id} invalid message placeholder: {ph}")
        if not (a.damage_components or a.healing_components or a.effects_applied or a.effects_removed or a.state_changes or (a.plugin_data or {}).get("canonical_effects")): warnings.append(f"ability {a.id} has no components")
        if not a.messages: warnings.append(f"ability {a.id} has no messages")
        return errors,warnings
    def validate(self) -> list[str]:
        out=[]
        for a in self.abilities.values(): out.extend(self.validate_ability(a)[0])
        for lid,l in self.loadouts.items():
            seen=set()
            for aid in l.ability_ids:
                if aid and aid not in self.abilities: out.append(f"loadout {lid} references missing ability: {aid}")
                if aid in seen: out.append(f"loadout {lid} duplicate ability: {aid}")
                seen.add(aid)
            for aid in l.priority_order + l.spellup_priority + [l.default_auto_attack, l.default_defensive_ability, l.default_heal_ability, l.default_escape_ability]:
                if aid and aid not in self.abilities: out.append(f"loadout {lid} references missing ability: {aid}")
        return out

class AbilityExecutionService:
    def __init__(self, db_path: Path|str|None=None, package: Any|None=None, event_bus: Any|None=None, world_id: str="", actor_registry: ActorRegistry | None=None):
        self.db_path = Path(db_path) if db_path else None; self.registry=AbilityRegistry(package); self.event_bus=event_bus; self.world_id=world_id or getattr(package,"id","")
        self.combat = CombatEngine(content=CombatContentRegistry(package)); self.actor_registry = actor_registry or ActorRegistry(); self.actors = self.actor_registry.actors; self.availability = AbilityAvailabilityService(self); self.effect_operations = AbilityEffectOperationRegistry()
        if self.db_path: init_ability_schema(self.db_path)
    def register_actor(self, actor: Actor) -> None: self.actor_registry.register(actor)
    def unregister_actor(self, actor_id: str) -> None: self.actor_registry.unregister(actor_id)
    def _get_actor(self, actor_id: str) -> Actor | None:
        actor = self.actor_registry.get(actor_id)
        if actor is None:
            self._log_missing_actor(actor_id, "", {})
        return actor
    def _log_missing_actor(self, actor_id: str, ability_id: str="", context: dict[str, Any] | None=None) -> None:
        logger = __import__("logging").getLogger(__name__)
        rt = getattr(self, "runtime", None)
        logger.error(
            "Ability actor registration missing: requested=%s ability=%s registry_keys=%s runtime_id=%s registry_id=%s service_id=%s world=%s command=%s",
            actor_id, ability_id, sorted(self.actor_registry.actors.keys()), id(rt) if rt else None, id(self.actor_registry), id(self),
            self.world_id, (context or {}).get("command", ""),
        )
    def _missing_actor_result(self, actor_id: str, ability_id: str) -> dict[str, Any]:
        return {"ok": False, "message": "Your character is not ready to use abilities yet. Please re-enter the world.", "reason_code": "actor_registration_missing", "trace": {"actor_id": actor_id, "ability_id": ability_id, "availability": "INTERNAL_ERROR"}}
    def actor_from_character(self, c: Any) -> Actor: a=actor_from_runtime_character(c,self.world_id); self.register_actor(a); return a
    def gateway(self) -> AbilityRuntimeGateway:
        return AbilityRuntimeGateway(self, getattr(self, "runtime", None))
    def _proficiency(self, actor_id: str, ability_id: str) -> int | None:
        if not self.db_path: return None
        try:
            with sqlite3.connect(self.db_path) as c:
                row=c.execute("SELECT proficiency FROM actor_ability_progression WHERE actor_id=? AND ability_id=? AND active=1", (actor_id, ability_id)).fetchone()
            return max(1, min(100, int(row[0] if row else 1)))
        except Exception:
            return None
    def _ability_success_message(self, ability_id: str) -> str:
        ab=self.registry.abilities.get(ability_id); pdata=(ab.plugin_data or {}) if ab else {}
        return str(pdata.get("success_message") or (ab.messages or {}).get("complete_self") or "").strip()
    def get_actor_abilities(self, actor_id: str) -> list[dict[str, Any]]:
        grants = self._grants(actor_id)
        progression=[]
        if self.db_path:
            try:
                with sqlite3.connect(self.db_path) as c:
                    c.row_factory=sqlite3.Row
                    progression=[dict(r) for r in c.execute("SELECT ability_id,rank,maximum_rank,proficiency,metadata_json FROM actor_ability_progression WHERE actor_id=? AND active=1", (actor_id,))]
            except Exception:
                progression=[]
        ids={g["ability_id"] for g in grants} | {p["ability_id"] for p in progression} | set(getattr(self.actors.get(actor_id), "plugin_data", {}).get("ability_ids", []) or [])
        out=[]
        for i in sorted(ids):
            if i in self.registry.abilities and self.registry.abilities[i].enabled:
                row=dict(self.registry.abilities[i].to_dict(), grants=[g for g in grants if g["ability_id"]==i])
                prog=next((p for p in progression if p["ability_id"]==i), None)
                if prog: row.update(rank=int(prog.get("rank") or 0), maximum_rank=int(prog.get("maximum_rank") or 100), proficiency=max(1, min(100, int(prog.get("proficiency") or 1))), maximum_proficiency=max(1, min(100, int(prog.get("maximum_rank") or 100))), progression_metadata=jload(prog.get("metadata_json"), {}))
                out.append(row)
        return out
    def grant_ability(self, actor_id: str, ability_id: str, source_type: str="admin", source_id: str="", source_instance_id: str="", temporary: bool=False) -> str:
        if ability_id not in self.registry.abilities: raise ValueError(f"Unknown ability: {ability_id}")
        gid=f"grant_{actor_id}_{ability_id}_{source_type}_{source_instance_id or source_id or 'manual'}"; ts=now()
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO actor_ability_grants VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (gid,self.world_id,"actor",actor_id,ability_id,source_type,source_id,source_instance_id,1,0,1,1 if temporary else 0,None,None,ts,ts,"{}"))
        self._pub("ability_granted", {"actor_id":actor_id,"ability_id":ability_id,"grant_id":gid,"source_type":source_type}); return gid
    def revoke_ability(self, actor_id: str, ability_id: str, source_type: str|None=None, source_instance_id: str|None=None) -> int:
        if not self.db_path: return 0
        wh="actor_id=? AND ability_id=?"; p=[actor_id,ability_id]
        if source_type is not None: wh+=" AND source_type=?"; p.append(source_type)
        if source_instance_id is not None: wh+=" AND source_instance_id=?"; p.append(source_instance_id)
        with sqlite3.connect(self.db_path) as c: cur=c.execute(f"DELETE FROM actor_ability_grants WHERE {wh}", p); n=cur.rowcount
        self._pub("ability_revoked", {"actor_id":actor_id,"ability_id":ability_id,"count":n}); return n
    def can_use_ability(self, actor_id: str, ability_id: str, target: Any=None) -> dict[str, Any]: return self.validate_ability_use(actor_id, ability_id, target)
    def _validation_result(self, base: dict[str, Any], availability: str, message: str, **extra: Any) -> dict[str, Any]:
        ok = availability in {"READY", "PASSIVE"}
        result = {
            **base, "ok": ok, "availability": availability, "reason_code": availability.lower(), "message": message,
            "ability_id": base.get("ability_id") or extra.get("ability_id"), "actor_id": base.get("actor_id") or extra.get("actor_id"),
            "target_requirement": extra.get("target_requirement"), "resolved_targets": base.get("targets", []),
            "resource_costs": base.get("costs", []), "resource_affordability": extra.get("resource_affordability", {}),
            "cooldown_remaining": extra.get("cooldown_remaining"), "posture_allowed": extra.get("posture_allowed", True),
            "combat_allowed": extra.get("combat_allowed", True), "room_allowed": extra.get("room_allowed", True),
            "environment_allowed": extra.get("environment_allowed", True), "equipment_allowed": extra.get("equipment_allowed", True),
            "item_allowed": extra.get("item_allowed", True), "effect_allowed": extra.get("effect_allowed", True), "prerequisites": extra.get("prerequisites", []),
        }
        return result

    def validate_ability_use(self, actor_id: str, ability_id: str, target: Any=None, context: Any=None, preview: bool=True) -> dict[str, Any]:
        """Non-mutating canonical legality validator shared by display and execution."""
        tr = self.trace_ability(actor_id, ability_id, target, _from_validator=True)
        tr.setdefault("actor_id", actor_id); tr.setdefault("ability_id", ability_id)
        ab = self.registry.abilities.get(ability_id)
        if not ab:
            return self._validation_result(tr, "UNKNOWN", "Unknown ability.", actor_id=actor_id, ability_id=ability_id)
        if not ab.enabled:
            return self._validation_result(tr, "BLOCKED_DISABLED", "This ability is disabled.")
        if ab.ability_type == "passive" or ab.activation_type == "passive":
            return self._validation_result(tr, "PASSIVE", "Passive")

        cd=tr.get("cooldowns") or {}
        if cd.get("remaining") is not None:
            rem = int(cd.get("remaining") or 0)
            tr["cooldown_remaining_text"] = f"{rem} game minute" + ("" if rem == 1 else "s")
        for step in tr.get("trace", []):
            name=str(step.get("step") or "")
            if step.get("ready") is False:
                remaining = tr.get("cooldown_remaining_text") or "0 game minutes"
                return self._validation_result(tr, "BLOCKED_COOLDOWN", f"Ready in {remaining}" if remaining != "Ready" else "Ready", cooldown_remaining=cd.get("remaining"))
            if step.get("ok") is False:
                if name == "confirm_grant": return self._validation_result(tr, "BLOCKED_NOT_LEARNED", "Not learned.")
                if name == "validate_resources":
                    costs=step.get("costs") or []
                    need=next((c for c in costs if not c.get("affordable", True)), None)
                    msg=f"Requires {int(num(need.get('amount'),0))} {need.get('resource_id')}." if need else "Insufficient resources."
                    return self._validation_result(tr, "BLOCKED_RESOURCE", msg, resource_affordability={str(c.get("resource_id")): bool(c.get("affordable", True)) for c in costs})
                if name == "resolve_target" and target is None:
                    mode=str((ab.targeting or {}).get("mode") or "self")
                    if mode not in {"self","none","room"}: return self._validation_result(tr, "READY_NEEDS_TARGET", "Ready — requires a visible hostile target.", target_requirement=mode)
                if name == "resolve_target": return self._validation_result(tr, "BLOCKED_TARGET", "Invalid target.")

        rt=getattr(self, "runtime", None); character=None; room_id=""
        if rt and hasattr(rt, "state_store"):
            try: character=rt.state_store.load_character(actor_id); room_id=getattr(character,"room_id","")
            except Exception: character=None
        ctx=context or {}
        posture=str(ctx.get("posture") or getattr(character,"posture", getattr(self.actors.get(actor_id), "state", "standing")) or "standing").lower()
        if posture != "standing" and any(x.get("operation") == "require" and x.get("state") == "standing" for x in (ab.state_changes or [])):
            return self._validation_result(tr, "BLOCKED_POSTURE", "You must be standing to do that.", posture_allowed=False)
        cr=getattr(rt, "combat_runtime", None) if rt else None
        in_combat=bool(ctx.get("in_combat"))
        if cr:
            try: in_combat = in_combat or cr.is_actor_in_active_combat(cr.actor_id_for_character(character) if character else actor_id)
            except Exception: pass
        if in_combat and ability_id in {"set_camp","build_campfire","recall"}:
            return self._validation_result(tr, "BLOCKED_COMBAT", "You cannot establish a camp while fighting." if ability_id == "set_camp" else ("You cannot do that while fighting." if ability_id != "recall" else "You cannot recall while fighting."), combat_allowed=False)
        room_tags=set(ctx.get("room_tags") or [])
        if str(ctx.get("room_no_recall") or "").lower() in {"1","true","yes"} or "no_recall" in room_tags:
            if ability_id == "recall": return self._validation_result(tr, "BLOCKED_ROOM", "You cannot recall from this place.", room_allowed=False)
        if ability_id == "recall":
            dest=str((ab.plugin_data or {}).get("recall_destination_room_id") or "")
            if not dest: return self._validation_result(tr, "BLOCKED_PREREQUISITE", "No recall destination is configured.", prerequisites=["recall_destination"])
        if ability_id in {"set_camp","build_campfire"} and ("no_camp" in room_tags or str(ctx.get("camping_allowed", "true")).lower() in {"0","false","no"}):
            return self._validation_result(tr, "BLOCKED_ROOM", "You cannot establish a camp here.", room_allowed=False)
        if ability_id in {"set_camp","build_campfire"} and rt and getattr(rt, "survival_needs", None) and getattr(rt.survival_needs, "db_path", None):
            with sqlite3.connect(rt.survival_needs.db_path) as c:
                c.row_factory=sqlite3.Row
                cs=c.execute("SELECT 1 FROM campsite_instances WHERE world_id=? AND created_by_actor_id=? AND room_id=? AND status IN ('active','occupied','abandoned')", (self.world_id, actor_id, room_id)).fetchone()
                if ability_id == "set_camp" and cs:
                    return self._validation_result(tr, "BLOCKED_PREREQUISITE", "A campsite is already established here.", prerequisites=["no_existing_campsite"])
                if ability_id == "build_campfire":
                    if not cs: return self._validation_result(tr, "BLOCKED_PREREQUISITE", "Requires an established campsite.", prerequisites=["campsite"])
                    cf=c.execute("SELECT 1 FROM campfire_instances WHERE world_id=? AND created_by_actor_id=? AND room_id=? AND status IN ('unlit','lit','low_fuel')", (self.world_id, actor_id, room_id)).fetchone()
                    if cf: return self._validation_result(tr, "BLOCKED_PREREQUISITE", "A campfire is already burning here.", prerequisites=["no_existing_campfire"])
        return self._validation_result(tr, "READY", "Ready")
    def trace_ability(self, actor_id: str, ability_id: str, target: Any=None, _from_validator: bool=False) -> dict[str, Any]:
        steps=[]; ok=True
        a=self._get_actor(actor_id); ab=self.registry.abilities.get(ability_id)
        if not a: return {"ok":False,"errors":["actor not found"],"trace":[{"step":"resolve_actor","ok":False}]}
        if not ab: return {"ok":False,"errors":["ability not found"],"trace":[{"step":"resolve_ability","ok":False}]}
        steps.append({"step":"resolve_actor","actor_id":actor_id,"ok":True}); steps.append({"step":"resolve_ability","ability_id":ability_id,"ok":True})
        grants=self._grants(actor_id)
        progression_known=False
        if self.db_path:
            try:
                with sqlite3.connect(self.db_path) as c:
                    progression_known=bool(c.execute("SELECT 1 FROM actor_ability_progression WHERE actor_id=? AND ability_id=? AND active=1", (actor_id, ability_id)).fetchone())
            except Exception:
                progression_known=False
        available=bool([g for g in grants if g["ability_id"]==ability_id]) or progression_known or ability_id in getattr(a,"plugin_data",{}).get("ability_ids",[]) or ab.ability_type in {"natural","monster","administrative"}
        steps.append({"step":"confirm_grant","ok":available,"sources":grants,"progression_known":progression_known}); ok &= available
        targets=self.resolve_target(a, ab, target); steps.append({"step":"resolve_target", **targets}); ok &= targets.get("ok",False)
        mats=self._validate_materials(actor_id, ab); steps.append({"step":"validate_materials", **mats}); ok &= mats.get("ok", True)
        costs=self._validate_costs(a, ab); steps.append({"step":"validate_resources", **costs}); ok &= costs.get("ok",False)
        cd=self._cooldown_status(actor_id, ab); steps.append({"step":"validate_cooldowns", **cd}); ok &= cd.get("ready",True)
        return {"ok":bool(ok),"errors":[s for s in steps if s.get("ok") is False or s.get("ready") is False],"trace":steps,"targets":targets.get("targets",[]),"costs":costs.get("costs",[]),"cooldowns":cd}
    def start_ability(self, actor_id: str, ability_id: str, target: Any=None) -> dict[str, Any]:
        if ability_id not in self.registry.abilities: return {"ok":False,"message":"Unknown ability.","reason_code":"unknown_ability"}
        ab=self.registry.abilities[ability_id]
        if ab.ability_type == "passive": return {"ok":False,"message":"Passive abilities do not create active casts."}
        if ab.activation_type == "instant" or bool((ab.timing or {}).get("completes_immediately", True)): return self.execute_instant_ability(actor_id, ability_id, target)
        tr=self.validate_ability_use(actor_id,ability_id,target,preview=False)
        if not tr["ok"]: self._pub("ability_failed", {"actor_id":actor_id,"ability_id":ability_id,"trace":tr}); return {"ok":False,"trace":tr,"message":tr.get("message") or "You cannot use that ability.", "reason_code":tr.get("reason_code")}
        cast_id="cast_"+uuid.uuid4().hex; wt=self.world_time(); dur=int(num((ab.timing or {}).get("cast_time"),0)); actor=self._get_actor(actor_id)
        if actor is None: return self._missing_actor_result(actor_id, ability_id)
        costs=self._pay_costs(actor,ab,"start")
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO actor_ability_casts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cast_id,self.world_id,"actor",actor_id,ability_id,jdump(tr.get("targets")),"casting",wt,wt+dur,wt+dur,jdump(costs),"{}","",now(),now(),"{}"))
        self._start_cooldown(actor_id, ab); self._pub("ability_started", {"actor_id":actor_id,"ability_id":ability_id,"cast_id":cast_id}); self._pub("cast_started", {"cast_id":cast_id})
        return {"ok":True,"cast_id":cast_id,"state":"casting","completes_world_time":wt+dur}
    def execute_instant_ability(self, actor_id: str, ability_id: str, target: Any=None) -> dict[str, Any]:
        tr=self.validate_ability_use(actor_id,ability_id,target,preview=False)
        if not tr["ok"]: self._pub("ability_failed", {"actor_id":actor_id,"ability_id":ability_id,"trace":tr}); return {"ok":False,"trace":tr,"message":tr.get("message") or "You cannot use that ability.", "reason_code":tr.get("reason_code")}
        actor=self._get_actor(actor_id)
        if actor is None: return self._missing_actor_result(actor_id, ability_id)
        cast_id="instant_"+uuid.uuid4().hex; ab=self.registry.abilities[ability_id]; material_results=self._consume_materials(actor_id, ab, "start"); costs=self._pay_costs(actor,ab,"start"); self._start_cooldown(actor_id,ab)
        result={"ok":True,"cast_id":cast_id,"trace":tr["trace"],"damage_events":[],"healing_events":[],"effect_events":[],"material_results":material_results,"message": self._ability_success_message(ability_id)}; self._pub("ability_started", {"actor_id":actor_id,"ability_id":ability_id,"cast_id":cast_id})
        for t in tr["targets"]:
            target_actor=self.actors.get(t.get("actor_id"))
            if not target_actor: continue
            for comp in ab.damage_components: result["damage_events"].append(self._apply_damage_component(actor,target_actor,ab,comp,cast_id))
            for comp in ab.healing_components:
                amount = int(num(comp.get("base_amount", comp.get("amount", 0))))
                result["healing_events"].append(asdict(self.apply_healing(actor.actor_id, target_actor.actor_id, amount, ability_id, comp.get("id"), {"cast_id": cast_id, "formula_id": comp.get("formula_id")})))
            for eff in ab.effects_applied: result["effect_events"].append(self._apply_effect(actor,target_actor,ab,eff,cast_id))
        for eff in (ab.plugin_data or {}).get("canonical_effects", []) or []:
            handled = self._apply_canonical_effect(actor, tr.get("targets", []), ab, eff, cast_id)
            result["effect_events"].append(handled)
            if handled.get("message"):
                result["message"] = str(handled.get("message"))
            if not handled.get("ok", True):
                result.update(ok=False, message=handled.get("message") or "You cannot use that ability.", reason_code=handled.get("reason") or handled.get("reason_code") or "effect_blocked")
                self._record_failed_use(actor_id, ability_id)
                return result
        for eff in (ab.plugin_data or {}).get("effects", []) or []:
            handled = self._apply_registered_effect(actor, ab, eff, cast_id)
            result["effect_events"].append(handled)
            if not handled.get("ok", True):
                result.update(ok=False, message=handled.get("message") or "You cannot use that ability.", reason_code=handled.get("reason") or handled.get("reason_code") or "effect_blocked")
                self._record_failed_use(actor_id, ability_id)
                return result
            if handled.get("message"):
                result["message"] = str(handled.get("message"))
        improvement = self.attempt_proficiency_improvement(actor_id, ability_id)
        result["proficiency_improvement"] = improvement
        self._pub("ability_completed", {"actor_id":actor_id,"ability_id":ability_id,"cast_id":cast_id,"proficiency_improvement":improvement}); return result

    def _select_effect_targets(self, actor: Actor, resolved_targets: list[dict[str, Any]], selector: str) -> list[Actor]:
        if selector in {"self","actor","source"}: return [actor]
        out=[]
        for t in resolved_targets or []:
            ta=self.actors.get(t.get("actor_id"))
            if ta: out.append(ta)
        return out or [actor]

    def _apply_canonical_effect(self, actor: Actor, targets: list[dict[str, Any]], ab: AbilityDefinition, eff: dict[str, Any], cast_id: str) -> dict[str, Any]:
        op=str(eff.get("operation") or ""); self.effect_operations.validate(op)
        selected=self._select_effect_targets(actor, targets, str(eff.get("target_selector") or "target"))
        out={"ok": True, "operation": op, "targets": [t.actor_id for t in selected], "results": []}
        for target in selected:
            amount=int(num(eff.get("base_value", eff.get("amount", 0)),0))
            if op == "deal_damage":
                out["results"].append(self._apply_damage_component(actor,target,ab,{"id":eff.get("effect_id",op),"base_amount":amount,"damage_type":eff.get("damage_type","physical"),"formula_id":eff.get("formula_id",""),"coefficient":eff.get("coefficient",1),"save_definition":eff.get("save_definition",{})},cast_id))
            elif op == "heal":
                out["results"].append(asdict(self.apply_healing(actor.actor_id,target.actor_id,amount,ab.id,str(eff.get("effect_id") or op),{"cast_id":cast_id,"formula_id":eff.get("formula_id")})))
            elif op == "modify_resource":
                rr=RuntimeResourceService(getattr(self,"runtime",None), db_path=self.db_path, event_bus=self.event_bus, world_id=self.world_id).mutate(target,str(eff.get("resource") or "mana"),"regeneration" if amount >= 0 else "cost",abs(amount),metadata={"source":"ability_effect","ability_id":ab.id})
                out["results"].append({"resource":rr.resource,"before":rr.before,"amount":rr.applied_amount,"after":rr.after})
            elif op in {"apply_affect","apply_condition","modify_stat","grant_resistance","grant_immunity","grant_vulnerability","damage_over_time","healing_over_time","resource_over_time"}:
                out["results"].append(self._persist_runtime_effect(actor,target,ab,eff,cast_id))
            elif op in {"remove_affect","remove_condition","dispel","cleanse"}:
                out["results"].append(self.remove_effects(target.actor_id, eff, "cleansed" if op=="cleanse" else "dispelled" if op=="dispel" else "removed"))
            elif op in {"teleport","recall","move_target"}:
                out.update(self._apply_registered_effect(actor, ab, {"type":"teleport_home","room_id":eff.get("parameters",{}).get("room_id")}, cast_id))
            elif op == "send_message":
                out["message"] = str((eff.get("messages") or {}).get("actor_success") or eff.get("message") or "")
            elif op in {"set_cooldown","reduce_cooldown","trigger_ability"}:
                out["results"].append({"reserved_runtime_operation": op, "ok": True})
        if not out.get("message"):
            out["message"] = str((eff.get("messages") or {}).get("actor_success") or "")
        self._pub("effect_applied" if op not in {"dispel","cleanse"} else f"effect_{op}", {"actor_id":actor.actor_id,"ability_id":ab.id,"operation":op,"cast_id":cast_id})
        return out

    def _persist_runtime_effect(self, actor: Actor, target: Actor, ab: AbilityDefinition, eff: dict[str, Any], cast_id: str) -> dict[str, Any]:
        wt=self.world_time(); dur=eff.get("duration") or {}; amount=int(num(dur.get("amount", eff.get("duration_amount", 0)),0)); domain=str(dur.get("domain") or "world_minutes"); expires=None if domain in {"permanent","while_equipped","while_source_exists"} else wt+amount
        tick=int(num(eff.get("tick_interval") or (eff.get("parameters") or {}).get("tick_interval"),0)); eid="eff_"+uuid.uuid4().hex; tags=list(eff.get("tags") or [])
        modifiers=list((eff.get("parameters") or {}).get("modifiers") or [])
        rec={"effect_instance_id":eid,"definition_id":str(eff.get("effect_id") or eff.get("operation")),"source_actor_id":actor.actor_id,"target_actor_id":target.actor_id,"source_ability_id":ab.id,"state":"active","tags":tags,"modifiers":modifiers,"stacks":int(num((eff.get("stacking") or {}).get("stacks",1),1)),"operation":eff.get("operation"),"origin_action_id":cast_id,"wear_off_messages":eff.get("messages") or {},"tick":{"operation":eff.get("operation"),"amount":eff.get("base_value",0),"damage_type":eff.get("damage_type","poison"),"resource":eff.get("resource","health")}}
        target.effect_container.setdefault("affects",{}).setdefault("canonical",[]).append(rec)
        if self.db_path:
            with sqlite3.connect(self.db_path) as c:
                c.execute("INSERT OR REPLACE INTO actor_effect_instances(effect_instance_id,world_id,effect_template_id,target_actor_type,target_actor_id,source_actor_type,source_actor_id,source_ability_id,category,disposition,visibility,stack_group,stack_count,maximum_stacks,started_world_time,expires_world_time,next_tick_world_time,active,suspended,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid,self.world_id,rec["definition_id"],"actor",target.actor_id,"actor",actor.actor_id,ab.id,",".join(tags),"harmful" if "poison" in tags or "debuff" in tags else "beneficial","public",str((eff.get("stacking") or {}).get("exclusive_group") or rec["definition_id"]),rec["stacks"],int(num((eff.get("stacking") or {}).get("maximum_stacks",1),1)),wt,expires or 0,wt+tick if tick else 0,1,0,now(),now(),jdump(rec)))
        return rec

    def remove_effects(self, target_actor_id: str, criteria: dict[str, Any], reason: str="removed") -> dict[str, Any]:
        tags=set(criteria.get("tags") or criteria.get("categories") or [])
        removed=[]
        if self.db_path:
            with sqlite3.connect(self.db_path) as c:
                c.row_factory=sqlite3.Row
                rows=c.execute("SELECT effect_instance_id,metadata_json FROM actor_effect_instances WHERE target_actor_id=? AND active=1", (target_actor_id,)).fetchall()
                for r in rows:
                    meta=jload(r["metadata_json"], {})
                    if not tags or tags.intersection(set(meta.get("tags") or [])):
                        c.execute("UPDATE actor_effect_instances SET active=0,removal_reason=?,updated_at=? WHERE effect_instance_id=?", (reason,now(),r["effect_instance_id"]))
                        removed.append(r["effect_instance_id"])
        self._pub("effect_removed", {"target_actor_id":target_actor_id,"removed":removed,"reason":reason})
        return {"status":"removed" if removed else "not_found", "removed": removed}

    def process_effect_ticks(self, world_time: int | None=None) -> list[dict[str, Any]]:
        if not self.db_path: return []
        wt=self.world_time() if world_time is None else int(world_time); work=[]; results=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            rows=c.execute("SELECT * FROM actor_effect_instances WHERE active=1 AND next_tick_world_time>0 AND next_tick_world_time<=? ORDER BY next_tick_world_time,effect_instance_id", (wt,)).fetchall()
            for r in rows:
                claim=f"tick_{r['effect_instance_id']}_{r['next_tick_world_time']}"
                try: c.execute("INSERT INTO ability_effect_tick_claims VALUES(?,?,?,?,?,?)", (claim,self.world_id,r['effect_instance_id'],r['next_tick_world_time'],now(),"{}"))
                except sqlite3.IntegrityError: continue
                work.append((dict(r), claim))
        for r, claim in work:
            meta=jload(r['metadata_json'], {}); src=self.actors.get(r['source_actor_id']); tgt=self.actors.get(r['target_actor_id'])
            tick=meta.get('tick') or {}; amount=int(num(tick.get('amount'),0))
            if src and tgt and meta.get('operation') == 'damage_over_time': results.append(self._apply_damage_component(src,tgt,self.registry.abilities.get(r['source_ability_id'], AbilityDefinition(r['source_ability_id'])),{"id":claim,"base_amount":amount,"damage_type":tick.get('damage_type','poison'),"requires_hit_roll":False,"can_critical":False},claim))
            elif tgt and meta.get('operation') in {'healing_over_time','resource_over_time'}:
                rr=RuntimeResourceService(getattr(self,'runtime',None), db_path=self.db_path, event_bus=self.event_bus, world_id=self.world_id).mutate(tgt,str(tick.get('resource') or 'health'),'regeneration' if amount >= 0 else 'cost',abs(amount),metadata={'source':'effect_tick'})
                results.append({'effect_instance_id':r['effect_instance_id'],'resource':rr.resource,'amount':rr.applied_amount})
            interval=int(num(meta.get('tick_interval') or r.get('tick_interval') or 1,1)); next_tick=int(r['next_tick_world_time'])+max(1, interval)
            with sqlite3.connect(self.db_path) as c:
                if r['expires_world_time'] and next_tick>int(r['expires_world_time']): c.execute("UPDATE actor_effect_instances SET next_tick_world_time=0 WHERE effect_instance_id=?", (r['effect_instance_id'],))
                else: c.execute("UPDATE actor_effect_instances SET next_tick_world_time=? WHERE effect_instance_id=?", (next_tick,r['effect_instance_id']))
            self._pub('effect_tick_completed', {'effect_instance_id':r['effect_instance_id'],'claim_id':claim})
        return results

    def process_effect_expirations(self, world_time: int | None=None) -> list[dict[str, Any]]:
        if not self.db_path: return []
        wt=self.world_time() if world_time is None else int(world_time); expired=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            rows=c.execute("SELECT effect_instance_id,metadata_json FROM actor_effect_instances WHERE active=1 AND expires_world_time>0 AND expires_world_time<=?", (wt,)).fetchall()
            for r in rows:
                c.execute("UPDATE actor_effect_instances SET active=0,removal_reason='expired',updated_at=? WHERE effect_instance_id=?", (now(),r['effect_instance_id']))
                meta=jload(r['metadata_json'],{}); expired.append({'effect_instance_id':r['effect_instance_id'],'messages':meta.get('wear_off_messages',{})})
                self._pub('effect_expired', {'effect_instance_id':r['effect_instance_id']})
        return expired

    def _apply_registered_effect(self, actor: Actor, ab: AbilityDefinition, eff: dict[str, Any], cast_id: str) -> dict[str, Any]:
        etype = str(eff.get("type") or eff.get("effect_type") or "")
        rt = getattr(self, "runtime", None)
        svc = getattr(rt, "survival_needs", None) if rt else None
        if etype == "create_campsite" and svc:
            res = svc.create_campsite(actor.actor_id, str(eff.get("profile") or "basic_campsite"))
            return {"effect_type": etype, **res, "message": "You establish a modest campsite here." if res.get("ok", True) else res.get("message") or "A campsite is already established here."}
        if etype == "create_campfire" and svc:
            res = svc.create_campfire(actor.actor_id, str(eff.get("profile") or "basic_campfire"))
            return {"effect_type": etype, **res, "message": "You build a small campfire." if res.get("ok", True) else res.get("message") or "You need an active campsite here before building a campfire."}
        if etype == "teleport_home" and rt:
            dest = str(eff.get("room_id") or (ab.plugin_data or {}).get("recall_destination_room_id") or getattr(getattr(rt, "active_world", None), "default_starting_room_id", "") or "")
            ch = rt.state_store.load_character(actor.actor_id) if getattr(rt, "state_store", None) else None
            if not dest or ch is None: return {"ok": False, "effect_type": etype, "reason": "no_destination", "message": "No recall point is available right now."}
            old=getattr(ch, "room_id", ""); ch.room_id=dest; rt.state_store.save_character(ch, getattr(rt, "active_world_id", "") or "")
            return {"ok": True, "effect_type": etype, "from_room_id": old, "room_id": dest, "message": f"{(ab.plugin_data or {}).get('casting_text') or 'You cast Recall.'}\n{(ab.plugin_data or {}).get('arrival_text') or 'You arrive at the recall point.'}"}
        if etype == "send_message":
            return {"ok": True, "effect_type": etype, "message": str(eff.get("message") or "")}
        return {"ok": False, "effect_type": etype, "reason": "unknown_effect", "message": "That ability is not configured correctly."}

    def _record_failed_use(self, actor_id: str, ability_id: str) -> None:
        if not self.db_path: return
        try:
            with sqlite3.connect(self.db_path) as c:
                row=c.execute("SELECT metadata_json FROM actor_ability_progression WHERE actor_id=? AND ability_id=? AND active=1", (actor_id, ability_id)).fetchone()
                if row:
                    meta=jload(row[0], {}); state=meta.setdefault("proficiency_state", {}); state["failed_uses"]=int(state.get("failed_uses",0) or 0)+1
                    c.execute("UPDATE actor_ability_progression SET metadata_json=? WHERE actor_id=? AND ability_id=?", (jdump(meta), actor_id, ability_id))
        except Exception:
            pass

    def attempt_proficiency_improvement(self, actor_id: str, ability_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Canonical +1% proficiency improvement hook for successful ability use."""
        if not self.db_path:
            return {"attempted": False, "reason": "no_store"}
        ab = self.registry.abilities.get(ability_id)
        pdata = (getattr(ab, "plugin_data", {}) or {}) if ab else {}
        chance = float(pdata.get("improvement_chance", pdata.get("proficiency_improvement_chance", 0)))
        minimum_successful_uses = int(pdata.get("minimum_successful_uses", 1) or 1)
        cooldown = int(pdata.get("improvement_roll_cooldown_seconds", 0) or 0)
        difficulty = int(pdata.get("improvement_difficulty", 0) or 0)
        now_ts = now()
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            try:
                row = c.execute("SELECT proficiency,maximum_rank,metadata_json FROM actor_ability_progression WHERE actor_id=? AND ability_id=? AND active=1", (actor_id, ability_id)).fetchone()
            except sqlite3.OperationalError:
                return {"attempted": False, "reason": "no_progression"}
            if not row:
                return {"attempted": False, "reason": "not_learned"}
            current = max(1, min(100, int(row["proficiency"] or 1)))
            maximum = max(1, min(100, int(row["maximum_rank"] or pdata.get("maximum_proficiency", 100) or 100)))
            meta = jload(row["metadata_json"], {})
            state = meta.setdefault("proficiency_state", {})
            state["successful_uses"] = int(state.get("successful_uses", 0) or 0) + 1
            if current >= maximum:
                c.execute("UPDATE actor_ability_progression SET proficiency=?,metadata_json=? WHERE actor_id=? AND ability_id=?", (maximum, jdump(meta), actor_id, ability_id))
                return {"attempted": False, "reason": "at_cap", "proficiency": maximum}
            if state["successful_uses"] < minimum_successful_uses:
                c.execute("UPDATE actor_ability_progression SET metadata_json=? WHERE actor_id=? AND ability_id=?", (jdump(meta), actor_id, ability_id))
                return {"attempted": False, "reason": "minimum_successful_uses", "proficiency": current}
            # Deterministic roll hook: 0 means disabled, >=1 means always succeeds; fractional formulas can be added here.
            attempted = chance > 0
            improved = attempted and chance >= 1
            if improved:
                current = min(maximum, current + 1)
                state["last_improvement_at"] = now_ts
                c.execute("UPDATE actor_ability_progression SET proficiency=?,metadata_json=? WHERE actor_id=? AND ability_id=?", (current, jdump(meta), actor_id, ability_id))
                self._pub("ability_proficiency_increased", {"actor_id": actor_id, "ability_id": ability_id, "proficiency": current, "difficulty": difficulty})
            else:
                c.execute("UPDATE actor_ability_progression SET metadata_json=? WHERE actor_id=? AND ability_id=?", (jdump(meta), actor_id, ability_id))
            return {"attempted": attempted, "improved": improved, "proficiency": current, "chance": chance, "difficulty": difficulty, "cooldown_seconds": cooldown}
    def complete_ability(self, cast_id: str) -> dict[str, Any]:
        if not self.db_path: return {"ok":False,"message":"No cast store."}
        with sqlite3.connect(self.db_path) as c: row=c.execute("SELECT actor_id,ability_id,target_data_json,state FROM actor_ability_casts WHERE cast_id=?",(cast_id,)).fetchone()
        if not row: return {"ok":False,"message":"Cast not found."}
        res=self.execute_instant_ability(row[0],row[1],jload(row[2],[]));
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE actor_ability_casts SET state='completed',updated_at=? WHERE cast_id=?",(now(),cast_id))
        self._pub("cast_completed", {"cast_id":cast_id}); return res
    def interrupt_ability(self, cast_id: str, reason: str|None=None) -> dict[str, Any]: return self._finish_cast(cast_id,"interrupted",reason or "interrupted")
    def cancel_ability(self, cast_id: str, reason: str|None=None) -> dict[str, Any]: return self._finish_cast(cast_id,"cancelled",reason or "cancelled")
    def process_ability_casts(self, world_id: str, world_time: int) -> list[dict[str, Any]]:
        if not self.db_path: return []
        with sqlite3.connect(self.db_path) as c: rows=c.execute("SELECT cast_id FROM actor_ability_casts WHERE world_id=? AND state IN ('casting','channeling','pending') AND completes_world_time<=? ORDER BY completes_world_time,cast_id",(world_id,world_time)).fetchall()
        return [self.complete_ability(r[0]) for r in rows]
    def get_ability_status(self, actor_id: str, ability_id: str) -> dict[str, Any]: return self._cooldown_status(actor_id,self.registry.abilities[ability_id])
    def resolve_target(self, actor: Actor, ab: AbilityDefinition, target: Any=None) -> dict[str, Any]:
        mode=str((ab.targeting or {}).get("mode") or "self"); allow_dead=bool((ab.targeting or {}).get("allow_dead",False)); targets=[]
        if isinstance(target,list) and target and isinstance(target[0],dict): targets=target
        elif mode in {"self","none"} or str(target or "").lower() in {"","self","me"}: targets=[{"actor_id":actor.actor_id,"name":actor.identity.name}]
        elif isinstance(target, Actor): targets=[{"actor_id":target.actor_id,"name":target.identity.name}]
        elif isinstance(target,str):
            q=target.lower().strip(); matches=[x for x in sorted(self.actors.values(), key=lambda z:z.actor_id) if x.actor_id.lower()==q or x.identity.name.lower()==q or q in x.identity.name.lower().split()]
            targets=[{"actor_id":x.actor_id,"name":x.identity.name} for x in matches[:int((ab.targeting or {}).get("maximum_targets") or 1)]]
        if mode.startswith("room_") and not target:
            maxn=int((ab.targeting or {}).get("maximum_targets") or 99); targets=[{"actor_id":x.actor_id,"name":x.identity.name} for x in sorted(self.actors.values(), key=lambda z:z.actor_id)[:maxn]]
        ok=bool(targets) or mode in {"none","room"}
        for t in targets:
            ta=self.actors.get(t.get("actor_id"));
            if ta and not allow_dead and str(ta.lifecycle_state).lower() in {"dead","corpse"}: ok=False; t["invalid"]="dead"
        return {"ok":ok,"mode":mode,"targets":targets,"runtime_instance_ids":[t.get("actor_id") for t in targets]}
    def _ensure_item_instance_material_columns(self, c: sqlite3.Connection) -> None:
        try:
            cols={row[1] for row in c.execute("PRAGMA table_info(item_instances)").fetchall()}
            if not cols:
                c.execute("CREATE TABLE IF NOT EXISTS item_instances(instance_id TEXT PRIMARY KEY,world_id TEXT,template_id TEXT,owner_type TEXT,owner_id TEXT,room_id TEXT,equipped_slot TEXT,stack_count INTEGER,condition TEXT,durability INTEGER,created_at TEXT,updated_at TEXT,custom_flags TEXT,plugin_data TEXT,destroyed_at TEXT,destroy_reason TEXT)")
                return
            if "destroyed_at" not in cols: c.execute("ALTER TABLE item_instances ADD COLUMN destroyed_at TEXT")
            if "destroy_reason" not in cols: c.execute("ALTER TABLE item_instances ADD COLUMN destroy_reason TEXT")
            if "stack_count" not in cols: c.execute("ALTER TABLE item_instances ADD COLUMN stack_count INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

    def _validate_materials(self, actor_id: str, ab: AbilityDefinition) -> dict[str, Any]:
        reqs=list((ab.plugin_data or {}).get("materials") or [])
        if not reqs or not self.db_path: return {"ok": True, "materials": []}
        out=[]; ok=True
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            self._ensure_item_instance_material_columns(c)
            for r in reqs:
                template=str(r.get("template_id") or r.get("specific_template") or ""); qty=int(num(r.get("quantity",1),1)); where="owner_id=? AND destroyed_at IS NULL"; params=[actor_id]
                if template: where += " AND template_id=?"; params.append(template)
                row=c.execute(f"SELECT COALESCE(SUM(stack_count),0) AS n FROM item_instances WHERE {where}", params).fetchone()
                have=int(row["n"] if row else 0); good=have>=qty; ok &= good; out.append({"template_id":template,"quantity":qty,"available":have,"ok":good,"consume_timing":r.get("consume_timing","start")})
        return {"ok": bool(ok), "materials": out}

    def _consume_materials(self, actor_id: str, ab: AbilityDefinition, timing: str) -> list[dict[str, Any]]:
        reqs=[r for r in list((ab.plugin_data or {}).get("materials") or []) if str(r.get("consume_timing","start")) == timing]
        if not reqs or not self.db_path: return []
        results=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; self._ensure_item_instance_material_columns(c); c.execute("BEGIN IMMEDIATE")
            for r in reqs:
                template=str(r.get("template_id") or r.get("specific_template") or ""); need=int(num(r.get("quantity",1),1)); consumed=0
                rows=c.execute("SELECT instance_id,stack_count FROM item_instances WHERE owner_id=? AND template_id=? AND destroyed_at IS NULL ORDER BY instance_id", (actor_id,template)).fetchall()
                if sum(int(x["stack_count"] or 1) for x in rows) < need: raise ValueError("material requirement became unavailable")
                for row in rows:
                    if consumed>=need: break
                    stack=int(row["stack_count"] or 1); take=min(stack, need-consumed); remain=stack-take; consumed += take
                    if remain>0: c.execute("UPDATE item_instances SET stack_count=? WHERE instance_id=?", (remain,row["instance_id"]))
                    else: c.execute("UPDATE item_instances SET destroyed_at=?,destroy_reason=? WHERE instance_id=?", (now(),"ability_material",row["instance_id"]))
                rec={"template_id":template,"quantity":need,"consumed":consumed}; results.append(rec); self._pub("ability_material_consumed", {"actor_id":actor_id,"ability_id":ab.id,**rec})
        return results

    def _validate_costs(self, actor: Actor, ab: AbilityDefinition) -> dict[str, Any]:
        out=[]; ok=True
        for c in ab.costs:
            amt=self._cost_amount(actor,c); res=str(c.get("resource_id")); cur=num(getattr(actor.resources,res,0)); needed=cur>=amt and amt>=0
            out.append({"resource_id":res,"amount":amt,"current":cur,"ok":needed}); ok &= needed
        return {"ok":ok,"costs":out}
    def _cost_amount(self, actor: Actor, c: dict[str,Any]) -> int:
        typ=str(c.get("cost_type","flat")); res=str(c.get("resource_id")); cur=num(getattr(actor.resources,res,0)); mx=num(getattr(actor.resources,"maximum_"+res,cur))
        if typ=="percentage_current": amt=cur*num(c.get("percentage"),0)/100
        elif typ=="percentage_maximum": amt=mx*num(c.get("percentage"),0)/100
        elif typ=="all_current": amt=cur
        else: amt=num(c.get("amount"),0)
        if c.get("minimum") is not None: amt=max(amt,num(c.get("minimum")))
        if c.get("maximum") is not None: amt=min(amt,num(c.get("maximum")))
        return max(0,int(amt))
    def _pay_costs(self, actor: Actor, ab: AbilityDefinition, consume_on: str) -> list[dict[str,Any]]:
        paid=[]
        for c in ab.costs:
            if str(c.get("consume_on","start")) != consume_on: continue
            amt=self._cost_amount(actor,c); rr=RuntimeResourceService(getattr(self,"runtime",None), db_path=self.db_path, event_bus=self.event_bus, world_id=self.world_id).pay_cost(actor,str(c.get("resource_id")),amt,metadata={"source":"ability_cost","ability_id":ab.id}); trace={"resource":rr.resource,"operation":rr.operation,"before":rr.before,"amount":rr.applied_amount,"after":rr.after,"reason_code":rr.reason_code}; paid.append(trace); self._pub("ability_cost_paid", dict(trace, ability_id=ab.id, actor_id=actor.actor_id))
        return paid
    def _cooldown_status(self, actor_id: str, ab: AbilityDefinition) -> dict[str, Any]:
        wt=self.world_time(); rows=[]
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: rows=c.execute("SELECT cooldown_id,cooldown_group,ready_world_time,charges_current,charges_maximum,active FROM actor_ability_cooldowns WHERE actor_id=? AND ability_id=? AND active=1 ORDER BY ready_world_time",(actor_id,ab.id)).fetchall()
        blocking=[r for r in rows if int(r[2] or 0)>wt and int(r[3] or 0)<=0]
        return {"ready":not blocking,"remaining":max([int(r[2])-wt for r in blocking] or [0]),"rows":[{"cooldown_id":r[0],"group":r[1],"ready_world_time":r[2],"charges_current":r[3],"charges_maximum":r[4]} for r in rows]}
    def _start_cooldown(self, actor_id: str, ab: AbilityDefinition) -> None:
        dur=int(num((ab.cooldowns or {}).get("cooldown_duration", (ab.cooldowns or {}).get("duration",0)))); charges=int(num((ab.cooldowns or {}).get("charges",0))); wt=self.world_time()
        if self.db_path and (dur or charges):
            cid=f"cd_{actor_id}_{ab.id}_{(ab.cooldowns or {}).get('cooldown_group','ability')}"
            metadata = jdump({"time_unit":"world_minutes","time_domain":"world_time","source_action":"ability_start"})
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO actor_ability_cooldowns VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid,self.world_id,"actor",actor_id,ab.id,str((ab.cooldowns or {}).get("cooldown_group") or ab.id),wt,wt+dur,max(0,charges-1) if charges else 0,charges,wt+int(num((ab.cooldowns or {}).get("charge_recovery",dur))),1,now(),now(),metadata))
            self._pub("ability_cooldown_started", {"actor_id":actor_id,"ability_id":ab.id,"ready_world_time":wt+dur})
    def _apply_damage_component(self, actor: Actor, target: Actor, ab: AbilityDefinition, comp: dict[str,Any], cast_id: str) -> dict[str,Any]:
        rt = getattr(self, "runtime", None)
        crt = getattr(rt, "combat_runtime", None) if rt else None
        if crt:
            from engine.combat_runtime import CombatActionRequest
            req = CombatActionRequest(
                action_id=str(comp.get("action_id") or f"ability_{cast_id}_{comp.get('id','damage')}"),
                round_id=str(getattr(crt, "find_actor_encounter", lambda _a: "")(actor.actor_id) or ""),
                world_id=self.world_id,
                room_id=getattr(actor.identity, "current_location", ""),
                attacker_id=actor.actor_id,
                defender_id=target.actor_id,
                ability_id=ab.id,
                attack_kind=str(comp.get("attack_kind") or "direct_damage"),
                damage_type=str(comp.get("damage_type") or "physical"),
                base_amount=int(num(comp.get("base_amount", comp.get("amount", 1)), 1)),
                formula_id=str(comp.get("formula_id") or ""),
                coefficient=float(num(comp.get("coefficient", 1), 1)),
                requires_hit_roll=bool(comp.get("requires_hit_roll", True)),
                can_critical=bool(comp.get("can_critical", True)),
                critical_type=str(comp.get("critical_type") or "ability"),
                armor_applies=bool(comp.get("armor_applies", True)),
                resistance_applies=bool(comp.get("resistance_applies", True)),
                save_definition=dict(comp.get("save") or comp.get("save_definition") or {}),
                source_type="ability",
                source_id=str(comp.get("id") or ab.id),
                metadata={"cast_id": cast_id, "component_id": str(comp.get("id") or "")},
            )
            rr = crt.submit_action(req)
            ev = {"ability_id": ab.id, "cast_id": cast_id, "component_id": comp.get("id"), "source_actor_id": actor.actor_id, "target_actor_id": target.actor_id, "action_id": req.action_id, "ok": bool(getattr(rr, "ok", False)), "messages": list(getattr(rr, "messages", []) or []), "final_amount": int((getattr(crt, "last_resolution", {}) or {}).get("damage", 0) or 0), "combat_result": getattr(rr, "__dict__", {})}
            self._pub("ability_damage_applied", ev); return ev
        old=actor.combat_profile.get("natural_weapons")
        actor.combat_profile["natural_weapons"]=[{"id":comp.get("id","ability_damage"),"name":ab.name,"damage_type":comp.get("damage_type","physical"),"base_damage":int(num(comp.get("base_amount",1)))}]
        res=self.combat.resolve_attack(actor,target,world_time=self.world_time())
        if old is None: actor.combat_profile.pop("natural_weapons",None)
        else: actor.combat_profile["natural_weapons"]=old
        ev=asdict(res.damage_event) if res.damage_event else {}; ev.update({"ability_id":ab.id,"cast_id":cast_id,"component_id":comp.get("id"),"source_actor_id":actor.actor_id,"target_actor_id":target.actor_id,"damage_profile_id":comp.get("damage_profile_id"),"final_amount":ev.get("final_damage",0),"trace":res.trace})
        self._pub("ability_damage_applied", ev); return ev
    def apply_healing(self, source_actor_id: str, target_actor_id: str, amount: int, ability_id: str|None=None, component_id: str|None=None, metadata: dict[str,Any]|None=None) -> HealingEvent:
        target=self._get_actor(target_actor_id)
        if target is None: raise ValueError(f"Actor not registered: {target_actor_id}")
        before=int(num(target.resources.health)); maxh=int(num(target.resources.maximum_health,before)); base=max(0,int(amount)); rr=RuntimeResourceService(getattr(self,"runtime",None), db_path=self.db_path, event_bus=self.event_bus, world_id=self.world_id).apply_healing(target,base,metadata={"source":"ability_healing","ability_id":ability_id or "","component_id":component_id or ""}); trace={"resource":rr.resource,"operation":rr.operation,"before":rr.before,"amount":rr.applied_amount,"after":rr.after,"reason_code":rr.reason_code}; final=int(rr.after)-before; ev=HealingEvent("heal_"+uuid.uuid4().hex,self.world_id,source_actor_id,target_actor_id,ability_id,metadata.get("cast_id") if metadata else None,component_id,base,(metadata or {}).get("formula_id"),False,None,{},final,max(0,before+base-maxh),self.world_time(),[{**trace}],metadata or {})
        self._pub("ability_healing_applied", asdict(ev)); return ev
    def _apply_effect(self, actor: Actor, target: Actor, ab: AbilityDefinition, eff: dict[str,Any], cast_id: str) -> dict[str,Any]:
        eid="eff_"+uuid.uuid4().hex; cat=str(eff.get("category") or eff.get("disposition") or ("positive" if ab.ability_type in {"buff","defensive"} else "negative")); rec={"effect_instance_id":eid,"effect_template_id":eff.get("effect_template_id"),"target_actor_id":target.actor_id,"source_actor_id":actor.actor_id,"ability_id":ab.id,"cast_id":cast_id,"category":cat,"stacks":int(num(eff.get("stacks",1),1))}
        target.effect_container.setdefault("affects",{}).setdefault(cat,[]).append({"name":eff.get("effect_template_id"),"source":ab.id,"duration":eff.get("duration",0),"stacks":rec["stacks"],"category":cat})
        if cat in {"positive","beneficial"}: target.effect_container.setdefault("spellup",{}).setdefault("long",[]).append({"name":eff.get("effect_template_id"),"source":ab.id,"duration":eff.get("duration",0),"stacks":rec["stacks"],"category":cat})
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO actor_effect_instances(effect_instance_id,world_id,effect_template_id,target_actor_type,target_actor_id,source_actor_type,source_actor_id,source_ability_id,category,disposition,visibility,stack_count,started_world_time,expires_world_time,active,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid,self.world_id,eff.get("effect_template_id"),"actor",target.actor_id,"actor",actor.actor_id,ab.id,cat,cat,eff.get("visibility","normal"),rec["stacks"],self.world_time(),self.world_time()+int(num(eff.get("duration",0))),1,now(),now(),jdump(rec)))
        self._pub("ability_effect_applied", rec); return rec
    def _finish_cast(self, cast_id: str, state: str, reason: str) -> dict[str,Any]:
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("UPDATE actor_ability_casts SET state=?,interrupt_reason=?,updated_at=? WHERE cast_id=?",(state,reason,now(),cast_id))
        self._pub("ability_"+state, {"cast_id":cast_id,"reason":reason}); self._pub("cast_interrupted", {"cast_id":cast_id,"state":state,"reason":reason}); return {"ok":True,"cast_id":cast_id,"state":state,"reason":reason}
    def _grants(self, actor_id: str) -> list[dict[str,Any]]:
        if not self.db_path: return []
        with sqlite3.connect(self.db_path) as c: rows=c.execute("SELECT grant_id,ability_id,source_type,source_id,source_instance_id,rank,proficiency,enabled,temporary,starts_at,expires_at,metadata_json FROM actor_ability_grants WHERE actor_id=? AND enabled=1 ORDER BY ability_id,source_type,grant_id",(actor_id,)).fetchall()
        return [{"grant_id":r[0],"ability_id":r[1],"source_type":r[2],"source_id":r[3],"source_instance_id":r[4],"rank":r[5],"proficiency":r[6],"enabled":bool(r[7]),"temporary":bool(r[8]),"starts_at":r[9],"expires_at":r[10],"metadata":jload(r[11])} for r in rows]
    def world_time(self) -> int:
        rt = getattr(self, "runtime", None)
        if rt and hasattr(rt, "get_world_time"):
            try:
                wt = rt.get_world_time(self.world_id) or {}
                if wt.get("total_minutes") is not None:
                    return int(wt.get("total_minutes") or 0)
                return (max(1, int(wt.get("day") or 1)) - 1) * 1440 + int(wt.get("hour") or 0) * 60 + int(wt.get("minute") or 0)
            except Exception:
                pass
        return int(getattr(self,"_world_time",0) or 0)
    def _pub(self, name: str, payload: dict[str,Any]) -> None:
        if self.event_bus: self.event_bus.publish(name,payload,source_system="abilities",world_id=self.world_id)

def init_ability_schema(db_path: Path|str) -> None:
    with sqlite3.connect(db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS actor_ability_grants (grant_id TEXT PRIMARY KEY, world_id TEXT, actor_type TEXT, actor_id TEXT, ability_id TEXT, source_type TEXT, source_id TEXT, source_instance_id TEXT, rank INTEGER, proficiency REAL, enabled INTEGER, temporary INTEGER, starts_at TEXT, expires_at TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actor_ability_grants_actor ON actor_ability_grants(world_id,actor_type,actor_id,enabled)")
        c.execute("CREATE TABLE IF NOT EXISTS actor_ability_cooldowns (cooldown_id TEXT PRIMARY KEY, world_id TEXT, actor_type TEXT, actor_id TEXT, ability_id TEXT, cooldown_group TEXT, started_world_time INTEGER, ready_world_time INTEGER, charges_current INTEGER, charges_maximum INTEGER, next_charge_world_time INTEGER, active INTEGER, created_at TEXT, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actor_ability_cooldowns_actor ON actor_ability_cooldowns(world_id,actor_type,actor_id,active)")
        c.execute("CREATE TABLE IF NOT EXISTS actor_ability_casts (cast_id TEXT PRIMARY KEY, world_id TEXT, actor_type TEXT, actor_id TEXT, ability_id TEXT, target_data_json TEXT, state TEXT, started_world_time INTEGER, completes_world_time INTEGER, next_tick_world_time INTEGER, cost_state_json TEXT, cooldown_state_json TEXT, interrupt_reason TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_actor_ability_casts_actor ON actor_ability_casts(world_id,actor_type,actor_id,state)")
        c.execute("CREATE TABLE IF NOT EXISTS ability_action_results (action_id TEXT PRIMARY KEY, world_id TEXT, actor_id TEXT, ability_id TEXT, ok INTEGER, reason_code TEXT, requested_at TEXT, completed_at TEXT, result_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS ability_effect_tick_claims (claim_id TEXT PRIMARY KEY, world_id TEXT, effect_instance_id TEXT, scheduled_world_time INTEGER, claimed_at TEXT, metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS ability_audit_history (audit_id TEXT PRIMARY KEY, world_id TEXT, actor_id TEXT, ability_id TEXT, event_type TEXT, created_at TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS actor_ability_charges (charge_id TEXT PRIMARY KEY, world_id TEXT, actor_id TEXT, ability_id TEXT, charges_current INTEGER, charges_maximum INTEGER, next_charge_world_time INTEGER, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS actor_effect_instances (effect_instance_id TEXT PRIMARY KEY, world_id TEXT, effect_template_id TEXT, target_actor_type TEXT, target_actor_id TEXT, source_actor_type TEXT, source_actor_id TEXT, source_ability_id TEXT, source_item_instance_id TEXT, category TEXT, disposition TEXT, visibility TEXT, stack_group TEXT, stack_count INTEGER, maximum_stacks INTEGER, started_world_time INTEGER, expires_world_time INTEGER, remaining_duration INTEGER, next_tick_world_time INTEGER, active INTEGER, suspended INTEGER, removal_reason TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT)")
        c.commit()
