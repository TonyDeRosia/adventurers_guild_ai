"""Canonical observation and action gateway for future Smart MUD agents.

The gateway is deliberately non-autonomous: controllers may request observations
and submit structured actions, but only existing MudRuntime services validate and
change authoritative state.
"""
from __future__ import annotations

import hashlib, json, sqlite3, uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Callable

AGENT_OBSERVATION_VERSION = 1
AGENT_ACTION_CONTRACT_VERSION = 1
AGENT_RESULT_CONTRACT_VERSION = 1
SUPPORTED_CONTROLLER_TYPES = {"manual_test", "deterministic", "future_behavior_tree", "future_utility", "future_llm"}
AUTONOMOUS_CONTROLLER_TYPES = SUPPORTED_CONTROLLER_TYPES - {"manual_test"}

RESULT_SUCCESS = "SUCCESS"
RESULT_QUEUED = "QUEUED"
RESULT_NO_OP = "NO_OP"
RESULT_REJECTED = "REJECTED"

REASON_SUCCESS = "SUCCESS"
REASON_TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
REASON_TARGET_NOT_VISIBLE = "TARGET_NOT_VISIBLE"
REASON_TARGET_DEAD = "TARGET_DEAD"
REASON_TARGET_OUT_OF_RANGE = "TARGET_OUT_OF_RANGE"
REASON_INVALID_TARGET_TYPE = "INVALID_TARGET_TYPE"
REASON_ACTION_NOT_AVAILABLE = "ACTION_NOT_AVAILABLE"
REASON_ACTION_NOT_ALLOWED = "ACTION_NOT_ALLOWED"
REASON_STALE_LIFECYCLE = "STALE_LIFECYCLE"
REASON_STALE_OBSERVATION = "STALE_OBSERVATION"
REASON_ACTOR_DEAD = "ACTOR_DEAD"
REASON_ACTOR_INCAPACITATED = "ACTOR_INCAPACITATED"
REASON_ACTOR_IN_COMBAT = "ACTOR_IN_COMBAT"
REASON_ACTOR_NOT_IN_COMBAT = "ACTOR_NOT_IN_COMBAT"
REASON_COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
REASON_INSUFFICIENT_RESOURCE = "INSUFFICIENT_RESOURCE"
REASON_MOVEMENT_BLOCKED = "MOVEMENT_BLOCKED"
REASON_EXIT_CLOSED = "EXIT_CLOSED"
REASON_EXIT_LOCKED = "EXIT_LOCKED"
REASON_CONTAINER_CLOSED = "CONTAINER_CLOSED"
REASON_INVENTORY_FULL = "INVENTORY_FULL"
REASON_ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
REASON_AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
REASON_INVALID_PARAMETERS = "INVALID_PARAMETERS"
REASON_UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
REASON_CONTROLLER_LEASE_REQUIRED = "CONTROLLER_LEASE_REQUIRED"
REASON_CONTROLLER_DISABLED = "CONTROLLER_DISABLED"
REASON_DUPLICATE_CONTROLLER = "DUPLICATE_CONTROLLER"
REASON_CONTRACT_VERSION_UNSUPPORTED = "CONTRACT_VERSION_UNSUPPORTED"

ALL_REASON_CODES = sorted(v for k, v in globals().items() if k.startswith("REASON_"))
ALL_RESULT_CODES = [RESULT_SUCCESS, RESULT_QUEUED, RESULT_NO_OP, RESULT_REJECTED]


