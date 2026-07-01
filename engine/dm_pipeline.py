"""Authoritative V2 DM input pipeline.

This module is intentionally deterministic. It centralizes intent extraction,
bootstrap readiness checks, and routing decisions before narration or turn
simulation are allowed to run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import time
from typing import Any, Literal

from engine.character_sheets import CharacterSheet
from engine.dm_reasoning import analyze_player_input


Mode = Literal["ic", "ooc"]
_PLACEHOLDERS = {"", "unknown", "untitled world", "starting area", "adventurer"}
_CLARIFICATION = "I’m not sure what you want your character to do. Do you want to act in the scene, ask me something out of character, or clarify your setup?"


@dataclass
class ExtractedFacts:
    character_name: str | None = None
    role: str | None = None
    race: str | None = None
    appearance: str | None = None
    background: str | None = None
    goals: str | None = None
    specific_abilities: list[str] = field(default_factory=list)
    broad_ability_claims: list[str] = field(default_factory=list)
    inventory_claims: list[str] = field(default_factory=list)
    world_clues: list[str] = field(default_factory=list)
    location_clues: list[str] = field(default_factory=list)
    tone_clues: list[str] = field(default_factory=list)
    relationship_claims: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


@dataclass
class DMInput:
    raw_text: str
    mode: Mode
    campaign_id: str
    startup_state: str
    current_turn: int
    active_character_name: str
    current_location: str


@dataclass
class DMUnderstanding:
    primary_intent: str
    secondary_intents: list[str] = field(default_factory=list)
    confidence: float = 0.65
    spoken_text: str | None = None
    target: str | None = None
    is_question: bool = False
    is_reflection: bool = False
    is_dialogue: bool = False
    is_character_intro: bool = False
    is_setup_answer: bool = False
    is_ooc: bool = False
    extracted_facts: ExtractedFacts = field(default_factory=ExtractedFacts)


@dataclass
class DMStateAssessment:
    missing_required_fields: list[str] = field(default_factory=list)
    startup_ready: bool = False
    ability_setup_needed: bool = False
    should_advance_turn: bool = False
    should_generate_opening_scene: bool = False
    should_use_normal_turn_engine: bool = False
    should_answer_from_state: bool = False
    should_create_events: bool = False
    should_update_character: bool = False
    should_update_inventory: bool = False
    should_update_world: bool = False


@dataclass
class DMDecision:
    branch: str
    response_kind: str
    followup_question: str | None = None
    ooc_answer: str | None = None
    state_updates: dict[str, Any] = field(default_factory=dict)
    campaign_events: list[dict[str, Any]] = field(default_factory=list)
    narration_prompt_context: dict[str, Any] = field(default_factory=dict)
    debug_notes: list[str] = field(default_factory=list)


@dataclass
class DMPipelineResult:
    messages_to_append: list[dict[str, Any]] = field(default_factory=list)
    state_updates_applied: dict[str, Any] = field(default_factory=dict)
    campaign_events_created: list[dict[str, Any]] = field(default_factory=list)
    turn_incremented: bool = False
    autosave_needed: bool = True
    branch: str = "unknown"
    debug_trace: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] | None = None


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _is_placeholder(value: Any) -> bool:
    return _clean(value).lower() in _PLACEHOLDERS


def _title(value: str) -> str:
    return _clean(value).title()


def _main_sheet(state: Any) -> Any | None:
    for sheet in getattr(state, "character_sheets", []) or []:
        if getattr(sheet, "sheet_type", "") == "main_character":
            return sheet
    return None


def get_or_create_main_character_sheet(state: Any) -> CharacterSheet:
    sheet = _main_sheet(state)
    if sheet is None:
        sheet = CharacterSheet(id="sheet_main", name=_clean(getattr(state.player, "name", "")) or "Adventurer", sheet_type="main_character")
        state.character_sheets.append(sheet)
    return sheet


def _missing_required(state: Any, facts: ExtractedFacts) -> list[str]:
    sheet = _main_sheet(state)
    name = facts.character_name or getattr(sheet, "name", "") or getattr(getattr(state, "player", None), "name", "")
    role = facts.role or getattr(sheet, "role", "") or getattr(getattr(state, "player", None), "char_class", "")
    missing: list[str] = []
    if _is_placeholder(name):
        missing.append("character_name")
    if _is_placeholder(role):
        missing.append("role")
    return missing


def set_bootstrap_missing_fields(state: Any, missing: list[str]) -> None:
    state.bootstrap_missing_fields = list(dict.fromkeys(missing))


def merge_character_facts(state: Any, facts: ExtractedFacts) -> CharacterSheet:
    sheet = get_or_create_main_character_sheet(state)
    if facts.character_name:
        sheet.name = _title(facts.character_name)
        state.player.name = sheet.name
    elif not _is_placeholder(getattr(sheet, "name", "")):
        state.player.name = sheet.name
    if facts.role:
        sheet.role = _title(facts.role)
        state.player.char_class = sheet.role
    elif facts.character_name and str(getattr(state, "startup_state", "ready")) == "character_creation":
        # A name-only bootstrap answer must not inherit create_campaign defaults
        # such as Ranger and accidentally start the opening scene.
        sheet.role = ""
        state.player.char_class = ""
    elif not _is_placeholder(getattr(sheet, "role", "")):
        state.player.char_class = sheet.role
    if facts.appearance:
        sheet.description = facts.appearance
    notes = []
    if facts.background:
        notes.append(f"Player introduction: {facts.background}")
    if facts.broad_ability_claims:
        notes.append(f"Broad ability claims: {', '.join(facts.broad_ability_claims)}")
    if facts.goals:
        notes.append(f"Goals: {facts.goals}")
    existing = _clean(getattr(sheet, "notes", ""))
    sheet.notes = "\n".join(dict.fromkeys([p for p in [existing, *notes] if p]))
    return sheet


def infer_bootstrap_world_metadata(state: Any, facts: ExtractedFacts) -> None:
    sheet = _main_sheet(state)
    blob = " ".join([_clean(getattr(state, "campaign_name", "")), _clean(getattr(state.world_meta, "world_theme", "")), _clean(getattr(state.world_meta, "premise", "")), _clean(facts.role), _clean(getattr(sheet, "role", "")), " ".join(facts.broad_ability_claims), " ".join(facts.world_clues)]).lower()
    if _is_placeholder(getattr(state.world_meta, "world_name", "")):
        state.world_meta.world_name = "The Arcane Realm" if any(t in blob for t in ("pyromancer", "fire", "magic", "spell", "fantasy")) else "The New World"
    if _is_placeholder(getattr(state.world_meta, "starting_location_name", "")):
        state.world_meta.starting_location_name = "Ashen Crossroads" if any(t in blob for t in ("pyromancer", "fire", "ember")) else ("Old Gate" if any(t in blob for t in ("magic", "fantasy", "spell")) else "Arrival Clearing")
    location = state.locations.get(state.current_location_id)
    if location is not None:
        location.name = state.world_meta.starting_location_name
        location.description = f"{state.world_meta.starting_location_name} in {state.world_meta.world_name}."
    scene_state = state.structured_state.runtime.scene_state if isinstance(state.structured_state.runtime.scene_state, dict) else {}
    scene_state["location_name"] = state.world_meta.starting_location_name
    state.structured_state.runtime.scene_state = scene_state


def create_ability_proposal_events(state: Any, abilities: list[str], reason: str) -> list[dict[str, Any]]:
    runtime = state.structured_state.runtime
    if not isinstance(runtime.campaign_events, list):
        runtime.campaign_events = []
    created: list[dict[str, Any]] = []
    for ability in dict.fromkeys([_clean(a) for a in abilities if _clean(a)]):
        normalized = re.sub(r"[^a-z0-9]+", "", ability.lower())
        if any(e.get("type") == "ability_suggested" and re.sub(r"[^a-z0-9]+", "", _clean(e.get("payload", {}).get("name") or e.get("title")).lower()) == normalized for e in runtime.campaign_events if isinstance(e, dict)):
            continue
        event = {"id": f"pipeline_ability_{int(time.time()*1000)}_{len(runtime.campaign_events)}", "type": "ability_suggested", "title": ability, "description": f"Player proposed {ability} as a starting ability. {reason}", "status": "pending", "payload": {"name": ability, "category": "spell", "tags": ["starter", "dm_pipeline"], "source_metadata": {"source": "dm_pipeline", "reason": reason}}}
        runtime.campaign_events.append(event)
        created.append(event)
    return created


def _accepted_abilities(state: Any) -> list[str]:
    names: list[str] = []
    runtime = state.structured_state.runtime
    for entry in getattr(runtime, "spellbook", []) or []:
        if isinstance(entry, dict): names.append(_clean(entry.get("name")))
    sheet = _main_sheet(state)
    for ability in getattr(sheet, "abilities", []) or []:
        names.append(_clean(getattr(ability, "name", ability if isinstance(ability, str) else "")))
    return [n for n in dict.fromkeys(names) if n]


def _pending_ability_names(state: Any) -> list[str]:
    return [_clean(e.get("payload", {}).get("name") or e.get("title")) for e in state.structured_state.runtime.campaign_events if isinstance(e, dict) and e.get("type") == "ability_suggested" and e.get("status", "pending") == "pending" and _clean(e.get("payload", {}).get("name") or e.get("title"))]


def _response(runtime: Any, text: str, narrative: str, branch: str, response_kind: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if text:
        runtime._append_message("player", text, persist=False)
    runtime._append_message("narrator", narrative, persist=False)
    runtime._flush_history_store()
    runtime.save_active_campaign(runtime.session.active_slot)
    meta = {"mode": response_kind, "branch": branch}
    if metadata: meta.update(metadata)
    return {"narrative": narrative, "system_messages": [], "messages": [{"type": "narrator", "text": narrative}], "should_exit": False, "metadata": meta, "state": runtime.serialize_state()}


def _opening_scene(state: Any, sheet: Any) -> str:
    name = _clean(sheet.name or state.player.name) or "Adventurer"
    role = _clean(sheet.role or state.player.char_class) or "adventurer"
    world = _clean(state.world_meta.world_name) or "The New World"
    location = _clean(state.world_meta.starting_location_name) or "Arrival Clearing"
    appearance = f", {sheet.description}" if _clean(getattr(sheet, "description", "")) else ""
    hook = "A smoldering courier-scroll waits beside a scorched milestone." if "pyromancer" in role.lower() or "ash" in location.lower() else "A local messenger clutches news that cannot wait."
    return f"{name}, a {role}{appearance}, arrives at {location} in {world}. {hook} What do you do?"


def _followup_for_ability(state: Any) -> str:
    name = _clean(getattr(_main_sheet(state), "name", "") or state.player.name) or "your character"
    role = _clean(getattr(_main_sheet(state), "role", "") or state.player.char_class).lower()
    if "pyromancer" in role or "fire" in role:
        return f"What fire spells does {name} already know? You can list a few, or describe his style of pyromancy."
    return f"What spells or signature abilities does {name} already know? You can list a few, or describe the style."


def understand(runtime: Any, text: str, mode: str) -> tuple[DMInput, DMUnderstanding, DMStateAssessment]:
    state = runtime.session.state
    normalized_mode: Mode = "ooc" if str(mode).lower() == "ooc" else "ic"
    location = state.locations.get(state.current_location_id)
    dm_input = DMInput(_clean(text), normalized_mode, str(state.campaign_id), str(getattr(state, "startup_state", "ready") or "ready"), int(getattr(state, "turn_count", 0) or 0), _clean(getattr(state.player, "name", "")), _clean(getattr(location, "name", "") or getattr(state.world_meta, "starting_location_name", "")))
    intent = analyze_player_input(dm_input.raw_text, mode=normalized_mode, campaign_state=state)
    abilities = [a for a in dict.fromkeys(intent.claimed_abilities) if " and " not in a.lower()]
    facts = ExtractedFacts(character_name=intent.character_name, role=intent.role, appearance=", ".join(intent.appearance) if intent.appearance else None, background=dm_input.raw_text, specific_abilities=abilities, broad_ability_claims=list(dict.fromkeys(intent.broad_power_claims)), world_clues=list(dict.fromkeys(intent.world_clues)), questions=list(dict.fromkeys(intent.explicit_questions)))
    understanding = DMUnderstanding(primary_intent=intent.primary_intent, confidence=float(intent.confidence), spoken_text=intent.spoken_text, is_question=bool(intent.explicit_questions), is_reflection=intent.primary_intent == "reflection", is_dialogue=intent.primary_intent == "spoken_dialogue", is_character_intro=intent.primary_intent == "character_introduction", is_setup_answer=dm_input.startup_state in {"character_creation", "ability_setup_followup", "world_setup_followup"}, is_ooc=normalized_mode == "ooc", extracted_facts=facts)
    missing = _missing_required(state, facts)
    ability_needed = bool(facts.broad_ability_claims and not facts.specific_abilities)
    startup_ready = not missing and not ability_needed
    assessment = DMStateAssessment(missing_required_fields=missing, startup_ready=startup_ready, ability_setup_needed=ability_needed, should_advance_turn=normalized_mode == "ic" and dm_input.startup_state == "ready" and intent.primary_intent == "action", should_generate_opening_scene=dm_input.startup_state != "ready" and startup_ready, should_use_normal_turn_engine=normalized_mode == "ic" and dm_input.startup_state == "ready" and intent.primary_intent == "action", should_answer_from_state=normalized_mode == "ooc" or intent.primary_intent in {"reflection", "information_request"}, should_create_events=bool(facts.specific_abilities), should_update_character=bool(facts.character_name or facts.role or facts.appearance), should_update_world=dm_input.startup_state != "ready")
    return dm_input, understanding, assessment


def _handle_startup(runtime: Any, dm_input: DMInput, understanding: DMUnderstanding, assessment: DMStateAssessment) -> tuple[str, str, list[dict[str, Any]], dict[str, Any]]:
    state = runtime.session.state
    facts = understanding.extracted_facts
    if dm_input.startup_state == "ability_setup_followup":
        created = create_ability_proposal_events(state, facts.specific_abilities or [_title(p) for p in re.split(r",| and ", dm_input.raw_text) if _clean(p)], "ability setup follow-up")
        sheet = merge_character_facts(state, facts)
        infer_bootstrap_world_metadata(state, facts)
        state.startup_state = "ready"; state.bootstrap_complete = True; set_bootstrap_missing_fields(state, [])
        narrative = _opening_scene(state, sheet)
        return "startup_ability_setup_followup", narrative, created, {"startup_flow": "ability_setup_completed"}
    sheet = merge_character_facts(state, facts)
    missing = _missing_required(state, ExtractedFacts())
    set_bootstrap_missing_fields(state, missing)
    state.bootstrap_complete = False
    if "role" in missing:
        state.startup_state = "character_creation"
        name = _clean(sheet.name or state.player.name) or "your character"
        return "startup_character_creation", f"Got it. Your name is {name}. What class, role, or concept should this adventure be built around?", [], {"startup_flow": "character_creation_missing_role"}
    if facts.broad_ability_claims and not facts.specific_abilities:
        state.startup_state = "ability_setup_followup"
        return "startup_character_creation", _followup_for_ability(state), [], {"startup_flow": "character_creation_needs_followup"}
    created = create_ability_proposal_events(state, facts.specific_abilities, "complete character introduction")
    infer_bootstrap_world_metadata(state, facts)
    state.startup_state = "ready"; state.bootstrap_complete = True; set_bootstrap_missing_fields(state, [])
    return "startup_character_creation", _opening_scene(state, sheet), created, {"startup_flow": "character_creation_completed"}


def _ooc_answer(state: Any, text: str) -> str:
    lower = text.lower(); sheet = _main_sheet(state); name = _clean(getattr(sheet, "name", "") or state.player.name) or "Your character"; role = _clean(getattr(sheet, "role", "") or state.player.char_class)
    pending = _pending_ability_names(state); accepted = _accepted_abilities(state)
    if "spell" in lower or "abilit" in lower:
        if accepted: return f"OOC: {name}'s accepted spells/abilities are: {', '.join(accepted)}."
        extra = f" Pending spell proposals: {', '.join(pending)}." if pending else ""
        return f"OOC: {name} does not have any accepted spells yet. If you already know starting spells, list them and I’ll create proposals for you to accept.{extra}"
    startup = _clean(getattr(state, "startup_state", "ready"))
    if startup != "ready":
        missing = getattr(state, "bootstrap_missing_fields", []) or []
        need = "role or concept" if "role" in missing else (", ".join(missing) or "the pending setup answer")
        return f"OOC: You’re setting up the campaign. I know your name is {name}, but I still need your {need}. Pending Campaign Events: {len(pending)}. Suggested next step: answer the setup question."
    loc = _clean(getattr(state.world_meta, "starting_location_name", "")) or "the current scene"
    return f"OOC: Campaign status — {state.campaign_name}. {name}{', a ' + role if role else ''} is at {loc}. Pending Campaign Events: {len(pending)}. Suggested next step: describe what you do next."


def _reflection_answer(state: Any, text: str) -> str:
    lower = text.lower(); name = _clean(getattr(_main_sheet(state), "name", "") or state.player.name) or "Your character"
    if "spell" in lower or "abilit" in lower:
        accepted = _accepted_abilities(state); pending = _pending_ability_names(state)
        if accepted: return f"{name} reviews accepted spells and abilities: {', '.join(accepted)}."
        return f"{name} searches his memory, but no spells have been accepted yet." + (" There may be pending spell proposals in Campaign Events." if pending else "")
    if "inventory" in lower:
        inv = getattr(state.player, "inventory", []) or getattr(state.structured_state.runtime, "inventory", []) or []
        return f"{name} checks his inventory: {', '.join(inv) if inv else 'nothing notable has been established yet'}."
    if "quest" in lower or "goal" in lower or "happened" in lower or "remember" in lower:
        memories = list(getattr(state, "recent_memory", []) or [])[-3:]
        return f"{name} reflects on what is known: {'; '.join(memories) if memories else 'no quests or recent events have been established yet'}."
    return _CLARIFICATION


def _dialogue_answer(state: Any, text: str, spoken: str | None) -> str:
    said = _clean(spoken) or _clean(text).strip('"')
    npcs = [n for n in getattr(state, "npcs", {}).values() if getattr(n, "location_id", None) == getattr(state, "current_location_id", None)] if isinstance(getattr(state, "npcs", {}), dict) else []
    if npcs:
        return f"You say, ‘{said}’ {getattr(npcs[0], 'name', 'Someone nearby')} turns toward you, ready to answer."
    return f"You say, ‘{said}’ No one nearby has been established yet. Who are you speaking to?"


def process_player_input(runtime: Any, text: str, mode: str) -> DMPipelineResult:
    dm_input, understanding, assessment = understand(runtime, text, mode)
    state = runtime.session.state
    turn_before = int(getattr(state, "turn_count", 0) or 0); startup_before = dm_input.startup_state; bootstrap_before = bool(getattr(state, "bootstrap_complete", startup_before == "ready")); events_before = len(getattr(state.structured_state.runtime, "campaign_events", []) or [])
    branch = "normal_turn_pipeline"; blocked_reason = ""; created: list[dict[str, Any]] = []
    if dm_input.mode == "ooc":
        branch = "ooc_state_answer"; narrative = _ooc_answer(state, dm_input.raw_text); response_kind = "ooc_state_answer"; blocked_reason = "ooc_input"
        response = _response(runtime, dm_input.raw_text, narrative, branch, response_kind)
    elif startup_before in {"character_creation", "ability_setup_followup", "world_setup_followup"}:
        branch, narrative, created, meta = _handle_startup(runtime, dm_input, understanding, assessment); response_kind = "startup"; blocked_reason = "startup_not_ready" if getattr(state, "startup_state", "ready") != "ready" else ""
        response = _response(runtime, dm_input.raw_text, narrative, branch, response_kind, meta)
    elif understanding.is_reflection or understanding.primary_intent == "information_request" or any(phrase in dm_input.raw_text.lower() for phrase in ("think about", "review my", "check my inventory", "remember what happened", "look over my quests")):
        branch = f"ic_{understanding.primary_intent}_state_answer"; blocked_reason = "non_turn_state_answer"; response_kind = "state_answer"
        response = _response(runtime, dm_input.raw_text, _reflection_answer(state, dm_input.raw_text), branch, response_kind)
    elif understanding.is_dialogue:
        branch = "ic_spoken_dialogue"; blocked_reason = "dialogue_needs_target"; response_kind = "dialogue"
        response = _response(runtime, dm_input.raw_text, _dialogue_answer(state, dm_input.raw_text, understanding.spoken_text), branch, response_kind)
    elif understanding.primary_intent in {"unknown", "ooc_instruction", "reflection"} or dm_input.raw_text.lower().strip(" .!") in {"seriously", "huh", "what"}:
        branch = "ic_clarification"; blocked_reason = "unknown_intent"; response_kind = "clarification"
        response = _response(runtime, dm_input.raw_text, _CLARIFICATION, branch, response_kind)
    elif not (dm_input.mode == "ic" and startup_before == "ready" and bool(getattr(state, "bootstrap_complete", True)) and understanding.primary_intent in {"action", "combat", "social_action", "exploration"} and not assessment.missing_required_fields):
        branch = "ic_clarification"; blocked_reason = "normal_turn_gate_blocked"; response_kind = "clarification"
        response = _response(runtime, dm_input.raw_text, _CLARIFICATION, branch, response_kind)
    else:
        response = runtime.handle_player_input(dm_input.raw_text); response_kind = "normal_turn"
    turn_after = int(getattr(state, "turn_count", 0) or 0); startup_after = str(getattr(state, "startup_state", "ready") or "ready"); bootstrap_after = bool(getattr(state, "bootstrap_complete", startup_after == "ready")); events_after = len(getattr(state.structured_state.runtime, "campaign_events", []) or [])
    if not created:
        created = list((getattr(state.structured_state.runtime, "campaign_events", []) or [])[events_before:events_after])
    debug = {"input_mode": dm_input.mode, "raw_text": dm_input.raw_text, "startup_state_before": startup_before, "startup_state_after": startup_after, "bootstrap_complete_before": bootstrap_before, "bootstrap_complete_after": bootstrap_after, "primary_intent": understanding.primary_intent, "secondary_intents": understanding.secondary_intents, "extracted_facts": asdict(understanding.extracted_facts), "missing_required_fields": getattr(state, "bootstrap_missing_fields", assessment.missing_required_fields), "startup_ready": startup_after == "ready" and bootstrap_after, "branch_taken": branch, "normal_turn_pipeline_used": branch == "normal_turn_pipeline", "opening_scene_started": startup_before != "ready" and startup_after == "ready", "turn_before": turn_before, "turn_after": turn_after, "campaign_events_created": len(created), "messages_appended": len(response.get("messages", [])) if isinstance(response, dict) else 0, "blocked_reason": blocked_reason, "response_kind": response_kind}
    runtime._set_last_turn_routing(**debug)
    return DMPipelineResult(messages_to_append=response.get("messages", []) if isinstance(response, dict) else [], campaign_events_created=created, turn_incremented=turn_after > turn_before, branch=branch, debug_trace=debug, response=response)
