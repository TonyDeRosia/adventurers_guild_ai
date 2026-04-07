"""Prompt templates for narration.

Prompt assets are isolated from rules and persistence so writers can iterate
without changing game math or save formats.
"""

SYSTEM_TONE_TEMPLATE = (
    "You are a fantasy campaign narrator. Keep responses concise, actionable, and immersive."
)
SYSTEM_ROLE_TEMPLATE = (
    "Role: Local campaign intelligence narrator and analyst. Maintain continuity and respect rules boundaries."
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

WORLD_META_TEMPLATE = (
    "World name: {world_name}. Theme/genre: {world_theme}. Starting location: {starting_location_name}. "
    "Desired tone/style: {tone}. Premise: {premise}. Player concept: {player_concept}."
)

TURN_TEMPLATE = """[Requested Mode]
{requested_mode}

[Conversation Context]
Recent chat turns: {recent_conversation}

[Memory Context]
Recent memory: {recent_memory}
Long-term memory: {long_term_memory}
Session summaries: {session_summaries}
Unresolved plot threads: {plot_threads}
Important world facts: {world_facts}

[Scene Context]
Campaign: {campaign_name}
World: {world_name} ({world_theme})
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
