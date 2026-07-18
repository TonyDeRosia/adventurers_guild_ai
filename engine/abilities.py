"""Canonical Phase 6C Ability architecture.

One data-driven pipeline owns skills, spells, heals, buffs, debuffs, natural
attacks, monster powers, item abilities, passives, and future AI-selected
runtime actions.  The implementation is deliberately deterministic and built on
Actor resources, CombatEngine damage, a canonical HealingEvent, effect-instance
persistence, world-time cooldowns, and EventBus publishing.
"""
from __future__ import annotations

import json, math, re, sqlite3, uuid, random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from enum import Enum

from engine.actors import Actor, ActorRegistry, actor_from_runtime_character
from engine.combat import CombatEngine, DamageEvent
from engine.runtime_resources import RuntimeResourceService
from engine.combat_equipment import CombatContentRegistry

ABILITY_TYPES = {"skill","spell","technique","heal","buff","debuff","utility","defensive","movement","racial","profession","monster","natural","item","passive","administrative","custom"}
TARGET_MODES = {"self","single_actor","single_enemy","single_ally","single_any","current_target","room_enemy","room_ally","room_all","room","direction","item","equipped_item","corpse","none","custom"}
ACTIVATION_TYPES = {"instant","cast","channel","charged","passive","toggle","custom"}
COST_TYPES = {"flat","formula","percentage_current","percentage_maximum","all_current","custom","legacy_spell_mana"}
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
PHASE14B_ADVANCED_OPERATIONS = {"aura","stance","transform","summon","dismiss_summon","create_item","destroy_item","alter_item","create_room_effect","remove_room_effect"}
PHASE14B_RESERVED_OPERATIONS: set[str] = set()
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
class AuraDefinition:
    aura_id: str; source_policy: str = "while_source_exists"; scope: str = "room"; radius: int = 0; target_policy: str = "allies"; refresh_policy: str = "no_duplicate"; granted_effect_id: str = ""; update_interval: int = 1; line_of_sight: bool = False; same_room: bool = True; same_area: bool = False; source_required: bool = True; remove_on_leave: bool = True; suppress_on_leave: bool = False; maximum_targets: int = 99; tags: tuple[str, ...] = (); messages: dict[str, str] = field(default_factory=dict); source_version: str = "1"

@dataclass(frozen=True)
class TransformationDefinition:
    transformation_id: str; body_profile_id: str = ""; size: str = "medium"; appearance: str = ""; natural_weapon_profiles: tuple[dict[str, Any], ...] = (); movement_mode: str = "walk"; stat_modifiers: tuple[dict[str, Any], ...] = (); resistance_modifiers: tuple[dict[str, Any], ...] = (); ability_grants: tuple[str, ...] = (); suppressed_abilities: tuple[str, ...] = (); equipment_policy: str = "keep_equipped"; duration: dict[str, Any] = field(default_factory=dict); reversion_policy: str = "restore"; exclusive_group: str = "form"; messages: dict[str, str] = field(default_factory=dict); source_version: str = "1"

@dataclass(frozen=True)
class SummonDefinition:
    summon_id: str; summon_template_id: str; count: int = 1; duration: int = 10; duration_domain: str = "world_minutes"; level_policy: str = "owner"; stat_scaling: dict[str, Any] = field(default_factory=dict); resource_scaling: dict[str, Any] = field(default_factory=dict); ability_grants: tuple[str, ...] = (); owner_relationship: str = "follow"; control_policy: str = "owner"; follow_policy: str = "same_room"; combat_policy: str = "assist"; death_policy: str = "cleanup"; dismiss_policy: str = "owner"; storage_policy: str = "temporary"; maximum_active: int = 1; maximum_per_ability: int = 1; exclusive_group: str = ""; replacement_policy: str = "dismiss_oldest"; messages: dict[str, str] = field(default_factory=dict); source_version: str = "1"

@dataclass(frozen=True)
class RoomEffectDefinition:
    room_effect_id: str; name: str = ""; description: str = ""; tags: tuple[str, ...] = (); duration: int = 10; duration_domain: str = "world_minutes"; tick_interval: int = 0; entry_operations: tuple[dict[str, Any], ...] = (); exit_operations: tuple[dict[str, Any], ...] = (); resident_operations: tuple[dict[str, Any], ...] = (); tick_operations: tuple[dict[str, Any], ...] = (); movement_modifiers: dict[str, Any] = field(default_factory=dict); ability_restrictions: dict[str, Any] = field(default_factory=dict); visibility: str = "public"; messages: dict[str, str] = field(default_factory=dict); persistence_policy: str = "runtime"; source_version: str = "1"

@dataclass(frozen=True)
class SummonProfile:
    profile_id: str; owner_actor_id: str; profile_name: str; summon_definition_id: str; entity_template_id: str; identity: dict[str, Any] = field(default_factory=dict); level: int = 1; primary_stat_profile: dict[str, Any] = field(default_factory=dict); secondary_modifier_profile: dict[str, Any] = field(default_factory=dict); resource_profile: dict[str, Any] = field(default_factory=dict); natural_weapons: tuple[dict[str, Any], ...] = (); ability_grants: tuple[str, ...] = (); appearance: str = ""; profile_schema_version: str = "1"; source_hash: str = ""; created_at: str = ""; updated_at: str = ""

@dataclass(frozen=True)
class RuntimeEffectInstance:
    effect_instance_id: str; definition_id: str; source_ability_id: str = ""; source_actor_id: str = ""; source_item_id: str = ""; target_actor_id: str = ""; target_item_id: str = ""; target_room_id: str = ""
    applied_at: int = 0; expires_at: int | None = None; duration_domain: str = "world_minutes"; next_tick_at: int | None = None; tick_interval: int = 0
    stacks: int = 1; intensity: int = 1; state: str = "active"; tags: tuple[str, ...] = (); modifiers: tuple[dict[str, Any], ...] = (); origin_action_id: str = ""; source_versions: dict[str, Any] = field(default_factory=dict); metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpellManaCostResult:
    ability_id: str
    actor_id: str
    actor_class_id: str
    actor_level: int
    class_unlock_level: int
    mana_max: int
    mana_min: int
    mana_change: int
    base_scaled_cost: int
    empowered_reduction: int = 0
    discipline_reduction: int = 0
    tactical_memory_reduction: int = 0
    enchanters_focus_reduction: int = 0
    total_additive_reduction_pct: int = 0
    final_cost: int = 0
    current_mana: int = 0
    sufficient: bool = False


