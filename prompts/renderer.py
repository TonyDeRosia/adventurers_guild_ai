"""Prompt rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re

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
    strict_sheet_enforcement: bool = False
    learning_mode: bool = True
    ability_name: str = "none"
    ability_state: str = "none"
    ability_confidence: str = "none"


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
        play_style = state.settings.play_style
        play_style_layer = "\n".join(
            [
                f"- allow_freeform_powers: {str(play_style.allow_freeform_powers).lower()}",
                f"- auto_update_character_sheet_from_actions: {str(play_style.auto_update_character_sheet_from_actions).lower()}",
                f"- strict_sheet_enforcement: {str(play_style.strict_sheet_enforcement).lower()}",
                f"- auto_sync_player_declared_identity: {str(play_style.auto_sync_player_declared_identity).lower()}",
                f"- auto_generate_npc_personalities: {str(play_style.auto_generate_npc_personalities).lower()}",
                f"- auto_evolve_npc_personalities: {str(play_style.auto_evolve_npc_personalities).lower()}",
                f"- reactive_world_persistence: {str(play_style.reactive_world_persistence).lower()}",
                f"- narration_format_mode: {play_style.narration_format_mode}",
                f"- scene_visual_mode: {play_style.scene_visual_mode}",
            ]
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
            f"[Campaign Play Style]\n{play_style_layer}\n"
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
        active_quest_count = sum(1 for quest in state.quests.values() if quest.status == "active")
        nearby_npcs = [
            f"{npc.name}(tier={npc.relationship_tier}, trust={npc.dynamic_state.trust_toward_player}, stress={npc.dynamic_state.stress})"
            for npc in state.npcs.values()
            if npc.location_id == state.current_location_id
        ]
        npc_context = " | ".join(nearby_npcs) if nearby_npcs else "none"
        suggested_move_instruction = self._build_writing_instructions_block(guidance_requested, state)
        focus = self._infer_player_fact_focus(action)
        structured_turn_context = self._format_turn_context(turn_context, action, location_summary, focus=focus)
        current_action_priority = self._build_current_action_priority_block(
            action,
            enforce_action_priority=enforce_action_priority,
            retry_action_priority=retry_action_priority,
        )
        scene_block = self._build_scene_prompt_block(
            state=state,
            location_summary=location_summary,
            scene_state_summary=scene_state_summary,
            recent_visible_consequences=turn_context.recent_consequences if turn_context else [],
        )
        npc_block = self._build_npc_prompt_block(turn_context=turn_context, npc_guidance=npc_guidance, npc_context=npc_context)
        enemy_block = self._build_enemy_prompt_block(state=state, turn_context=turn_context)
        player_facts_block = self._build_player_facts_prompt_block(
            state=state,
            action=action,
            active_quest_count=active_quest_count,
            character_sheet_guidance=character_sheet_guidance,
            gm_context=gm_context,
            focus=focus,
        )
        recent_consequences_block = self._build_recent_consequences_prompt_block(
            memory=memory,
            turn_context=turn_context,
            long_term_memory=" | ".join(memory.long_term_memory) if memory.long_term_memory else "none",
            session_summaries=" | ".join(memory.session_summaries) if memory.session_summaries else "none",
            plot_threads=" | ".join(memory.unresolved_plot_threads) if memory.unresolved_plot_threads else "none",
            world_facts=" | ".join(memory.important_world_facts) if memory.important_world_facts else "none",
        )
        narrator_rules_block = self._build_narrator_rules_prompt_block(state=state, turn_context=turn_context)
        return TURN_TEMPLATE.format(
            requested_mode=requested_mode,
            current_action_priority=current_action_priority,
            scene_block=scene_block,
            npc_block=npc_block,
            enemy_block=enemy_block,
            player_facts_block=player_facts_block,
            recent_consequences_block=recent_consequences_block,
            narrator_rules_block=narrator_rules_block,
            writing_instructions_block=(
                f"{suggested_move_instruction}\n\n[STRUCTURED TURN SNAPSHOT]\n{structured_turn_context}"
            ),
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
            "Resolve this action first, then narrate consequences.\n"
            "Latest action overrides any stale unresolved prior action."
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

    def _format_turn_context(self, context: TurnPromptContext | None, action: str, location_summary: str, *, focus: str) -> str:
        if context is None:
            return f"- current_player_action: {action}\n- scene_location: {location_summary}\n- active_participants: none"
        lines = [
            f"- current_player_action: {context.current_player_action or action}",
            f"- scene_location: {context.scene_location or location_summary}",
            f"- active_participants: {', '.join(context.active_participants) if context.active_participants else 'none'}",
            f"- environment_state: {'; '.join(context.environment_state[:2]) if context.environment_state else 'none'}",
            f"- recent_consequences: {'; '.join(context.recent_consequences[:2]) if context.recent_consequences else 'none'}",
            f"- strict_sheet_enforcement: {str(context.strict_sheet_enforcement).lower()}",
            f"- learning_mode: {str(context.learning_mode).lower()}",
            f"- attempted_ability: {context.ability_name}",
            f"- ability_state: {context.ability_state}",
            f"- ability_confidence: {context.ability_confidence}",
        ]
        if focus == "dialogue":
            lines.append(f"- npc_states: {'; '.join(context.npc_states[:2]) if context.npc_states else 'none'}")
        elif focus in {"combat", "magic"}:
            lines.append(f"- unresolved_threats: {'; '.join(context.unresolved_threats[:3]) if context.unresolved_threats else 'none'}")
        return "\n".join(lines)

    def _build_scene_prompt_block(
        self,
        *,
        state: CampaignState,
        location_summary: str,
        scene_state_summary: str,
        recent_visible_consequences: list[str] | None = None,
    ) -> str:
        recent_visible = recent_visible_consequences or []
        parts = [
            f"- Campaign: {state.campaign_name}",
            f"- World: {state.world_meta.world_name} ({state.world_meta.world_theme})",
            f"- Location: {location_summary}",
            f"- Visible environmental changes: {scene_state_summary or 'none'}",
            f"- Recent visible consequences: {' | '.join(recent_visible) if recent_visible else 'none'}",
        ]
        return "\n".join(parts)

    def _build_npc_prompt_block(
        self,
        *,
        turn_context: TurnPromptContext | None,
        npc_guidance: list[str] | None,
        npc_context: str,
    ) -> str:
        npc_states = turn_context.npc_states if turn_context else []
        lines = [f"- Active participants: {', '.join(turn_context.active_participants) if turn_context and turn_context.active_participants else 'none'}"]
        lines.extend(
            [
                "- Identity continuity: reuse established NPC names once introduced.",
                "- Do not rename existing NPCs or split one character into duplicate entries.",
                "- Generic references (for example, 'the guard' or 'the stranger') should map to the established character when context matches.",
            ]
        )
        if npc_states:
            for npc_state in npc_states:
                lines.append(f"- {npc_state}")
        else:
            lines.append("- none")
        if npc_guidance:
            lines.append(f"- NPC behavior anchors: {' | '.join(npc_guidance[:4])}")
        elif npc_context != "none":
            lines.append(f"- NPC behavior anchors: {npc_context}")
        return "\n".join(lines)

    def _build_enemy_prompt_block(self, *, state: CampaignState, turn_context: TurnPromptContext | None) -> str:
        threats = list(turn_context.unresolved_threats) if turn_context else []
        if state.active_enemy_id and (state.active_enemy_hp or 0) > 0:
            threat_line = f"active enemy present: {state.active_enemy_id} (HP {state.active_enemy_hp})"
            if threat_line not in threats:
                threats.append(threat_line)
        if not threats:
            return "- No active combat mobs or immediate hostile threats."
        return "- " + "\n- ".join(threats)

    def _build_player_facts_prompt_block(
        self,
        *,
        state: CampaignState,
        action: str,
        active_quest_count: int,
        character_sheet_guidance: list[str] | None,
        gm_context: str,
        focus: str,
    ) -> str:
        active_conditions = sorted([key for key, enabled in state.combat_effects.items() if enabled])
        inventory = state.player.inventory
        spellbook = state.structured_state.runtime.spellbook
        facts = [
            f"- Player: {state.player.name} ({state.player.char_class})",
            f"- HP: {state.player.hp}/{state.player.max_hp}",
            f"- Active conditions: {', '.join(active_conditions[:4]) or 'none'}",
            f"- Active quest count: {active_quest_count}",
            f"- Focus for this turn: {focus}",
        ]
        if focus in {"combat", "inventory_use", "item_use"}:
            facts.extend(
                [
                    f"- Attack bonus: +{state.player.attack_bonus}",
                    f"- Equipped item: {state.player.equipped_item_id or 'none'}",
                ]
            )
        if focus in {"inventory_use", "item_use", "combat", "exploration"}:
            facts.append(f"- Inventory highlights: {', '.join(inventory[:5]) if inventory else 'none'}")
        if focus in {"magic", "combat", "exploration"}:
            facts.append(
                f"- Spellbook highlights: {', '.join(entry.get('name', 'unknown') for entry in spellbook[:5]) if spellbook else 'none'}"
            )
        if focus == "dialogue":
            facts.append(f"- Social loadout cue: equipped item {state.player.equipped_item_id or 'none'}")
        facts.extend(
            [
            f"- [Character Sheet Guidance] {' | '.join(character_sheet_guidance[:2]) if character_sheet_guidance else 'none'}",
            f"- Structured truth attached: {'yes' if bool(gm_context.strip()) else 'no'}",
            "[STRUCTURED CAMPAIGN FACTS]",
            self._compress_structured_truth(gm_context, focus=focus),
            ]
        )
        return "\n".join(facts)

    def _infer_player_fact_focus(self, action: str) -> str:
        lowered = action.lower()
        if any(word in lowered for word in ("cast", "spell", "ritual", "arcane", "magic")):
            return "magic"
        if any(word in lowered for word in ("use ", "drink ", "consume ", "apply ", "equip ", "draw ")):
            return "item_use"
        if any(word in lowered for word in ("attack", "defend", "strike", "flee", "ability")):
            return "combat"
        if any(word in lowered for word in ("talk", "say", "ask", "persuade", "threaten", "negotiate", "choose")):
            return "dialogue"
        return "exploration"

    def _compress_structured_truth(self, gm_context: str, *, focus: str) -> str:
        text = (gm_context or "").strip()
        if not text:
            return "none"
        compact = re.sub(r"\s+", " ", text)

        def _segment(label: str, next_labels: list[str]) -> str:
            start = compact.find(label)
            if start == -1:
                return ""
            end = len(compact)
            for candidate in next_labels:
                idx = compact.find(candidate, start + len(label))
                if idx != -1:
                    end = min(end, idx)
            return compact[start:end].strip().rstrip(',')

        core_labels = [
            "Canon:",
            "'player_core':",
            "'inventory_state':",
            "'spellbook':",
            "'nearby_npcs':",
            "'scene_actors':",
            "'world_state':",
            "Recent Turn Memory:",
        ]
        segments: list[str] = []
        for idx, label in enumerate(core_labels):
            chunk = _segment(label, core_labels[idx + 1 :])
            if chunk:
                segments.append(chunk)

        focus_map = {
            "magic": ["'spellbook':", "'player_core':", "'nearby_npcs':", "'world_state':"],
            "item_use": ["'inventory_state':", "'player_core':", "'world_state':", "'nearby_npcs':"],
            "inventory_use": ["'inventory_state':", "'player_core':", "'world_state':", "'nearby_npcs':"],
            "dialogue": ["'nearby_npcs':", "'scene_actors':", "'player_core':", "'world_state':"],
            "combat": ["'player_core':", "'world_state':", "'nearby_npcs':", "'spellbook':", "'inventory_state':"],
            "exploration": ["'world_state':", "'scene_actors':", "'nearby_npcs':", "'player_core':"],
        }
        ordered_focus_labels = focus_map.get(focus, focus_map["exploration"])
        prioritized: list[str] = []
        for label in ["Canon:", *ordered_focus_labels, "Recent Turn Memory:"]:
            chunk = next((seg for seg in segments if seg.startswith(label)), "")
            if chunk and chunk not in prioritized:
                prioritized.append(chunk)

        if not prioritized:
            prioritized = segments
        joined = " || ".join(prioritized)
        if len(joined) <= 900:
            return joined
        return joined[:900].rstrip() + " ...[truncated]"

    def _build_recent_consequences_prompt_block(
        self,
        *,
        memory: RetrievedMemory,
        turn_context: TurnPromptContext | None,
        long_term_memory: str,
        session_summaries: str,
        plot_threads: str,
        world_facts: str,
    ) -> str:
        turn_recent = " | ".join(turn_context.recent_consequences) if turn_context and turn_context.recent_consequences else "none"
        return "\n".join(
            [
                f"- Turn-level consequences: {turn_recent}",
                f"- Recent memory summary: {self._summarize_recent_memory(memory)}",
                f"- Retrieved consequence cues: {self._summarize_recent_consequences(memory)}",
                f"- Long-term memory: {long_term_memory}",
                f"- Session summaries: {session_summaries}",
                f"- Unresolved plot threads: {plot_threads}",
                f"- Important world facts: {world_facts}",
            ]
        )

    def _build_narrator_rules_prompt_block(self, *, state: CampaignState, turn_context: TurnPromptContext | None) -> str:
        custom_rules = [
            str(entry.get("text", "")).strip()
            for entry in state.structured_state.canon.custom_narrator_rules
            if isinstance(entry, dict) and str(entry.get("text", "")).strip()
        ]
        combined = [*self.built_in_narrator_rules, *custom_rules]
        if turn_context and turn_context.narrator_rules:
            combined.extend(turn_context.narrator_rules)
        if not combined:
            return "- none"
        deduped: list[str] = []
        for rule in combined:
            if rule not in deduped:
                deduped.append(rule)
        return "- " + "\n- ".join(deduped[:12])

    def _build_writing_instructions_block(self, guidance_requested: bool, state: CampaignState) -> str:
        narration_mode = state.settings.play_style.narration_format_mode
        strict_sheet = state.settings.play_style.strict_sheet_enforcement
        freeform = state.settings.play_style.allow_freeform_powers
        auto_update = state.settings.play_style.auto_update_character_sheet_from_actions
        mode_instruction = {
            "compact": "Prefer shorter, tighter narration with minimal flourish and rapid turn pacing.",
            "dialogue_focused": "Prioritize character dialogue and conversational exchange while still resolving action consequences.",
            "book": "Use immersive prose-first narration with descriptive scene transitions.",
        }.get(narration_mode, "Use immersive prose-first narration with descriptive scene transitions.")
        sheet_instruction = (
            "When powers are used, treat only abilities already present in structured character sheet/spellbook as authoritative. "
            "If an ability is unknown in strict mode, portray it as unstable, weaker, or risky unless it becomes learned through successful play."
            if strict_sheet
            else (
                "Allow creative freeform actions and powers, grounding outcomes in campaign truth and continuity."
                if freeform
                else "Allow actions not explicitly listed, but mark outcomes cautiously and keep continuity grounded."
            )
        )
        learning_instruction = (
            "Learning mode is enabled: successful new actions may be promoted into permanent abilities."
            if auto_update
            else "Learning mode is disabled: do not promote new actions into permanent abilities."
        )
        return (
            "Write natural, expressive scene prose using the structured facts above as truth.\n"
            "Write like a scene, not a report: avoid wrappers such as 'Turn X' or 'Outcome summary'.\n"
            "Resolve the current action first, then show concrete consequences in scene, NPC behavior, and threat behavior.\n"
            "Use spacing and paragraph breaks generously when they improve readability.\n"
            "Separate setting, action/reaction, and dialogue into readable blocks when appropriate instead of one dense paragraph.\n"
            "Present speech directly as dialogue when characters speak; avoid summary phrasing like 'you say' or 'the player says'.\n"
            "Do not cram multiple speakers into one paragraph when a break improves clarity.\n"
            "Internal composition concepts (Scene, NPC Reactions, Enemy/Threat Reactions, Dialogue, Immediate Result, Turn Snapshot) are for planning only.\n"
            "Do not print visible scaffold labels such as [Scene], [Dialogue], [Turn Snapshot], [NPC Reactions], [Enemy/Threat Reactions], or [Immediate Result] in normal story mode.\n"
            "Use natural prose paragraphs and spacing instead of bracketed section headers.\n"
            "Do not collapse into stat-sheet formatting unless the player explicitly asked for structured output.\n"
            "Keep output compact (usually 1-4 short paragraphs) and end on a clean handoff to player agency.\n"
            f"{mode_instruction}\n"
            f"{sheet_instruction}\n"
            f"{learning_instruction}\n"
            "Do not suggest actions, next steps, or recommendations unless the player explicitly asked for guidance.\n"
            + (
                "Guidance was explicitly requested this turn; recommendations are allowed."
                if guidance_requested
                else "Guidance was not requested this turn; avoid advisory phrasing."
            )
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
