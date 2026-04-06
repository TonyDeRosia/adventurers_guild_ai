"""Prompt templates for narration."""

SYSTEM_TONE_TEMPLATE = (
    "You are a fantasy campaign narrator. Keep responses concise, actionable, "
    "and immersive. Mature themes are a style/tone modifier only."
)

PROFILE_TONES = {
    "classic_fantasy": "Tone profile: hopeful heroism, wonder, and grounded danger.",
    "dark_fantasy": "Tone profile: grim atmosphere, difficult choices, and restrained dread.",
}

SCENE_TEMPLATE = "Scene: {location}. Recent events: {recent_events}."

PLAYER_STATE_TEMPLATE = (
    "Player: {player_name} HP {hp}/{max_hp} XP {xp}. "
    "Equipped weapon: {weapon}. Equipped trinket: {trinket}."
)
