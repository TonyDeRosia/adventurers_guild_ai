"""LLM-first Game Master orchestrator for Core Game V1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.core_game import by_id, load_core_game

DECISION_KEYS = ("action_interpretation","skill_or_ability_used","difficulty","outcome","state_changes","npc_reactions","quest_updates","inventory_changes","memory_notes","narration")

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
        return GMContext(player_input, scene, character, character.get("classic_attributes", {}) or character, list(inventory_state.get("entries", [])), abilities, quests, npcs, intelligence_chunks or [], rules)

    def decide(self, player_input: str, state: Any, intelligence_chunks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        context = self.build_context(player_input, state, intelligence_chunks)
        if self._provider_available():
            raw = self._ask_provider(context)
            return self._normalize_decision(raw, context)
        return self._fallback_decision(context)

    def _provider_available(self) -> bool:
        return self.provider is not None and not getattr(self.provider, "is_null", False) and (hasattr(self.provider, "gm_decision") or hasattr(self.provider, "generate"))

    def _ask_provider(self, context: GMContext) -> Any:
        payload = {"schema": list(DECISION_KEYS), "context": context.__dict__}
        if hasattr(self.provider, "gm_decision"):
            return self.provider.gm_decision(payload)
        return self.provider.generate("Return a structured Core Game V1 GM decision.", payload)

    def _normalize_decision(self, raw: Any, context: GMContext) -> dict[str, Any]:
        data = raw if isinstance(raw, dict) else {"narration": str(raw or "")}
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
