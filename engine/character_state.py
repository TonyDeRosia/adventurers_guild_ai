"""Canonical character action-state and Adventurer's Lair HP/position reconciliation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

NEGATIVE_HEALTH_THRESHOLDS = {
    "stunned_min": -2,
    "incapacitated_min": -5,
    "mortally_wounded_min": -10,
    "dead_max": -11,
}
POSITIVE_POSITIONS = {"standing", "sitting", "resting", "sleeping", "fighting", "in_combat", "idle"}
DOWN_POSITIONS = {"stunned", "incapacitated", "mortally_wounded", "mortallyw", "dead", "unconscious"}

@dataclass(frozen=True)
class CharacterActionState:
    actor_id: str
    health: int
    maximum_health: int
    derived_position: str
    stored_position: str
    lifecycle_state: str
    combat_state: str
    active_encounter_id: str = ""
    active_target_id: str = ""
    is_alive: bool = True
    is_conscious: bool = True
    is_awake: bool = True
    can_stand: bool = True
    can_move: bool = True
    can_attack: bool = True
    can_cast: bool = True
    can_rest: bool = True
    can_sleep: bool = True
    blocking_reason: str = ""
    repair_required: bool = False

def normalize_position(value: Any) -> str:
    pos = str(value or "standing").strip().lower().replace(" ", "_")
    return "mortally_wounded" if pos == "mortallyw" else pos

def derive_position_from_health(health: int, stored_position: str = "standing", lifecycle_state: str = "alive") -> str:
    stored = normalize_position(stored_position)
    life = str(lifecycle_state or "alive").lower()
    if health <= -11 or life == "dead":
        return "dead"
    if health <= -6:
        return "mortally_wounded"
    if health <= -3:
        return "incapacitated"
    if health <= 0:
        return "stunned"
    if stored in {"sitting", "resting", "sleeping", "fighting", "in_combat"}:
        return stored
    return "standing" if stored in DOWN_POSITIONS or not stored else stored

def state_message(position: str) -> str:
    return {
        "sleeping": "You are asleep. WAKE before trying to fight.",
        "resting": "You need to stand before you can attack.",
        "sitting": "You need to stand before you can attack.",
        "stunned": "You are too stunned to attack.",
        "incapacitated": "You are incapacitated and cannot fight.",
        "mortally_wounded": "You are mortally wounded and cannot fight.",
        "dead": "You are dead and cannot attack.",
    }.get(normalize_position(position), "")

def get_actor_position(actor: Any) -> str:
    cp = getattr(actor, "combat_profile", {}) or {}
    return normalize_position(cp.get("combat_state") or getattr(getattr(actor, "identity", None), "position", "standing"))

def set_actor_position(actor: Any, position: str) -> None:
    pos = normalize_position(position)
    if hasattr(actor, "identity"):
        actor.identity.position = pos.replace("_", " ").title()
    cp = getattr(actor, "combat_profile", None)
    if isinstance(cp, dict):
        cp["combat_state"] = "idle" if pos == "standing" else pos
        cp["position"] = pos

def reconcile_actor_position(actor: Any, runtime: Any = None, *, reason: str = "state_reconcile", persist_dirty: bool = False) -> tuple[str, str, bool]:
    health = int(getattr(getattr(actor, "resources", None), "health", 0) or 0)
    life = str(getattr(actor, "lifecycle_state", "alive") or "alive").lower()
    stored = get_actor_position(actor)
    derived = derive_position_from_health(health, stored, life)
    changed = derived != stored or (health > 0 and life == "alive" and stored in DOWN_POSITIONS)
    if changed:
        set_actor_position(actor, derived)
        if derived == "dead":
            actor.lifecycle_state = "dead"
        elif health > 0 and life == "dead":
            # Do not resurrect dead lifecycle evidence; caller must decide. Keep dead.
            set_actor_position(actor, "dead"); derived = "dead"
        if runtime is not None:
            counters = getattr(runtime, "performance_counters", {})
            counters["state_reconciliations"] = counters.get("state_reconciliations", 0) + 1
            counters["stale_position_repairs"] = counters.get("stale_position_repairs", 0) + 1
            if health > 0 and stored in {"incapacitated", "mortally_wounded", "stunned", "dead", "unconscious"}:
                counters["positive_health_incapacitated_repairs"] = counters.get("positive_health_incapacitated_repairs", 0) + 1
            print(f"[state-reconcile] actor={getattr(getattr(actor,'identity',None),'name',actor.actor_id)} stored={stored} derived={derived} health={health} action=repaired reason={reason}")
            if persist_dirty and str(getattr(actor, "actor_id", "")).startswith("character:") and hasattr(runtime, "mark_character_dirty"):
                runtime.mark_character_dirty(actor.actor_id.split(":",1)[1], "state_reconcile")
    return stored, derived, changed

def build_action_state(actor: Any, runtime: Any = None, *, active_encounter_id: str = "", active_target_id: str = "") -> CharacterActionState:
    stored = get_actor_position(actor)
    health = int(getattr(getattr(actor, "resources", None), "health", 0) or 0)
    maxh = int(getattr(getattr(actor, "resources", None), "maximum_health", health) or health)
    life = str(getattr(actor, "lifecycle_state", "alive") or "alive").lower()
    derived = derive_position_from_health(health, stored, life)
    msg = state_message(derived)
    fighting = bool(active_encounter_id)
    if fighting and not msg:
        msg = "already_fighting"
    can_attack = not msg and life != "dead" and health > 0
    return CharacterActionState(actor.actor_id, health, maxh, derived, stored, life, str((getattr(actor,"combat_profile",{}) or {}).get("combat_state", "")), active_encounter_id, active_target_id, life != "dead" and derived != "dead", derived not in {"stunned","incapacitated","mortally_wounded","dead"}, derived != "sleeping", derived in {"sitting","resting","standing"}, derived == "standing", can_attack, can_attack, derived in {"standing","sitting"}, derived in {"standing","sitting","resting"}, msg, derived != stored)
