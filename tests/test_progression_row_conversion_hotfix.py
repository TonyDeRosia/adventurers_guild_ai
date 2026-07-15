import sqlite3
from types import SimpleNamespace

import pytest

from engine.display_services import CharacterDisplaySnapshotService
from engine.mud_displays import build_score_document, build_worth_document, render_display_plain
from engine.mud_state_store import MUDStateStore
from engine.progression import ProgressionService, row_to_mapping


class TupleProgressionStore(MUDStateStore):
    def initialize(self):
        MUDStateStore(self.campaign_id, self.world_id, db_path=self.db_path).initialize()

    def connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = None
        return con


def _character():
    return SimpleNamespace(
        id="Kraevok-production-regression-actor-id-with-long-first-column",
        character_id="Kraevok-production-regression-actor-id-with-long-first-column",
        name="Kraevok",
        level=1,
        xp=0,
        race="Human",
        char_class="Adventurer",
        inventory=[],
        equipment=[],
        actor_data={},
        age=22,
        play_time="1 hour",
        current_weight=1,
        carry_capacity=100,
        encumbrance_text="Unburdened",
        posture="standing",
        hunger="Satisfied",
        thirst="Hydrated",
        quest_summary={"completed_count": 0, "quest_points": 0},
        calculated_stats={
            "armor": 0, "evasion": 0, "spell_saves": 0, "hit_bonus": 0,
            "damage_bonus": 0, "accuracy": 0, "critical_melee": 0,
            "critical_spell": 0, "critical_heal": 0,
        },
        weapon_damage_summary={"weapon_name": "Unarmed", "minimum_damage": 1, "maximum_damage": 2},
        unarmed_damage_summary={"minimum_damage": 1, "maximum_damage": 2},
        attributes={"strength": {"base": 10, "final": 10}},
        currency={"gold": 7, "diamonds": 0, "glory": 0, "bank": 0},
    )


def _seed(store):
    svc = ProgressionService(store)
    state = svc.initialize_actor_progression(
        _character().id,
        defaults={"race_id": "human", "species_id": "humanoid", "primary_class_id": "adventurer"},
    )
    return svc, state


def test_row_to_mapping_rejects_positional_without_description():
    with pytest.raises(TypeError, match="cursor_description"):
        row_to_mapping(("Kraevok-production-regression-actor-id-with-long-first-column", 1))


def test_progression_handles_tuple_and_sqlite_row_connections(tmp_path):
    normal = MUDStateStore("c", "shattered_realms", db_path=tmp_path / "normal.sqlite")
    tuple_store = TupleProgressionStore("c", "shattered_realms", db_path=tmp_path / "tuple.sqlite")
    for store in (normal, tuple_store):
        store.initialize()
        svc, seeded = _seed(store)
        state = svc.get_actor_progression(_character().id)
        assert state["actor_id"] == _character().id
        assert state["race_id"] == "human"
        assert isinstance(state["profession_ids"], list)
        assert state["metadata"]["profile_id"] == ""

        with store.connect() as con:
            cur = con.execute(
                "SELECT actor_id,level FROM actor_progression_state WHERE actor_id=?",
                (_character().id,),
            )
            raw = cur.fetchone()
            mapped = row_to_mapping(raw, cur.description)
        assert mapped["actor_id"] == _character().id
        assert mapped["level"] == seeded["level"]


def test_progression_display_score_and_worth_rebuild_after_tuple_row(tmp_path):
    store = TupleProgressionStore("c", "shattered_realms", db_path=tmp_path / "tuple.sqlite")
    store.initialize()
    svc, _ = _seed(store)
    runtime = SimpleNamespace(_progression_service=lambda: svc, performance_counters={})
    character = _character()
    display = CharacterDisplaySnapshotService(runtime)

    first = display.build_snapshot(character)
    score_text = render_display_plain(build_score_document(snapshot=first, mode="full"))
    worth_text = render_display_plain(build_worth_document(worth_snapshot=display.build_worth_snapshot(character)))
    second = display.build_snapshot(character)

    assert "score_projection_incomplete" not in score_text
    assert "Kraevok" in score_text
    assert "Your character data could not be loaded completely" not in score_text
    assert "Gold" in worth_text
    assert second.race["id"] == "human"
