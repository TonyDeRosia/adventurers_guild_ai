"""Prompt templates for narration.

Prompt assets are isolated from rules and persistence so writers can iterate
without changing game math or save formats.
"""

SYSTEM_TONE_TEMPLATE = (
    "You are a fantasy campaign narrator. Keep responses concise, actionable, and immersive."
)

CAMPAIGN_TONE_TEMPLATE = (
    "Campaign profile: {profile}. Narration tone: {tone}. Mature themes tone-layer: {maturity}."
)

CONTENT_SETTINGS_TEMPLATE = (
    "Content settings (local campaign configuration): tone={tone}; maturity_level={maturity_level}; "
    "thematic_flags={thematic_flags}. "
    "These settings only guide narration/dialogue/scene description and must never alter combat math, "
    "character progression, item mechanics, or rules resolution."
)

TURN_TEMPLATE = """[Scene Context]
Campaign: {campaign_name}
Location: {location}
Action: {action}

[Player State Summary]
Player: {player_name} ({char_class})
HP: {hp}/{max_hp}
Attack bonus: +{attack_bonus}
Active quest count: {active_quest_count}
World flags: {world_flags}
Recent events: {recent_events}

Respond with 2-4 sentences and one suggested next move.
"""
