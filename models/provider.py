"""Scaffold provider interface for future local inference backends."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol


@dataclass
class NarrationRequest:
    system_tone: str
    campaign_tone: str
    scene_context: str
    player_state_summary: str


class NarrationProvider(Protocol):
    provider_name: str

    def narrate(self, request: NarrationRequest) -> str:
        """Generate narration from structured prompt layers."""


class LocalTemplateProvider:
    """Offline-safe Basic DM provider with player-facing fallback text."""

    provider_name = "local_template"

    def narrate(self, request: NarrationRequest) -> str:
        action = ""
        location = "the current scene"
        character = "Your character"
        for line in request.scene_context.splitlines():
            stripped = line.strip()
            if stripped.startswith("Action:"):
                action = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Location:"):
                location = stripped.split(":", 1)[1].strip() or location
            elif stripped.lower().startswith("player:"):
                character = stripped.split(":", 1)[1].strip() or character
        return self._basic_response(action, location=location, character=character)

    def _basic_response(self, action: str, *, location: str, character: str) -> str:
        clean = re.sub(r"\s+", " ", str(action or "").strip())
        lowered = clean.lower()
        name = character.split(",", 1)[0].strip() or "Your character"
        if not clean:
            return "I’m not sure what you want your character to do. Are you acting in the scene, asking me out of character, or clarifying your setup?"
        cast_match = re.search(r"\bcast\s+(.+?)(?:\s+on\s+(.+)|\s+at\s+(.+))?$", clean, re.I)
        if cast_match:
            spell = cast_match.group(1).strip(" .,!?")
            target = (cast_match.group(2) or cast_match.group(3) or "the immediate scene").strip(" .,!?")
            target_phrase = "over himself" if target.lower() in {"myself", "me", "self"} else f"toward {target}"
            if spell.lower() in {"colour spray", "color spray"} and target.lower() in {"myself", "me", "self"}:
                return f"{name} raises a hand and releases a burst of shifting color over himself. The magic flickers across his clothes and skin, bright but harmless unless you shape it toward a clear purpose. What do you do?"
            return f"{name} attempts to cast {spell}, shaping the magic {target_phrase}. The effect stirs in {location}, waiting on a clear purpose or consequence. What do you do?"
        if re.search(r"\b(?:use|invoke|channel|summon|activate|perform)\b", lowered):
            return f"{name} tries to turn that ability into action in {location}. The attempt becomes part of the scene without changing the character sheet by itself. What do you do?"
        if not re.search(r"\b(i|look|go|move|walk|run|attack|talk|say|ask|tell|cast|use|invoke|channel|summon|take|open|inspect)\b", lowered):
            return "I’m not sure what you want your character to do. Are you acting in the scene, asking me out of character, or clarifying your setup?"
        return f"{name} follows through in {location}. The scene responds in a grounded, immediate way, and the next choice is yours. What do you do?"
