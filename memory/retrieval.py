"""Memory retrieval pipeline for play/summarize/analyze prompt context."""

from __future__ import annotations

from dataclasses import dataclass

from engine.entities import CampaignState, LongTermMemoryEntry


@dataclass
class RetrievalRequest:
    location_id: str
    active_quest_ids: list[str]
    current_npc_id: str | None
    recent_actions: list[str]
    important_world_state: list[str]


@dataclass
class RetrievedMemory:
    recent_memory: list[str]
    long_term_memory: list[str]
    session_summaries: list[str]
    unresolved_plot_threads: list[str]
    important_world_facts: list[str]


class MemoryRetrievalPipeline:
    """Retrieves the most relevant memory snippets for current turn context."""

    def retrieve(self, state: CampaignState, request: RetrievalRequest, limit: int = 8) -> RetrievedMemory:
        ranked_entries = sorted(
            state.long_term_memory,
            key=lambda entry: self._score_entry(entry, request, state.turn_count),
            reverse=True,
        )
        selected_long_term = [entry.text for entry in ranked_entries[: max(1, min(limit, len(ranked_entries)))]]

        relevant_summaries = []
        for summary in reversed(state.session_summaries):
            if summary.location_id == request.location_id or any(qid in request.active_quest_ids for qid in summary.quest_ids):
                relevant_summaries.append(summary.summary)
            if len(relevant_summaries) >= 3:
                break

        filtered_recent = [m for m in state.recent_memory if self._memory_matches_request(m, request)]
        if not filtered_recent:
            filtered_recent = state.recent_memory[-4:]

        return RetrievedMemory(
            recent_memory=filtered_recent[-4:],
            long_term_memory=selected_long_term[:4],
            session_summaries=list(reversed(relevant_summaries)),
            unresolved_plot_threads=state.unresolved_plot_threads[:5],
            important_world_facts=state.important_world_facts[:5],
        )

    def _score_entry(self, entry: LongTermMemoryEntry, request: RetrievalRequest, current_turn: int) -> int:
        score = entry.weight
        if entry.location_id and entry.location_id == request.location_id:
            score += 3
        if entry.quest_id and entry.quest_id in request.active_quest_ids:
            score += 4
        if entry.npc_id and request.current_npc_id and entry.npc_id == request.current_npc_id:
            score += 4
        if any(action in entry.text.lower() for action in request.recent_actions):
            score += 2
        if any(flag in entry.text.lower() for flag in request.important_world_state):
            score += 2
        recency_bonus = max(0, 3 - ((current_turn - entry.turn) // 5))
        return score + recency_bonus

    def _memory_matches_request(self, memory: str, request: RetrievalRequest) -> bool:
        text = memory.lower()
        if request.location_id in text:
            return True
        if request.current_npc_id and request.current_npc_id in text:
            return True
        if any(qid in text for qid in request.active_quest_ids):
            return True
        if any(flag in text for flag in request.important_world_state):
            return True
        return any(action in text for action in request.recent_actions)
