"""Prompt rendering helpers."""

from __future__ import annotations

from engine.entities import CampaignState
from prompts.templates import SYSTEM_TEMPLATE, TURN_TEMPLATE


class PromptRenderer:
    """Converts current state + player action into model-ready prompts."""

    def build_system_prompt(self, state: CampaignState) -> str:
        maturity = "enabled" if state.settings.mature_content_enabled else "disabled"
        return (
            f"{SYSTEM_TEMPLATE} Profile: {state.settings.profile}. "
            f"Tone: {state.settings.narration_tone}. Mature themes: {maturity}."
        )

    def build_turn_prompt(self, state: CampaignState, action: str, location_summary: str) -> str:
        recent = " | ".join(state.event_log[-3:]) if state.event_log else "No significant events yet"
        return TURN_TEMPLATE.format(
            campaign_name=state.campaign_name,
            location=location_summary,
            player_name=state.player.name,
            hp=state.player.hp,
            max_hp=state.player.max_hp,
            action=action,
            recent_events=recent,
        )
