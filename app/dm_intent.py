"""Compatibility wrapper for the centralized DM reasoning layer."""

from __future__ import annotations

from engine.dm_reasoning import DMIntent, analyze_player_input


def analyze_dm_intent(text: str) -> DMIntent:
    intent = analyze_player_input(text, mode="ic")
    if intent.role and intent.role != "Pyromancer":
        intent.role = intent.role.lower()
    if isinstance(intent.appearance, list):
        intent.appearance = ", ".join(dict.fromkeys(intent.appearance))  # type: ignore[assignment]
    return intent
