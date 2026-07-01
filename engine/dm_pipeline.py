"""Authoritative V2 DM input pipeline.

This module is intentionally deterministic. It centralizes intent extraction,
bootstrap readiness checks, and routing decisions before narration or turn
simulation are allowed to run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from engine.dm_reasoning import analyze_player_input


Mode = Literal["ic", "ooc"]


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


def _main_sheet(state: Any) -> Any | None:
    for sheet in getattr(state, "character_sheets", []) or []:
        if getattr(sheet, "sheet_type", "") == "main_character":
            return sheet
    return None


def _missing_required(state: Any, facts: ExtractedFacts) -> list[str]:
    sheet = _main_sheet(state)
    name = facts.character_name or getattr(sheet, "name", "") or getattr(getattr(state, "player", None), "name", "")
    role = facts.role or getattr(sheet, "role", "") or getattr(getattr(state, "player", None), "char_class", "")
    missing: list[str] = []
    if not str(name or "").strip() or str(name).strip().lower() == "adventurer":
        missing.append("character_name")
    if not str(role or "").strip() or str(role).strip().lower() == "adventurer":
        missing.append("role")
    return missing


def understand(runtime: Any, text: str, mode: str) -> tuple[DMInput, DMUnderstanding, DMStateAssessment]:
    state = runtime.session.state
    normalized_mode: Mode = "ooc" if str(mode).lower() == "ooc" else "ic"
    location = state.locations.get(state.current_location_id)
    dm_input = DMInput(
        raw_text=str(text or "").strip(),
        mode=normalized_mode,
        campaign_id=str(state.campaign_id),
        startup_state=str(getattr(state, "startup_state", "ready") or "ready"),
        current_turn=int(getattr(state, "turn_count", 0) or 0),
        active_character_name=str(getattr(state.player, "name", "") or ""),
        current_location=str(getattr(location, "name", "") or getattr(state.world_meta, "starting_location_name", "") or ""),
    )
    intent = analyze_player_input(dm_input.raw_text, mode=normalized_mode, campaign_state=state)
    facts = ExtractedFacts(
        character_name=intent.character_name,
        role=intent.role,
        appearance=", ".join(intent.appearance) if intent.appearance else None,
        background=dm_input.raw_text,
        specific_abilities=list(dict.fromkeys(intent.claimed_abilities)),
        broad_ability_claims=list(dict.fromkeys(intent.broad_power_claims)),
        world_clues=list(dict.fromkeys(intent.world_clues)),
        questions=list(dict.fromkeys(intent.explicit_questions)),
    )
    understanding = DMUnderstanding(
        primary_intent=intent.primary_intent,
        confidence=float(intent.confidence),
        spoken_text=intent.spoken_text,
        is_question=bool(intent.explicit_questions),
        is_reflection=intent.primary_intent == "reflection",
        is_dialogue=intent.primary_intent == "spoken_dialogue",
        is_character_intro=intent.primary_intent == "character_introduction",
        is_setup_answer=dm_input.startup_state in {"character_creation", "ability_setup_followup", "world_setup_followup"},
        is_ooc=normalized_mode == "ooc",
        extracted_facts=facts,
    )
    missing = _missing_required(state, facts)
    ability_needed = bool(facts.broad_ability_claims and not facts.specific_abilities)
    startup_ready = not missing and not ability_needed
    assessment = DMStateAssessment(
        missing_required_fields=missing,
        startup_ready=startup_ready,
        ability_setup_needed=ability_needed,
        should_advance_turn=normalized_mode == "ic" and dm_input.startup_state == "ready" and intent.primary_intent == "action",
        should_generate_opening_scene=dm_input.startup_state != "ready" and startup_ready,
        should_use_normal_turn_engine=normalized_mode == "ic" and dm_input.startup_state == "ready" and intent.primary_intent == "action",
        should_answer_from_state=normalized_mode == "ooc" or intent.primary_intent in {"reflection", "information_request"},
        should_create_events=bool(facts.specific_abilities),
        should_update_character=bool(facts.character_name or facts.role or facts.appearance),
        should_update_inventory=bool(facts.role),
        should_update_world=dm_input.startup_state != "ready",
    )
    return dm_input, understanding, assessment


def process_player_input(runtime: Any, text: str, mode: str) -> DMPipelineResult:
    dm_input, understanding, assessment = understand(runtime, text, mode)
    state = runtime.session.state
    turn_before = int(getattr(state, "turn_count", 0) or 0)
    startup_before = dm_input.startup_state
    branch = "normal_turn_pipeline"
    blocked_reason = ""

    if dm_input.mode == "ooc":
        branch = "ooc_state_answer"
        response = runtime.handle_ooc_input(dm_input.raw_text)
    elif startup_before == "ability_setup_followup":
        branch = "startup_ability_setup_followup"
        response = runtime._handle_ability_setup_followup(dm_input.raw_text, __import__("time").perf_counter(), __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
    elif startup_before == "character_creation":
        branch = "startup_character_creation"
        response = runtime._handle_character_creation_answer(dm_input.raw_text, __import__("time").perf_counter(), __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
        if not assessment.startup_ready:
            blocked_reason = "bootstrap_missing_fields_or_ability_followup"
    elif understanding.is_reflection or understanding.is_dialogue or understanding.primary_intent == "information_request":
        branch = f"ic_{understanding.primary_intent}_non_turn"
        response = runtime._handle_reasoned_non_turn_input(dm_input.raw_text, __import__("time").perf_counter(), __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
        if response is None:
            branch = "ic_clarification"
            narrative = "What are you trying to do?"
            runtime._append_message("player", dm_input.raw_text, persist=False)
            runtime._append_message("narrator", narrative, persist=False)
            runtime._flush_history_store()
            runtime.save_active_campaign(runtime.session.active_slot)
            response = {"narrative": narrative, "system_messages": [], "messages": [{"type": "narrator", "text": narrative}], "should_exit": False, "metadata": {"mode": "clarification"}, "state": runtime.serialize_state()}
            blocked_reason = "non_turn_input_not_action"
    else:
        if understanding.primary_intent in {"unknown", "ooc_instruction"}:
            branch = "ic_clarification"
            narrative = "I’m not sure whether you mean that in character or out of character. Do you want your character to do something, or are you asking me as the DM?"
            runtime._append_message("player", dm_input.raw_text, persist=False)
            runtime._append_message("narrator", narrative, persist=False)
            runtime._flush_history_store()
            runtime.save_active_campaign(runtime.session.active_slot)
            response = {"narrative": narrative, "system_messages": [], "messages": [{"type": "narrator", "text": narrative}], "should_exit": False, "metadata": {"mode": "clarification"}, "state": runtime.serialize_state()}
            blocked_reason = "unknown_intent"
        else:
            response = runtime.handle_player_input(dm_input.raw_text)

    turn_after = int(getattr(state, "turn_count", 0) or 0)
    startup_after = str(getattr(state, "startup_state", "ready") or "ready")
    created_events = []
    try:
        created_events = [event for event in state.structured_state.runtime.campaign_events if isinstance(event, dict) and event.get("type") == "ability_suggested"]
    except Exception:
        created_events = []
    debug = {
        "input_mode": dm_input.mode,
        "raw_text": dm_input.raw_text,
        "startup_state_before": startup_before,
        "startup_state_after": startup_after,
        "primary_intent": understanding.primary_intent,
        "secondary_intents": understanding.secondary_intents,
        "extracted_facts": asdict(understanding.extracted_facts),
        "missing_required_fields": assessment.missing_required_fields,
        "startup_ready": assessment.startup_ready,
        "branch_taken": branch,
        "normal_turn_pipeline_used": branch == "normal_turn_pipeline",
        "opening_scene_started": startup_before != "ready" and startup_after == "ready",
        "turn_before": turn_before,
        "turn_after": turn_after,
        "campaign_events_created": len(created_events),
        "messages_appended": len(response.get("messages", [])) if isinstance(response, dict) else 0,
        "blocked_reason": blocked_reason,
    }
    runtime._set_last_turn_routing(**debug)
    return DMPipelineResult(
        messages_to_append=response.get("messages", []) if isinstance(response, dict) else [],
        campaign_events_created=created_events,
        turn_incremented=turn_after > turn_before,
        branch=branch,
        debug_trace=debug,
        response=response,
    )
