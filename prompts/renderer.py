"""Prompt rendering helpers."""

from __future__ import annotations

from engine.entities import CampaignState
from prompts.templates import CAMPAIGN_TONE_TEMPLATE, CONTENT_SETTINGS_TEMPLATE, SYSTEM_TONE_TEMPLATE, TURN_TEMPLATE


class PromptRenderer:
    """Converts current state + player action into model-ready prompts."""

    def build_system_prompt(self, state: CampaignState) -> str:
        maturity = "enabled" if state.settings.mature_content_enabled else "disabled"
        content_settings = state.settings.content_settings
        thematic_flags = ", ".join(content_settings.thematic_flags) if content_settings.thematic_flags else "none"
        campaign_tone = CAMPAIGN_TONE_TEMPLATE.format(
            profile=state.settings.profile,
            tone=state.settings.narration_tone,
            maturity=maturity,
        )
        content_layer = CONTENT_SETTINGS_TEMPLATE.format(
            tone=content_settings.tone,
            maturity_level=content_settings.maturity_level,
            thematic_flags=thematic_flags,
        )
        return (
            f"[System Tone]\n{SYSTEM_TONE_TEMPLATE}\n"
            f"[Campaign Tone]\n{campaign_tone}\n"
            f"[Content Settings]\n{content_layer}"
        )

    def build_turn_prompt(self, state: CampaignState, action: str, location_summary: str) -> str:
        recent = " | ".join(state.event_log[-4:]) if state.event_log else "No significant events yet"
        active_quest_count = sum(1 for quest in state.quests.values() if quest.status == "active")
        flags = ", ".join(k for k, v in sorted(state.world_flags.items()) if v) or "none"
        return TURN_TEMPLATE.format(
            campaign_name=state.campaign_name,
            location=location_summary,
            action=action,
            player_name=state.player.name,
            char_class=state.player.char_class,
            hp=state.player.hp,
            max_hp=state.player.max_hp,
            attack_bonus=state.player.attack_bonus,
            active_quest_count=active_quest_count,
            world_flags=flags,
            recent_events=recent,
        )
