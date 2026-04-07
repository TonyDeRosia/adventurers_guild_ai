"""Prompt rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass

from engine.character_sheets import CharacterSheetPromptFormatter
from engine.entities import CampaignState
from memory.retrieval import RetrievedMemory
from prompts.templates import (
    CAMPAIGN_TONE_TEMPLATE,
    CONTENT_SETTINGS_TEMPLATE,
    DIALOGUE_QUALITY_TEMPLATE,
    NARRATIVE_EXAMPLES_TEMPLATE,
    PLAYER_AGENCY_TEMPLATE,
    STORY_QUALITY_TEMPLATE,
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
    def __init__(self) -> None:
        self.sheet_formatter = CharacterSheetPromptFormatter()
        self.built_in_narrator_rules = [
            "Never make decisions for the player character.",
            "Do not dictate the player's emotions, intentions, or choices.",
            "When the player explicitly asks for stats, include concrete numeric stats available in state.",
        ]

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
        custom_rules = [
            str(entry.get("text", "")).strip()
            for entry in state.structured_state.canon.custom_narrator_rules
            if isinstance(entry, dict) and str(entry.get("text", "")).strip()
        ]
        injected_custom = bool(custom_rules)
        print(f"[narrator-rules] injected_custom_rules={str(injected_custom).lower()} count={len(custom_rules)}")
        narrator_rules_layer = "\n".join(
            [f"- {rule}" for rule in self.built_in_narrator_rules]
            + ([f"- {rule}" for rule in custom_rules] if custom_rules else ["- none"])
        )
        print("[narrative-quality] strengthened_prompt=true")
        return (
            f"[System Role]\n{SYSTEM_ROLE_TEMPLATE}\n"
            f"[System Tone]\n{SYSTEM_TONE_TEMPLATE}\n"
            f"[Storytelling Quality]\n{STORY_QUALITY_TEMPLATE}\n"
            f"[Player Agency Guardrails]\n{PLAYER_AGENCY_TEMPLATE}\n"
            f"[Dialogue Quality]\n{DIALOGUE_QUALITY_TEMPLATE}\n"
            f"[Narrative Examples]\n{NARRATIVE_EXAMPLES_TEMPLATE}\n"
            f"[Narrator Rules - Hard]\n{narrator_rules_layer}\n"
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
        guidance_requested: bool = False,
        npc_guidance: list[str] | None = None,
        character_sheet_guidance: list[str] | None = None,
        gm_context: str = "",
        scene_state_summary: str = "",
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
            "Respond with compact but substantial narration (usually 1-3 short paragraphs) focused on immediate scene framing, "
            "specific reactions, concrete consequences, and a clean handoff. "
            "Do not suggest actions, next steps, or recommended moves unless the player explicitly asked for guidance. "
            + (
                "In this turn, the player explicitly asked for guidance, so you may include clear options or recommendations."
                if guidance_requested
                else "In this turn, the player did not ask for guidance, so do not include advisory phrasing."
            )
        )
        npc_personality_guidance = (
            "[NPC Personality Guidance]\n" + " | ".join(npc_guidance)
            if npc_guidance
            else "[NPC Personality Guidance]\nnone"
        )
        sheet_guidance_text = (
            "[Character Sheet Guidance]\n" + " | ".join(character_sheet_guidance)
            if character_sheet_guidance
            else "[Character Sheet Guidance]\nnone"
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
            scene_state=scene_state_summary or "Current Scene State:\n- none",
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
            character_sheet_guidance=sheet_guidance_text,
            gm_context=gm_context or "none",
        )

    def build_prompt_packet(
        self,
        state: CampaignState,
        *,
        action: str,
        location_summary: str,
        memory: RetrievedMemory,
        requested_mode: str = "play",
        guidance_requested: bool = False,
        npc_guidance: list[str] | None = None,
        gm_context: str = "",
        scene_state_summary: str = "",
    ) -> PromptPacket:
        sheet_guidance = self.sheet_formatter.build_guidance_blocks(
            state.character_sheets,
            campaign_strength=state.character_sheet_guidance_strength,
        )
        gm_context_text = gm_context or ""
        gm_context_lower = gm_context_text.lower()
        print(f"[gm-context-audit] prompt_injection_campaign={str('campaign' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_world={str('world_state' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_player_core={str('player_core' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_inventory={str('inventory_state' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_spellbook={str('spellbook' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_npc_state={str('nearby_npcs' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_minions={str('minions' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_recent_memory={str('recent turn memory' in gm_context_lower).lower()}")
        print(f"[gm-context-audit] prompt_injection_custom_rules={str('custom_narrator_rules' in gm_context_lower).lower()}")
        return PromptPacket(
            system_prompt=self.build_system_prompt(state, requested_mode=requested_mode),
            turn_prompt=self.build_turn_prompt(
                state,
                action=action,
                location_summary=location_summary,
                memory=memory,
                requested_mode=requested_mode,
                guidance_requested=guidance_requested,
                npc_guidance=npc_guidance,
                character_sheet_guidance=sheet_guidance,
                gm_context=gm_context_text,
                scene_state_summary=scene_state_summary,
            ),
        )
