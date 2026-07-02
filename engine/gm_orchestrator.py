"""LLM-first Game Master orchestrator for Core Game V1."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from engine.core_game import load_core_game

GM_DECISION_SCHEMA: dict[str, Any] = {
    "action_interpretation": "Plain-language summary of what the player tried.",
    "intent_type": "One of look, talk, cast_known_spell, use_unknown_spell, rude_action, attack, travel, inventory, quest, other.",
    "outcome": "One of success, partial_success, failure, complication, unclear, rejected.",
    "difficulty": "Trivial/easy/standard/hard/extreme/impossible or a compact DC label.",
    "narration": "Player-facing prose only. Address what the character perceives; never decide private thoughts.",
    "scene_updates": "Object containing validated scene_v1 changes.",
    "npc_state_updates": "List of updates for existing nearby NPC actor_id/id/name only.",
    "inventory_changes": "List of add/remove changes. Non-core/non-inventory item ids must include improvised:true.",
    "quest_updates": "List of quest or journal updates.",
    "memory_notes": "List of durable facts to remember.",
    "follow_up_prompt": "Short player-facing prompt for what they can do next.",
}
DECISION_KEYS = tuple(GM_DECISION_SCHEMA.keys())
OPTIONAL_DECISION_KEYS = ("skill_or_ability_used", "state_changes", "npc_reactions", "journal_updates", "ability_checks", "rule_references", "debug_notes")
OUTCOMES = {"success", "partial_success", "failure", "complication", "unclear", "rejected"}
INTENT_TYPES = {"look", "talk", "cast_known_spell", "use_unknown_spell", "rude_action", "attack", "travel", "inventory", "quest", "other"}

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
        self.last_debug: dict[str, Any] = {}

    def build_context(self, player_input: str, state: Any, intelligence_chunks: list[dict[str, Any]] | None = None) -> GMContext:
        runtime = getattr(getattr(state, "structured_state", None), "runtime", None)
        mud_room_state = getattr(runtime, "room_state", {}) if runtime else {}
        scene = getattr(runtime, "scene_state", {}).get("scene_v1", {}) if runtime else {}
        if mud_room_state:
            scene = {**scene, "mud_room": mud_room_state.get("room", {}), "authoritative_location_truth": "mud_room"}
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
        objects = list(mud_room_state.get("visible_objects", [])) or [e for e in scene.get("entities", []) if isinstance(e, dict) and e.get("kind") in {"object", "item", "feature"}]
        exits = list((mud_room_state.get("room", {}) or {}).get("exits", [])) or list(scene.get("exits", []) or [])
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
        payload = {"schema": GM_DECISION_SCHEMA, "allowed_intent_types": sorted(INTENT_TYPES), "allowed_outcomes": sorted(OUTCOMES), "context": context.__dict__}
        instruction = (
            "You are the live Game Master inside a MUD engine. The engine owns mechanics and world data is truth; do not invent exits, items, stats, known spells, or permanent NPCs. "
            "Make narrative/game decisions; the engine validates and applies state changes. "
            "Return exactly one JSON object matching the schema, with all required keys. No markdown. No prose outside JSON. "
            "Never control player thoughts, feelings, motives, or speech. Never invent known abilities/spells; if a player uses an unknown spell, set intent_type='use_unknown_spell', outcome='rejected', and explain what is missing. "
            "Only update NPCs present in nearby_npcs. Only use known item ids from inventory/core items unless inventory_changes entries are marked improvised:true. Narration must be player-facing prose. "
            "Examples: look around => intent_type look, scene observations, no forced thoughts; talk to NPC => intent_type talk, NPC reaction update only for that NPC; "
            "cast known spell => intent_type cast_known_spell and skill_or_ability_used must match known_abilities; use unknown spell => rejected, no new ability granted; "
            "rude action => rude_action with plausible social consequences; attack => attack with difficulty/outcome and NPC reaction; travel => travel only for valid exits supplied in context."
        )
        if hasattr(self.provider, "gm_decision"):
            return self.provider.gm_decision({"instruction": instruction, **payload})
        return self.provider.generate(json.dumps(payload, default=str), instruction)

    def _extract_json_object(self, raw: Any) -> tuple[dict[str, Any] | None, str | None]:
        if isinstance(raw, dict):
            return raw, None
        text = str(raw or "")
        try:
            parsed = json.loads(text)
            return (parsed if isinstance(parsed, dict) else None), None if isinstance(parsed, dict) else "json_not_object"
        except (TypeError, json.JSONDecodeError):
            pass
        start = text.find("{")
        if start < 0:
            return None, "no_json_object_found"
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                escape = (not escape and ch == "\\")
                if ch == '"' and not escape:
                    in_string = False
                elif ch != "\\":
                    escape = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:idx + 1])
                        return (parsed if isinstance(parsed, dict) else None), None if isinstance(parsed, dict) else "json_not_object"
                    except json.JSONDecodeError as exc:
                        return None, f"invalid_json:{exc.msg}"
        return None, "unterminated_json_object"

    def _normalize_decision(self, raw: Any, context: GMContext) -> dict[str, Any]:
        data, parse_error = self._extract_json_object(raw)
        fallback = self._fallback_decision(context)
        if data is None:
            data = dict(fallback)
            if parse_error:
                data.setdefault("debug_notes", []).append(parse_error)
        for key in DECISION_KEYS:
            data.setdefault(key, fallback[key])
        data.setdefault("skill_or_ability_used", fallback.get("skill_or_ability_used"))
        data.setdefault("state_changes", {})
        data.setdefault("npc_reactions", [])
        self.last_debug = {"raw_provider_response": raw, "parsed_decision": data, "validation_errors": [parse_error] if parse_error else [], "applied_changes": {}}
        return data

    def _fallback_decision(self, context: GMContext) -> dict[str, Any]:
        ability = self._match_known_ability(context.player_input, context.known_abilities)
        return {
            "action_interpretation": context.player_input,
            "intent_type": "cast_known_spell" if ability else "other",
            "skill_or_ability_used": ability.get("name") if ability else None,
            "difficulty": "standard",
            "outcome": "partial_success",
            "state_changes": {},
            "npc_reactions": [f"{npc.get('name')} watches for consequences." for npc in context.nearby_npcs[:2]],
            "scene_updates": {},
            "npc_state_updates": [],
            "quest_updates": [],
            "inventory_changes": [],
            "memory_notes": [f"Player attempted: {context.player_input}"],
            "follow_up_prompt": "What do you do next?",
            "narration": (f"You use {ability.get('name')}: {ability.get('narrative_guidance') or ability.get('description')}" if ability else "You act, and the world responds cautiously while awaiting a fuller GM ruling."),
        }

    def _match_known_ability(self, text: str, abilities: list[dict[str, Any]]) -> dict[str, Any] | None:
        q = text.lower()
        core_by_name = {a["name"].lower(): a for a in self.core_game.get("abilities", []) + self.core_game.get("spells", []) if a.get("name")}
        for entry in abilities:
            name = str(entry.get("name", "")).lower()
            if name and name in q:
                return core_by_name.get(name, entry)
        return None

    def validate_decision(self, decision: dict[str, Any], context: GMContext, *, strict_rules: bool = False) -> tuple[dict[str, Any], list[str], bool]:
        repaired = dict(decision or {})
        errors: list[str] = []
        repair = False
        fallback = self._fallback_decision(context)
        for key in DECISION_KEYS:
            if key not in repaired:
                errors.append(f"missing_{key}"); repaired[key] = fallback[key]
        narration = str(repaired.get("narration", "")).strip()
        if not narration:
            errors.append("missing_narration"); repaired["narration"] = fallback["narration"]; repair = True
        if narration.lstrip().startswith(("{", "[")) or not re.search(r"[A-Za-z]", narration):
            errors.append("narration_not_player_facing_prose")
        if re.search(r"\byou (think|feel|decide|want|believe|remember|realize)\b", narration, re.I):
            errors.append("player_thought_control")
        if repaired.get("outcome") not in OUTCOMES:
            errors.append("invalid_outcome"); repaired["outcome"] = "unclear"; repair = True
        if repaired.get("intent_type") not in INTENT_TYPES:
            errors.append("invalid_intent_type"); repaired["intent_type"] = "other"; repair = True
        if not isinstance(repaired.get("scene_updates"), dict):
            errors.append("scene_updates_not_dict"); repaired["scene_updates"] = {}; repair = True
        if not isinstance(repaired.get("state_changes"), dict):
            errors.append("state_changes_not_dict"); repaired["state_changes"] = {}; repair = True
        used = str(repaired.get("skill_or_ability_used") or "").strip().lower()
        known_names = {str(a.get("name", "")).strip().lower() for a in context.known_abilities if isinstance(a, dict)}
        if used and used not in known_names:
            errors.append("unknown_ability_used")
        known_npcs = {str(e.get("actor_id") or e.get("id") or e.get("name")) for e in context.nearby_npcs if isinstance(e, dict)}
        for upd in repaired.get("npc_state_updates", []) if isinstance(repaired.get("npc_state_updates"), list) else []:
            key = str(upd.get("actor_id") or upd.get("id") or upd.get("name") or "") if isinstance(upd, dict) else ""
            if key not in known_npcs:
                errors.append(f"unknown_npc_update:{key or 'missing'}")
        valid_items = {str(i.get("id") or i.get("name")) for i in context.inventory if isinstance(i, dict)} | {str(i.get("id") or i.get("name")) for i in self.core_game.get("items", []) if isinstance(i, dict)}
        for ch in repaired.get("inventory_changes", []) if isinstance(repaired.get("inventory_changes"), list) else []:
            item = ch.get("item") or {"id": ch.get("item_id"), "name": ch.get("name")} if isinstance(ch, dict) else {}
            iid = str(item.get("id") or item.get("name") or "") if isinstance(item, dict) else str(item or "")
            if iid and iid not in valid_items and not bool(ch.get("improvised")):
                errors.append(f"invalid_item_id:{iid}")
        if errors:
            self.last_debug["validation_errors"] = list(dict.fromkeys([e for e in self.last_debug.get("validation_errors", []) if e] + errors))
        return repaired, errors, repair

    def apply_gm_decision(self, decision: dict[str, Any], state: Any) -> dict[str, Any]:
        applied: dict[str, Any] = {"scene": False, "npc": [], "inventory": [], "journal": [], "memory": False, "turn_summary": ""}
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
            scene.update(decision["scene_updates"]); applied["scene"] = True
        if isinstance(decision.get("npc_state_updates"), list):
            known = {str(e.get("actor_id") or e.get("id") or e.get("name")): e for e in scene.get("entities", []) if isinstance(e, dict)}
            for upd in decision["npc_state_updates"]:
                if not isinstance(upd, dict): continue
                key = str(upd.get("actor_id") or upd.get("id") or upd.get("name") or "")
                if key in known:
                    known[key].update({k: v for k, v in upd.items() if k not in {"actor_id", "id", "name"}}); applied["npc"].append(key)
        inv_state = getattr(runtime, "inventory_state", {})
        inv = inv_state.setdefault("entries", []) if isinstance(inv_state, dict) else []
        for ch in decision.get("inventory_changes", []) if isinstance(decision.get("inventory_changes"), list) else []:
            if not isinstance(ch, dict): continue
            action = str(ch.get("action", ch.get("type", ""))).lower()
            item = ch.get("item") or {"id": ch.get("item_id"), "name": ch.get("name") or ch.get("item_id")}
            iid = str(item.get("id") or item.get("name") or "").strip() if isinstance(item, dict) else str(item)
            if action in {"add", "gain", "added"} and iid:
                inv.append(item if isinstance(item, dict) else {"id": iid, "name": iid}); applied["inventory"].append(f"add:{iid}")
            elif action in {"remove", "drop", "consume"} and iid:
                before = len(inv); inv[:] = [e for e in inv if str(e.get("id") or e.get("name")) != iid]
                if len(inv) != before: applied["inventory"].append(f"remove:{iid}")
        quest_updates = list(decision.get("quest_updates", []) or []) + list(decision.get("journal_updates", []) or [])
        for upd in quest_updates:
            if not isinstance(upd, dict): continue
            qid = str(upd.get("quest_id") or upd.get("id") or upd.get("title") or "gm_note")
            status = str(upd.get("status") or upd.get("state") or "updated")
            if hasattr(state, "quests") and qid in getattr(state, "quests", {}):
                state.quests[qid].status = status
            runtime.quest_state[qid] = status
            runtime.campaign_events.append({"type": "quest_update", "quest_id": qid, "status": status, "note": upd.get("note") or upd.get("description") or ""})
            applied["journal"].append(qid)
        notes = decision.get("memory_notes")
        if notes:
            runtime.campaign_events = list(getattr(runtime, "campaign_events", []) or []) + [{"type": "gm_memory", "notes": notes}]
            applied["memory"] = True
        applied["turn_summary"] = str(decision.get("action_interpretation") or "").strip() or narration[:120]
        scene_state["last_turn_summary"] = applied["turn_summary"]
        self.last_debug["applied_changes"] = applied
        return applied
