"""Prompt templates for narration.

Prompt assets are isolated from rules and persistence so writers can iterate
without changing game math or save formats.
"""

SYSTEM_TEMPLATE = (
    "You are a fantasy campaign narrator. Keep responses concise, actionable, "
    "and immersive. Respect campaign content settings."
)

TURN_TEMPLATE = """Campaign: {campaign_name}
Location: {location}
Player: {player_name} (HP {hp}/{max_hp})
Action: {action}
Recent events: {recent_events}
Respond with 2-4 sentences and one suggested next move.
"""
