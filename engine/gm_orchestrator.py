"""LLM-first Game Master orchestrator for Core Game V1."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from engine.core_game import by_id, load_core_game

DECISION_KEYS = ("action_interpretation","skill_or_ability_used","difficulty","outcome","state_changes","npc_reactions","quest_updates","inventory_changes","memory_notes","narration")
OPTIONAL_DECISION_KEYS = ("scene_updates","npc_state_updates","journal_updates","ability_checks","rule_references","debug_notes")
OUTCOMES = {"success", "partial_success", "failure", "complication", "unclear"}

@dataclass
class GMContext:
    player_input: str
    scene_v1: dict[str, Any]
    character_sheet: dict[str, Any]
    stats: dict[str, Any]
    inventory: list[dict[str, Any]]
    known_abilities: list[dict[str, Any]]
    active_quests: list[dict[str, Any]]
    nearby_npcs: list[dict[str, Any]]
    active_hooks: list[dict[str, Any]] = field(default_factory=list)
    current_location: dict[str, Any] = field(default_factory=dict)
    visible_objects: list[dict[str, Any]] = field(default_factory=list)
    exits: list[dict[str, Any]] = field(default_factory=list)
    class_data: dict[str, Any] = field(default_factory=dict)
    race_data: dict[str, Any] = field(default_factory=dict)
    background_data: dict[str, Any] = field(default_factory=dict)
    intelligence_chunks: list[dict[str, Any]] = field(default_factory=list)
    relevant_rules: dict[str, Any] = field(default_factory=dict)

class GMOrchestrator:
    """Builds context and lets the provider decide when one is available."""
    def __init__(self, provider: Any = None, core_game: dict[str, Any] | None = None) -> None:
        self.provider = provider
        self.core_game = core_game or load_core_game()

    def build_context(self, player_input: str, state: Any, intelligence_chunks: list[dict[str, Any]] | None = None) -> GMContext:
        runtime = getattr(getattr(state, "structured_state", None), "runtime", None)
        scene = getattr(runtime, "scene_state", {}).get("scene_v1", {}) if runtime else {}
        inventory_state = getattr(runtime, "inventory_state", {}) if runtime else {}
        abilities = list(getattr(runtime, "abilities", []) or getattr(runtime, "spellbook", []) or []) if runtime else []
        quests = [q if isinstance(q, dict) else getattr(q, "__dict__", {}) for q in getattr(state, "quests", {}).values()] if hasattr(state, "quests") else []
        npcs = [e for e in scene.get("entities", []) if isinstance(e, dict) and e.get("kind") in {"npc", "creature"}]
        character = getattr(getattr(state, "player", None), "__dict__", {}) if state is not None else {}
        rules = {"stats": self.core_game["stats"], "combat": self.core_game.get("combat", {}), "magic": self.core_game.get("magic", {})}
        known = self._match_known_ability(player_input, abilities)
        if known: rules["known_ability_definition"] = known
        loc = getattr(state, "locations", {}).get(getattr(state, "current_location_id", "")) if state is not None else None
        current_location = getattr(loc, "__dict__", {}) if loc else {"id": getattr(state, "current_location_id", ""), "name": scene.get("location_name", "")}
        objects = [e for e in scene.get("entities", []) if isinstance(e, dict) and e.get("kind") in {"object", "item", "feature"}]
        exits = list(scene.get("exits", []) or [])
        hooks = list(getattr(getattr(state, "structured_state", None), "runtime", None).scene_state.get("active_hooks", []) or []) if runtime else []
        cls_name = str(character.get("character_class", character.get("role", ""))).lower()
        class_data = next((c for c in self.core_game.get("classes", []) if str(c.get("name", c.get("id", ""))).lower() == cls_name or str(c.get("id", "")).lower() == cls_name), {})
        return GMContext(player_input, scene, character, character.get("classic_attributes", {}) or character, list(inventory_state.get("entries", [])), abilities, quests, npcs, hooks, current_location, objects, exits, class_data, {}, {}, intelligence_chunks or [], rules)

    def decide(self, player_input: str, state: Any, intelligence_chunks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        context = self.build_context(player_input, state, intelligence_chunks)
        if self._provider_available():
            raw = self._ask_provider(context)
            return self._normalize_decision(raw, context)
        return self._fallback_decision(context)

    def _provider_available(self) -> bool:
        return self.provider is not None and not getattr(self.provider, "is_null", False) and (hasattr(self.provider, "gm_decision") or (bool(getattr(self.provider, "provider_name", "")) and getattr(self.provider, "provider_name", "") != "null" and hasattr(self.provider, "generate")))

    def _ask_provider(self, context: GMContext) -> Any:
        payload = {"schema": list(DECISION_KEYS + OPTIONAL_DECISION_KEYS), "context": context.__dict__}
        instruction = ("You are the Game Master for Adventure Guild AI. Use the supplied Core Game rules and scene state as truth. "
            "Do not invent accepted abilities the character does not know. Do not override character identity. "
            "Do not decide the player’s internal thoughts. Resolve the player’s attempted action naturally. "
            "Apply consequences. Use nearby NPCs and scene objects. Return only structured JSON matching the decision schema.")
        if hasattr(self.provider, "gm_decision"):
            return self.provider.gm_decision({"instruction": instruction, **payload})
        return self.provider.generate(json.dumps(payload, default=str), instruction)

    def _normalize_decision(self, raw: Any, context: GMContext) -> dict[str, Any]:
        if isinstance(raw, dict):
            data = raw
        else:
            try:
                parsed = json.loads(str(raw or ""))
                data = parsed if isinstance(parsed, dict) else {"narration": str(raw or "")}
            except (TypeError, json.JSONDecodeError):
                data = {"narration": str(raw or "")}
        fallback = self._fallback_decision(context)
        for key in DECISION_KEYS:
            data.setdefault(key, fallback[key])
        return data

    def _fallback_decision(self, context: GMContext) -> dict[str, Any]:
        ability = self._match_known_ability(context.player_input, context.known_abilities)
        return {
            "action_interpretation": context.player_input,
            "skill_or_ability_used": ability.get("name") if ability else None,
            "difficulty": "standard",
            "outcome": "partial_success",
            "state_changes": {},
            "npc_reactions": [f"{npc.get('name')} watches for consequences." for npc in context.nearby_npcs[:2]],
            "quest_updates": [],
            "inventory_changes": [],
            "memory_notes": [f"Player attempted: {context.player_input}"],
            "narration": (f"You use {ability.get('name')}: {ability.get('narrative_guidance') or ability.get('description')}" if ability else "You act, and the world responds cautiously while awaiting a fuller GM ruling."),
        }

    def _match_known_ability(self, text: str, abilities: list[dict[str, Any]]) -> dict[str, Any] | None:
        q = text.lower()
        core_by_name = {a["name"].lower(): a for a in self.core_game.get("abilities", [])}
        for entry in abilities:
            name = str(entry.get("name", "")).lower()
            if name and name in q:
                return core_by_name.get(name, entry)
        return None

    def validate_decision(self, decision: dict[str, Any], context: GMContext, *, strict_rules: bool = False) -> tuple[dict[str, Any], list[str], bool]:
        repaired = dict(decision or {})
        errors: list[str] = []
        repair = False
        if not str(repaired.get("narration", "")).strip():
            errors.append("missing_narration")
            repaired["narration"] = self._fallback_decision(context)["narration"]
            repair = True
        if repaired.get("outcome") not in OUTCOMES:
            errors.append("invalid_outcome")
            repaired["outcome"] = "unclear"
            repair = True
        if not isinstance(repaired.get("state_changes"), dict):
            errors.append("state_changes_not_dict")
            repaired["state_changes"] = {}
            repair = True
        used = str(repaired.get("skill_or_ability_used") or "").strip().lower()
        known_names = {str(a.get("name", "")).strip().lower() for a in context.known_abilities if isinstance(a, dict)}
        if strict_rules and used and used not in known_names:
            errors.append("unknown_ability_used")
        return repaired, errors, repair

    def apply_gm_decision(self, decision: dict[str, Any], state: Any) -> dict[str, Any]:
        applied: dict[str, Any] = {"scene": False, "npc": [], "inventory": [], "journal": False, "memory": False}
        runtime = getattr(getattr(state, "structured_state", None), "runtime", None)
        if runtime is None:
            return applied
        scene_state = getattr(runtime, "scene_state", {})
        scene = scene_state.setdefault("scene_v1", {})
        narration = str(decision.get("narration", "")).strip()
        if narration:
            scene["recent_changes"] = (list(scene.get("recent_changes", [])) + [narration])[-5:]
            runtime.last_narration = narration
            applied["scene"] = True
        if isinstance(decision.get("scene_updates"), dict):
            scene.update(decision["scene_updates"])
            applied["scene"] = True
        if isinstance(decision.get("npc_state_updates"), list):
            known = {str(e.get("actor_id") or e.get("id") or e.get("name")): e for e in scene.get("entities", []) if isinstance(e, dict)}
            for upd in decision["npc_state_updates"]:
                if not isinstance(upd, dict):
                    continue
                key = str(upd.get("actor_id") or upd.get("id") or upd.get("name") or "")
                if key in known:
                    known[key].update({k: v for k, v in upd.items() if k not in {"actor_id", "id", "name"}})
                    applied["npc"].append(key)
        inv_state = getattr(runtime, "inventory_state", {})
        inv = inv_state.setdefault("entries", []) if isinstance(inv_state, dict) else []
        changes = decision.get("inventory_changes", [])
        for ch in changes if isinstance(changes, list) else []:
            if not isinstance(ch, dict):
                continue
            action = str(ch.get("action", ch.get("type", ""))).lower()
            item = ch.get("item") or {"id": ch.get("item_id"), "name": ch.get("name") or ch.get("item_id")}
            iid = str(item.get("id") or item.get("name") or "").strip() if isinstance(item, dict) else str(item)
            if action in {"add", "gain", "added"} and iid:
                inv.append(item if isinstance(item, dict) else {"id": iid, "name": iid})
                applied["inventory"].append(f"add:{iid}")
            elif action in {"remove", "drop", "consume"} and iid:
                before = len(inv)
                inv[:] = [e for e in inv if str(e.get("id") or e.get("name")) != iid]
                if len(inv) != before:
                    applied["inventory"].append(f"remove:{iid}")
        notes = decision.get("memory_notes")
        if notes:
            runtime.campaign_events = list(getattr(runtime, "campaign_events", []) or []) + [{"type": "gm_memory", "notes": notes}]
            applied["memory"] = True
        return applied
