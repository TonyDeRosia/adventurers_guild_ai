"""Prompt rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass

from engine.entities import CampaignState
from prompts.templates import PLAYER_STATE_TEMPLATE, PROFILE_TONES, SCENE_TEMPLATE, SYSTEM_TONE_TEMPLATE


@dataclass(frozen=True)
class PromptBundle:
    system_tone: str
    profile_tone: str
    scene_context: str
    player_state_summary: str


class PromptRenderer:
    """Converts current state + player action into organized prompt context."""

    def build_prompt_bundle(self, state: CampaignState, location_summary: str) -> PromptBundle:
        maturity = "enabled" if state.settings.mature_content_enabled else "disabled"
        system_tone = f"{SYSTEM_TONE_TEMPLATE} Mature themes: {maturity}."
        profile_tone = PROFILE_TONES.get(state.settings.profile, "Tone profile: neutral fantasy.")
        recent = " | ".join(state.event_log[-3:]) if state.event_log else "No significant events yet"
        scene_context = SCENE_TEMPLATE.format(location=location_summary, recent_events=recent)
        player_state_summary = PLAYER_STATE_TEMPLATE.format(
            player_name=state.player.name,
            hp=state.player.hp,
            max_hp=state.player.max_hp,
            xp=state.player.xp,
            weapon=state.player.equipped_weapon_id or "none",
            trinket=state.player.equipped_trinket_id or "none",
        )
        return PromptBundle(
            system_tone=system_tone,
            profile_tone=profile_tone,
            scene_context=scene_context,
            player_state_summary=player_state_summary,
        )
