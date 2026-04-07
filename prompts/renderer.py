"""Prompt rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass

from engine.entities import CampaignState
from memory.retrieval import RetrievedMemory
from prompts.templates import (
    CAMPAIGN_TONE_TEMPLATE,
    CONTENT_SETTINGS_TEMPLATE,
    SYSTEM_ROLE_TEMPLATE,
    SYSTEM_TONE_TEMPLATE,
    TURN_TEMPLATE,
    WORLD_META_TEMPLATE,
)


@dataclass
class PromptPacket:
    system_prompt: str
    turn_prompt: str


class PromptRenderer:
    """Converts current state + player action into model-ready prompts."""

    def build_system_prompt(self, state: CampaignState, requested_mode: str = "play") -> str:
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
        world_meta = state.world_meta
        world_layer = WORLD_META_TEMPLATE.format(
            world_name=world_meta.world_name,
            world_theme=world_meta.world_theme,
            starting_location_name=world_meta.starting_location_name,
            tone=world_meta.tone,
            premise=world_meta.premise or "none",
            player_concept=world_meta.player_concept or "none",
        )
        return (
            f"[System Role]\n{SYSTEM_ROLE_TEMPLATE}\n"
            f"[System Tone]\n{SYSTEM_TONE_TEMPLATE}\n"
            f"[Campaign Tone]\n{campaign_tone}\n"
            f"[Content Settings]\n{content_layer}\n"
            f"[World Setup]\n{world_layer}\n"
            f"[Requested Mode]\n{requested_mode}"
        )

    def build_turn_prompt(
        self,
        state: CampaignState,
        action: str,
        location_summary: str,
        memory: RetrievedMemory,
        requested_mode: str = "play",
        suggested_moves_enabled: bool = True,
        npc_guidance: list[str] | None = None,
    ) -> str:
        recent = " | ".join(state.event_log[-4:]) if state.event_log else "No significant events yet"
        recent_conversation = " | ".join(
            f"You: {turn.player_input} || Narrator: {turn.narrator_response}"
            for turn in state.conversation_turns[-3:]
        )
        active_quest_count = sum(1 for quest in state.quests.values() if quest.status == "active")
        flags = ", ".join(k for k, v in sorted(state.world_flags.items()) if v) or "none"
        nearby_npcs = [
            f"{npc.name}(tier={npc.relationship_tier}, trust={npc.dynamic_state.trust_toward_player}, stress={npc.dynamic_state.stress})"
            for npc in state.npcs.values()
            if npc.location_id == state.current_location_id
        ]
        npc_context = " | ".join(nearby_npcs) if nearby_npcs else "none"
        suggested_move_instruction = (
            "Respond with 2-4 sentences and one suggested next move."
            if suggested_moves_enabled
            else "Respond with 2-4 sentences. Do not include any suggested next move line."
        )
        npc_personality_guidance = (
            "[NPC Personality Guidance]\n" + " | ".join(npc_guidance)
            if npc_guidance
            else "[NPC Personality Guidance]\nnone"
        )
        return TURN_TEMPLATE.format(
            requested_mode=requested_mode,
            recent_conversation=recent_conversation or "none",
            recent_memory=" | ".join(memory.recent_memory) if memory.recent_memory else "none",
            long_term_memory=" | ".join(memory.long_term_memory) if memory.long_term_memory else "none",
            session_summaries=" | ".join(memory.session_summaries) if memory.session_summaries else "none",
            plot_threads=" | ".join(memory.unresolved_plot_threads) if memory.unresolved_plot_threads else "none",
            world_facts=" | ".join(memory.important_world_facts) if memory.important_world_facts else "none",
            campaign_name=state.campaign_name,
            world_name=state.world_meta.world_name,
            world_theme=state.world_meta.world_theme,
            location=location_summary,
            action=action,
            player_name=state.player.name,
            char_class=state.player.char_class,
            hp=state.player.hp,
            max_hp=state.player.max_hp,
            attack_bonus=state.player.attack_bonus,
            active_quest_count=active_quest_count,
            world_flags=flags,
            recent_events=f"{recent} | Nearby NPC context: {npc_context}",
            suggested_move_instruction=suggested_move_instruction,
            npc_personality_guidance=npc_personality_guidance,
        )

    def build_prompt_packet(
        self,
        state: CampaignState,
        *,
        action: str,
        location_summary: str,
        memory: RetrievedMemory,
        requested_mode: str = "play",
        suggested_moves_enabled: bool = True,
        npc_guidance: list[str] | None = None,
    ) -> PromptPacket:
        return PromptPacket(
            system_prompt=self.build_system_prompt(state, requested_mode=requested_mode),
            turn_prompt=self.build_turn_prompt(
                state,
                action=action,
                location_summary=location_summary,
                memory=memory,
                requested_mode=requested_mode,
                suggested_moves_enabled=suggested_moves_enabled,
                npc_guidance=npc_guidance,
            ),
        )
