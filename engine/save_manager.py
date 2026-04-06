"""Persistence manager for campaign save/load."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine.entities import CampaignState, SessionSummary


class SaveManager:
    """Reads and writes campaign state as JSON."""

    def __init__(self, save_dir: Path) -> None:
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _save_path(self, slot: str) -> Path:
        return self.save_dir / f"{slot}.json"

    def save(self, state: CampaignState, slot: str = "autosave") -> Path:
        latest = state.session_summaries[-1] if state.session_summaries else None
        if latest is None or latest.trigger != f"save:{slot}" or latest.turn != state.turn_count:
            state.session_summaries.append(
                SessionSummary(
                    turn=state.turn_count,
                    trigger=f"save:{slot}",
                    summary=f"Save checkpoint written to slot '{slot}' at turn {state.turn_count}.",
                    location_id=state.current_location_id,
                )
            )
        path = self._save_path(slot)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        return path

    def load(self, slot: str = "autosave") -> CampaignState | None:
        path = self._save_path(slot)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CampaignState.from_dict(payload)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            if path.exists():
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = path.with_suffix(f".corrupt.{timestamp}.json")
                path.replace(backup)
            return None

    def exists(self, slot: str = "autosave") -> bool:
        return self._save_path(slot).exists()
