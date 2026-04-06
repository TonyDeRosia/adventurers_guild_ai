"""Lightweight terminal chat-style presentation helpers."""

from __future__ import annotations

from engine.campaign_engine import TurnResult


class TerminalPresenter:
    PREFIX = {
        "player": "🧭 You",
        "narrator": "📜 Narrator",
        "npc": "🗣️ NPC",
        "quest": "📌 Quest",
        "system": "⚙️ System",
    }

    def format_player(self, action: str) -> str:
        return f"{self.PREFIX['player']}: {action}"

    def render_turn(self, result: TurnResult) -> list[str]:
        output: list[str] = []
        for message in result.system_messages:
            output.append(self._format_system_message(message))
        output.append(f"{self.PREFIX['narrator']}: {result.narrative}")
        return output

    def _format_system_message(self, message: str) -> str:
        lowered = message.lower()
        if "quest" in lowered:
            prefix = self.PREFIX["quest"]
        elif "relationship" in lowered or "choose <number>" in lowered or lowered.startswith('"'):
            prefix = self.PREFIX["npc"]
        else:
            prefix = self.PREFIX["system"]
        return f"{prefix}: {message}"
