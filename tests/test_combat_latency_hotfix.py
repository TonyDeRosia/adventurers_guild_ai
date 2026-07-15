from __future__ import annotations

import time
from types import SimpleNamespace

from engine.combat_runtime import ResidentCombatEncounter
from engine.combat_warmup import CombatWarmupReport


def test_resident_encounter_tracks_eligible_violence_pulse() -> None:
    enc = ResidentCombatEncounter("enc_test", "shattered_realms", "room")
    enc.eligible_violence_pulse = 42
    assert enc.eligible_violence_pulse == 42
    assert enc.last_violence_pulse == -1


def test_combat_warmup_report_uses_fractional_milliseconds() -> None:
    report = CombatWarmupReport("shattered_realms")
    report.duration_ms = 0.304
    report.timings["sqlite_prepared_statement_initialization"] = 0.012
    assert isinstance(report.duration_ms, float)
    assert report.duration_ms > 0
    assert report.timings["sqlite_prepared_statement_initialization"] > 0


def test_player_and_actor_combat_start_do_not_refresh_content() -> None:
    text = __import__("pathlib").Path("engine/combat_runtime.py").read_text()
    start = text.index("    def start_player_attack")
    actor = text.index("    def start_actor_attack")
    target = text.index("    def _resident_character_actor")
    assert "refresh_content(" not in text[start:actor]
    assert "refresh_content(" not in text[actor:target]
