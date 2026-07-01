"""Centralized heuristic DM reasoning layer.

The functions here intentionally avoid model calls.  They classify player input
before startup or turn handling so runtime code can decide whether to advance
canon, answer OOC, ask setup follow-ups, or pass an action to narration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


ROLE_VOCABULARY = (
    "pyromancer", "necromancer", "archmage", "mage", "wizard", "sorcerer", "witch", "warlock",
    "ranger", "knight", "warrior", "soldier", "veteran", "veteran soldier", "rogue", "thief",
    "assassin", "cleric", "priest", "paladin", "druid", "hunter", "pilot", "captain", "engineer",
    "medic", "noble", "merchant", "bard", "fighter", "monk", "barbarian", "gunslinger", "detective",
    "healer", "swordsman", "master swordsman",
)

APPEARANCE_TERMS = (
    "bald", "muscular", "tall", "short", "slender", "broad", "scarred", "pale", "old", "young",
    "armored", "scarred", "robed",
)

SPECIFIC_ABILITY_HINTS = (
    "fireball", "fire bolt", "firebolt", "flame shield", "ember step", "healing light", "teleport",
    "chain lightning", "flamestrike",
)


@dataclass
class DMIntent:
    raw_text: str
    input_mode: str = "ic"
    primary_intent: str = "unknown"
    spoken_text: str | None = None
    character_name: str | None = None
    role: str | None = None
    appearance: list[str] = field(default_factory=list)
    claimed_abilities: list[str] = field(default_factory=list)
    broad_power_claims: list[str] = field(default_factory=list)
    world_clues: list[str] = field(default_factory=list)
    explicit_questions: list[str] = field(default_factory=list)
    needs_followup: bool = False
    followup_topic: str | None = None
    confidence: float = 0.65

    @property
    def intent(self) -> str:
        if self.primary_intent == "character_introduction" and self.broad_power_claims:
            return "ability_setup_followup" if self.needs_followup else "character_setup_followup"
        return self.primary_intent

    @property
    def claimed_powers(self) -> list[str]:
        return self.broad_power_claims

    @property
    def specific_abilities(self) -> list[str]:
        return self.claimed_abilities

    @property
    def needs_setup_clarification(self) -> bool:
        return self.needs_followup

    @property
    def clarification_topic(self) -> str:
        return self.followup_topic or ""

    def to_inferred_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"background": re.sub(r"\s+", " ", self.raw_text).strip(), "intent": self.primary_intent}
        if self.spoken_text:
            data["spoken_text"] = self.spoken_text
        if self.character_name:
            data["name"] = self.character_name
        if self.role:
            data["role"] = self.role
        if self.appearance:
            data["appearance"] = ", ".join(dict.fromkeys(self.appearance))
        if self.broad_power_claims:
            data["starting_claims"] = list(dict.fromkeys(self.broad_power_claims))
        if self.claimed_abilities:
            data["specific_abilities"] = list(dict.fromkeys(self.claimed_abilities))
        if self.world_clues:
            data["world_clues"] = list(dict.fromkeys(self.world_clues))
        if self.needs_followup:
            data["needs_ability_followup"] = self.followup_topic or "setup"
        return data


@dataclass
class DMPlan:
    should_advance_turn: bool = True
    should_generate_narration: bool = True
    should_start_opening_scene: bool = False
    should_ask_followup: bool = False
    followup_question: str | None = None
    character_updates: dict[str, Any] = field(default_factory=dict)
    inventory_updates: list[dict[str, Any]] = field(default_factory=list)
    campaign_event_proposals: list[dict[str, Any]] = field(default_factory=list)
    ooc_answer: str | None = None
    intent_notes: list[str] = field(default_factory=list)


@dataclass
class DMResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _title(text: str) -> str:
    return " ".join(part.capitalize() for part in str(text).split())


def _extract_quoted_dialogue(clean: str) -> str | None:
    match = re.search(r'\b(?:i\s+)?(?:say|tell|ask|shout|whisper)(?:\s+[^\"]{0,50})?\s*"([^"]*)"', clean, re.I)
    if match:
        return match.group(1).strip()
    match = re.fullmatch(r'\s*"([^"]+)"\s*', clean)
    return match.group(1).strip() if match else None


def analyze_player_input(text: str, mode: str = "ic", campaign_state: Any | None = None) -> DMIntent:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    lowered = clean.lower()
    intent = DMIntent(raw_text=clean, input_mode="ooc" if str(mode).lower() == "ooc" else "ic")

    spoken = _extract_quoted_dialogue(clean)
    if spoken is not None:
        intent.spoken_text = spoken
        intent.primary_intent = "spoken_dialogue"

    for pattern in (
        r"\bmy name is\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)",
        r"\bname\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)",
        r"\b(?:i am|i'm|im)\s+([A-Z][A-Za-z'\-]+)(?=\s*,|\s+an?\b|\s+the\b|\.|$)",
        r"\b(?:i am called|i'm called|call me)\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)",
    ):
        match = re.search(pattern, clean, re.I)
        if match:
            intent.character_name = match.group(1).strip(" .,;:")
            break

    for role in sorted(ROLE_VOCABULARY, key=len, reverse=True):
        if re.search(rf"\b{re.escape(role)}\b", lowered):
            intent.role = _title(role)
            break

    for term in APPEARANCE_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            intent.appearance.append(term)
    for pattern in (
        r"\b(?:black|brown|blonde|silver|white|red|blue|green|gray|grey) hair\b",
        r"\b(?:black|brown|blue|green|gray|grey|gold|amber|violet) eyes\b",
        r"\b(?:with|has|wearing|wears|clad in) [^,.;]*(?:hair|eyes|scar|scars|cloak|robes|armor)[^,.;]*",
    ):
        intent.appearance.extend(m.group(0).strip(" .,;:") for m in re.finditer(pattern, clean, re.I))

    broad_patterns = (
        r"\bfire spells\b", r"\bmany spells\b", r"\bpowerful magic\b", r"\bmaster of fire\b",
        r"\bpyromancy\b", r"\bmaster swordsman\b", r"\bmagical powers\b",
    )
    for pattern in broad_patterns:
        intent.broad_power_claims.extend(m.group(0).strip(" .,;:") for m in re.finditer(pattern, clean, re.I))
    if intent.role in {"Pyromancer", "Archmage", "Necromancer"} and intent.role.lower() not in [p.lower() for p in intent.broad_power_claims]:
        intent.broad_power_claims.append(intent.role.lower())

    list_match = re.search(r"\b(?:my\s+)?(?:spells?|abilities|powers)\s*(?:are|:|include|like|such as)\s+([^.;]+)", clean, re.I)
    if list_match:
        for item in re.split(r",|\band\b", list_match.group(1)):
            item = item.strip(" .;:")
            if len(item) >= 3:
                intent.claimed_abilities.append(_title(item))
    for pattern in (r"\bknows?\s+([a-z][a-z ]{2,30})", r"\bcan\s+(?:cast|summon)\s+([a-z][a-z ]{2,30})"):
        for m in re.finditer(pattern, clean, re.I):
            intent.claimed_abilities.append(_title(m.group(1).strip()))
    for ability in SPECIFIC_ABILITY_HINTS:
        if re.search(rf"\b{re.escape(ability)}\b", lowered):
            intent.claimed_abilities.append(_title(ability))

    for clue in ("awakening in a new world", "new world", "isekai", "summoned", "magical world", "magic", "space", "starship", "post-apocalyptic", "wastes"):
        if clue in lowered:
            intent.world_clues.append(clue)

    if "?" in clean or lowered.startswith(("what ", "who ", "where ", "when ", "why ", "how ")):
        intent.explicit_questions.append(clean)
    reflection = bool(re.search(r"\b(i think over|i remember|i check what i know|i review|what spells do i know|current spells)\b", lowered))
    if not reflection and re.fullmatch(r"seriously[.!?…\.]*", lowered):
        reflection = True
    if intent.input_mode == "ooc":
        intent.primary_intent = "ooc_question" if intent.explicit_questions or any(w in lowered for w in ("spells", "inventory", "sheet", "status", "what can")) else "ooc_instruction"
    elif reflection:
        intent.primary_intent = "reflection"
    elif intent.primary_intent == "unknown" and (intent.character_name or intent.role or intent.appearance):
        intent.primary_intent = "character_introduction"
    elif intent.primary_intent == "unknown" and intent.claimed_abilities:
        intent.primary_intent = "ability_definition"
    elif intent.primary_intent == "unknown" and intent.explicit_questions:
        intent.primary_intent = "information_request"
    elif intent.primary_intent == "unknown" and lowered.startswith(("i ", "look", "go ", "move ", "attack", "walk", "run")):
        intent.primary_intent = "action"

    if intent.broad_power_claims and not intent.claimed_abilities:
        intent.needs_followup = True
        intent.followup_topic = "spells" if any("spell" in p or intent.role in {"Pyromancer", "Archmage", "Mage", "Wizard"} for p in intent.broad_power_claims) else "abilities"
    return intent


def build_startup_plan(intent: DMIntent, campaign_state: Any | None = None) -> DMPlan:
    updates: dict[str, Any] = {}
    if intent.character_name:
        updates["name"] = intent.character_name
    if intent.role:
        updates["role"] = intent.role
    if intent.appearance:
        updates["appearance"] = ", ".join(dict.fromkeys(intent.appearance))
    plan = DMPlan(should_advance_turn=False, should_generate_narration=False, character_updates=updates, intent_notes=[intent.primary_intent])
    if intent.needs_followup:
        who = intent.character_name or getattr(getattr(campaign_state, "player", None), "name", "your character")
        topic = "fire spells" if any("fire" in p.lower() or p.lower() == "pyromancer" for p in intent.broad_power_claims) else "abilities"
        plan.should_ask_followup = True
        plan.followup_question = f"What {topic} does {who} already know? You can list a few, or describe their style."
        plan.campaign_event_proposals.append({"type": "ability_suggested", "title": "Starting Spell List", "reason": "Player described existing magic, but no specific spells were defined."})
    else:
        plan.should_start_opening_scene = True
    return plan


def _ability_names(state: Any) -> list[str]:
    runtime = getattr(getattr(state, "structured_state", None), "runtime", None)
    entries = list(getattr(runtime, "spellbook", []) or [])
    sheets = list(getattr(state, "character_sheets", []) or [])
    names = [str(e.get("name", "")).strip() for e in entries if isinstance(e, dict)]
    for sheet in sheets:
        for ability in getattr(sheet, "abilities", []) or []:
            names.append(str(getattr(ability, "name", "")).strip())
    return [n for n in dict.fromkeys(names) if n]


def build_ooc_response(intent: DMIntent, campaign_state: Any | None = None) -> DMResponse | None:
    lowered = intent.raw_text.lower()
    if not any(word in lowered for word in ("spell", "ability", "abilities")):
        return None
    names = _ability_names(campaign_state)
    player = getattr(getattr(campaign_state, "player", None), "name", "Your character") if campaign_state is not None else "Your character"
    role = getattr(getattr(campaign_state, "player", None), "char_class", "") if campaign_state is not None else ""
    if names:
        return DMResponse(f"OOC: {player}'s defined spells/abilities are: {', '.join(names)}.", {"handled_by": "dm_reasoning"})
    if str(role).lower() == "pyromancer":
        return DMResponse(f"OOC: {player} does not have any defined spells yet. Since {player} is a pyromancer, we should define a few starting fire spells. You can list them, or I can suggest a starter set.", {"handled_by": "dm_reasoning"})
    return DMResponse(f"OOC: {player} does not have any defined spells or abilities yet. You can list them, or I can help suggest a starter set.", {"handled_by": "dm_reasoning"})
