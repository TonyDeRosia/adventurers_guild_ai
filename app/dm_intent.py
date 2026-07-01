"""Heuristic DM intent analysis for setup and turn input.

This module is intentionally small and deterministic so it can be replaced or
augmented by an LLM-backed analyzer later without changing runtime call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class DMIntent:
    raw_text: str
    intent: str = "unknown"
    spoken_text: str = ""
    character_name: str = ""
    role: str = ""
    appearance: str = ""
    claimed_powers: list[str] = field(default_factory=list)
    specific_abilities: list[str] = field(default_factory=list)
    world_clues: list[str] = field(default_factory=list)
    tone_clues: list[str] = field(default_factory=list)
    needs_setup_clarification: bool = False
    clarification_topic: str = ""

    def to_inferred_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"background": re.sub(r"\s+", " ", self.raw_text).strip(), "intent": self.intent}
        if self.spoken_text:
            data["spoken_text"] = self.spoken_text
        if self.character_name:
            data["name"] = self.character_name
        if self.role:
            data["role"] = self.role
        if self.appearance:
            data["appearance"] = self.appearance
        if self.claimed_powers:
            data["starting_claims"] = list(dict.fromkeys(self.claimed_powers))
        if self.specific_abilities:
            data["specific_abilities"] = list(dict.fromkeys(self.specific_abilities))
        if self.world_clues:
            data["world_clues"] = list(dict.fromkeys(self.world_clues))
        if self.tone_clues:
            data["tone_clues"] = list(dict.fromkeys(self.tone_clues))
        if self.needs_setup_clarification:
            data["needs_ability_followup"] = self.clarification_topic or "setup"
        return data


def analyze_dm_intent(text: str) -> DMIntent:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    lowered = clean.lower()
    result = DMIntent(raw_text=clean)

    quote_match = re.search(r"\b(?:i\s+)?(?:say|tell|ask|shout|whisper)(?:\s+[^\"']{0,40})?\s*([\"'])(.*?)\1", clean, re.I)
    if quote_match:
        result.spoken_text = quote_match.group(2).strip()
        result.intent = "spoken_dialogue"
    elif re.fullmatch(r"[\"']([^\"']+)[\"']", clean):
        result.spoken_text = clean.strip("\"'").strip()
        result.intent = "spoken_dialogue"

    for pattern in (
        r"\bmy name is\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)",
        r"\bname\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)",
        r"\b(?:i am|i'm)\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)(?=\s*,|\s+an?\b|\s+the\b|\.|$)",
        r"\b(?:i am called|i'm called|call me)\s+([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?)",
    ):
        match = re.search(pattern, clean, re.I)
        if match:
            result.character_name = match.group(1).strip(" .,;:")
            break

    known_roles = (
        "archmage", "mage", "wizard", "sorcerer", "witch", "warlock", "ranger", "knight", "soldier",
        "veteran soldier", "pilot", "sci-fi pilot", "captain", "rogue", "thief", "cleric", "priest",
        "druid", "bard", "fighter", "paladin", "monk", "barbarian", "gunslinger", "detective",
    )
    for role in sorted(known_roles, key=len, reverse=True):
        if re.search(rf"\b{re.escape(role)}\b", lowered):
            result.role = role
            break
    if not result.role:
        role_match = re.search(r"(?:a|an|the) ([a-z][a-z '\-]{2,40}?)(?: named| called| with| who| from|,|\.|$)", clean, re.I)
        if role_match and role_match.group(1).strip().lower() not in {"name", "world"}:
            result.role = role_match.group(1).strip(" .,;:")

    appearance_parts: list[str] = []
    for pattern in (
        r"\b(?:very\s+)?(?:tall|short|slender|broad|scarred|armored|muscular)\b",
        r"\b(?:black|brown|blonde|silver|white|red|blue|green|gray|grey) hair\b",
        r"\b(?:black|brown|blue|green|gray|grey|gold|amber|violet) eyes\b",
        r"\b(?:wearing|wears|clad in) [^,.;]+",
        r"\b(?:with|has) [^,.;]*(?:hair|eyes|scar|cloak|robes|armor)[^,.;]*",
    ):
        appearance_parts.extend(m.group(0).strip(" .,;:") for m in re.finditer(pattern, clean, re.I))
    result.appearance = ", ".join(dict.fromkeys(appearance_parts))

    for pattern in (r"\bmany spells(?: in my arsenal)?\b", r"\bmagical powers\b", r"\bmaster [a-z ]+\b", r"\bstarting out with [^,.;]+"):
        result.claimed_powers.extend(m.group(0).strip(" .,;:") for m in re.finditer(pattern, clean, re.I))
    list_match = re.search(r"\b(?:spells?|abilities|powers)\s*(?:are|:|include|like|such as)\s+([^.;]+)", clean, re.I)
    if list_match:
        for item in re.split(r",|\band\b", list_match.group(1)):
            item = item.strip(" .;:")
            if len(item) >= 3:
                result.specific_abilities.append(item.title())
    if ("archmage" in lowered or "wizard" in lowered or "mage" in lowered) and not result.specific_abilities and ("many spells" in lowered or "magical powers" in lowered):
        result.needs_setup_clarification = True
        result.clarification_topic = "spells"

    for clue in ("awakening in a new world", "new world", "isekai", "summoned", "magical world", "space", "starship", "post-apocalyptic", "wastes"):
        if clue in lowered:
            result.world_clues.append(clue)
    for clue in ("grim", "heroic", "dark", "cozy", "mysterious", "horror", "comedic"):
        if clue in lowered:
            result.tone_clues.append(clue)

    if result.intent == "unknown":
        if result.character_name or result.role or result.appearance:
            result.intent = "character_introduction"
        elif result.world_clues or result.tone_clues:
            result.intent = "world_setup"
        elif lowered.startswith(("please ", "set ", "change ", "make ", "use ")):
            result.intent = "ooc_instruction"
        elif lowered.startswith(("i ", "look", "go ", "move ", "attack", "walk", "run")):
            result.intent = "action"
    if result.intent == "character_introduction" and result.claimed_powers:
        result.intent = "ability_setup_followup" if result.needs_setup_clarification else "character_setup_followup"
    return result