def init_agent_runtime_schema(db_path: str) -> None:
    with sqlite3.connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS agent_controllers(controller_id TEXT PRIMARY KEY,controller_type TEXT,actor_id TEXT,enabled INTEGER DEFAULT 1,priority INTEGER DEFAULT 0,created_at TEXT,updated_at TEXT,metadata_json TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS agent_control_leases(lease_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,lifecycle_id TEXT,controller_id TEXT,controller_type TEXT,active INTEGER DEFAULT 1,override_reason TEXT,acquired_at TEXT,released_at TEXT,metadata_json TEXT)""")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_one_active_lease ON agent_control_leases(world_id,actor_id,lifecycle_id) WHERE active=1")
        con.execute("""CREATE TABLE IF NOT EXISTS agent_observations(observation_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,lifecycle_id TEXT,room_id TEXT,combat_encounter_id TEXT,world_time INTEGER,observation_version INTEGER,observation_hash TEXT,created_at TEXT,metadata_json TEXT)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_agent_observations_actor ON agent_observations(world_id,actor_id,lifecycle_id,created_at)")
        con.execute("""CREATE TABLE IF NOT EXISTS agent_action_audit(audit_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,lifecycle_id TEXT,request_id TEXT,controller_id TEXT,controller_type TEXT,observation_id TEXT,action_type TEXT,target_ref TEXT,secondary_target_ref TEXT,parameters_json TEXT,accepted INTEGER,executed INTEGER,result_code TEXT,reason_code TEXT,summary TEXT,world_time INTEGER,result_json TEXT,created_at TEXT,completed_at TEXT,UNIQUE(world_id,actor_id,lifecycle_id,request_id))""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_agent_action_audit_actor ON agent_action_audit(world_id,actor_id,lifecycle_id,created_at)")
        con.execute("""CREATE TABLE IF NOT EXISTS agent_recent_events(event_id TEXT PRIMARY KEY,world_id TEXT,room_id TEXT,actor_id TEXT,event_type TEXT,source_ref TEXT,target_ref TEXT,summary TEXT,world_time INTEGER,created_at TEXT,expires_world_time INTEGER,payload_json TEXT)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_agent_recent_events_scope ON agent_recent_events(world_id,room_id,actor_id,world_time)")
        con.commit()


@dataclass(frozen=True)
class AgentActionCapability:
    action_type: str
    display_label: str
    target_requirements: str = "none"
    allowed_target_refs: list[str] = field(default_factory=list)
    allowed_target_categories: list[str] = field(default_factory=list)
    required_parameters: list[str] = field(default_factory=list)
    optional_parameters: list[str] = field(default_factory=list)
    resource_cost_summary: dict[str, Any] = field(default_factory=dict)
    cooldown_summary: dict[str, Any] = field(default_factory=dict)
    range_requirement: str = "current_room"
    current_availability: bool = True
    unavailability_reason_code: str = ""
    contract_version: int = AGENT_ACTION_CONTRACT_VERSION


@dataclass(frozen=True)
class AgentActionRequest:
    request_id: str
    actor_id: str
    lifecycle_id: str
    observation_id: str
    action_type: str
    target_ref: str = ""
    secondary_target_ref: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    requested_world_time: int = 0
    controller_id: str = ""
    controller_type: str = "manual_test"
    contract_version: int = AGENT_ACTION_CONTRACT_VERSION


@dataclass(frozen=True)
class AgentActionResult:
    request_id: str
    actor_id: str
    lifecycle_id: str
    action_type: str
    accepted: bool
    executed: bool
    result_code: str
    reason_code: str
    summary: str
    world_time: int
    resulting_observation_required: bool = False
    resulting_state_changes: dict[str, Any] = field(default_factory=dict)
    events_emitted: list[str] = field(default_factory=list)
    target_ref: str = ""
    encounter_id: str = ""
    ability_id: str = ""
    item_refs: list[str] = field(default_factory=list)
    retryable: bool = False
    contract_version: int = AGENT_RESULT_CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class AgentObservation:
    observation_id: str
    world_id: str
    actor_id: str
    lifecycle_id: str
    world_time: int
    room: dict[str, Any]
    self_state: dict[str, Any]
    visible_actors: list[dict[str, Any]]
    visible_objects: list[dict[str, Any]]
    visible_features: list[dict[str, Any]]
    visible_exits: list[dict[str, Any]]
    current_combat: dict[str, Any]
    recent_events: list[dict[str, Any]]
    available_actions: list[dict[str, Any]]
    observation_version: int = AGENT_OBSERVATION_VERSION

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class ActionRegistration:
    action_type: str
    parameter_schema: dict[str, Any]
    target_categories: list[str]
    executor: Callable[[AgentActionRequest], AgentActionResult]
    availability: Callable[[Any], AgentActionCapability]
    version: int = AGENT_ACTION_CONTRACT_VERSION


class AgentRuntimeGateway:
    """Single capability boundary for future controllers."""

    def __init__(self, runtime: Any):
        self.runtime = runtime
        self.db_path = str(runtime.state_store.db_path)
        init_agent_runtime_schema(self.db_path)
        self._registry: dict[str, ActionRegistration] = {}
        self._register_default_actions()

    def world_time(self) -> int:
        wt = self.runtime.get_world_time(self.runtime.active_world_id or "")
        return int(wt.get("total_minutes") or (int(wt.get("day", 1))*1440 + int(wt.get("hour", 0))*60 + int(wt.get("minute", 0))))

    def actor_lifecycle_id(self, char: Any) -> str:
        data = getattr(char, "actor_data", {}) or {}
        life = data.get("lifecycle_id") or data.get("lifecycle", {}).get("lifecycle_id")
        if not life:
            life = f"character:{char.id}:life"
            data["lifecycle_id"] = life
            char.actor_data = data
            self.runtime.state_store.save_character(char, self.runtime.active_world_id or "")
        return str(life)

    def actor_id_for_character(self, char: Any) -> str:
        return self.runtime.combat_runtime.actor_id_for_character(char) if getattr(self.runtime, "combat_runtime", None) else f"character:{char.id}"

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.runtime.event_bus:
            clean = {k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool, type(None), list, dict))}
            self.runtime.event_bus.publish(event_type, clean, source_system="agent_runtime", world_id=clean.get("world_id") or self.runtime.active_world_id or "")

    def _target_ref(self, category: str, *parts: Any) -> str:
        return "agentref:v1:" + ":".join([self.runtime.active_world_id or "", category, *[str(p).replace(":", "%3A") for p in parts]])

    def _parse_target_ref(self, ref: str) -> dict[str, str] | None:
        parts = str(ref or "").split(":")
        if len(parts) < 4 or parts[0] != "agentref" or parts[1] != "v1": return None
        if parts[2] != (self.runtime.active_world_id or ""): return None
        return {"world_id": parts[2], "category": parts[3], "parts": [p.replace("%3A", ":") for p in parts[4:]]}

    def _condition_band(self, hp: int, max_hp: int) -> str:
        if hp <= 0: return "dead"
        pct = hp / max(1, max_hp)
        if pct >= .8: return "healthy"
        if pct >= .5: return "wounded"
        if pct >= .25: return "badly_wounded"
        return "near_death"

    def create_observation(self, actor_id: str, controller_id: str = "", *, require_lease: bool = True) -> AgentObservation:
        char = self._load_controlled_character(actor_id, controller_id, require_lease=require_lease)
        lifecycle_id = self.actor_lifecycle_id(char)
        world_id = self.runtime.active_world_id or ""
        room = self.runtime._current_room(char)
        wt = self.world_time()
        combat_id = self.runtime.combat_runtime.find_actor_encounter(self.actor_id_for_character(char)) if getattr(self.runtime, "combat_runtime", None) else ""
        visible = self.runtime.find_visible_entities(char.room_id, char)
        actors = []
        for ent in visible.get("npcs", []) + visible.get("mobs", []):
            st = ent.get("state") or {}
            if st.get("current_state") == "dead" or ent.get("is_alive") is False: continue
            life = str(st.get("lifecycle_id") or ent.get("entity_id") or ent.get("instance_id") or "")
            max_hp = int(st.get("maximum_health") or st.get("max_health") or 100); hp = int(st.get("current_health") or st.get("health") or max_hp)
            actors.append({"target_ref": self._target_ref("actor", "entity", ent.get("instance_id") or ent.get("entity_id"), life), "actor_id": "entity:" + str(ent.get("instance_id") or ent.get("entity_id")), "lifecycle_id": life, "display_name": ent.get("name") or "Someone", "actor_type": ent.get("entity_type") or "npc", "room_line": ent.get("name") or "Someone is here.", "condition_band": self._condition_band(hp, max_hp), "posture": st.get("posture") or st.get("current_state") or "standing", "combat_status": "in_combat" if (getattr(self.runtime, "combat_runtime", None) and self.runtime.combat_runtime.find_actor_encounter("entity:" + str(ent.get("instance_id") or ent.get("entity_id")))) else "none", "current_target_ref": "", "visible_effects": [], "visible_equipment_summary": [], "relationship": "unknown", "interaction_capabilities": ["inspect", "attack", "target"], "distance": "same_room"})
        objects = []
        for obj in visible.get("objects", []) + visible.get("corpses", []):
            oid = obj.get("instance_id") or obj.get("entity_id") or obj.get("id") or obj.get("template_id")
            category = "corpse" if obj.get("entity_type") == "corpse" else "item"
            st = obj.get("state") or {}
            objects.append({"target_ref": self._target_ref(category, oid), "object_type": category if category == "corpse" else obj.get("entity_type") or "item", "display_name": obj.get("name") or (obj.get("template") or {}).get("name") or str(oid), "room_line": obj.get("short_description") or obj.get("name") or "", "description_summary": obj.get("description") or obj.get("short_description") or "", "keywords": list(obj.get("keywords") or (obj.get("template") or {}).get("keywords") or [])[:6], "container_state": "open" if st.get("container_open") else ("closed" if st.get("container_open") is False else "not_container"), "lit_state": "lit" if st.get("lit") else "unlit", "corpse_freshness_state": st.get("decay_state") or "", "extraction_state": {"skinned": bool(st.get("skinned")), "butchered": bool(st.get("butchered"))}, "quantity": int(obj.get("stack_count") or obj.get("quantity") or 1), "interaction_capabilities": ["inspect", "get_item"] + (["loot_container"] if category == "corpse" or st.get("container_open") is not None else []), "ownership_summary": "visible"})
        exits = []
        for direction, ex in self.runtime.canonical_exits(char, char.room_id).items():
            if ex.get("hidden"): continue
            _edata, reason = self.runtime.resolve_exit(char, char.room_id, direction)
            exits.append({"target_ref": self._target_ref("exit", char.room_id, direction), "direction": direction, "display_name": ex.get("name") or direction, "open_state": "closed" if ex.get("closed") else "open", "locked_state": "locked" if ex.get("locked") else "unlocked", "destination_display_name": "", "movement_allowed": reason == "ok", "blocking_reason_code": "" if reason == "ok" else self._map_block_reason(reason), "interaction_capabilities": ["move", "look"]})
        features = []
        for feat in self.runtime._resolved_room_features(char.room_id, char):
            fid = feat.get("id") or feat.get("feature_id") or feat.get("name")
            features.append({"target_ref": self._target_ref("feature", char.room_id, fid), "feature_id": fid, "display_name": feat.get("name") or fid, "room_line": feat.get("short_description") or feat.get("name") or "", "description_summary": feat.get("long_description") or feat.get("short_description") or "", "interaction_capabilities": ["inspect", "interact"]})
        obs = AgentObservation("obs_" + uuid.uuid4().hex, world_id, actor_id, lifecycle_id, wt, {"room_id": room.id, "display_name": room.title, "description": room.description, "environment": {}, "light_level": "unknown", "weather": self.runtime.environment.get_weather("world", world_id) if getattr(self.runtime, "environment", None) else {}, "terrain_tags": [], "visible_exit_count": len(exits), "visible_actor_count": len(actors), "visible_object_count": len(objects)}, {"actor_id": actor_id, "lifecycle_id": lifecycle_id, "display_name": char.name, "actor_type": "player", "current_room_id": char.room_id, "room_display_name": room.title, "posture": (char.actor_data or {}).get("posture", "standing"), "lifecycle_state": "dead" if char.hp <= 0 else "alive", "health": char.hp, "maximum_health": char.max_hp, "mana": char.mana, "maximum_mana": char.max_mana, "stamina": char.stamina, "maximum_stamina": char.max_stamina, "active_visible_effects": list((char.affects or {}).keys()), "current_combat_encounter_id": combat_id or "", "current_target_id": "", "current_target_display_name": "", "queued_action_summary": self._queued_action_summary(actor_id), "known_cooldown_summaries": self._cooldowns(char), "inventory_capacity_summary": {"item_count": len(self.runtime.find_inventory_items(char.id)) if hasattr(self.runtime, "find_inventory_items") else len(char.inventory)}, "encumbrance_summary": {"supported": False}}, actors, objects, features, exits, {"encounter_id": combat_id or "", "in_combat": bool(combat_id)}, self._recent_events(char), [asdict(c) for c in self.available_actions(actor_id)], AGENT_OBSERVATION_VERSION)
        h = hashlib.sha256(json.dumps(obs.to_dict(), sort_keys=True, default=str).encode()).hexdigest()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO agent_observations VALUES(?,?,?,?,?,?,?,?,?,?,?)", (obs.observation_id, world_id, actor_id, lifecycle_id, char.room_id, combat_id or "", wt, AGENT_OBSERVATION_VERSION, h, datetime.now(timezone.utc).isoformat(), json.dumps({"summary_counts": {"actors": len(actors), "objects": len(objects), "exits": len(exits)}})))
        self._publish("agent_observation_created", {"world_id": world_id, "actor_id": actor_id, "lifecycle_id": lifecycle_id, "controller_id": controller_id, "request_id": "", "action_type": "", "result_code": RESULT_SUCCESS, "reason_code": REASON_SUCCESS, "world_time": wt})
        return obs

    def available_actions(self, actor_id: str) -> list[AgentActionCapability]:
        char = self._character_from_actor_id(actor_id)
        return [reg.availability(char) for reg in self._registry.values()]

    def submit_action(self, request: AgentActionRequest | dict[str, Any]) -> AgentActionResult:
        if isinstance(request, dict): request = AgentActionRequest(**{k: v for k, v in request.items() if k in AgentActionRequest.__dataclass_fields__})
        prior = self._prior_result(request)
        if prior: return prior
        self._publish("agent_action_requested", {"world_id": self.runtime.active_world_id or "", "actor_id": request.actor_id, "lifecycle_id": request.lifecycle_id, "controller_id": request.controller_id, "request_id": request.request_id, "action_type": request.action_type, "target_ref": request.target_ref, "world_time": self.world_time()})
        pre = self._prevalidate_request(request)
        if pre: return self._finish_request(request, pre)
        reg = self._registry.get(request.action_type.lower())
        if not reg: return self._finish_request(request, self._reject(request, REASON_UNSUPPORTED_ACTION, "Unsupported action type."))
        schema_error = self._validate_parameters(request, reg.parameter_schema)
        if schema_error: return self._finish_request(request, self._reject(request, REASON_INVALID_PARAMETERS, schema_error))
        result = reg.executor(request)
        return self._finish_request(request, result)

    def register_controller(self, controller_id: str, controller_type: str, actor_id: str, *, enabled: bool = True, priority: int = 0, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if controller_type not in SUPPORTED_CONTROLLER_TYPES: raise ValueError("unsupported controller_type")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR REPLACE INTO agent_controllers VALUES(?,?,?,?,?,?,?,?)", (controller_id, controller_type, actor_id, 1 if enabled else 0, int(priority), now, now, json.dumps(metadata or {})))
        return {"controller_id": controller_id, "controller_type": controller_type, "actor_id": actor_id, "enabled": enabled}

    def acquire_control(self, actor_id: str, controller_id: str, *, controller_type: str = "manual_test", override_reason: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        char = self._character_from_actor_id(actor_id); lifecycle_id = self.actor_lifecycle_id(char)
        self.register_controller(controller_id, controller_type, actor_id, metadata=metadata)
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT lease_id,controller_id FROM agent_control_leases WHERE world_id=? AND actor_id=? AND lifecycle_id=? AND active=1", (self.runtime.active_world_id or "", actor_id, lifecycle_id)).fetchone()
            if row and row[1] != controller_id and not override_reason:
                return {"ok": False, "reason_code": REASON_DUPLICATE_CONTROLLER, "lease_id": row[0]}
            if row and override_reason:
                con.execute("UPDATE agent_control_leases SET active=0,released_at=? WHERE lease_id=?", (datetime.now(timezone.utc).isoformat(), row[0]))
            lease_id = "lease_" + uuid.uuid4().hex
            con.execute("INSERT INTO agent_control_leases VALUES(?,?,?,?,?,?,?,?,?,?,?)", (lease_id, self.runtime.active_world_id or "", actor_id, lifecycle_id, controller_id, controller_type, 1, override_reason, datetime.now(timezone.utc).isoformat(), None, json.dumps(metadata or {})))
        self._publish("agent_control_acquired", {"world_id": self.runtime.active_world_id or "", "actor_id": actor_id, "lifecycle_id": lifecycle_id, "controller_id": controller_id, "world_time": self.world_time()})
        return {"ok": True, "lease_id": lease_id, "actor_id": actor_id, "lifecycle_id": lifecycle_id, "controller_id": controller_id}

    def release_control(self, actor_id: str, controller_id: str) -> dict[str, Any]:
        char = self._character_from_actor_id(actor_id); life = self.actor_lifecycle_id(char)
        with sqlite3.connect(self.db_path) as con:
            changed = con.execute("UPDATE agent_control_leases SET active=0,released_at=? WHERE world_id=? AND actor_id=? AND lifecycle_id=? AND controller_id=? AND active=1", (datetime.now(timezone.utc).isoformat(), self.runtime.active_world_id or "", actor_id, life, controller_id)).rowcount
        self._publish("agent_control_released", {"world_id": self.runtime.active_world_id or "", "actor_id": actor_id, "lifecycle_id": life, "controller_id": controller_id, "world_time": self.world_time()})
        return {"ok": bool(changed), "released": int(changed)}

    def _character_from_actor_id(self, actor_id: str):
        cid = str(actor_id).split(":", 1)[1] if str(actor_id).startswith("character:") else str(actor_id)
        ch = self.runtime.state_store.load_character(cid)
        if not ch: raise ValueError("actor not found")
        return ch

    def _load_controlled_character(self, actor_id: str, controller_id: str, *, require_lease: bool):
        ch = self._character_from_actor_id(actor_id)
        if require_lease and not self._has_lease(actor_id, self.actor_lifecycle_id(ch), controller_id):
            raise PermissionError(REASON_CONTROLLER_LEASE_REQUIRED)
        return ch

    def _has_lease(self, actor_id: str, lifecycle_id: str, controller_id: str) -> bool:
        if not controller_id: return False
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT c.enabled FROM agent_control_leases l JOIN agent_controllers c ON c.controller_id=l.controller_id WHERE l.world_id=? AND l.actor_id=? AND l.lifecycle_id=? AND l.controller_id=? AND l.active=1", (self.runtime.active_world_id or "", actor_id, lifecycle_id, controller_id)).fetchone()
        return bool(row and int(row[0] or 0) == 1)

    def _prevalidate_request(self, r: AgentActionRequest) -> AgentActionResult | None:
        if r.contract_version != AGENT_ACTION_CONTRACT_VERSION: return self._reject(r, REASON_CONTRACT_VERSION_UNSUPPORTED, "Unsupported action contract version.")
        if not r.request_id or not r.actor_id or not r.lifecycle_id: return self._reject(r, REASON_INVALID_PARAMETERS, "request_id, actor_id, and lifecycle_id are required.")
        try: char = self._character_from_actor_id(r.actor_id)
        except Exception: return self._reject(r, REASON_TARGET_NOT_FOUND, "Controlled actor was not found.")
        if self.actor_lifecycle_id(char) != r.lifecycle_id: return self._reject(r, REASON_STALE_LIFECYCLE, "Controlled actor lifecycle is stale.")
        if char.hp <= 0 and r.action_type.lower() not in {"look", "inspect"}: return self._reject(r, REASON_ACTOR_DEAD, "Controlled actor is dead.")
        if not self._has_lease(r.actor_id, r.lifecycle_id, r.controller_id): return self._reject(r, REASON_CONTROLLER_LEASE_REQUIRED, "Controller does not hold an active lifecycle lease.")
        if r.observation_id:
            stale = self._staleness_reason(r, char)
            if stale: return self._reject(r, REASON_STALE_OBSERVATION, stale)
        return None

    def _staleness_reason(self, r: AgentActionRequest, char: Any) -> str:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT room_id,combat_encounter_id FROM agent_observations WHERE observation_id=? AND actor_id=? AND lifecycle_id=?", (r.observation_id, r.actor_id, r.lifecycle_id)).fetchone()
        if not row: return "Observation is unknown for this actor lifecycle."
        action = r.action_type.lower()
        if action in {"move", "attack", "target", "assist", "get_item", "loot_container", "interact", "inspect"} and row[0] != char.room_id:
            return "Actor room changed since observation."
        return ""

    def _validate_parameters(self, r: AgentActionRequest, schema: dict[str, Any]) -> str:
        params = r.parameters or {}
        for key in schema.get("required", []):
            if key not in params or params[key] in (None, ""): return f"Missing required parameter: {key}."
        allowed = set(schema.get("required", [])) | set(schema.get("optional", []))
        unknown = set(params) - allowed
        if unknown: return f"Unknown parameters are not accepted: {', '.join(sorted(unknown))}."
        return ""

    def _resolve_target(self, char: Any, ref: str, allowed: set[str]) -> tuple[dict[str, Any] | None, str]:
        parsed = self._parse_target_ref(ref)
        if not parsed: return None, REASON_TARGET_NOT_FOUND
        cat = parsed["category"]; parts = parsed["parts"]
        if cat not in allowed: return None, REASON_INVALID_TARGET_TYPE
        if cat == "exit":
            if len(parts) < 2 or parts[0] != char.room_id: return None, REASON_STALE_OBSERVATION
            ex, reason = self.runtime.resolve_exit(char, char.room_id, parts[1])
            if reason == "ok": return {"category": cat, "direction": parts[1], "exit": ex}, REASON_SUCCESS
            return None, self._map_block_reason(reason)
        if cat == "actor":
            if len(parts) < 3 or parts[0] != "entity": return None, REASON_INVALID_TARGET_TYPE
            ent = self.runtime.find_entity(parts[1])
            if not ent: return None, REASON_TARGET_NOT_FOUND
            if str((ent.get("state") or {}).get("lifecycle_id") or ent.get("entity_id") or ent.get("instance_id")) != parts[2]: return None, REASON_STALE_LIFECYCLE
            if ent.get("room_id") != char.room_id: return None, REASON_TARGET_NOT_VISIBLE
            if ent.get("is_alive") is False or (ent.get("state") or {}).get("current_state") in {"dead", "corpse", "despawned"}: return None, REASON_TARGET_DEAD
            visible = self.runtime.find_visible_entities(char.room_id, char)
            ids = {str(e.get("instance_id") or e.get("entity_id")) for e in visible.get("npcs", []) + visible.get("mobs", [])}
            if parts[1] not in ids: return None, REASON_TARGET_NOT_VISIBLE
            return {"category": cat, "entity": ent}, REASON_SUCCESS
        if cat in {"item", "corpse"}:
            item = None
            if cat == "item": item = next((i for i in self.runtime.get_visible_room_items(char.room_id) if str(i.get("instance_id")) == (parts[0] if parts else "")), None)
            else: item = self.runtime.find_entity(parts[0] if parts else "")
            if not item: return None, REASON_ITEM_NOT_FOUND
            return {"category": cat, "object": item}, REASON_SUCCESS
        if cat == "feature":
            if len(parts) < 2 or parts[0] != char.room_id: return None, REASON_STALE_OBSERVATION
            feats = self.runtime._resolved_room_features(char.room_id, char)
            feat = next((f for f in feats if str(f.get("id") or f.get("feature_id") or f.get("name")) == parts[1]), None)
            return ({"category": cat, "feature": feat}, REASON_SUCCESS) if feat else (None, REASON_TARGET_NOT_FOUND)
        return None, REASON_INVALID_TARGET_TYPE

    def _map_block_reason(self, reason: str) -> str:
        return {"closed": REASON_EXIT_CLOSED, "locked": REASON_EXIT_LOCKED, "no_exit": REASON_MOVEMENT_BLOCKED, "hidden": REASON_TARGET_NOT_VISIBLE}.get(str(reason), REASON_MOVEMENT_BLOCKED)

    def _finish_request(self, r: AgentActionRequest, result: AgentActionResult) -> AgentActionResult:
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO agent_action_audit VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("audit_" + uuid.uuid4().hex, self.runtime.active_world_id or "", r.actor_id, r.lifecycle_id, r.request_id, r.controller_id, r.controller_type, r.observation_id, r.action_type.lower(), r.target_ref, r.secondary_target_ref, json.dumps(r.parameters or {}), 1 if result.accepted else 0, 1 if result.executed else 0, result.result_code, result.reason_code, result.summary, result.world_time, json.dumps(result.to_dict()), datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
        event = "agent_action_completed" if result.executed else "agent_action_rejected"
        if result.accepted and result.result_code == RESULT_QUEUED: self._publish("agent_action_queued", self._event_payload(r, result))
        if result.accepted: self._publish("agent_action_accepted", self._event_payload(r, result))
        if result.executed: self._publish("agent_action_executed", self._event_payload(r, result))
        self._publish(event, self._event_payload(r, result))
        return result

    def _event_payload(self, r: AgentActionRequest, result: AgentActionResult) -> dict[str, Any]:
        return {"world_id": self.runtime.active_world_id or "", "actor_id": r.actor_id, "lifecycle_id": r.lifecycle_id, "controller_id": r.controller_id, "request_id": r.request_id, "action_type": r.action_type.lower(), "target_ref": r.target_ref, "result_code": result.result_code, "reason_code": result.reason_code, "world_time": result.world_time}

    def _prior_result(self, r: AgentActionRequest) -> AgentActionResult | None:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT result_json FROM agent_action_audit WHERE world_id=? AND actor_id=? AND lifecycle_id=? AND request_id=?", (self.runtime.active_world_id or "", r.actor_id, r.lifecycle_id, r.request_id)).fetchone()
        return AgentActionResult(**json.loads(row[0])) if row else None

    def _reject(self, r: AgentActionRequest, reason: str, summary: str) -> AgentActionResult:
        return AgentActionResult(r.request_id, r.actor_id, r.lifecycle_id, r.action_type.lower(), False, False, RESULT_REJECTED, reason, summary, self.world_time(), retryable=reason not in {REASON_UNSUPPORTED_ACTION, REASON_INVALID_PARAMETERS, REASON_STALE_LIFECYCLE})

    def _ok(self, r: AgentActionRequest, summary: str, *, queued: bool = False, changes: dict[str, Any] | None = None, encounter_id: str = "", target_ref: str = "", item_refs: list[str] | None = None, ability_id: str = "") -> AgentActionResult:
        return AgentActionResult(r.request_id, r.actor_id, r.lifecycle_id, r.action_type.lower(), True, not queued, RESULT_QUEUED if queued else RESULT_SUCCESS, REASON_SUCCESS, summary, self.world_time(), resulting_observation_required=True, resulting_state_changes=changes or {}, target_ref=target_ref or r.target_ref, encounter_id=encounter_id, ability_id=ability_id, item_refs=item_refs or [])

    def _register(self, action_type: str, required: list[str], optional: list[str], targets: list[str], executor: Callable[[AgentActionRequest], AgentActionResult]) -> None:
        def avail(char: Any, at=action_type, targets=targets):
            reason = "" if char and char.hp > 0 else REASON_ACTOR_DEAD
            return AgentActionCapability(at, at.replace("_", " ").title(), "target_ref" if targets else "none", [], targets, required, optional, current_availability=not reason, unavailability_reason_code=reason)
        self._registry[action_type] = ActionRegistration(action_type, {"required": required, "optional": optional}, targets, executor, avail)

    def _register_default_actions(self) -> None:
        self._register("wait", [], ["minutes"], [], self._exec_wait); self._register("look", [], [], [], self._exec_look); self._register("inspect", [], [], ["actor", "item", "corpse", "feature", "exit"], self._exec_inspect)
        self._register("move", [], [], ["exit"], self._exec_move); self._register("speak", ["text"], [], [], self._exec_speak); self._register("attack", [], [], ["actor"], self._exec_attack); self._register("target", [], [], ["actor"], self._exec_target)
        self._register("defend", [], [], [], self._exec_defend); self._register("flee", [], ["direction"], ["exit"], self._exec_flee); self._register("assist", [], [], ["actor"], self._exec_assist); self._register("use_ability", ["ability_id"], [], ["actor"], self._exec_use_ability)
        self._register("get_item", [], [], ["item"], self._exec_get_item); self._register("drop_item", ["item_query"], [], [], self._exec_drop_item); self._register("loot_container", [], [], ["corpse", "item"], self._exec_loot_container)
        for a in ("rest", "stand", "sleep", "wake"): self._register(a, [], [], [], self._exec_posture)
        self._register("interact", ["verb"], [], ["feature", "item", "corpse", "exit"], self._exec_interact)

    def _char(self, r): return self._character_from_actor_id(r.actor_id)
    def _exec_wait(self, r):
        mins = int((r.parameters or {}).get("minutes") or 1); self.runtime.runtime_pulse(max(1, mins)); return self._ok(r, f"Waited {max(1, mins)} minute(s).", changes={"world_time_advanced": max(1, mins)})
    def _exec_look(self, r): return self._ok(r, self.runtime._room_text(self.runtime._current_room(self._char(r))))
    def _exec_inspect(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"actor","item","corpse","feature","exit"}) if r.target_ref else (None, REASON_INVALID_PARAMETERS)
        if not tgt: return self._reject(r, reason, "Inspection target is not available.")
        if tgt["category"] == "actor": return self._ok(r, str(tgt["entity"].get("description") or tgt["entity"].get("name") or "You see nothing special."))
        if tgt["category"] == "exit": return self._ok(r, f"Exit {tgt['direction']} is visible.")
        obj = tgt.get("object") or tgt.get("feature") or {}; return self._ok(r, str(obj.get("description") or obj.get("long_description") or obj.get("short_description") or obj.get("name") or "You see nothing special."))
    def _exec_move(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"exit"})
        if not tgt: return self._reject(r, reason, "Move target is not available.")
        before = ch.room_id; res = self.runtime._move_character(ch, tgt["direction"])
        return self._ok(r, res.narrative, changes={"from_room_id": before, "to_room_id": ch.room_id}) if res.ok else self._reject(r, REASON_MOVEMENT_BLOCKED, res.narrative)
    def _exec_speak(self, r):
        text = str((r.parameters or {}).get("text") or "").strip()
        if not text: return self._reject(r, REASON_INVALID_PARAMETERS, "Speech text is required.")
        res = self.runtime.command_engine.handle_command(self._char(r), "say " + text)
        return self._ok(r, res.narrative)
    def _exec_attack(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"actor"})
        if not tgt: return self._reject(r, reason, "Attack target is not available.")
        res = self.runtime.combat_runtime.start_player_attack(ch, tgt["entity"].get("name") or "")
        return self._ok(r, " ".join(res.messages), queued=True, encounter_id=res.encounter_id) if res.ok else self._reject(r, REASON_ACTION_NOT_ALLOWED, " ".join(res.messages))
    def _exec_target(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"actor"})
        if not tgt: return self._reject(r, reason, "Target is not available.")
        res = self.runtime.combat_runtime.target(ch, tgt["entity"].get("name") or "")
        return self._ok(r, " ".join(res.messages), queued=True, encounter_id=res.encounter_id) if res.ok else self._reject(r, REASON_ACTOR_NOT_IN_COMBAT, " ".join(res.messages))
    def _exec_defend(self, r):
        res = self.runtime.combat_runtime.defend(self._char(r)); return self._ok(r, " ".join(res.messages), queued=True, encounter_id=res.encounter_id) if res.ok else self._reject(r, REASON_ACTOR_NOT_IN_COMBAT, " ".join(res.messages))
    def _exec_flee(self, r):
        direction = (r.parameters or {}).get("direction") or ""; ch = self._char(r)
        if r.target_ref:
            tgt, reason = self._resolve_target(ch, r.target_ref, {"exit"})
            if not tgt: return self._reject(r, reason, "Flee exit is not available.")
            direction = tgt["direction"]
        res = self.runtime.combat_runtime.flee(ch, direction); return self._ok(r, " ".join(res.messages), encounter_id=res.encounter_id) if res.ok else self._reject(r, REASON_ACTOR_NOT_IN_COMBAT, " ".join(res.messages))
    def _exec_assist(self, r):
        res = self.runtime.combat_runtime.assist(self._char(r), ""); return self._ok(r, " ".join(res.messages), queued=True, encounter_id=res.encounter_id) if res.ok else self._reject(r, REASON_ACTION_NOT_AVAILABLE, " ".join(res.messages))
    def _exec_use_ability(self, r):
        res = self.runtime.combat_runtime.queue_ability(self._char(r), str((r.parameters or {}).get("ability_id") or "")); return self._ok(r, " ".join(res.messages), queued=True, encounter_id=res.encounter_id, ability_id=str((r.parameters or {}).get("ability_id") or "")) if res.ok else self._reject(r, REASON_ACTION_NOT_ALLOWED, " ".join(res.messages))
    def _exec_get_item(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"item"})
        if not tgt: return self._reject(r, reason, "Item is not available.")
        msg = self.runtime.pickup_item(ch.id, ch.room_id, tgt["object"].get("name") or tgt["object"].get("instance_id") or "")
        ok = not any(s in msg.lower() for s in ["don't see", "cannot", "can't"]); return self._ok(r, msg) if ok else self._reject(r, REASON_ITEM_NOT_FOUND, msg)
    def _exec_drop_item(self, r):
        ch = self._char(r); msg = self.runtime.drop_item(ch.id, str((r.parameters or {}).get("item_query") or "")); ok = "you drop" in msg.lower(); return self._ok(r, msg) if ok else self._reject(r, REASON_ITEM_NOT_FOUND, msg)
    def _exec_loot_container(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"corpse", "item"})
        if not tgt: return self._reject(r, reason, "Container is not available.")
        obj = tgt["object"]; msg = self.runtime.loot_container(ch, obj.get("name") or obj.get("entity_id") or obj.get("instance_id") or "corpse"); ok = msg.startswith("You take") or "empty" in msg.lower(); return self._ok(r, msg) if ok else self._reject(r, REASON_CONTAINER_CLOSED if "closed" in msg.lower() else REASON_ITEM_NOT_FOUND, msg)
    def _exec_posture(self, r):
        ch = self._char(r); action = r.action_type.lower(); data = ch.actor_data or {}; data["posture"] = {"rest":"resting", "stand":"standing", "sleep":"sleeping", "wake":"standing"}[action]; ch.actor_data = data; self.runtime.state_store.save_character(ch, self.runtime.active_world_id or ""); return self._ok(r, f"Posture is now {data['posture']}.")
    def _exec_interact(self, r):
        ch = self._char(r); tgt, reason = self._resolve_target(ch, r.target_ref, {"feature", "item", "corpse", "exit"})
        if not tgt: return self._reject(r, reason, "Interaction target is not available.")
        verb = str((r.parameters or {}).get("verb") or "").strip().lower()
        if verb not in {"look", "use", "touch", "push", "pull", "open", "close", "read", "pray", "climb"}: return self._reject(r, REASON_INVALID_PARAMETERS, "Unsupported interaction verb.")
        name = (tgt.get("feature") or tgt.get("object") or {}).get("name") or tgt.get("direction") or "target"
        res = self.runtime._handle_interaction_command(ch, verb, [name], f"{verb} {name}") if hasattr(self.runtime, "_handle_interaction_command") else None
        return self._ok(r, getattr(res, "narrative", "Interaction completed.")) if res is not None else self._reject(r, REASON_ACTION_NOT_AVAILABLE, "No canonical interaction is available for that target.")

    def _queued_action_summary(self, actor_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT action_type,ability_id,target_actor_id FROM combat_action_queue WHERE actor_id=? AND status='queued' ORDER BY created_at DESC LIMIT 1", (actor_id,)).fetchone()
        return {"action_type": row[0], "ability_id": row[1], "target_actor_id": row[2]} if row else {}
    def _cooldowns(self, char: Any) -> list[dict[str, Any]]:
        svc = getattr(self.runtime, "abilities", None)
        return [svc.get_ability_status(char.id, a.get("id")) for a in (svc.get_actor_abilities(char.id) if svc else []) if a.get("id")][:10] if svc else []
    def _recent_events(self, char: Any) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as con:
            rows = con.execute("SELECT event_id,event_type,world_time,source_ref,target_ref,summary,expires_world_time FROM agent_recent_events WHERE world_id=? AND (room_id=? OR actor_id=?) ORDER BY world_time DESC LIMIT 20", (self.runtime.active_world_id or "", char.room_id, self.actor_id_for_character(char))).fetchall()
        return [{"event_ref": r[0], "event_type": r[1], "world_time": r[2], "source_target_ref": r[3], "target_target_ref": r[4], "structured_summary": {"text": r[5]}, "perception_channel": "visible_or_audible", "importance": "normal", "expiration_world_time": r[6]} for r in rows]


class AgentTestControllerAdapter:
    """Minimal deterministic test adapter; it never chooses actions."""
    def __init__(self, gateway: AgentRuntimeGateway, controller_id: str, controller_type: str = "manual_test"):
        self.gateway = gateway; self.controller_id = controller_id; self.controller_type = controller_type
    def acquire(self, actor_id: str) -> dict[str, Any]: return self.gateway.acquire_control(actor_id, self.controller_id, controller_type=self.controller_type)
    def observe(self, actor_id: str) -> AgentObservation: return self.gateway.create_observation(actor_id, self.controller_id)
    def submit(self, **kwargs: Any) -> AgentActionResult:
        kwargs.setdefault("controller_id", self.controller_id); kwargs.setdefault("controller_type", self.controller_type)
        return self.gateway.submit_action(AgentActionRequest(**kwargs))
