"""Durable player presentation preferences."""
from __future__ import annotations

import json, re, sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_PRESETS = {"compact", "classic", "combat", "explorer", "minimal"}
WIDTH_MIN, WIDTH_MAX = 40, 160

@dataclass(frozen=True)
class PlayerPresentationPreferences:
    character_id: str
    prompt_preset: str | None = None
    prompt_template: str | None = None
    display_theme: str | None = None
    display_width: int | None = None

class PlayerPresentationPreferenceService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.initialize()

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS character_presentation_preferences(
                character_id TEXT PRIMARY KEY,
                prompt_preset TEXT,
                prompt_template TEXT,
                display_theme TEXT,
                display_width INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")

    def _repair(self, raw: dict[str, Any]) -> dict[str, Any]:
        preset = str(raw.get("prompt_preset") or "").lower() or None
        if preset and preset not in VALID_PRESETS: preset = None
        width = raw.get("display_width")
        try: width = int(width) if width not in (None, "") else None
        except Exception: width = None
        if width is not None and not (WIDTH_MIN <= width <= WIDTH_MAX): width = None
        theme = str(raw.get("display_theme") or "").strip() or None
        if theme and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", theme): theme = None
        template = raw.get("prompt_template")
        template = str(template) if template not in (None, "") else None
        return {"prompt_preset": preset, "prompt_template": template, "display_theme": theme, "display_width": width}

    def load(self, character_id: str) -> PlayerPresentationPreferences:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT prompt_preset,prompt_template,display_theme,display_width FROM character_presentation_preferences WHERE character_id=?", (character_id,)).fetchone()
        repaired = self._repair(dict(zip(("prompt_preset","prompt_template","display_theme","display_width"), row)) if row else {})
        return PlayerPresentationPreferences(character_id, **repaired)

    def apply_to_character(self, character: Any) -> PlayerPresentationPreferences:
        cid = str(getattr(character, "id", getattr(character, "character_id", "")))
        prefs = self.load(cid)
        store = getattr(character, "preferences", None) or {}
        for k in ("prompt_preset", "prompt_template", "display_theme", "display_width"):
            v = getattr(prefs, k)
            if v is not None: store[k] = v; setattr(character, k, v)
            elif k in store: store.pop(k, None); setattr(character, k, None)
        setattr(character, "preferences", store)
        return prefs

    def save(self, character_id: str, **values: Any) -> PlayerPresentationPreferences:
        current = self.load(character_id)
        raw = {"prompt_preset": current.prompt_preset, "prompt_template": current.prompt_template, "display_theme": current.display_theme, "display_width": current.display_width}
        raw.update(values)
        repaired = self._repair(raw)
        with sqlite3.connect(self.db_path) as con:
            con.execute("""INSERT INTO character_presentation_preferences(character_id,prompt_preset,prompt_template,display_theme,display_width,updated_at)
                           VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                           ON CONFLICT(character_id) DO UPDATE SET prompt_preset=excluded.prompt_preset,prompt_template=excluded.prompt_template,display_theme=excluded.display_theme,display_width=excluded.display_width,updated_at=CURRENT_TIMESTAMP""",
                        (character_id, repaired["prompt_preset"], repaired["prompt_template"], repaired["display_theme"], repaired["display_width"]))
        return PlayerPresentationPreferences(character_id, **repaired)

    def reset_prompt(self, character_id: str) -> PlayerPresentationPreferences:
        return self.save(character_id, prompt_preset=None, prompt_template=None)
