"""Player-facing output guards for Adventure Mode.

This module keeps engine/developer diagnostics out of the campaign log while
allowing callers to retain those lines in debug traces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_BLOCKED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^\s*Action noted\.\s*$",
        r"\bYou commit to\b",
        r"\bAbility authority\b",
        r"\bFreeform power note\b",
        r"\bLearning mode is disabled\b",
        r"\bstrict\s*=",
        r"\bconfidence\s*=",
        r"\bstate\s*=\s*untrained\b",
        r"^\s*\[(?:settings|ability-state|ability-learn|turn-routing|narration-debug|scene-state|control-audit|turn-quality|campaign-event)[^\]]*\]",
        r"^\s*(?:requested mode|conversation context|memory context|scene context|player state summary)\s*:",
    )
)


@dataclass
class FilteredOutput:
    player_messages: list[str] = field(default_factory=list)
    quarantined_messages: list[str] = field(default_factory=list)


def is_player_facing_message(message: str) -> bool:
    """Return False for diagnostics/scaffold text that should not enter logs."""
    text = re.sub(r"\s+", " ", str(message or "").strip())
    if not text:
        return False
    return not any(pattern.search(text) for pattern in _BLOCKED_PATTERNS)


def filter_player_messages(messages: list[str]) -> FilteredOutput:
    result = FilteredOutput()
    for message in messages:
        text = re.sub(r"\s+", " ", str(message or "").strip())
        if not text:
            continue
        if is_player_facing_message(text):
            result.player_messages.append(text)
        else:
            result.quarantined_messages.append(text)
    return result


def narrative_needs_player_facing_fallback(narrative: str) -> bool:
    text = re.sub(r"\s+", " ", str(narrative or "").strip())
    return bool(text) and not is_player_facing_message(text)
