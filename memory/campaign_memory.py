"""Campaign memory storage and lifecycle helpers."""

from __future__ import annotations

from engine.entities import CampaignState, ConversationTurn, LongTermMemoryEntry, SessionSummary


class CampaignMemory:
    """Maintains recent, long-term, and summary memory for campaign continuity."""

    def __init__(self, recent_limit: int = 8, long_term_limit: int = 120, summary_limit: int = 48) -> None:
        self.recent_limit = recent_limit
        self.long_term_limit = long_term_limit
        self.summary_limit = summary_limit
        self.conversation_limit = 120

    def record_recent(self, state: CampaignState, memory: str) -> None:
        text = memory.strip()
        if not text:
            return
        state.recent_memory.append(text)
        if len(state.recent_memory) > self.recent_limit:
            state.recent_memory = state.recent_memory[-self.recent_limit :]

    def record_long_term(
        self,
        state: CampaignState,
        *,
        category: str,
        text: str,
        location_id: str | None = None,
        quest_id: str | None = None,
        npc_id: str | None = None,
        weight: int = 1,
    ) -> None:
        memory_id = f"m{state.turn_count}_{len(state.long_term_memory) + 1}"
        state.long_term_memory.append(
            LongTermMemoryEntry(
                id=memory_id,
                category=category,
                text=text.strip(),
                location_id=location_id,
                quest_id=quest_id,
                npc_id=npc_id,
                turn=state.turn_count,
                weight=max(1, weight),
            )
        )
        if len(state.long_term_memory) > self.long_term_limit:
            state.long_term_memory = state.long_term_memory[-self.long_term_limit :]

    def add_session_summary(
        self,
        state: CampaignState,
        *,
        trigger: str,
        summary: str,
        quest_ids: list[str] | None = None,
        npc_ids: list[str] | None = None,
        world_flags: list[str] | None = None,
    ) -> None:
        state.session_summaries.append(
            SessionSummary(
                turn=state.turn_count,
                trigger=trigger,
                summary=summary.strip(),
                location_id=state.current_location_id,
                quest_ids=quest_ids or [],
                npc_ids=npc_ids or [],
                world_flags=world_flags or [],
            )
        )
        if len(state.session_summaries) > self.summary_limit:
            state.session_summaries = state.session_summaries[-self.summary_limit :]

    def add_plot_thread(self, state: CampaignState, thread: str) -> None:
        clean = thread.strip()
        if clean and clean not in state.unresolved_plot_threads:
            state.unresolved_plot_threads.append(clean)

    def resolve_plot_thread(self, state: CampaignState, contains: str) -> None:
        needle = contains.strip().lower()
        if not needle:
            return
        state.unresolved_plot_threads = [t for t in state.unresolved_plot_threads if needle not in t.lower()]

    def add_world_fact(self, state: CampaignState, fact: str) -> None:
        clean = fact.strip()
        if clean and clean not in state.important_world_facts:
            state.important_world_facts.append(clean)

    def record_conversation_turn(
        self,
        state: CampaignState,
        *,
        player_input: str,
        system_messages: list[str],
        narrator_response: str,
        requested_mode: str,
    ) -> None:
        state.conversation_turns.append(
            ConversationTurn(
                turn=state.turn_count,
                player_input=player_input.strip(),
                system_messages=[message.strip() for message in system_messages if message.strip()],
                narrator_response=narrator_response.strip(),
                requested_mode=requested_mode,
                location_id=state.current_location_id,
            )
        )
        if len(state.conversation_turns) > self.conversation_limit:
            state.conversation_turns = state.conversation_turns[-self.conversation_limit :]