class SpellResourceCostService:
    """Canonical legacy-TBA spell mana cost calculator."""
    CLASS_ALIASES = {"mage": "magic_user", "magic user": "magic_user", "magic-user": "magic_user", "adventurer": "adventurer"}
    DEFAULT_UNLOCKS = {"magic_missile": {"adventurer": 1, "magic_user": 1, "mage": 1}}

    def __init__(self, service: "AbilityExecutionService"):
        self.service = service

    def actor_class_id(self, actor: Actor) -> str:
        for src in (getattr(actor, "plugin_data", {}) or {}, getattr(actor, "builder_metadata", {}) or {}, getattr(actor, "progression_profile", {}) or {}):
            for key in ("primary_class_id", "class_id", "canonical_class_id"):
                if src.get(key):
                    raw = str(src.get(key)).lower().replace(" ", "_").replace("-", "_")
                    return self.CLASS_ALIASES.get(raw, raw)
        return "adventurer"

    def _metadata(self, ab: AbilityDefinition) -> tuple[int, int, int, dict[str, int]]:
        meta = dict((ab.plugin_data or {}).get("legacy_mana") or {})
        if ab.id == "magic_missile" and not meta:
            meta = {"mana_max": 25, "mana_min": 10, "mana_change": 3, "class_unlock_levels": {"adventurer": 1, "magic_user": 1, "mage": 1}}
        if not meta:
            cost = next((c for c in ab.costs if str(c.get("resource_id")) == "mana"), {})
            amount = int(num(cost.get("amount"), 0))
            meta = {"mana_max": amount, "mana_min": amount, "mana_change": 0, "class_unlock_levels": {}}
        unlocks = {str(k).lower().replace(" ", "_").replace("-", "_"): int(v) for k, v in (meta.get("class_unlock_levels") or self.DEFAULT_UNLOCKS.get(ab.id, {})).items()}
        return int(meta.get("mana_max", 0)), int(meta.get("mana_min", 0)), int(meta.get("mana_change", 0)), unlocks

    def calculate(self, actor: Actor, ab: AbilityDefinition) -> SpellManaCostResult:
        cls = self.actor_class_id(actor)
        level = max(1, int((getattr(actor, "progression_profile", {}) or {}).get("level", 1) or 1))
        mana_max, mana_min, mana_change, unlocks = self._metadata(ab)
        unlock = int(unlocks.get(cls, unlocks.get(self.CLASS_ALIASES.get(cls, cls), 1)) or 1)
        base = max(mana_max - mana_change * (level - unlock), mana_min)
        cost = base
        affects = getattr(actor, "effect_container", {}) or {}
        flags = set((getattr(actor, "plugin_data", {}) or {}).get("affect_flags", []) or []) | set(affects.get("flags", []) or [])
        empowered = 10 if "AFF_EMPOWERED" in flags or "empowered" in flags else 0
        if empowered:
            cost = max(1, cost * 90 // 100)
        pdata = getattr(actor, "plugin_data", {}) or {}
        discipline = 5 if pdata.get("supreme_caster_discipline") else 0
        tactical = 5 if pdata.get("tactical_spell_memory") else 0
        focus = 10 if pdata.get("enchanters_focus") else 0
        additive = min(20, discipline + tactical + focus)
        if additive:
            cost = max(1, cost * (100 - additive) // 100)
        cur = int(getattr(actor.resources, "mana", 0) or 0)
        return SpellManaCostResult(ab.id, actor.actor_id, cls, level, unlock, mana_max, mana_min, mana_change, base, empowered, discipline, tactical, focus, additive, max(1, cost), cur, cur >= max(1, cost))

@dataclass(frozen=True)
class AbilityUseRequest:
    action_id: str; actor_id: str; ability_id: str; command_form: str = "cast"; raw_target: Any = None; resolved_targets: tuple[dict[str, Any], ...] = (); source_type: str = "learned"; source_id: str = ""; world_id: str = ""; room_id: str = ""; context: dict[str, Any] = field(default_factory=dict); requested_at: str = field(default_factory=now); metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ActorAbilityProficiency:
    actor_id: str; ability_id: str; learned: bool = True; proficiency: int = 1; maximum_proficiency: int = 100; practice_progress: int = 0; mastery_rank: str = "novice"; uses: int = 0; successes: int = 0; failures: int = 0; last_used: str = ""; source: str = "learned"; version: int = 1

@dataclass(frozen=True)
class AbilityGrantProjection:
    ability_id: str
    source_type: str
    source_id: str = ""
    source_instance_id: str = ""
    proficiency: int = 1
    temporary: bool = False
    active: bool = True
    suppressed: bool = False
    visible: bool = True
    source_version: str = "1"
    grant_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AbilityEffectOperationSpec:
    operation_id: str
    result_type: str = "operation_result"
    idempotency_policy: str = "action_id"
    allowed_target_types: tuple[str, ...] = ("self", "actor")
    required_services: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    builder_field_schema: dict[str, Any] = field(default_factory=dict)
    executable: bool = True


class AbilityEffectOperationRegistry:
    def __init__(self):
        self.specs: dict[str, AbilityEffectOperationSpec] = {}
        self.reserved: set[str] = set()
        for op in sorted(set(PHASE14A_OPERATIONS) | set(PHASE14B_ADVANCED_OPERATIONS)):
            self.register(AbilityEffectOperationSpec(
                operation_id=op,
                result_type="runtime_effect" if op in {"apply_affect","apply_condition","modify_stat","grant_resistance","grant_immunity","grant_vulnerability","damage_over_time","healing_over_time","resource_over_time","aura","stance","transform","create_room_effect"} else "operation_result",
                idempotency_policy="origin_action_id" if op in PHASE14B_ADVANCED_OPERATIONS else "component_id",
                allowed_target_types=("self","actor","room","item") if op in PHASE14B_ADVANCED_OPERATIONS else ("self","actor"),
                required_services=("effect_store",) if op in {"aura","stance","transform","create_room_effect","remove_room_effect"} else (),
                event_names=(f"{op}_completed", "effect_applied"),
                builder_field_schema={"operation": {"type": "string", "const": op}, "parameters": {"type": "object"}},
                executable=True,
            ))
    @property
    def operations(self) -> set[str]: return set(self.specs)
    def register(self, spec: AbilityEffectOperationSpec) -> None:
        if not spec.operation_id or not spec.executable:
            raise ValueError("Registered ability operations must be executable and named")
        self.specs[spec.operation_id] = spec
    def validate(self, operation: str) -> None:
        if operation not in self.specs:
            raise ValueError(f"Unknown ability effect operation: {operation}")
        if not self.specs[operation].executable:
            raise ValueError(f"Ability effect operation is not executable: {operation}")
    def schema_for(self, operation: str) -> dict[str, Any]:
        self.validate(operation); return dict(self.specs[operation].builder_field_schema)
    def is_reserved(self, operation: str) -> bool: return operation in self.reserved

class AbilityAvailabilityService:
    def __init__(self, service: "AbilityExecutionService"):
        self.service = service
    def resolve_actor_abilities(self, actor_id: str) -> list[dict[str, Any]]:
        rows=[]
        for row in self.service.get_actor_abilities(actor_id):
            rows.append({"ability": row, "availability_state": "active" if row.get("enabled", True) else "inactive", "source_type": ("NPC template" if (row.get("grants") or [{}])[0].get("source_type") == "legacy_actor_plugin_adapter" else (row.get("grants") or [{}])[0].get("source_type", row.get("source", "learned"))), "source_id": (row.get("grants") or [{}])[0].get("source_id", ""), "proficiency": row.get("proficiency", 1), "hidden": row.get("visibility") == "hidden", "visible": row.get("visibility") != "hidden", "active": row.get("enabled", True), "denial_reason": ""})
        actor=self.service.actors.get(actor_id)
        for aid in (getattr(actor, "plugin_data", {}) or {}).get("npc_ability_ids", []) if actor else []:
            if aid in self.service.registry.abilities and not any(r["ability"].get("id")==aid for r in rows):
                ab=self.service.registry.abilities[aid]
                rows.append({"ability": ab.to_dict(), "availability_state": "active", "source_type": "NPC template", "source_id": actor_id, "proficiency": int((getattr(actor,"plugin_data",{}) or {}).get("proficiency", 50)), "hidden": False, "visible": True, "active": True, "denial_reason": ""})
        return rows


class AuraRuntimeService:
    """Runtime authority for aura instances and actor memberships."""
    def __init__(self, ability_service: "AbilityExecutionService"):
        self.ability_service = ability_service; self.event_bus = ability_service.event_bus
        self._subscribe()
    def _subscribe(self) -> None:
        if not self.event_bus: return
        for name in ("actor_entered_room","actor_left_room","movement_succeeded","actor_defeated","actor_died","character_logout","item_unequipped","effect_removed","effect_expired","stance_removed","world_loaded","runtime_ready","startup_complete"):
            self.event_bus.subscribe(name, self.handle_event, source="AuraRuntimeService")
    def handle_event(self, event: Any) -> None:
        p = getattr(event, "payload", {}) or {}; svc=self.ability_service
        actor_id = str(p.get("actor_id") or p.get("character_id") or p.get("source_actor_id") or "")
        if event.event_name in {"actor_defeated","actor_died","character_logout"} and actor_id:
            self.remove_source_auras(actor_id, event.event_name)
        if event.event_name in {"item_unequipped","effect_removed","effect_expired","stance_removed"}:
            source_id = str(p.get("item_instance_id") or p.get("effect_instance_id") or p.get("stance_effect_instance_id") or "")
            if source_id: self.remove_source_auras(source_id, event.event_name)
        if event.event_name in {"actor_entered_room","actor_left_room","movement_succeeded"} and actor_id:
            new_room = str(p.get("new_room_id") or p.get("room_id") or "")
            if new_room and actor_id in svc.actors: svc.actors[actor_id].identity.current_location = new_room
            self.reconcile_actor_memberships(actor_id)
            if event.event_name == "movement_succeeded":
                self.reconcile_source_auras(actor_id)
        if event.event_name in {"world_loaded","runtime_ready","startup_complete"}:
            self.recover_auras()
    def activate_aura(self, actor_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        return self.ability_service.create_aura(actor_id, ability_id, eff, origin_action_id)
    def remove_aura(self, aura_instance_id: str, reason: str="removed") -> dict[str, Any]:
        return self.ability_service.remove_aura(aura_instance_id, reason)
    def reconcile_aura(self, aura_instance_id: str) -> list[dict[str, Any]]:
        return self.ability_service.update_aura_membership(aura_instance_id)
    def reconcile_actor_memberships(self, actor_id: str) -> list[dict[str, Any]]:
        if not self.ability_service.db_path: return []
        with sqlite3.connect(self.ability_service.db_path) as c:
            ids=[r[0] for r in c.execute("SELECT aura_instance_id FROM aura_instances WHERE active=1")]
        return [x for aid in ids for x in self.reconcile_aura(aid)]
    def reconcile_source_auras(self, actor_id: str) -> list[dict[str, Any]]:
        if not self.ability_service.db_path: return []
        with sqlite3.connect(self.ability_service.db_path) as c:
            ids=[r[0] for r in c.execute("SELECT aura_instance_id FROM aura_instances WHERE active=1 AND source_actor_id=?", (actor_id,))]
        return [x for aid in ids for x in self.reconcile_aura(aid)]
    def recover_auras(self) -> list[dict[str, Any]]:
        if not self.ability_service.db_path: return []
        with sqlite3.connect(self.ability_service.db_path) as c:
            ids=[r[0] for r in c.execute("SELECT aura_instance_id FROM aura_instances WHERE active=1")]
        return [x for aid in ids for x in self.reconcile_aura(aid)]
    def remove_source_auras(self, source_id: str, reason: str="source_removed") -> list[dict[str, Any]]:
        if not self.ability_service.db_path: return []
        with sqlite3.connect(self.ability_service.db_path) as c:
            ids=[r[0] for r in c.execute("SELECT aura_instance_id FROM aura_instances WHERE active=1 AND (source_actor_id=? OR source_instance_id=?)", (source_id, source_id))]
        return [self.remove_aura(aid, reason) for aid in ids]


class SummonRuntimeService:
    def __init__(self, ability_service: "AbilityExecutionService"):
        self.ability_service=ability_service; self.event_bus=ability_service.event_bus
        if self.event_bus:
            for name in ("movement_succeeded","actor_died","actor_defeated","character_logout","actor_left_world","runtime_ready","world_loaded"):
                self.event_bus.subscribe(name, self.handle_event, source="SummonRuntimeService")
    def handle_event(self, event: Any) -> None:
        p=getattr(event,"payload",{}) or {}; actor_id=str(p.get("actor_id") or p.get("character_id") or "")
        if event.event_name == "movement_succeeded" and actor_id: self.follow_owner(actor_id, str(p.get("new_room_id") or p.get("room_id") or ""))
        if event.event_name in {"actor_died","actor_defeated","character_logout","actor_left_world"} and actor_id: self.cleanup_owner_summons(actor_id, event.event_name)
        if event.event_name in {"runtime_ready","world_loaded"}: self.recover_summons()
    def create_summons(self,*a: Any, **kw: Any) -> list[dict[str, Any]]: return self.ability_service.create_summons(*a, **kw)
    def cleanup_summon(self, summon_id: str, reason: str, origin_action_id: str="") -> dict[str, Any]:
        actor=self.ability_service.actors.get(summon_id); owner=(actor.plugin_data or {}).get("owner_actor_id","") if actor else ""
        if not owner and self.ability_service.db_path:
            with sqlite3.connect(self.ability_service.db_path) as c:
                row=c.execute("SELECT owner_actor_id FROM summon_relationships WHERE actor_id=?", (summon_id,)).fetchone(); owner=row[0] if row else ""
        return self.ability_service.dismiss_summon(owner, summon_id, reason)
    def cleanup_owner_summons(self, owner_id: str, reason: str) -> dict[str, Any]: return self.ability_service.dismiss_summon(owner_id, "all", reason)
    def follow_owner(self, owner_id: str, new_room_id: str) -> list[dict[str, Any]]:
        out=[]
        for actor in list(self.ability_service.actors.values()):
            pd=actor.plugin_data or {}
            if pd.get("owner_actor_id")==owner_id and pd.get("follow_policy", pd.get("relationship","follow")) in {"same_room","follow_when_possible","follow"} and new_room_id:
                actor.identity.current_location = new_room_id; out.append({"summon_instance_id":actor.actor_id,"result":"followed","room_id":new_room_id})
                self.ability_service._pub("summon_followed", out[-1] | {"owner_actor_id": owner_id})
        return out
    def recover_summons(self) -> list[dict[str, Any]]:
        # Current lightweight actors are in-memory; persisted relationships are idempotently skipped if already present.
        return []


class RoomEffectRuntimeService:
    def __init__(self, ability_service: "AbilityExecutionService"):
        self.ability_service=ability_service; self.event_bus=ability_service.event_bus
        if self.event_bus:
            for name in ("actor_entered_room","actor_left_room","movement_succeeded","runtime_ready","world_loaded","runtime_shutdown"):
                self.event_bus.subscribe(name, self.handle_event, source="RoomEffectRuntimeService")
    def handle_event(self, event: Any) -> None:
        p=getattr(event,"payload",{}) or {}; actor_id=str(p.get("actor_id") or p.get("character_id") or "")
        if event.event_name in {"actor_entered_room","movement_succeeded"} and actor_id: self.actor_entered(actor_id, str(p.get("new_room_id") or p.get("room_id") or ""))
        if event.event_name == "actor_left_room" and actor_id: self.actor_exited(actor_id, str(p.get("old_room_id") or p.get("room_id") or ""))
        if event.event_name in {"runtime_ready","world_loaded"}: self.recover_room_effects()
    def create_room_effect(self,*a: Any, **kw: Any) -> dict[str, Any]: return self.ability_service.create_room_effect(*a, **kw)
    def actor_entered(self, actor_id: str, room_id: str) -> list[dict[str, Any]]:
        return self.ability_service.reconcile_room_effect_memberships(room_id, actor_id)
    def actor_exited(self, actor_id: str, room_id: str) -> list[dict[str, Any]]:
        return self.ability_service.remove_room_effect_memberships(room_id, actor_id, "left_room")
    def process_ticks(self, world_time: int|None=None) -> list[dict[str, Any]]: return self.ability_service.process_room_effect_ticks(world_time)
    def recover_room_effects(self) -> list[dict[str, Any]]:
        if not self.ability_service.db_path: return []
        with sqlite3.connect(self.ability_service.db_path) as c:
            rows=c.execute("SELECT room_id FROM room_effect_instances WHERE state='active'").fetchall()
        return [x for (rid,) in rows for x in self.ability_service.reconcile_room_effect_memberships(rid)]


class StanceRuntimeService:
    def __init__(self, ability_service: "AbilityExecutionService"): self.ability_service=ability_service
class TransformationRuntimeService:
    def __init__(self, ability_service: "AbilityExecutionService"): self.ability_service=ability_service
class SummonProfileService:
    def __init__(self, ability_service: "AbilityExecutionService"): self.ability_service=ability_service
class PassiveTriggerService:
    def __init__(self, ability_service: "AbilityExecutionService"): self.ability_service=ability_service
class ItemAbilityRuntimeService:
    def __init__(self, ability_service: "AbilityExecutionService"): self.ability_service=ability_service



ABILITY_EXECUTION_STATUSES = {
    "SUCCESS", "FAILED", "UNKNOWN_ABILITY", "NOT_KNOWN", "WRONG_CATEGORY",
    "INVALID_TARGET", "INVALID_POSITION", "INSUFFICIENT_MANA", "INSUFFICIENT_MOVE",
    "ON_COOLDOWN", "ALREADY_ACTIVE", "TARGET_ALREADY_AFFECTED",
    "HANDLER_NOT_IMPLEMENTED", "EXECUTION_INTERRUPTED",
}


# Phase 21B deliberately keeps the mature execution implementation below, but
# gives every caller one transport-neutral contract.  The old gateway remains a
# compatibility adapter for integrations written before this contract existed.
class AbilityInvocationType(str, Enum):
    CAST_COMMAND = "CAST_COMMAND"
    SKILL_COMMAND = "SKILL_COMMAND"
    ITEM_ACTIVATION = "ITEM_ACTIVATION"
    NPC_AI = "NPC_AI"
    SCRIPT = "SCRIPT"
    PASSIVE_TRIGGER = "PASSIVE_TRIGGER"
    ADMIN_TEST = "ADMIN_TEST"


@dataclass(frozen=True)
class AbilityExecutionRequest:
    """Transport-independent request accepted by :class:`AbilityRuntimeService`."""
    request_id: str
    world_id: str
    actor_id: str
    ability_id: str
    invocation_type: AbilityInvocationType = AbilityInvocationType.CAST_COMMAND
    raw_argument_text: str = ""
    explicit_target_actor_id: str = ""
    explicit_target_item_id: str = ""
    explicit_target_room_id: str = ""
    explicit_direction: str = ""
    source_item_instance_id: str = ""
    source_script_id: str = ""
    source_command: str = ""
    actor_life_generation: int | None = None
    current_tick: int | None = None
    engagement_id: str = ""
    parent_event_id: str = ""
    idempotency_key: str = ""
    preview: bool = False
    debug: bool = False
    authorized_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AbilityValidationResult:
    valid: bool
    failure_code: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AbilityCostPreview:
    validation: AbilityValidationResult
    costs: tuple[dict[str, Any], ...] = ()


class AbilityRandomProvider(Protocol):
    """Injectable randomness boundary for every runtime-owned ability roll."""
    def roll_percent(self) -> int: ...
    def randint(self, minimum: int, maximum: int) -> int: ...


class PythonAbilityRandomProvider:
    def roll_percent(self) -> int:
        return random.randint(1, 100)
    def randint(self, minimum: int, maximum: int) -> int:
        return random.randint(minimum, maximum)


class AbilityRuntimeService:
    """The canonical active-ability boundary.

    This is the canonical orchestrator, not a gateway around the historical
    executor.  ``AbilityExecutionService`` supplies domain authorities (costs,
    effects, cooldown storage and persistence), while this class owns their
    ordering and the request receipt.
    """
    def __init__(self, service: "AbilityExecutionService", random_provider: AbilityRandomProvider | None = None):
        self.service = service
        self.random_provider = random_provider or PythonAbilityRandomProvider()
        self._ledger: dict[str, AbilityExecutionResult] = {}

    def resolve_definition(self, ability_reference: str) -> AbilityDefinition | None:
        aid = self.service.gateway().resolve_definition(ability_reference)
        return self.service.registry.abilities.get(aid)

    def validate(self, request: AbilityExecutionRequest) -> AbilityValidationResult:
        if not request.ability_id or request.ability_id not in self.service.registry.abilities:
            return AbilityValidationResult(False, "ABILITY_NOT_FOUND")
        actor = self.service.actor_registry.get(request.actor_id)
        if actor is None:
            return AbilityValidationResult(False, "ACTOR_NOT_FOUND")
        remaining = max(0, int(getattr(actor, "wait_state", 0) or 0))
        if remaining:
            return AbilityValidationResult(False, "WAIT_STATE", {"remaining_wait": remaining, "message": f"You must wait {remaining} more tick(s)."})
        trace = self.service.validate_ability_use(request.actor_id, request.ability_id,
            request.explicit_target_actor_id or request.raw_argument_text or "self", preview=True)
        if trace.get("ok"):
            return AbilityValidationResult(True, details={"trace": trace})
        errors = trace.get("errors") or []
        # Existing validators have stable detailed messages but not all historic
        # reason codes.  Preserve them as details while exposing a stable code.
        code = str(trace.get("reason_code") or ("INVALID_TARGET" if any("target" in str(x).lower() for x in errors) else "VALIDATION_FAILED"))
        return AbilityValidationResult(False, code, {"trace": trace})

    def preview_cost(self, request: AbilityExecutionRequest) -> AbilityCostPreview:
        validation = self.validate(request)
        costs: tuple[dict[str, Any], ...] = ()
        if validation.details.get("trace"):
            costs = tuple(validation.details["trace"].get("costs") or ())
        return AbilityCostPreview(validation, costs)

    def execute(self, request: AbilityExecutionRequest) -> AbilityExecutionResult:
        key = request.idempotency_key or request.request_id
        if key and key not in self._ledger:
            stored = self._load_durable_result(request, key)
            if stored is not None:
                self._ledger[key] = stored
        if key and key in self._ledger:
            prior = self._ledger[key]
            self.service._pub("ability.duplicate_ignored", {"request_id": request.request_id, "actor_id": request.actor_id, "ability_id": request.ability_id})
            return AbilityExecutionResult(status="DUPLICATE_IGNORED", request_id=request.request_id, ability_id=prior.ability_id, ability_name=prior.ability_name,
                actor_id=request.actor_id, target_id=prior.target_id, stage_reached="idempotency", player_message="That ability request was already processed.", failure_code="DUPLICATE_IGNORED", metadata={"original_status": prior.status})
        if request.preview:
            preview = self.preview_cost(request)
            return AbilityExecutionResult(status="SUCCESS" if preview.validation.valid else "FAILED_VALIDATION", request_id=request.request_id, ability_id=request.ability_id,
                actor_id=request.actor_id, invocation_type=request.invocation_type.value, stage_reached="preview", validation=preview.validation, calculated_costs=list(preview.costs), metadata={"preview": True, "costs": list(preview.costs), "failure_code": preview.validation.failure_code}, failure_code=preview.validation.failure_code)
        self.service._pub("ability.requested", {"request_id": request.request_id, "actor_id": request.actor_id, "ability_id": request.ability_id, "invocation_type": request.invocation_type.value})
        validation = self.validate(request)
        if not validation.valid:
            self.service._pub("ability.validation.failed", {"request_id": request.request_id, "failure_code": validation.failure_code})
            return AbilityExecutionResult(status="FAILED_VALIDATION", request_id=request.request_id, actor_id=request.actor_id, ability_id=request.ability_id, invocation_type=request.invocation_type.value, stage_reached="validation", validation=validation, failure_code=validation.failure_code, failure_details=validation.details, player_message=str((validation.details.get("trace") or {}).get("message") or "You cannot use that ability."))
        trace = validation.details["trace"]
        actor = self.service.actor_registry.get(request.actor_id)
        ability = self.service.registry.abilities[request.ability_id]
        targets = list(trace.get("targets") or [])
        costs = list(trace.get("costs") or [])
        self.service._pub("ability.definition.resolved", {"request_id": request.request_id, "ability_id": ability.id})
        self.service._pub("ability.target.resolved", {"request_id": request.request_id, "targets": targets})
        self.service._pub("ability.cost.calculated", {"request_id": request.request_id, "costs": costs})
        self.service._pub("ability.resource.checked", {"request_id": request.request_id, "costs": costs})
        before = self.service._proficiency(actor.actor_id, ability.id)
        policy = str((ability.proficiency_policy or {}).get("success_policy") or "ALWAYS_SUCCEEDS").upper()
        threshold = max(1, min(100, int(before or 100)))
        roll = None if policy in {"ALWAYS_SUCCEEDS", "PASSIVE_NO_ROLL", "EFFECT_HANDLER_DEFINED"} else self.random_provider.roll_percent()
        succeeded = policy not in {"LEARNED_PERCENT_ROLL", "OPPOSED_ROLL"} or bool(roll is not None and roll <= threshold)
        self.service._pub("ability.roll.completed", {"request_id": request.request_id, "actor_id": actor.actor_id, "ability_id": ability.id, "roll": roll, "threshold": threshold, "policy": policy, "success": succeeded})
        if not succeeded:
            return AbilityExecutionResult(status="FAILED_ROLL", request_id=request.request_id, actor_id=actor.actor_id, ability_id=ability.id, ability_name=ability.name, invocation_type=request.invocation_type.value, stage_reached="success_roll", validation=validation, resolved_targets=targets, calculated_costs=costs, proficiency_before=before, success_roll=roll, success_threshold=threshold, metadata={"success_policy": policy}, player_message="You fail to execute the ability.")
        paid = self.service._pay_costs(actor, ability, "start")
        self.service._pub("ability.resource.paid", {"request_id": request.request_id, "costs": paid})
        cast_id = "runtime_" + request.request_id.replace(" ", "_") if request.request_id else "runtime_" + uuid.uuid4().hex
        self.service._pub("ability.effect.started", {"request_id": request.request_id, "cast_id": cast_id})
        effect = self.service.execute_effect_handler(actor, ability, targets, cast_id)
        improvement = self.service.attempt_proficiency_improvement(actor.actor_id, ability.id, random_provider=self.random_provider)
        after = self.service._proficiency(actor.actor_id, ability.id)
        if improvement.get("improved"):
            self.service._pub("ability.proficiency.changed", {"request_id": request.request_id, **improvement})
        wait_before = max(0, int(getattr(actor, "wait_state", 0) or 0))
        requested_wait = max(0, int((ability.timing or {}).get("wait_state", (ability.timing or {}).get("wait_duration", 0)) or 0))
        applied_wait = requested_wait if effect.get("ok", True) else 0
        if applied_wait:
            # Actor.wait_state is the existing combat/death lifecycle field; no parallel timer is created.
            actor.wait_state = wait_before + applied_wait
            self.service._pub("ability.wait_state.applied", {"request_id": request.request_id, "actor_id": actor.actor_id, "ability_id": ability.id, "before": wait_before, "duration": applied_wait, "after": actor.wait_state, "policy": "ON_EFFECT_COMMIT"})
        wait_receipt = {"before": wait_before, "requested_duration": requested_wait, "applied_duration": applied_wait, "after": max(0, int(getattr(actor, "wait_state", 0) or 0)), "policy": "ON_EFFECT_COMMIT"}
        self.service._start_cooldown(actor.actor_id, ability)
        cooldown = {"applied": bool(ability.cooldowns), "policy": "ON_EFFECT_COMMIT"}
        if cooldown["applied"]: self.service._pub("ability.cooldown.applied", {"request_id": request.request_id, **cooldown})
        result = AbilityExecutionResult(status="SUCCESS" if effect.get("ok", True) else "FAILED", request_id=request.request_id, ability_id=ability.id, ability_name=ability.name, actor_id=actor.actor_id,
            target_id=str((targets[0] if targets else {}).get("actor_id") or ""), invocation_type=request.invocation_type.value, stage_reached="effect_completed", validation=validation, resolved_targets=targets, calculated_costs=costs, paid_costs=paid,
            proficiency_before=before, success_roll=roll, success_threshold=threshold, success_policy=policy, improvement_roll=improvement.get("roll"), improvement_threshold=improvement.get("threshold"), improvement_amount=int(improvement.get("amount", 0) or 0), proficiency_result=improvement, proficiency_after=after, wait_state_applied=wait_receipt, cooldown_applied=cooldown,
            effect_results=list(effect.get("effect_events") or []), damage_results=list(effect.get("damage_events") or []), resource_changes=paid, cooldown_started=cooldown["applied"], player_message=str(effect.get("message") or self.service._ability_success_message(ability.id) or "Ability activated."), messages=[str(effect.get("message") or "")], metadata={"cast_id": cast_id, "payment_policy": "PAY_ON_ATTEMPT", "success_policy": policy})
        if key and result.ok:
            self._ledger[key] = result
            self._store_durable_result(request, key, result)
        self.service._pub("ability.succeeded" if result.ok else "ability.failed", {"request_id": request.request_id, "actor_id": request.actor_id, "ability_id": request.ability_id, "status": result.status})
        return result


    def _store_durable_result(self, request: AbilityExecutionRequest, key: str, result: "AbilityExecutionResult") -> None:
        if not self.service.db_path:
            return
        summary = {"status": result.status, "ability_id": result.ability_id, "ability_name": result.ability_name, "target_id": result.target_id, "stage_reached": result.stage_reached, "player_message": result.player_message, "success_roll": result.success_roll, "success_threshold": result.success_threshold}
        with sqlite3.connect(self.service.db_path) as con:
            con.execute("DELETE FROM ability_execution_ledger WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP")
            con.execute("INSERT OR REPLACE INTO ability_execution_ledger(world_id,idempotency_key,request_id,actor_id,actor_life_generation,ability_id,invocation_type,status,stage_reached,result_summary_json,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now','+30 days'))", (request.world_id or self.service.world_id, key, request.request_id, request.actor_id, str(request.actor_life_generation or ""), request.ability_id, request.invocation_type.value, result.status, result.stage_reached, jdump(summary)))

    def _load_durable_result(self, request: AbilityExecutionRequest, key: str) -> "AbilityExecutionResult | None":
        if not self.service.db_path:
            return None
        with sqlite3.connect(self.service.db_path) as con:
            row = con.execute("SELECT result_summary_json FROM ability_execution_ledger WHERE world_id=? AND idempotency_key=? AND actor_id=? AND actor_life_generation=? AND (expires_at IS NULL OR expires_at >= CURRENT_TIMESTAMP)", (request.world_id or self.service.world_id, key, request.actor_id, str(request.actor_life_generation or ""))).fetchone()
        if not row:
            return None
        data = jload(row[0], {})
        return AbilityExecutionResult(**{k: data[k] for k in AbilityExecutionResult.__dataclass_fields__ if k in data})


@dataclass(frozen=True)
class AbilityExecutionContext:
    """Strongly typed canonical context passed to ability gameplay handlers."""
    actor: Actor
    ability: "AbilityDefinition"
    actor_id: str
    ability_id: str
    ability_progression: dict[str, Any] = field(default_factory=dict)
    target_actor: Actor | None = None
    target_object: Any | None = None
    target_room: Any | None = None
    current_room: Any | None = None
    execution_source: str = "player_command"
    parsed_arguments: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    event_bus: Any | None = None
    world_state: dict[str, Any] = field(default_factory=dict)
    resolved_targets: tuple[dict[str, Any], ...] = ()
    invocation_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AbilityExecutionResult:
    """Structured runtime outcome returned by the canonical ability gateway."""
    status: str
    ability_id: str = ""
    ability_name: str = ""
    actor_id: str = ""
    target_id: str = ""
    player_message: str = ""
    room_message: str = ""
    target_message: str = ""
    applied_effects: list[dict[str, Any]] = field(default_factory=list)
    damage_dealt: list[dict[str, Any]] = field(default_factory=list)
    healing_done: list[dict[str, Any]] = field(default_factory=list)
    resource_changes: list[dict[str, Any]] = field(default_factory=list)
    cooldown_started: bool = False
    cooldown_remaining: int = 0
    events_published: list[dict[str, Any]] = field(default_factory=list)
    context: AbilityExecutionContext | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Phase 21B lifecycle record.  The legacy presentation fields above remain
    # for callers written before the request boundary; these fields are the
    # authoritative, transport-neutral execution receipt.
    request_id: str = ""
    invocation_type: str = ""
    stage_reached: str = ""
    validation: AbilityValidationResult | None = None
    resolved_targets: list[dict[str, Any]] = field(default_factory=list)
    calculated_costs: list[dict[str, Any]] = field(default_factory=list)
    paid_costs: list[dict[str, Any]] = field(default_factory=list)
    proficiency_before: int | None = None
    success_roll: int | None = None
    success_threshold: int | None = None
    success_policy: str = ""
    improvement_roll: int | None = None
    improvement_threshold: int | None = None
    improvement_amount: int = 0
    proficiency_result: dict[str, Any] = field(default_factory=dict)
    proficiency_after: int | None = None
    wait_state_applied: dict[str, Any] = field(default_factory=dict)
    cooldown_applied: dict[str, Any] = field(default_factory=dict)
    effect_results: list[dict[str, Any]] = field(default_factory=list)
    damage_results: list[dict[str, Any]] = field(default_factory=list)
    death_results: list[dict[str, Any]] = field(default_factory=list)
    affect_ids: list[str] = field(default_factory=list)
    created_item_ids: list[str] = field(default_factory=list)
    room_state_changes: list[dict[str, Any]] = field(default_factory=list)
    emitted_event_ids: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failure_code: str = ""
    failure_details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"


class AbilityTargetResolver:
    """Canonical target resolver for actor, room, object, and future target kinds."""
    def __init__(self, service: "AbilityExecutionService"):
        self.service = service

    def resolve(self, actor: Actor, ability: "AbilityDefinition", target: Any = None) -> dict[str, Any]:
        return self.service._resolve_target_canonical(actor, ability, target)

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
    canonical_effects: list[dict[str, Any]] = field(default_factory=list); prerequisites: list[dict[str, Any]] = field(default_factory=list)
    materials: list[dict[str, Any]] = field(default_factory=list); proficiency_policy: dict[str, Any] = field(default_factory=dict)
    display: dict[str, Any] = field(default_factory=dict); source_version: str = "1"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AbilityDefinition":
        return LegacyAbilityDefinitionAdapter.adapt(raw)
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    @property
    def ordered_effects(self) -> list[dict[str, Any]]: return list(self.canonical_effects or (self.plugin_data or {}).get("canonical_effects", []) or [])
    @property
    def activation_type(self) -> str: return str((self.timing or {}).get("activation_type") or "instant")


class LegacyAbilityDefinitionAdapter:
    """Deterministically normalizes older Phase 6C ability dictionaries.

    Published runtime code consumes AbilityDefinition.canonical_effects,
    prerequisites, materials, proficiency_policy, display, and source_version.
    Legacy plugin_data.canonical_effects/materials remain loadable, but are copied
    into typed top-level fields so new definitions do not hide behavior in
    generic plugin_data.
    """
    @staticmethod
    def adapt(raw: dict[str, Any]) -> AbilityDefinition:
        data = {k: raw.get(k) for k in AbilityDefinition.__dataclass_fields__ if k in raw and k != "canonical_effects"}
        data.setdefault("name", raw.get("name") or raw.get("id", ""))
        pdata = dict(raw.get("plugin_data") or {})
        canonical = raw.get("canonical_effects")
        if canonical is None:
            canonical = pdata.get("canonical_effects") or []
        data["canonical_effects"] = [dict(e) for e in canonical if isinstance(e, dict)]
        data["materials"] = list(raw.get("materials") or pdata.get("materials") or [])
        data["prerequisites"] = list(raw.get("prerequisites") or raw.get("requirements", {}).get("prerequisites", []) if isinstance(raw.get("requirements"), dict) else [])
        data["proficiency_policy"] = dict(raw.get("proficiency_policy") or pdata.get("proficiency_policy") or {})
        data["display"] = dict(raw.get("display") or {"name": data.get("name", ""), "short_name": raw.get("short_name", ""), "visibility": raw.get("visibility", "normal")})
        data["source_version"] = str(raw.get("source_version") or raw.get("version") or "1")
        pdata.pop("canonical_effects", None); pdata.pop("materials", None); pdata.pop("proficiency_policy", None)
        data["plugin_data"] = pdata
        return AbilityDefinition(**data)

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

    def execute_by_id(self, character_id: str, ability_id: str, target_query: Any=None, invocation_context: dict[str, Any] | None=None) -> AbilityUseResult:
        ctx = dict(invocation_context or {})
        ctx["ability_pre_resolved"] = True
        return self.execute(character_id, ability_id, target_query, ctx)

    def execute(self, character_id: str, ability_query: str, target_query: Any=None, invocation_context: dict[str, Any] | None=None) -> AbilityUseResult:
        actor = self.service.actor_registry.get(character_id)
        if actor is None:
            self.service._log_missing_actor(character_id, ability_query, invocation_context or {})
            return AbilityUseResult(False, reason_code="actor_registration_missing", player_message="Your character is not ready to use abilities yet. Please re-enter the world.", actor_id=character_id)
        invocation_context = invocation_context or {}
        pre_resolved = bool(invocation_context.get("ability_pre_resolved"))
        resolved = str(ability_query) if pre_resolved and str(ability_query) in self.service.registry.abilities else (self.resolve_ability(actor.actor_id, ability_query) or self.resolve_ability(character_id, ability_query))
        known_ids = {str(r.get("id")) for r in self.service.get_actor_abilities(actor.actor_id)} | {str(r.get("id")) for r in self.service.get_actor_abilities(character_id)}
        defined = resolved or self.resolve_definition(ability_query)
        if not defined:
            return AbilityUseResult(False, reason_code="unknown_ability", player_message=f'You do not recognize an ability called "{self._normalize_query(ability_query) or ability_query}".', actor_id=character_id)
        ab = self.service.registry.abilities[defined]
        command = str(invocation_context.get("command") or "").strip().split()
        verb = command[0].lower() if command else str(invocation_context.get("verb") or "")
        if verb == "cast" and ab.ability_type != "spell":
            return AbilityUseResult(False, ability_id=defined, ability_name=ab.name, reason_code="wrong_category", player_message=f"{ab.name} is a {ab.ability_type}, not a spell.", actor_id=character_id)
        if defined not in known_ids:
            return AbilityUseResult(False, ability_id=defined, ability_name=ab.name, reason_code="not_known", player_message=f"You do not know {ab.name}.", actor_id=character_id)
        if not (ab.damage_components or ab.healing_components or ab.effects_applied or ab.effects_removed or ab.state_changes or ab.ordered_effects):
            return AbilityUseResult(False, ability_id=defined, ability_name=ab.name, reason_code="handler_not_implemented", player_message=f"{ab.name} is recognized, but its gameplay handler is not implemented yet.", actor_id=character_id)
        resolved = defined
        before = self.service._proficiency(actor.actor_id, resolved)
        res = self.service.start_ability(actor.actor_id, resolved, target_query or "self")
        after = self.service._proficiency(actor.actor_id, resolved)
        trace_obj = res.get("trace") or []
        trace_steps = trace_obj if isinstance(trace_obj, list) else trace_obj.get("trace", []) if isinstance(trace_obj, dict) else []
        resolved_target = next((t for st in trace_steps if isinstance(st, dict) and st.get("step") == "resolve_target" for t in st.get("targets", []) if isinstance(t, dict)), {})
        return AbilityUseResult(
            ok=bool(res.get("ok")), ability_id=resolved, ability_name=ab.name, reason_code=str(res.get("reason_code") or ("ok" if res.get("ok") else "blocked")),
            player_message=str(res.get("message") or self.service._ability_success_message(resolved) or "Ability activated."), actor_id=actor.actor_id,
            target_id=str(resolved_target.get("actor_id") or target_query or ""), resource_changes=list(res.get("resource_changes") or []), cooldown_started=bool(res.get("cooldown_started")),
            effects_applied=list(res.get("effect_events") or []), proficiency_before=before, proficiency_after=after, proficiency_increased=after is not None and before is not None and after > before,
            events=list(res.get("events") or []), metadata={**{k: v for k, v in (res.get("metadata") or {}).items() if k in {"effect_type", "room_id"}}, "damage_events": list(res.get("damage_events") or []), "healing_events": list(res.get("healing_events") or [])},
        )

    def execute_result(self, character_id: str, ability_query: str, target_query: Any=None, invocation_context: dict[str, Any] | None=None) -> AbilityExecutionResult:
        before_events = len(getattr(self.service, "_published_execution_events", []))
        legacy = self.execute(character_id, ability_query, target_query, invocation_context)
        status_map = {
            "ok": "SUCCESS", "unknown_ability": "UNKNOWN_ABILITY", "not_known": "NOT_KNOWN",
            "wrong_category": "WRONG_CATEGORY", "handler_not_implemented": "HANDLER_NOT_IMPLEMENTED",
            "BLOCKED_COOLDOWN": "ON_COOLDOWN", "blocked_cooldown": "ON_COOLDOWN",
            "BLOCKED_RESOURCE": "INSUFFICIENT_MANA", "blocked_resource": "INSUFFICIENT_MANA",
            "BLOCKED_TARGET": "INVALID_TARGET", "invalid_target": "INVALID_TARGET",
            "BLOCKED_POSTURE": "INVALID_POSITION", "execution_interrupted": "EXECUTION_INTERRUPTED",
        }
        status = "SUCCESS" if legacy.ok else status_map.get(legacy.reason_code, status_map.get(str(legacy.reason_code).upper(), "FAILED"))
        if not legacy.ok and "move" in legacy.player_message.lower(): status = "INSUFFICIENT_MOVE"
        events = list(getattr(self.service, "_published_execution_events", [])[before_events:])
        actor = self.service.actor_registry.get(legacy.actor_id or character_id)
        ab = self.service.registry.abilities.get(legacy.ability_id)
        target_actor = self.service.actor_registry.get(legacy.target_id) if legacy.target_id else None
        ctx = AbilityExecutionContext(
            actor=actor, actor_id=(actor.actor_id if actor else character_id), ability=ab or AbilityDefinition(legacy.ability_id or ability_query), ability_id=legacy.ability_id,
            target_actor=target_actor, current_room=getattr(getattr(actor, "identity", None), "current_location", "") if actor else "",
            execution_source=str((invocation_context or {}).get("source") or "player_command"), parsed_arguments={"target": target_query, "ability_query": ability_query},
            services={"ability_service": self.service, "target_resolver": getattr(self.service, "target_resolver", None)}, event_bus=self.service.event_bus,
            world_state={"world_id": self.service.world_id, "world_time": self.service.world_time()}, invocation_context=invocation_context or {},
        ) if actor else None
        return AbilityExecutionResult(status=status, ability_id=legacy.ability_id, ability_name=legacy.ability_name, actor_id=legacy.actor_id or character_id,
            target_id=legacy.target_id, player_message=legacy.player_message, applied_effects=legacy.effects_applied,
            damage_dealt=list((legacy.metadata or {}).get("damage_events") or []), healing_done=list((legacy.metadata or {}).get("healing_events") or []),
            resource_changes=legacy.resource_changes, cooldown_started=legacy.cooldown_started, events_published=events, context=ctx, metadata=legacy.metadata)

    @staticmethod
    def _normalize_query(query: str) -> str:
        value = str(query or "").strip()
        value = re.sub(r"^[\'\"]+|[\'\"]+$", "", value)
        value = re.sub(r"\s+", " ", value.lower().replace("_", " ").replace("-", " ")).strip()
        return re.sub(r"^(use|cast|perform|invoke)\s+", "", value).strip()

    def resolve_ability_prefix(self, actor_id: str, query: str) -> tuple[str, str]:
        raw = str(query or "").strip()
        m = re.match(r"^[\'\"]([^\'\"]+)[\'\"](?:\s+(.*))?$", raw)
        if m:
            aid = self.resolve_ability(actor_id, m.group(1))
            return (aid, (m.group(2) or "").strip() or "self") if aid else ("", "")
        q = self._normalize_query(raw)
        learned = {str(r["id"]) for r in self.service.list_known_abilities(actor_id)}
        matches=[]
        for aid, ab in self.service.registry.abilities.items():
            if aid not in learned: continue
            aliases=(ab.plugin_data or {}).get("aliases") or []
            if isinstance(aliases, str): aliases=[aliases]
            candidates={self._normalize_query(aid), self._normalize_query(aid.replace("_"," ")), self._normalize_query(ab.name), self._normalize_query(ab.short_name)} | {self._normalize_query(a) for a in aliases}
            for c in candidates:
                if c and (q == c or q.startswith(c + " ")):
                    matches.append((len(c), aid, c))
        if not matches: return "", ""
        longest=max(x[0] for x in matches)
        ids=sorted({aid for n,aid,c in matches if n==longest})
        if len(ids) != 1: return "", ""
        c=next(c for n,aid,c in matches if n==longest and aid==ids[0])
        return ids[0], q[len(c):].strip() or "self"


    def _split_quoted_spell_input(self, text: str) -> dict[str, Any] | None:
        raw = str(text or "").strip()
        if not raw or raw[0] not in {"'", '"'}:
            return None
        quote = raw[0]
        escaped = False
        chars: list[str] = []
        for idx, ch in enumerate(raw[1:], start=1):
            if escaped:
                chars.append(ch); escaped = False; continue
            if ch == "\\":
                escaped = True; continue
            if ch == quote:
                return {"status": "OK", "spell_text": "".join(chars).strip(), "target_text": raw[idx + 1:].strip(), "quote": quote}
            chars.append(ch)
        return {"status": "UNTERMINATED_QUOTE", "spell_text": "".join(chars).strip(), "target_text": "", "quote": quote}

    def tokenize_ability_input(self, text: str) -> list[str]:
        return [self._normalize_query(t) for t in str(text or "").split() if self._normalize_query(t)]

    def _spell_phrases(self, ab: AbilityDefinition) -> set[str]:
        aliases = (ab.plugin_data or {}).get("aliases") or []
        if isinstance(aliases, str): aliases=[aliases]
        return {p for p in ({self._normalize_query(ab.id), self._normalize_query(ab.id.replace("_"," ")), self._normalize_query(ab.name), self._normalize_query(ab.short_name)} | {self._normalize_query(a) for a in aliases}) if p}

    def _match_known_spell_query(self, actor_id: str, spell_text: str, require_known: bool = True) -> dict[str, Any]:
        tokens = self.tokenize_ability_input(spell_text)
        if not tokens:
            return {"status": "UNKNOWN_ABILITY", "ability_id": "", "consumed_tokens": 0, "candidates": []}
        learned = {str(r["id"]) for r in self.service.list_known_abilities(actor_id)}
        candidates: list[tuple[int, int, int, str, str]] = []
        for aid, ab in self.service.registry.abilities.items():
            if str(ab.ability_type) != "spell":
                continue
            if require_known and aid not in learned:
                continue
            for phrase in self._spell_phrases(ab):
                ptoks = phrase.split(); maxn = min(len(tokens), len(ptoks))
                for n in range(maxn, 0, -1):
                    given = tokens[:n]
                    if n == len(ptoks) and given == ptoks:
                        rank = 100
                    elif all(ptoks[i].startswith(given[i]) for i in range(n)):
                        rank = 80 + n
                    elif n == 1 and phrase.startswith(given[0]):
                        rank = 60
                    else:
                        continue
                    candidates.append((rank, n, sum(map(len, given)), aid, phrase)); break
        if not candidates:
            defined = self.resolve_definition(" ".join(tokens))
            return {"status": "NOT_KNOWN" if defined and defined not in learned else "UNKNOWN_ABILITY", "ability_id": defined if defined and defined not in learned else "", "consumed_tokens": 0, "candidates": []}
        best_rank=max(c[0] for c in candidates); best=[c for c in candidates if c[0]==best_rank]
        best_n=max(c[1] for c in best); best=[c for c in best if c[1]==best_n]
        ids=sorted({c[3] for c in best})
        if len(ids) != 1:
            return {"status": "AMBIGUOUS_ABILITY", "ability_id": "", "consumed_tokens": 0, "candidates": ids}
        return {"status": "RESOLVED", "ability_id": ids[0], "consumed_tokens": best_n, "candidates": [ids[0]], "match_type": "token_prefix"}

    def resolve_spell_tokens(self, actor_id: str, text: str, require_known: bool = True) -> dict[str, Any]:
        quoted = self._split_quoted_spell_input(text)
        self.service._pub("cast_parse_started", {"actor_id": actor_id, "raw_input": text})
        if quoted:
            if quoted["status"] != "OK":
                return {"status": "UNTERMINATED_QUOTE", "ability_id": "", "canonical_name": "", "matched_text": quoted.get("spell_text", ""), "consumed_tokens": 0, "target_text": "", "match_type": "quoted", "candidates": []}
            match = self._match_known_spell_query(actor_id, quoted["spell_text"], require_known=require_known)
            aid = str(match.get("ability_id") or "")
            ab = self.service.registry.abilities.get(aid)
            result = {**match, "canonical_name": ab.name if ab else "", "matched_text": quoted["spell_text"], "consumed_tokens": len(self.tokenize_ability_input(quoted["spell_text"])), "target_text": quoted["target_text"], "match_type": "quoted", "ambiguity_candidates": match.get("candidates", [])}
            self.service._pub("cast_target_text_extracted", {"actor_id": actor_id, "parsed_spell_text": quoted["spell_text"], "target_text": quoted["target_text"], "ability_id": aid, "status": result.get("status")})
            return result
        tokens = self.tokenize_ability_input(text)
        if not tokens:
            return {"status": "UNKNOWN_ABILITY", "ability_id": "", "canonical_name": "", "matched_text": "", "consumed_tokens": 0, "target_text": "", "match_type": "empty", "candidates": []}
        match = self._match_known_spell_query(actor_id, " ".join(tokens), require_known=require_known)
        consumed = int(match.get("consumed_tokens") or 0)
        aid = str(match.get("ability_id") or "")
        ab = self.service.registry.abilities.get(aid)
        result = {**match, "canonical_name": ab.name if ab else "", "matched_text": " ".join(tokens[:consumed]), "target_text": " ".join(tokens[consumed:]), "ambiguity_candidates": match.get("candidates", [])}
        self.service._pub("cast_spell_text_resolved", {"actor_id": actor_id, "raw_input": text, "ability_id": aid, "parsed_spell_text": result.get("matched_text"), "consumed_token_count": consumed, "target_text": result.get("target_text"), "status": result.get("status")})
        return result

    def resolve_definition(self, query: str) -> str:
        """Resolve an ability definition independent of whether an actor knows it."""
        q = self._normalize_query(query)
        matches: list[str] = []
        for aid, ab in self.service.registry.abilities.items():
            pdata = ab.plugin_data or {}
            aliases = pdata.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            candidates = {self._normalize_query(aid), self._normalize_query(aid.replace("_", " ")), self._normalize_query(str(ab.name)), self._normalize_query(str(ab.short_name)), self._normalize_query(str(pdata.get("command") or ""))} | {self._normalize_query(str(a)) for a in aliases}
            if q and q in {c for c in candidates if c}:
                matches.append(aid)
        unique = sorted(set(matches))
        return unique[0] if len(unique) == 1 else ""

    def resolve_ability(self, actor_id: str, query: str) -> str:
        q = self._normalize_query(query)
        learned = {str(r["id"]) for r in self.service.list_known_abilities(actor_id)}
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
        for eff in a.ordered_effects or []:
            op=str(eff.get("operation") or "")
            if op not in self.effect_operations.operations: errors.append(f"ability {a.id} unknown operation: {op}")
            if eff.get("duration", {}).get("amount", 0) is not None and num(eff.get("duration", {}).get("amount", 0)) < 0: errors.append(f"ability {a.id} negative duration")
            st=str((eff.get("stacking") or {}).get("policy") or "unique")
            if st not in STACKING_POLICIES: errors.append(f"ability {a.id} invalid stacking: {st}")
            for key,msg in (eff.get("messages") or {}).items():
                for ph in re.findall(r"{([^{}]+)}", str(msg)):
                    if ph not in PLACEHOLDERS: errors.append(f"ability {a.id} invalid message placeholder: {ph}")
        if not (a.damage_components or a.healing_components or a.effects_applied or a.effects_removed or a.state_changes or a.ordered_effects): warnings.append(f"ability {a.id} has no components")
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
    def __init__(self, db_path: Path|str|None=None, package: Any|None=None, event_bus: Any|None=None, world_id: str="", actor_registry: ActorRegistry | None=None, combat_runtime: Any|None=None, combat_stat_service: Any|None=None, resource_service: Any|None=None, effect_service: Any|None=None, lifecycle_service: Any|None=None, item_service: Any|None=None, world_registry: Any|None=None, room_service: Any|None=None, formula_engine: Any|None=None, state_store: Any|None=None, allow_isolated_combat_engine: bool=False):
        self.db_path = Path(db_path) if db_path else None; self.registry=AbilityRegistry(package); self.event_bus=event_bus; self.world_id=world_id or getattr(package,"id","")
        self.combat_runtime = combat_runtime; self.combat_stat_service = combat_stat_service; self.resource_service = resource_service; self.effect_service = effect_service; self.lifecycle_service = lifecycle_service; self.item_service = item_service; self.world_registry = world_registry; self.room_service = room_service; self.formula_engine = formula_engine; self.state_store = state_store
        self.allow_isolated_combat_engine = bool(allow_isolated_combat_engine or combat_runtime is None)
        self.combat = CombatEngine(content=CombatContentRegistry(package)) if self.allow_isolated_combat_engine else None
        self.actor_registry = actor_registry or ActorRegistry(); self.actors = self.actor_registry.actors; self.availability = AbilityAvailabilityService(self); self.effect_operations = AbilityEffectOperationRegistry()
        self.target_resolver = AbilityTargetResolver(self); self.spell_costs = SpellResourceCostService(self); self._published_execution_events = []
        self.runtime_service = AbilityRuntimeService(self)
        self.aura_runtime = AuraRuntimeService(self); self.stance_runtime = StanceRuntimeService(self); self.transformation_runtime = TransformationRuntimeService(self); self.summon_runtime = SummonRuntimeService(self); self.summon_profile_service = SummonProfileService(self); self.passive_trigger_service = PassiveTriggerService(self); self.item_ability_runtime = ItemAbilityRuntimeService(self); self.room_effect_runtime = RoomEffectRuntimeService(self)
        if combat_runtime is not None and self.combat is not None:
            raise RuntimeError("AbilityExecutionService cannot own a duplicate CombatEngine when CombatRuntimeService is injected")
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
    def ability_runtime(self) -> AbilityRuntimeService:
        """Return the sole typed entry point for active abilities."""
        return self.runtime_service
    def assert_runtime_combat_authority(self) -> None:
        rt = getattr(self, "runtime", None)
        crt = self.combat_runtime or (getattr(rt, "combat_runtime", None) if rt else None)
        if crt is not None and self.combat is not None:
            raise RuntimeError("Duplicate normal-runtime combat authority detected")

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
    def _actor_lookup_ids(self, actor_id: str) -> list[str]:
        aid = str(actor_id or "")
        ids = [aid]
        if aid.startswith("character:"):
            ids.append(aid.split(":", 1)[1])
        elif aid:
            ids.append("character:" + aid)
        return [x for x in dict.fromkeys(ids) if x]

    def list_known_abilities(self, actor_id: str, ability_type: str | None = None) -> list[dict[str, Any]]:
        """Canonical learned-ability projection shared by display, parsing, and execution.

        Definition existence/enabled checks happen here so callers never display
        orphaned grants and never execute from a different learned source than
        SKILLS/SPELLS used.  Both legacy character ids and live ``character:``
        actor ids are treated as aliases for the same player actor.
        """
        lookup_ids = self._actor_lookup_ids(actor_id)
        grants: list[dict[str, Any]] = []
        progression: list[dict[str, Any]] = []
        if self.db_path:
            for lookup_id in lookup_ids:
                grants.extend(self._grants(lookup_id))
            try:
                with sqlite3.connect(self.db_path) as c:
                    c.row_factory=sqlite3.Row
                    for lookup_id in lookup_ids:
                        progression.extend([dict(r) for r in c.execute("SELECT ability_id,rank,maximum_rank,proficiency,metadata_json FROM actor_ability_progression WHERE actor_id=? AND active=1", (lookup_id,))])
            except Exception:
                progression=[]
        else:
            for lookup_id in lookup_ids:
                grants.extend(self._grants(lookup_id))
        plugin_ids: set[str] = set()
        for lookup_id in lookup_ids:
            plugin_ids |= set(getattr(self.actors.get(lookup_id), "plugin_data", {}).get("ability_ids", []) or [])
        ids={str(g["ability_id"]) for g in grants} | {str(p["ability_id"]) for p in progression} | plugin_ids
        out=[]
        for i in sorted(ids):
            definition = self.registry.abilities.get(i)
            if not definition or not definition.enabled:
                continue
            if ability_type and str(definition.ability_type) != ability_type:
                continue
            row=dict(definition.to_dict(), grants=[g for g in grants if g["ability_id"]==i])
            prog=next((p for p in progression if p["ability_id"]==i), None)
            if prog: row.update(rank=int(prog.get("rank") or 0), maximum_rank=int(prog.get("maximum_rank") or 100), proficiency=max(1, min(100, int(prog.get("proficiency") or 1))), maximum_proficiency=max(1, min(100, int(prog.get("maximum_rank") or 100))), progression_metadata=jload(prog.get("metadata_json"), {}))
            out.append(row)
        return out

    def get_actor_abilities(self, actor_id: str) -> list[dict[str, Any]]:
        return self.list_known_abilities(actor_id)

    def list_known_spells(self, actor_id: str) -> list[dict[str, Any]]:
        return self.list_known_abilities(actor_id, "spell")

    def list_known_skills(self, actor_id: str) -> list[dict[str, Any]]:
        skill_kinds={"skill", "proficiency", "trade_skill", "combat_skill", "technique"}
        return [r for r in self.list_known_abilities(actor_id) if str(r.get("ability_type") or "").lower() in skill_kinds]

    def knows(self, actor_id: str, ability_id: str) -> bool:
        return any(str(r.get("id")) == str(ability_id) for r in self.list_known_abilities(actor_id))

    def find_known(self, actor_id: str, query: str, ability_type: str | None = None) -> dict[str, Any] | None:
        gateway = self.gateway()
        q = gateway._normalize_query(query)
        for row in self.list_known_abilities(actor_id, ability_type):
            ab = self.registry.abilities[str(row["id"])]
            pdata = ab.plugin_data or {}; aliases = pdata.get("aliases") or []
            if isinstance(aliases, str): aliases=[aliases]
            candidates={gateway._normalize_query(row.get("id")), gateway._normalize_query(str(row.get("name") or "")), gateway._normalize_query(ab.short_name), gateway._normalize_query(str(pdata.get("command") or ""))} | {gateway._normalize_query(str(a)) for a in aliases}
            if q and q in {c for c in candidates if c}:
                return row
        return None

    def find_known_spell(self, actor_id: str, query: str) -> dict[str, Any] | None:
        return self.find_known(actor_id, query, "spell")

    def find_known_skill(self, actor_id: str, query: str) -> dict[str, Any] | None:
        row = self.find_known(actor_id, query)
        return row if row and str(row.get("ability_type") or "").lower() != "spell" else None
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
                    if need and str(need.get('resource_id')) == 'mana' and ab.ability_type == 'spell':
                        msg=f"You need {int(num(need.get('amount'),0))} mana to cast {ab.name}, but you only have {int(num(need.get('current'),0))}."
                    else:
                        msg=f"Requires {int(num(need.get('amount'),0))} {need.get('resource_id')}." if need else "Insufficient resources."
                    return self._validation_result(tr, "BLOCKED_RESOURCE", msg, resource_affordability={str(c.get("resource_id")): bool(c.get("affordable", True)) for c in costs})
                if name == "resolve_target" and target is None:
                    mode=str((ab.targeting or {}).get("mode") or "self")
                    if mode in {"single_enemy", "current_target"}: return self._validation_result(tr, "BLOCKED_TARGET", "No current opponent.", target_requirement=mode)
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
        known_rows = self.list_known_abilities(actor_id)
        grants=[g for row in known_rows for g in (row.get("grants") or [])]
        progression_known=any(str(row.get("id")) == ability_id and row.get("progression_metadata") is not None for row in known_rows)
        available=self.knows(actor_id, ability_id) or ab.ability_type in {"natural","monster","administrative"}
        steps.append({"step":"confirm_grant","ok":available,"sources":grants,"progression_known":progression_known,"canonical_service":"list_known_abilities"}); ok &= available
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
        result={"ok":True,"cast_id":cast_id,"trace":tr["trace"],"damage_events":[],"healing_events":[],"effect_events":[],"material_results":material_results,"resource_changes":costs,"cooldown_started": bool(ab.cooldowns), "message": self._ability_success_message(ability_id)}; self._pub("ability_started", {"actor_id":actor_id,"ability_id":ability_id,"cast_id":cast_id})
        for t in tr["targets"]:
            target_actor=self.actors.get(t.get("actor_id"))
            if not target_actor: continue
            for comp in ab.damage_components: result["damage_events"].append(self._apply_damage_component(actor,target_actor,ab,comp,cast_id))
            for comp in ab.healing_components:
                amount = int(num(comp.get("base_amount", comp.get("amount", 0))))
                result["healing_events"].append(asdict(self.apply_healing(actor.actor_id, target_actor.actor_id, amount, ability_id, comp.get("id"), {"cast_id": cast_id, "formula_id": comp.get("formula_id")})))
            for eff in ab.effects_applied: result["effect_events"].append(self._apply_effect(actor,target_actor,ab,eff,cast_id))
        for eff in ab.ordered_effects or []:
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

    def execute_effect_handler(self, actor: Actor, ab: AbilityDefinition, targets: list[dict[str, Any]], cast_id: str) -> dict[str, Any]:
        """Effect-only adapter used by :class:`AbilityRuntimeService`.

        It intentionally contains no authorization, resource payment, generic
        cooldown, or proficiency mutation.  Direct legacy callers retain
        ``execute_instant_ability`` for compatibility, but production command
        requests enter the runtime orchestrator above.
        """
        result={"ok":True,"cast_id":cast_id,"damage_events":[],"healing_events":[],"effect_events":[],"message":self._ability_success_message(ab.id)}
        for t in targets:
            target_actor=self.actors.get(t.get("actor_id"))
            if not target_actor: continue
            for comp in ab.damage_components:
                result["damage_events"].append(self._apply_damage_component(actor,target_actor,ab,comp,cast_id))
            for comp in ab.healing_components:
                amount=int(num(comp.get("base_amount", comp.get("amount", 0))))
                result["healing_events"].append(asdict(self.apply_healing(actor.actor_id,target_actor.actor_id,amount,ab.id,comp.get("id"),{"cast_id":cast_id,"formula_id":comp.get("formula_id")})))
            for eff in ab.effects_applied:
                result["effect_events"].append(self._apply_effect(actor,target_actor,ab,eff,cast_id))
        for eff in ab.ordered_effects or []:
            handled=self._apply_canonical_effect(actor,targets,ab,eff,cast_id); result["effect_events"].append(handled)
            if handled.get("message"): result["message"]=str(handled["message"])
            if not handled.get("ok",True): return {**result,"ok":False,"reason_code":handled.get("reason") or handled.get("reason_code") or "effect_blocked","message":handled.get("message") or "You cannot use that ability."}
        for eff in (ab.plugin_data or {}).get("effects",[]) or []:
            handled=self._apply_registered_effect(actor,ab,eff,cast_id); result["effect_events"].append(handled)
            if handled.get("message"): result["message"]=str(handled["message"])
            if not handled.get("ok",True): return {**result,"ok":False,"reason_code":handled.get("reason") or handled.get("reason_code") or "effect_blocked","message":handled.get("message") or "You cannot use that ability."}
        self._pub("ability.effect.completed", {"actor_id":actor.actor_id,"ability_id":ab.id,"cast_id":cast_id})
        return result

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
            elif op == "aura":
                out["results"].append(self.create_aura(actor.actor_id, ab.id, eff, cast_id))
            elif op == "stance":
                out["results"].append(self.activate_stance(actor.actor_id, ab.id, eff, cast_id))
            elif op == "transform":
                out["results"].append(self.start_transformation(actor.actor_id, ab.id, eff, cast_id))
            elif op == "summon":
                out["results"].extend(self.create_summons(actor.actor_id, ab.id, eff, cast_id))
            elif op == "dismiss_summon":
                out["results"].append(self.dismiss_summon(actor.actor_id, str((eff.get("parameters") or {}).get("summon_id") or "all"), "ability"))
            elif op == "create_item":
                out["results"].append(self.create_item(actor.actor_id, ab.id, eff, cast_id))
            elif op == "destroy_item":
                out["results"].append(self.destroy_item(actor.actor_id, str((eff.get("parameters") or {}).get("item_instance_id") or eff.get("target_item_id") or ""), cast_id))
            elif op == "alter_item":
                out["results"].append(self.alter_item(actor.actor_id, eff, cast_id))
            elif op == "create_room_effect":
                out["results"].append(self.create_room_effect(actor.actor_id, ab.id, eff, cast_id))
            elif op == "remove_room_effect":
                out["results"].append(self.remove_room_effect(str((eff.get("parameters") or {}).get("room_effect_instance_id") or ""), "ability"))
        if not out.get("message"):
            out["message"] = str((eff.get("messages") or {}).get("actor_success") or "")
        self._pub("effect_applied" if op not in {"dispel","cleanse"} else f"effect_{op}", {"actor_id":actor.actor_id,"ability_id":ab.id,"operation":op,"cast_id":cast_id})
        return out

    def _persist_runtime_effect(self, actor: Actor, target: Actor, ab: AbilityDefinition, eff: dict[str, Any], cast_id: str) -> dict[str, Any]:
        wt=self.world_time(); dur=eff.get("duration") or {}; amount=int(num(dur.get("amount", eff.get("duration_amount", 0)),0)); domain=str(dur.get("domain") or "world_minutes"); expires=None if domain in {"permanent","while_equipped","while_source_exists"} else wt+amount
        tick=int(num(eff.get("tick_interval") or (eff.get("parameters") or {}).get("tick_interval"),0)); eid="eff_"+uuid.uuid4().hex; tags=list(eff.get("tags") or [])
        modifiers=list((eff.get("parameters") or {}).get("modifiers") or [])
        stack_group=str((eff.get("stacking") or {}).get("exclusive_group") or eff.get("effect_id") or eff.get("operation"))
        policy=str((eff.get("stacking") or {}).get("policy") or "unique")
        rec={"effect_instance_id":eid,"definition_id":str(eff.get("effect_id") or eff.get("operation")),"source_actor_id":actor.actor_id,"target_actor_id":target.actor_id,"source_ability_id":ab.id,"state":"active","tags":tags,"modifiers":modifiers,"stacks":int(num((eff.get("stacking") or {}).get("stacks",1),1)),"operation":eff.get("operation"),"origin_action_id":cast_id,"wear_off_messages":eff.get("messages") or {},"tick_interval":tick,"tick":{"operation":eff.get("operation"),"amount":eff.get("base_value",0),"damage_type":eff.get("damage_type","poison"),"resource":eff.get("resource","health")}}
        existing=None
        if self.db_path and policy in {"refresh_duration","replace","unique","unique_by_ability"}:
            with sqlite3.connect(self.db_path) as c:
                c.row_factory=sqlite3.Row
                existing=c.execute("SELECT effect_instance_id,metadata_json FROM actor_effect_instances WHERE target_actor_id=? AND active=1 AND stack_group=? ORDER BY started_world_time DESC LIMIT 1", (target.actor_id, stack_group)).fetchone()
                if existing:
                    eid=existing["effect_instance_id"]; rec["effect_instance_id"]=eid
                    c.execute("UPDATE actor_effect_instances SET expires_world_time=?,next_tick_world_time=?,updated_at=?,metadata_json=? WHERE effect_instance_id=?", (expires or 0, wt+tick if tick else 0, now(), jdump(rec), eid))
        if not existing:
            target.effect_container.setdefault("affects",{}).setdefault("canonical",[]).append(rec)
            if self.db_path:
                with sqlite3.connect(self.db_path) as c:
                    c.execute("INSERT OR REPLACE INTO actor_effect_instances(effect_instance_id,world_id,effect_template_id,target_actor_type,target_actor_id,source_actor_type,source_actor_id,source_ability_id,category,disposition,visibility,stack_group,stack_count,maximum_stacks,started_world_time,expires_world_time,next_tick_world_time,active,suspended,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid,self.world_id,rec["definition_id"],"actor",target.actor_id,"actor",actor.actor_id,ab.id,",".join(tags),"harmful" if "poison" in tags or "debuff" in tags else "beneficial","public",stack_group,rec["stacks"],int(num((eff.get("stacking") or {}).get("maximum_stacks",1),1)),wt,expires or 0,wt+tick if tick else 0,1,0,now(),now(),jdump(rec)))
        else:
            rec["refreshed"] = True
        rt = getattr(self, "runtime", None)
        if rt and hasattr(rt, "invalidate_character_projections"):
            for key in dict.fromkeys([str(target.actor_id), str(target.actor_id).split(":", 1)[1] if str(target.actor_id).startswith("character:") else str(target.actor_id)]):
                if key: rt.invalidate_character_projections(key, "effects")
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


    # Phase 14B advanced operations.  These methods deliberately keep all
    # state in the canonical ability database/effect tables and ActorRegistry so
    # player, NPC, script, item, and summon invocations share one path.
    def create_aura(self, actor_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        params=eff.get("parameters") or {}; wt=self.world_time(); aid="aura_"+uuid.uuid4().hex; granted=str(params.get("granted_effect_id") or eff.get("effect_id") or "aura_effect")
        dur=int(num((eff.get("duration") or params.get("duration") or {}).get("amount", params.get("duration", 0)),0)); expires=wt+dur if dur else 0
        rec={"aura_instance_id":aid,"definition_id":str(params.get("aura_id") or eff.get("effect_id") or ability_id),"source_actor_id":actor_id,"source_ability_id":ability_id,"granted_effect_id":granted,"scope":params.get("scope","room"),"target_policy":params.get("target_policy","allies"),"remove_on_leave":params.get("remove_on_leave", True),"origin_action_id":origin_action_id}
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO aura_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,self.world_id,rec['definition_id'],actor_id,ability_id,"actor",actor_id,wt,expires,1,origin_action_id,now(),now(),jdump(rec),jdump({"source_version":eff.get("source_version","1")})))
        self._pub("aura_created", {"aura_instance_id":aid,"actor_id":actor_id,"origin_action_id":origin_action_id}); self.update_aura_membership(aid); return {"ok":True,**rec}

    def update_aura_membership(self, aura_instance_id: str) -> list[dict[str, Any]]:
        if not self.db_path: return []
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; row=c.execute("SELECT * FROM aura_instances WHERE aura_instance_id=? AND active=1",(aura_instance_id,)).fetchone()
            if not row: return []
            meta=jload(row['metadata_json'],{}); current={r[0] for r in c.execute("SELECT target_actor_id FROM aura_membership WHERE aura_instance_id=? AND active=1",(aura_instance_id,))}
        source=row['source_actor_id']; src=self.actors.get(source); src_room=getattr(getattr(src,"identity",None),"current_location","") if src else ""
        scope=str(meta.get("scope") or "room"); max_targets=int(num(meta.get("maximum_targets", 99), 99))
        desired=set()
        for aid, actor in self.actors.items():
            if aid == source: continue
            room=getattr(getattr(actor,"identity",None),"current_location","")
            if scope in {"room","same_room"} and src_room and room != src_room: continue
            desired.add(aid)
            if len(desired) >= max_targets: break
        events=[]
        for actor_id in sorted(desired-current):
            actor=self.actors.get(actor_id); src=self.actors.get(source)
            if actor and src:
                pseudo=AbilityDefinition(str(row['source_ability_id'] or 'aura'), name='Aura')
                eff={"effect_id":meta.get('granted_effect_id') or row['definition_id'],"operation":"apply_affect","duration":{"domain":"while_source_exists","amount":0},"tags":["aura"],"parameters":{"aura_instance_id":aura_instance_id}}
                applied=self._persist_runtime_effect(src, actor, pseudo, eff, str(row['origin_action_id'] or aura_instance_id))
                with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO aura_membership VALUES(?,?,?,?,?,?,?,?,?,?,?)",(f"am_{aura_instance_id}_{actor_id}",aura_instance_id,self.world_id,actor_id,applied['effect_instance_id'],1,0,self.world_time(),None,now(),jdump({})))
                self._pub("aura_member_added", {"aura_instance_id":aura_instance_id,"target_actor_id":actor_id,"origin_action_id":row['origin_action_id']}); events.append({"added":actor_id})
        for actor_id in sorted(current-desired):
            self.remove_aura_member(aura_instance_id, actor_id, "left_scope"); events.append({"removed":actor_id})
        return events

    def remove_source_auras(self, source_id: str, reason: str="source_removed") -> list[dict[str, Any]]:
        return self.aura_runtime.remove_source_auras(source_id, reason)

    def remove_aura_member(self, aura_instance_id: str, actor_id: str, reason: str) -> None:
        if not self.db_path: return
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row; rows=c.execute("SELECT granted_effect_instance_id FROM aura_membership WHERE aura_instance_id=? AND target_actor_id=? AND active=1",(aura_instance_id,actor_id)).fetchall()
            for r in rows: c.execute("UPDATE actor_effect_instances SET active=0,removal_reason=?,updated_at=? WHERE effect_instance_id=?",(reason,now(),r[0]))
            c.execute("UPDATE aura_membership SET active=0,left_world_time=?,updated_at=? WHERE aura_instance_id=? AND target_actor_id=?",(self.world_time(),now(),aura_instance_id,actor_id))
        self._pub("aura_member_removed", {"aura_instance_id":aura_instance_id,"target_actor_id":actor_id,"reason":reason})

    def remove_aura(self, aura_instance_id: str, reason: str="removed") -> dict[str, Any]:
        if not self.db_path: return {"ok":False}
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; members=[r[0] for r in c.execute("SELECT target_actor_id FROM aura_membership WHERE aura_instance_id=? AND active=1",(aura_instance_id,))]
        for m in members: self.remove_aura_member(aura_instance_id,m,reason)
        with sqlite3.connect(self.db_path) as c: c.execute("UPDATE aura_instances SET active=0,updated_at=? WHERE aura_instance_id=?",(now(),aura_instance_id))
        self._pub("aura_removed", {"aura_instance_id":aura_instance_id,"reason":reason}); return {"ok":True,"removed_members":members}

    def activate_stance(self, actor_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        params=eff.get('parameters') or {}; group=str(params.get('exclusive_group') or 'stance')
        self.remove_effects(actor_id, {"tags":[f"stance:{group}"]}, "stance_replaced")
        actor=self.actors[actor_id]; ab=self.registry.abilities.get(ability_id, AbilityDefinition(ability_id)); eff=dict(eff); eff['operation']='apply_affect'; eff.setdefault('tags',[]); eff['tags']=list(set(eff['tags']+["stance",f"stance:{group}"])); rec=self._persist_runtime_effect(actor,actor,ab,eff,origin_action_id)
        self._pub("stance_activated", {"actor_id":actor_id,"ability_id":ability_id,"effect_instance_id":rec['effect_instance_id'],"exclusive_group":group}); return {"ok":True,"stance_effect_instance_id":rec['effect_instance_id'],"exclusive_group":group}

    def start_transformation(self, actor_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        actor=self.actors[actor_id]; params=eff.get('parameters') or {}; meta={"original_body_profile":actor.combat_profile.get('body_profile'),"original_natural_weapons":actor.combat_profile.get('natural_weapons'),"equipment_policy":params.get('equipment_policy','keep_equipped')}
        actor.combat_profile['body_profile']=params.get('body_profile_id','transformed'); actor.combat_profile['natural_weapons']=params.get('natural_weapon_profiles') or params.get('natural_weapons') or []
        rec=self._persist_runtime_effect(actor,actor,self.registry.abilities.get(ability_id,AbilityDefinition(ability_id)), {**eff,"operation":"apply_affect","tags":["transformation"],"parameters":{"modifiers":params.get('stat_modifiers',[]),"transformation":meta}}, origin_action_id)
        self._pub("transformation_started", {"actor_id":actor_id,"ability_id":ability_id,"effect_instance_id":rec['effect_instance_id']}); return {"ok":True,"effect_instance_id":rec['effect_instance_id'],"body_profile_id":actor.combat_profile.get('body_profile')}

    def create_summons(self, owner_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> list[dict[str, Any]]:
        params=eff.get('parameters') or {}; count=max(1,int(num(params.get('count',1),1))); out=[]; owner=self.actors[owner_id]
        for i in range(count):
            sid="summon_"+uuid.uuid4().hex; name=str(params.get('name') or params.get('summon_template_id') or 'Summon'); actor=Actor.create(sid,name,'summon'); actor.plugin_data.update({"owner_actor_id":owner_id,"source_ability_id":ability_id,"relationship":params.get('owner_relationship','follow'),"npc_ability_ids":list(params.get('ability_grants') or [])}); actor.combat_profile['natural_weapons']=params.get('natural_weapon_profiles') or [] ; self.register_actor(actor)
            actor.identity.current_location = getattr(getattr(owner,"identity",None),"current_location","")
            actor.plugin_data["follow_policy"] = params.get("follow_policy", "same_room")
            expires=self.world_time()+int(num(params.get('duration', eff.get('duration',{}).get('amount',10) if isinstance(eff.get('duration'),dict) else 10),10))
            if self.db_path:
                with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO summon_relationships VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,self.world_id,sid,str(params.get('summon_template_id') or ''),owner_id,ability_id,origin_action_id,self.world_time(),expires,'active',params.get('owner_relationship','follow'),params.get('control_policy','owner'),params.get('follow_policy','same_room'),params.get('combat_policy','assist'),now(),now(),jdump(actor.plugin_data)))
            self._pub("summon_created", {"summon_instance_id":sid,"owner_actor_id":owner_id,"ability_id":ability_id,"origin_action_id":origin_action_id}); out.append({"ok":True,"summon_instance_id":sid,"owner_actor_id":owner_id,"expires_world_time":expires})
        return out

    def dismiss_summon(self, owner_id: str, summon_id: str="all", reason: str="dismissed") -> dict[str, Any]:
        ids=[summon_id] if summon_id and summon_id!='all' else [a.actor_id for a in self.actors.values() if (a.plugin_data or {}).get('owner_actor_id')==owner_id]
        for sid in ids:
            self.unregister_actor(sid)
            if self.db_path:
                with sqlite3.connect(self.db_path) as c: c.execute("UPDATE summon_relationships SET state=?,updated_at=? WHERE owner_actor_id=? AND actor_id=?",(reason,now(),owner_id,sid))
            self._pub("summon_dismissed", {"summon_instance_id":sid,"owner_actor_id":owner_id,"reason":reason})
        return {"ok":True,"dismissed":ids}

    def process_summon_expirations(self, world_time: int|None=None) -> list[dict[str, Any]]:
        if not self.db_path: return []
        wt=self.world_time() if world_time is None else int(world_time); out=[]
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; rows=c.execute("SELECT * FROM summon_relationships WHERE state='active' AND expires_world_time>0 AND expires_world_time<=?",(wt,)).fetchall()
        for r in rows:
            self.dismiss_summon(r['owner_actor_id'], r['actor_id'], 'expired'); self._pub('summon_expired', {'summon_instance_id':r['actor_id'],'owner_actor_id':r['owner_actor_id']}); out.append(dict(r))
        return out

    def create_item(self, actor_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        params=eff.get('parameters') or {}; iid="item_"+uuid.uuid4().hex; template=str(params.get('template_id') or params.get('template') or 'temporary_item'); qty=max(1,int(num(params.get('quantity',1),1)))
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: self._ensure_item_instance_material_columns(c); c.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,self.world_id,template,params.get('owner_type','actor'),actor_id,params.get('room_id',''),'',qty,'normal',100,now(),now(),jdump({}),jdump({'source_ability_id':ability_id,'origin_action_id':origin_action_id,'temporary':bool(params.get('duration'))})))
        self._pub('item_created', {'item_instance_id':iid,'actor_id':actor_id,'template_id':template,'origin_action_id':origin_action_id}); return {'ok':True,'item_instance_id':iid,'template_id':template,'quantity':qty}

    def destroy_item(self, actor_id: str, item_instance_id: str, origin_action_id: str) -> dict[str, Any]:
        if not self.db_path or not item_instance_id: return {'ok':False,'reason':'missing_item'}
        with sqlite3.connect(self.db_path) as c: self._ensure_item_instance_material_columns(c); cur=c.execute("UPDATE item_instances SET destroyed_at=COALESCE(destroyed_at,?),destroy_reason=COALESCE(destroy_reason,?) WHERE instance_id=? AND owner_id=?",(now(),'ability_destroy',item_instance_id,actor_id))
        self._pub('item_destroyed', {'item_instance_id':item_instance_id,'actor_id':actor_id,'origin_action_id':origin_action_id}); return {'ok':cur.rowcount>=0,'item_instance_id':item_instance_id}

    def alter_item(self, actor_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        params=eff.get('parameters') or {}; iid=str(params.get('item_instance_id') or ''); mutation=str(params.get('mutation') or 'repair_durability'); amount=int(num(params.get('amount',0),0))
        if self.db_path and iid and mutation in {'repair_durability','damage_durability','change_charges','identify','add_temporary_enchantment','remove_enchantment','apply_temporary_item_effect'}:
            with sqlite3.connect(self.db_path) as c: self._ensure_item_instance_material_columns(c); c.execute("UPDATE item_instances SET durability=CASE WHEN ?='repair_durability' THEN MIN(100,durability+?) WHEN ?='damage_durability' THEN MAX(0,durability-?) ELSE durability END, updated_at=? WHERE instance_id=? AND owner_id=?",(mutation,amount,mutation,amount,now(),iid,actor_id))
        self._pub('item_altered', {'item_instance_id':iid,'actor_id':actor_id,'mutation':mutation,'origin_action_id':origin_action_id}); return {'ok':bool(iid),'item_instance_id':iid,'mutation':mutation}

    def create_room_effect(self, actor_id: str, ability_id: str, eff: dict[str, Any], origin_action_id: str) -> dict[str, Any]:
        params=eff.get('parameters') or {}; rid=str(params.get('room_id') or getattr(self.actors.get(actor_id).identity,'current_location','') or 'room'); rei='roomfx_'+uuid.uuid4().hex; wt=self.world_time(); dur=int(num(params.get('duration', eff.get('duration',{}).get('amount',10) if isinstance(eff.get('duration'),dict) else 10),10)); tick=int(num(params.get('tick_interval', eff.get('tick_interval',0)),0))
        rec={'room_effect_instance_id':rei,'definition_id':str(params.get('room_effect_id') or eff.get('effect_id') or ability_id),'room_id':rid,'source_actor_id':actor_id,'source_ability_id':ability_id,'origin_action_id':origin_action_id}
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO room_effect_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(rei,self.world_id,rec['definition_id'],actor_id,ability_id,rid,params.get('area_id',''),wt,wt+dur if dur else 0,wt+tick if tick else 0,'active',origin_action_id,now(),now(),jdump({**params,'tick_operations':params.get('tick_operations',[])}),jdump({'source_version':eff.get('source_version','1')})))
        self._pub('room_effect_created', {**rec}); self.reconcile_room_effect_memberships(rid); return {'ok':True,**rec}

    def reconcile_room_effect_memberships(self, room_id: str, actor_id: str | None=None) -> list[dict[str, Any]]:
        if not self.db_path: return []
        out=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            effects=c.execute("SELECT * FROM room_effect_instances WHERE state='active' AND room_id=?", (room_id,)).fetchall()
        actors=[actor_id] if actor_id else [aid for aid,a in self.actors.items() if getattr(a.identity,"current_location","")==room_id]
        for r in effects:
            meta=jload(r["metadata_json"], {})
            for aid in actors:
                actor=self.actors.get(aid)
                if not actor: continue
                mid=f"rem_{r['room_effect_instance_id']}_{aid}"
                with sqlite3.connect(self.db_path) as c:
                    exists=c.execute("SELECT granted_effect_instance_ids_json FROM room_effect_membership WHERE membership_id=? AND state='active'", (mid,)).fetchone()
                if exists: continue
                granted=[]
                ops=list(meta.get("resident_operations") or []) + list(meta.get("entry_operations") or [])
                for op in ops or [{"effect_id": r["definition_id"], "operation":"apply_affect", "tags":["room_effect"], "duration":{"domain":"while_source_exists","amount":0}}]:
                    src=self.actors.get(r["source_actor_id"]) or actor
                    rec=self._persist_runtime_effect(src, actor, self.registry.abilities.get(r["source_ability_id"], AbilityDefinition(r["source_ability_id"] or "room_effect")), {**op, "operation":"apply_affect", "tags":list(set((op.get("tags") or [])+["room_effect"]))}, str(r["origin_action_id"] or r["room_effect_instance_id"]))
                    granted.append(rec["effect_instance_id"])
                with sqlite3.connect(self.db_path) as c:
                    c.execute("INSERT OR REPLACE INTO room_effect_membership VALUES(?,?,?,?,?,?,?,?,?)", (mid,r["room_effect_instance_id"],self.world_id,aid,jdump(granted),self.world_time(),None,"active",now()))
                self._pub("room_effect_member_entered", {"room_effect_instance_id":r["room_effect_instance_id"],"actor_id":aid}); out.append({"room_effect_instance_id":r["room_effect_instance_id"],"actor_id":aid,"entered":True})
        return out

    def remove_room_effect_memberships(self, room_id: str, actor_id: str, reason: str="left_room") -> list[dict[str, Any]]:
        if not self.db_path: return []
        out=[]
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            rows=c.execute("SELECT m.* FROM room_effect_membership m JOIN room_effect_instances r ON r.room_effect_instance_id=m.room_effect_instance_id WHERE r.room_id=? AND m.actor_id=? AND m.state='active'", (room_id,actor_id)).fetchall()
            for r in rows:
                for eid in jload(r["granted_effect_instance_ids_json"], []):
                    c.execute("UPDATE actor_effect_instances SET active=0,removal_reason=?,updated_at=? WHERE effect_instance_id=?", (reason,now(),eid))
                c.execute("UPDATE room_effect_membership SET state=?,left_world_time=?,updated_at=? WHERE membership_id=?", (reason,self.world_time(),now(),r["membership_id"]))
                out.append({"room_effect_instance_id":r["room_effect_instance_id"],"actor_id":actor_id,"removed":True})
        for row in out: self._pub("room_effect_member_exited", row | {"reason": reason})
        return out

    def process_room_effect_ticks(self, world_time: int|None=None) -> list[dict[str, Any]]:
        if not self.db_path: return []
        wt=self.world_time() if world_time is None else int(world_time); out=[]
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; rows=c.execute("SELECT * FROM room_effect_instances WHERE state='active' AND next_tick_at>0 AND next_tick_at<=?",(wt,)).fetchall()
        for r in rows:
            claim=f"roomfx_tick_{r['room_effect_instance_id']}_{r['next_tick_at']}"
            try:
                with sqlite3.connect(self.db_path) as c: c.execute("INSERT INTO room_effect_tick_claims VALUES(?,?,?,?,?,?)",(claim,self.world_id,r['room_effect_instance_id'],r['next_tick_at'],now(),jdump({}))); c.execute("UPDATE room_effect_instances SET next_tick_at=? WHERE room_effect_instance_id=?",(int(r['next_tick_at'])+1,r['room_effect_instance_id']))
            except sqlite3.IntegrityError: continue
            self._pub('room_effect_tick_completed', {'room_effect_instance_id':r['room_effect_instance_id'],'claim_id':claim}); out.append({'room_effect_instance_id':r['room_effect_instance_id'],'claim_id':claim})
        return out

    def remove_room_effect(self, room_effect_instance_id: str, reason: str='removed') -> dict[str, Any]:
        if self.db_path and room_effect_instance_id:
            with sqlite3.connect(self.db_path) as c:
                c.row_factory=sqlite3.Row
                rows=c.execute("SELECT * FROM room_effect_membership WHERE room_effect_instance_id=? AND state='active'", (room_effect_instance_id,)).fetchall()
                for r in rows:
                    for eid in jload(r["granted_effect_instance_ids_json"], []):
                        c.execute("UPDATE actor_effect_instances SET active=0,removal_reason=?,updated_at=? WHERE effect_instance_id=?", (reason,now(),eid))
                    c.execute("UPDATE room_effect_membership SET state=?,left_world_time=?,updated_at=? WHERE membership_id=?", (reason,self.world_time(),now(),r["membership_id"]))
        if self.db_path and room_effect_instance_id:
            with sqlite3.connect(self.db_path) as c: c.execute("UPDATE room_effect_instances SET state=?,updated_at=? WHERE room_effect_instance_id=?",(reason,now(),room_effect_instance_id))
        self._pub('room_effect_removed', {'room_effect_instance_id':room_effect_instance_id,'reason':reason}); return {'ok':bool(room_effect_instance_id)}

    def save_summon_profile(self, owner_actor_id: str, summon_actor_id: str, profile_name: str='companion') -> dict[str, Any]:
        actor=self.actors.get(summon_actor_id); pid=f"profile_{owner_actor_id}_{profile_name}"; ts=now(); data={'identity': {'name': getattr(getattr(actor,'identity',None),'name',profile_name) if actor else profile_name}, 'natural_weapons': (actor.combat_profile.get('natural_weapons') if actor else []), 'ability_grants': (actor.plugin_data.get('npc_ability_ids',[]) if actor else [])}
        if self.db_path:
            with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO summon_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,self.world_id,owner_actor_id,profile_name,(actor.plugin_data or {}).get('source_ability_id','') if actor else '',summon_actor_id,data['identity'].get('name',''),1,jdump({}),jdump({}),jdump({}),jdump(data['natural_weapons']),jdump(data['ability_grants']),'', '1', str(abs(hash(jdump(data)))), ts,ts,jdump(data)))
        self._pub('summon_profile_saved', {'profile_id':pid,'owner_actor_id':owner_actor_id}); return {'ok':True,'profile_id':pid}

    def restore_summon_profile(self, owner_actor_id: str, profile_id: str) -> dict[str, Any]:
        if not self.db_path: return {'ok':False}
        with sqlite3.connect(self.db_path) as c: c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM summon_profiles WHERE profile_id=? AND owner_actor_id=?",(profile_id,owner_actor_id)).fetchone()
        if not r: return {'ok':False,'reason':'not_found'}
        meta=jload(r['metadata_json'],{}); eff={'parameters': {'name': r['identity'], 'summon_template_id': r['entity_template_id'], 'natural_weapon_profiles': jload(r['natural_weapons_json'],[]), 'ability_grants': jload(r['ability_grants_json'],[]), 'duration': 0}}
        out=self.create_summons(owner_actor_id, str(r['summon_definition_id'] or 'profile_restore'), eff, 'profile_restore')[0]
        self._pub('summon_profile_restored', {'profile_id':profile_id,'owner_actor_id':owner_actor_id,'summon_instance_id':out['summon_instance_id']}); return {'ok':True,**out}

    def repair_summon_profile(self, profile: dict[str, Any], source_template: dict[str, Any]|None=None) -> dict[str, Any]:
        repaired=dict(profile or {}); tmpl=source_template or {}; repaired.setdefault('level', int(tmpl.get('level', 1) or 1)); repaired.setdefault('body_profile_id', tmpl.get('body_profile_id','humanoid')); repaired.setdefault('combat_role', tmpl.get('combat_role','guardian')); repaired['repair_strategy']='template' if source_template else 'deterministic_fallback'; return repaired

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

    def attempt_proficiency_improvement(self, actor_id: str, ability_id: str, context: dict[str, Any] | None = None, random_provider: AbilityRandomProvider | None = None) -> dict[str, Any]:
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
            attempted = chance > 0
            threshold = max(0, min(100, int(chance * 100 if chance <= 1 else chance)))
            roll = random_provider.roll_percent() if attempted and random_provider else (1 if attempted and chance >= 1 else None)
            improved = attempted and bool(roll is not None and roll <= threshold)
            if improved:
                current = min(maximum, current + 1)
                state["last_improvement_at"] = now_ts
                c.execute("UPDATE actor_ability_progression SET proficiency=?,metadata_json=? WHERE actor_id=? AND ability_id=?", (current, jdump(meta), actor_id, ability_id))
                self._pub("ability_proficiency_increased", {"actor_id": actor_id, "ability_id": ability_id, "proficiency": current, "difficulty": difficulty})
            else:
                c.execute("UPDATE actor_ability_progression SET metadata_json=? WHERE actor_id=? AND ability_id=?", (jdump(meta), actor_id, ability_id))
            return {"attempted": attempted, "improved": improved, "proficiency": current, "chance": chance, "roll": roll, "threshold": threshold, "amount": 1 if improved else 0, "difficulty": difficulty, "cooldown_seconds": cooldown}
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
    def _resolve_target_canonical(self, actor: Actor, ab: AbilityDefinition, target: Any=None) -> dict[str, Any]:
        mode=str((ab.targeting or {}).get("mode") or "self"); allow_dead=bool((ab.targeting or {}).get("allow_dead",False)); allow_self=bool((ab.targeting or {}).get("allow_self", True)); targets=[]; invalid=""
        q=str(target or "").lower().strip()
        if isinstance(target,list) and target and isinstance(target[0],dict): targets=target
        elif mode in {"none"}: targets=[]
        elif mode == "room": return {"ok": True, "mode": mode, "targets": [], "target_room": getattr(actor.identity, "current_location", ""), "target_type": "room", "runtime_instance_ids": []}
        elif mode == "self" or (q in {"self", "me"} and allow_self): targets=[{"actor_id":actor.actor_id,"name":actor.identity.name,"target_type":"self"}]
        elif isinstance(target, Actor): targets=[{"actor_id":target.actor_id,"name":target.identity.name,"target_type":"actor"}]
        elif isinstance(target,str):
            visible=[x for x in sorted(self.actors.values(), key=lambda z:z.actor_id) if getattr(x.identity, "current_location", "") == getattr(actor.identity, "current_location", "")]
            exact=[x for x in visible if x.actor_id.lower()==q or x.identity.name.lower()==q or q in x.identity.name.lower().split()]
            prefix=[x for x in visible if x not in exact and q and (x.actor_id.lower().startswith(q) or x.identity.name.lower().startswith(q) or any(part.startswith(q) for part in x.identity.name.lower().split()))]
            matches=exact or prefix
            max_targets=int((ab.targeting or {}).get("maximum_targets") or 1)
            if len(matches) > max_targets:
                return {"ok":False,"mode":mode,"targets":[],"target_type":"actor","invalid_reason":"ambiguous_target","candidates":[{"actor_id":x.actor_id,"name":x.identity.name} for x in matches],"runtime_instance_ids":[]}
            targets=[{"actor_id":x.actor_id,"name":x.identity.name,"target_type":"actor"} for x in matches[:max_targets]]
            if targets: self._pub("target_resolved", {"actor_id": actor.actor_id, "query": q, "target_id": targets[0].get("actor_id")})
        if mode in {"single_enemy", "current_target"} and not targets and not q:
            current=str((getattr(actor, "plugin_data", {}) or {}).get("current_combat_target") or "")
            crt = self.combat_runtime or (getattr(getattr(self, "runtime", None), "combat_runtime", None) if getattr(self, "runtime", None) else None)
            if not current and crt:
                try:
                    eid = crt.find_actor_encounter(actor.actor_id)
                    enc = getattr(crt, "resident_encounters", {}).get(eid) if eid else None
                    part = enc.participants.get(actor.actor_id) if enc else None
                    current = str(getattr(part, "target_actor_id", "") or "")
                except Exception:
                    current = ""
            if current and current in self.actors: targets=[{"actor_id":current,"name":self.actors[current].identity.name,"target_type":"actor"}]
        if mode.startswith("room_") and not target:
            maxn=int((ab.targeting or {}).get("maximum_targets") or 99); targets=[{"actor_id":x.actor_id,"name":x.identity.name,"target_type":"actor"} for x in sorted(self.actors.values(), key=lambda z:z.actor_id)[:maxn]]
        ok=bool(targets) or mode in {"none","room"}
        for t in targets:
            ta=self.actors.get(t.get("actor_id"));
            if ta and not allow_dead and str(ta.lifecycle_state).lower() in {"dead","corpse"}: ok=False; invalid="dead"; t["invalid"]="dead"
            if ta and ta.actor_id == actor.actor_id and not allow_self: ok=False; invalid="self_not_allowed"; t["invalid"]="self_not_allowed"
        if mode in {"single_enemy","current_target"} and targets and targets[0].get("actor_id") == actor.actor_id: ok=False; invalid="self_not_allowed"
        return {"ok":ok,"mode":mode,"targets":targets,"target_type":targets[0].get("target_type") if targets else mode,"invalid_reason":invalid,"runtime_instance_ids":[t.get("actor_id") for t in targets]}

    def resolve_target(self, actor: Actor, ab: AbilityDefinition, target: Any=None) -> dict[str, Any]:
        return self.target_resolver.resolve(actor, ab, target) if hasattr(self, "target_resolver") else self._resolve_target_canonical(actor, ab, target)
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
        reqs=list(ab.materials or (ab.plugin_data or {}).get("materials") or [])
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
        reqs=[r for r in list(ab.materials or (ab.plugin_data or {}).get("materials") or []) if str(r.get("consume_timing","start")) == timing]
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
            res=str(c.get("resource_id"))
            if ab.ability_type == "spell" and res == "mana":
                calc = self.spell_costs.calculate(actor, ab)
                amt=calc.final_cost; cur=calc.current_mana; needed=calc.sufficient
                rec={"resource_id":res,"amount":amt,"current":cur,"ok":needed,"affordable":needed,"spell_mana_cost":asdict(calc)}
                out.append(rec); ok &= needed; self._pub("spell_cost_calculated", asdict(calc));
                if not needed: self._pub("spell_resource_validation_failed", asdict(calc))
                continue
            amt=self._cost_amount(actor,c); cur=num(getattr(actor.resources,res,0)); needed=cur>=amt and amt>=0
            out.append({"resource_id":res,"amount":amt,"current":cur,"ok":needed,"affordable":needed}); ok &= needed
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
            res=str(c.get("resource_id")); amt=self.spell_costs.calculate(actor, ab).final_cost if ab.ability_type == "spell" and res == "mana" else self._cost_amount(actor,c); rr=RuntimeResourceService(getattr(self,"runtime",None), db_path=self.db_path, event_bus=self.event_bus, world_id=self.world_id).pay_cost(actor,res,amt,metadata={"source":"ability_cost","ability_id":ab.id}); trace={"resource":rr.resource,"operation":rr.operation,"before":rr.before,"amount":rr.applied_amount,"after":rr.after,"reason_code":rr.reason_code}; paid.append(trace); self._pub("ability_cost_paid", dict(trace, ability_id=ab.id, actor_id=actor.actor_id)); self._pub("spell_resource_spent" if ab.ability_type == "spell" and res == "mana" else "mana_changed", dict(trace, ability_id=ab.id, actor_id=actor.actor_id, payment_reason=consume_on))
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
        crt = self.combat_runtime or (getattr(rt, "combat_runtime", None) if rt else None)
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
        if self.combat is None:
            raise RuntimeError("Ability damage requires CombatRuntimeService in normal runtime")
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
    def _grant_key(self, grant: dict[str, Any]) -> tuple[str, str, str, str]:
        return (str(grant.get("ability_id") or ""), str(grant.get("source_type") or ""), str(grant.get("source_id") or ""), str(grant.get("source_instance_id") or ""))

    def _legacy_npc_ability_grants(self, actor_id: str) -> list[dict[str, Any]]:
        actor = self.actors.get(actor_id)
        pdata = getattr(actor, "plugin_data", {}) or {} if actor else {}
        grants=[]
        for aid in list(pdata.get("npc_ability_ids", []) or []) + list(pdata.get("ability_ids", []) or []):
            grants.append(AbilityGrantProjection(ability_id=str(aid), source_type="legacy_actor_plugin_adapter", source_id=actor_id, source_instance_id=actor_id, proficiency=int(num(pdata.get("proficiency", 50), 50)), temporary=False, active=True, suppressed=False, visible=True, source_version=str(pdata.get("source_version", "legacy")), grant_id=f"legacy_{actor_id}_{aid}").to_dict())
        return grants

    def project_ability_grants(self, actor_id: str, include_suppressed: bool=True) -> list[dict[str, Any]]:
        projected: list[dict[str, Any]] = []
        if self.db_path:
            with sqlite3.connect(self.db_path) as c:
                c.row_factory=sqlite3.Row
                rows=c.execute("SELECT grant_id,ability_id,source_type,source_id,source_instance_id,rank,proficiency,enabled,temporary,starts_at,expires_at,metadata_json FROM actor_ability_grants WHERE actor_id=? ORDER BY ability_id,source_type,grant_id",(actor_id,)).fetchall()
                for r in rows:
                    meta=jload(r["metadata_json"], {})
                    projected.append(AbilityGrantProjection(ability_id=r["ability_id"], source_type=r["source_type"], source_id=r["source_id"] or "", source_instance_id=r["source_instance_id"] or "", proficiency=max(1, min(100, int(num(r["proficiency"], 1)))), temporary=bool(r["temporary"]), active=bool(r["enabled"]), suppressed=bool(meta.get("suppressed", False)), visible=bool(meta.get("visible", True)), source_version=str(meta.get("source_version", "1")), grant_id=r["grant_id"]).to_dict())
                effect_rows=c.execute("SELECT effect_instance_id,effect_template_id,metadata_json,active,suspended,source_ability_id FROM actor_effect_instances WHERE target_actor_id=?", (actor_id,)).fetchall()
                for er in effect_rows:
                    meta=jload(er["metadata_json"], {})
                    params=meta.get("parameters") or {}
                    for aid in list(meta.get("ability_grants") or params.get("ability_grants") or []):
                        projected.append(AbilityGrantProjection(ability_id=str(aid), source_type="active_effect", source_id=str(er["effect_template_id"] or er["source_ability_id"] or ""), source_instance_id=str(er["effect_instance_id"]), proficiency=int(num(meta.get("proficiency", 1), 1)), temporary=True, active=bool(er["active"]), suppressed=bool(er["suspended"]), visible=True, source_version=str(meta.get("source_version", "1")), grant_id=f"effect_{er['effect_instance_id']}_{aid}").to_dict())
        projected.extend(self._legacy_npc_ability_grants(actor_id))
        dedup: dict[tuple[str,str,str,str], dict[str,Any]] = {}
        for g in projected:
            if not include_suppressed and (g.get("suppressed") or not g.get("active", True)):
                continue
            dedup.setdefault(self._grant_key(g), g)
        return sorted(dedup.values(), key=lambda g:(g.get("ability_id",""), g.get("source_type",""), g.get("source_instance_id","")))

    def _grants(self, actor_id: str) -> list[dict[str,Any]]:
        return [g for g in self.project_ability_grants(actor_id, include_suppressed=False) if g.get("active", True) and not g.get("suppressed", False)]
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
        self._published_execution_events.append({"event_name": name, "payload": dict(payload or {})}) if hasattr(self, "_published_execution_events") else None
        aliases={"ability_cooldown_started":"cooldown_started","ability_damage_applied":"damage_applied","ability_healing_applied":"healing_applied","ability_effect_applied":"effect_applied"}
        if name == "ability_completed": self._pub("cooldown_finished", {"ability_id": payload.get("ability_id", ""), "actor_id": payload.get("actor_id", ""), "synthetic": True})
        if aliases.get(name): self._pub(aliases[name], payload)
        if self.event_bus: self.event_bus.publish(name,payload,source_system="abilities",world_id=self.world_id)

def init_ability_schema(db_path: Path|str) -> None:
    with sqlite3.connect(db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS ability_execution_ledger (world_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_id TEXT NOT NULL, actor_id TEXT NOT NULL, actor_life_generation TEXT, ability_id TEXT NOT NULL, invocation_type TEXT, status TEXT NOT NULL, stage_reached TEXT, result_summary_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, committed_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, PRIMARY KEY(world_id,idempotency_key,actor_id,actor_life_generation))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ability_execution_ledger_expiry ON ability_execution_ledger(expires_at)")
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

        c.execute("CREATE TABLE IF NOT EXISTS aura_instances (aura_instance_id TEXT PRIMARY KEY, world_id TEXT, definition_id TEXT, source_actor_id TEXT, source_ability_id TEXT, source_type TEXT, source_instance_id TEXT, created_world_time INTEGER, expires_world_time INTEGER, active INTEGER, origin_action_id TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT, source_versions_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS aura_membership (membership_id TEXT PRIMARY KEY, aura_instance_id TEXT, world_id TEXT, target_actor_id TEXT, granted_effect_instance_id TEXT, active INTEGER, suppressed INTEGER, joined_world_time INTEGER, left_world_time INTEGER, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS summon_relationships (summon_instance_id TEXT PRIMARY KEY, world_id TEXT, actor_id TEXT, template_id TEXT, owner_actor_id TEXT, source_ability_id TEXT, origin_action_id TEXT, created_world_time INTEGER, expires_world_time INTEGER, state TEXT, relationship_policy TEXT, control_policy TEXT, follow_policy TEXT, combat_policy TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS summon_profiles (profile_id TEXT PRIMARY KEY, world_id TEXT, owner_actor_id TEXT, profile_name TEXT, summon_definition_id TEXT, entity_template_id TEXT, identity TEXT, level INTEGER, primary_stat_profile_json TEXT, secondary_modifier_profile_json TEXT, resource_profile_json TEXT, natural_weapons_json TEXT, ability_grants_json TEXT, appearance TEXT, profile_schema_version TEXT, source_hash TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS room_effect_instances (room_effect_instance_id TEXT PRIMARY KEY, world_id TEXT, definition_id TEXT, source_actor_id TEXT, source_ability_id TEXT, room_id TEXT, area_id TEXT, created_world_time INTEGER, expires_at INTEGER, next_tick_at INTEGER, state TEXT, origin_action_id TEXT, created_at TEXT, updated_at TEXT, metadata_json TEXT, source_versions_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS room_effect_membership (membership_id TEXT PRIMARY KEY, room_effect_instance_id TEXT, world_id TEXT, actor_id TEXT, granted_effect_instance_ids_json TEXT, entered_world_time INTEGER, left_world_time INTEGER, state TEXT, updated_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS room_effect_tick_claims (claim_id TEXT PRIMARY KEY, world_id TEXT, room_effect_instance_id TEXT, scheduled_world_time INTEGER, claimed_at TEXT, metadata_json TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS trigger_claims (claim_id TEXT PRIMARY KEY, world_id TEXT, trigger_chain_id TEXT, actor_id TEXT, trigger_name TEXT, origin_action_id TEXT, depth INTEGER, created_at TEXT, metadata_json TEXT)")
        c.commit()
