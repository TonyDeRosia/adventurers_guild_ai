from types import SimpleNamespace

from engine.display_services import CharacterDisplaySnapshotService
from engine.mud_commands import MudCommandEngine
from tests.test_phase13c3_b_score import frozen_snapshot


class CountingService:
    def __init__(self):
        self.snapshot_calls = 0
        self.worth_calls = 0
    def build_snapshot(self, character):
        self.snapshot_calls += 1
        return frozen_snapshot()
    def build_worth_snapshot(self, character):
        self.worth_calls += 1
        return SimpleNamespace(currencies={"gold": 7})


def test_score_requests_one_display_snapshot_and_worth_requests_none():
    svc = CountingService()
    engine = MudCommandEngine()
    engine.character_display_snapshots = svc
    char = SimpleNamespace(id="c1", name="Aster", role="player")

    assert engine._cmd_score(char, [], "score").ok
    assert svc.snapshot_calls == 1
    assert svc.worth_calls == 0

    assert engine._cmd_worth(char, [], "worth").ok
    assert svc.snapshot_calls == 1
    assert svc.worth_calls == 1


def test_display_snapshot_cache_reuses_unchanged_and_invalidates_equipment_effects_currency():
    char = SimpleNamespace(
        id="c1", name="Aster", level=1, xp=0, gold=0, room_id="r1",
        inventory=[], equipment=[], effects=[], attributes={"strength": 10}, calculated_stats={"armor": 1},
    )
    svc = CharacterDisplaySnapshotService()
    first = svc.build_snapshot(char)
    assert svc.build_snapshot(char) is first
    assert svc.last_cache_hit is True

    char.equipment.append({"id": "boots"})
    assert svc.build_snapshot(char) is not first
    equipment_snapshot = svc.build_snapshot(char)

    char.effects.append({"name": "Bless"})
    assert svc.build_snapshot(char) is not equipment_snapshot

    worth = svc.build_worth_snapshot(char)
    assert svc.build_worth_snapshot(char) is worth
    char.gold = 12
    assert svc.build_worth_snapshot(char) is not worth


def test_score_modes_do_not_build_detailed_formula_traces_or_unused_compact_sections():
    engine = MudCommandEngine()
    engine.character_display_snapshots = CountingService()
    char = SimpleNamespace(id="c1", name="Aster", role="player")
    normal = engine._cmd_score(char, [], "score").narrative
    compact = engine._cmd_score(char, ["compact"], "score compact").narrative
    assert "SNAPSHOT DIAGNOSTICS" not in normal
    assert "FORMULA DEBUG" not in normal
    assert "ACTIVE EFFECTS" not in compact
