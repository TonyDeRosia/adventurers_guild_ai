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
        self.campaign_state_root = self.save_dir / "campaign_state"
        self.campaign_state_root.mkdir(parents=True, exist_ok=True)

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
        state_root = self.campaign_state_root / slot
        state_root.mkdir(parents=True, exist_ok=True)
        print(f"[campaign-memory] save campaign={slot}")
        print(f"[campaign-memory] isolated_state_root={state_root}")
        return path

    def load(self, slot: str = "autosave") -> CampaignState | None:
        path = self._save_path(slot)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_settings = payload.get("settings", {}) if isinstance(payload, dict) else {}
            if not isinstance(raw_settings, dict):
                raw_settings = {}
            missing_fields: list[str] = []
            if "campaign_auto_visuals_enabled" not in raw_settings:
                missing_fields.append("campaign_auto_visuals_enabled")
            if "suggested_moves_enabled" not in raw_settings:
                missing_fields.append("suggested_moves_enabled")
            print(f"[settings-defaults] existing_campaign_preserved=true campaign={slot}")
            if missing_fields:
                print(
                    "[settings-defaults] existing_campaign_missing_fields "
                    f"campaign={slot} initialized={','.join(missing_fields)}"
                )
            loaded = CampaignState.from_dict(payload)
            print(f"[campaign-memory] load campaign={slot}")
            print(f"[campaign-memory] isolated_state_root={self.campaign_state_root / slot}")
            print(f"[campaign-memory] loaded_inventory_items={len(loaded.player.inventory)}")
            print(f"[campaign-memory] loaded_spell_count={len(loaded.structured_state.runtime.spellbook)}")
            print(f"[campaign-memory] loaded_npc_states={len(loaded.structured_state.runtime.npc_relationships)}")
            return loaded
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            if path.exists():
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = path.with_suffix(f".corrupt.{timestamp}.json")
                path.replace(backup)
            return None

    def exists(self, slot: str = "autosave") -> bool:
        return self._save_path(slot).exists()
