import sqlite3
from pathlib import Path
from types import SimpleNamespace

from engine.actors import Actor
from engine.phase5f import ActorLifecycleManager, BodyProfileRegistry, PopulationManager, item_occupancy, validate_item_occupancy
from engine.score_renderer import ActorScoreRenderer


def test_body_profiles_include_humanoid_wolf_dragon_and_no_removed_slots():
    reg = BodyProfileRegistry()
    assert "main_hand" in reg.get("humanoid").slot_ids()
    assert "off_hand" in reg.get("humanoid").slot_ids()
    assert "light" in reg.get("humanoid").slot_ids()
    assert "collar" in reg.get("wolf").slot_ids()
    assert "left_wing" in reg.get("dragon").slot_ids()
    for removed in {"primary_weapon", "secondary_weapon", "shield", "quiver", "ranged", "ammo", "both_hands"}:
        assert removed not in reg.get("humanoid").slot_ids()


def test_dynamic_score_rendering_uses_actor_body_profile():
    actor = Actor.create("wolf1", "Grey", "mob")
    actor.body_profile_id = "wolf"
    actor.equipment_profile = {"equipped": {"collar": "silver collar"}}
    text = ActorScoreRenderer().render_equipment(actor)
    assert "Collar" in text and "silver collar" in text
    assert "Main Hand" not in text


def test_equipment_occupancy_two_handed_and_offhand_shield():
    humanoid = BodyProfileRegistry().get("humanoid")
    great_sword = {"name": "Great Sword", "occupies_slots": ["main_hand", "off_hand"]}
    shield = {"name": "Kite Shield", "occupies_slots": ["off_hand"]}
    assert item_occupancy(great_sword) == ["main_hand", "off_hand"]
    assert validate_item_occupancy(humanoid, great_sword) == []
    assert validate_item_occupancy(humanoid, shield) == []


def test_population_startup_unique_and_maintenance(tmp_path: Path):
    defs = [
        {"id": "unique_trainer", "spawn_policy": "persistent_unique", "actor_id": "trainer", "template_id": "trainer", "room_id": "hall"},
        {"id": "wolves", "spawn_policy": "maintain_population", "template_id": "wolf", "room_id": "den", "target_population": 2, "body_profile_id": "wolf"},
    ]
    pm = PopulationManager(tmp_path / "state.sqlite", "test", defs)
    spawned = pm.startup(world_time=10)
    assert len(spawned) == 3
    assert len(pm.startup(world_time=11)) == 0
    assert len(pm.instances("wolves")) == 2


def test_lifecycle_corpse_and_respawn_queue_persist_restart(tmp_path: Path):
    db = tmp_path / "state.sqlite"
    lm = ActorLifecycleManager(db, "test")
    corpse = lm.actor_died("wolf1", "den", world_time=100, respawn_delay=30, spawn_definition_id="wolves")
    assert corpse["corpse_id"].startswith("corpse_")
    reloaded = ActorLifecycleManager(db, "test")
    assert reloaded.get("wolf1")["state"] == "corpse"
    assert reloaded.respawn_due(129) == []
    due = reloaded.respawn_due(130)
    assert due and due[0]["actor_id"] == "wolf1"
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT owner_actor_id FROM corpse_instances").fetchone()[0] == "wolf1"
