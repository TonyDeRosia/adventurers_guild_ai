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


@dataclass
class TurnPromptContext:
    current_player_action: str
    scene_location: str
    active_participants: list[str]
    npc_states: list[str]
    environment_state: list[str]
    unresolved_threats: list[str]
    recent_consequences: list[str]
    narrator_rules: list[str]


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
        turn_context: TurnPromptContext | None = None,
        enforce_action_priority: bool = True,
        retry_action_priority: bool = False,
    ) -> str:
        recent = " | ".join(state.event_log[-4:]) if state.event_log else "No significant events yet"
        recent_conversation = self._summarize_recent_conversation(state)
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
        structured_turn_context = self._format_turn_context(turn_context, action, location_summary)
        current_action_priority = self._build_current_action_priority_block(
            action,
            enforce_action_priority=enforce_action_priority,
            retry_action_priority=retry_action_priority,
        )
        return TURN_TEMPLATE.format(
            requested_mode=requested_mode,
            recent_conversation=recent_conversation or "none",
            current_action_priority=current_action_priority,
            turn_resolution_order=(
                "1) Resolve the current player action immediately. "
                "2) Identify direct targets and effects. "
                "3) Update NPC/environment state with concrete consequences. "
                "4) Narrate the resulting moment with concise flavor."
            ),
            structured_turn_context=structured_turn_context,
            recent_memory_summary=self._summarize_recent_memory(memory),
            recent_consequences_summary=self._summarize_recent_consequences(memory),
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

    def _build_current_action_priority_block(self, action: str, *, enforce_action_priority: bool, retry_action_priority: bool) -> str:
        if not enforce_action_priority:
            return f"Current player action: {action}"
        retry_suffix = (
            " This is a retry because a prior draft failed action resolution; resolve this action explicitly before any atmosphere."
            if retry_action_priority
            else ""
        )
        return (
            "CURRENT PLAYER ACTION - HIGHEST PRIORITY\n"
            f"Action: {action}\n"
            "This exact action must be resolved now.\n"
            "Do not replace it with earlier actions or prior narration.\n"
            "Do not ignore it.\n"
            "Resolve this action first, then narrate consequences."
            + retry_suffix
        )

    def _summarize_recent_conversation(self, state: CampaignState) -> str:
        snippets: list[str] = []
        for turn in state.conversation_turns[-3:]:
            user_text = turn.player_input.strip()
            if not user_text:
                continue
            narrator_preview = turn.narrator_response.strip()
            narrator_preview = narrator_preview.split(".")[0][:100].strip() if narrator_preview else "no narrator line"
            snippets.append(f"You: {user_text} || Result: {narrator_preview or 'no narrator line'}")
        return " | ".join(snippets) if snippets else "none"

    def _summarize_recent_memory(self, memory: RetrievedMemory) -> str:
        if not memory.recent_memory:
            return "none"
        return " | ".join(memory.recent_memory[-3:])

    def _summarize_recent_consequences(self, memory: RetrievedMemory) -> str:
        consequence_like = [item for item in memory.recent_memory if item.lower().startswith("narrator:") or "damage" in item.lower() or "quest" in item.lower()]
        if not consequence_like:
            return "none"
        return " | ".join(consequence_like[-3:])

    def _format_turn_context(self, context: TurnPromptContext | None, action: str, location_summary: str) -> str:
        if context is None:
            return f"- current_player_action: {action}\n- scene_location: {location_summary}\n- active_participants: none"
        lines = [
            f"- current_player_action: {context.current_player_action or action}",
            f"- scene_location: {context.scene_location or location_summary}",
            f"- active_participants: {', '.join(context.active_participants) if context.active_participants else 'none'}",
            f"- npc_states: {'; '.join(context.npc_states) if context.npc_states else 'none'}",
            f"- environment_state: {'; '.join(context.environment_state) if context.environment_state else 'none'}",
            f"- unresolved_threats: {'; '.join(context.unresolved_threats) if context.unresolved_threats else 'none'}",
            f"- recent_consequences: {'; '.join(context.recent_consequences) if context.recent_consequences else 'none'}",
            f"- narrator_rules: {'; '.join(context.narrator_rules) if context.narrator_rules else 'none'}",
        ]
        return "\n".join(lines)

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
        turn_context: TurnPromptContext | None = None,
        retry_action_priority: bool = False,
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
                turn_context=turn_context,
                retry_action_priority=retry_action_priority,
            ),
        )
