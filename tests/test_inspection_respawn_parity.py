import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path, name="Inspect Tester"):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name=name)["character_id"]
    return rt, cid


def output(rt, cid, cmd):
    return rt.handle_input(cid, cmd)["output"]


def test_targeted_fountain_look_variants_do_not_render_room(tmp_path):
    rt, cid = make_runtime(tmp_path)
    room = output(rt, cid, "look")
    assert "Guildhall Crossing Square" in room
    for cmd in ["look fountain", "l fountain", "look at fountain"]:
        text = output(rt, cid, cmd)
        assert "Fountain" in text
        assert "weathered stone fountain" in text
        assert "Guildhall Crossing Square" not in text
        assert "[ Exits:" not in text
        assert "Old Gate" not in text
    detailed = output(rt, cid, "examine fountain")
    assert "Age has softened" in detailed
    assert "Possible interactions" in detailed
    assert "Guildhall Crossing Square" not in detailed
    assert "Age has softened" in output(rt, cid, "inspect fountain")


def test_item_modes_are_distinct_for_flask(tmp_path):
    rt, cid = make_runtime(tmp_path)
    rt.handle_input(cid, "east")
    rt.handle_input(cid, "get flask")
    look = output(rt, cid, "look flask")
    examine = output(rt, cid, "examine flask")
    identify = output(rt, cid, "identify flask")
    assert "stoppered leather flask" in look
    assert "treated hide" in examine
    assert "Weight:" in identify and "Value:" in identify
    assert "treated hide" not in identify
    assert look != identify


def test_direction_actor_runtime_object_and_corpse_inspection(tmp_path):
    rt, cid = make_runtime(tmp_path)
    assert "North" in output(rt, cid, "look north") or "north" in output(rt, cid, "look north").lower()
    ch = rt.state_store.load_character(cid)
    ch.room_id = "emberwood_hunting_trail"
    rt.state_store.save_character(ch, "shattered_realms")
    wolf = output(rt, cid, "look wolf")
    assert "Forest Wolf" in wolf and "wary eyes" in wolf
    ent = rt.resolve_entity_keywords("wolf", rt.find_visible_entities("emberwood_hunting_trail", ch).get("mobs", []))["entity"]
    corpse = rt.create_corpse(ent["entity_id"], death_id="death_test", killer_actor_id=f"character:{cid}")
    assert corpse
    assert "corpse" in output(rt, cid, "look corpse").lower()
    assert "Inside the corpse" in output(rt, cid, "look in corpse") or "corpse is empty" in output(rt, cid, "look in corpse")


def test_forest_wolf_respawn_queue_restart_and_new_lifecycle(tmp_path):
    rt, cid = make_runtime(tmp_path)
    ch = rt.state_store.load_character(cid)
    ch.room_id = "emberwood_hunting_trail"
    rt.state_store.save_character(ch, "shattered_realms")
    wolf = rt.resolve_entity_keywords("wolf", rt.find_visible_entities(ch.room_id, ch).get("mobs", []))["entity"]
    old_lifecycle = (wolf.get("state") or {}).get("lifecycle_id")
    rt.create_corpse(wolf["entity_id"], death_id="death_respawn_a", killer_actor_id=f"character:{cid}")
    assert not rt.resolve_entity_keywords("wolf", rt.find_visible_entities(ch.room_id, ch).get("mobs", [])).get("entity")
    with sqlite3.connect(rt.state_store.db_path) as con:
        row = con.execute("SELECT due_at,state FROM entity_respawn_queue WHERE template_id='forest_wolf'").fetchone()
        assert row and row[1] == "WAITING_TO_RESPAWN"
        due = datetime.fromisoformat(row[0])
        assert 55 <= (due - datetime.now(timezone.utc)).total_seconds() <= 65
    early = (due - timedelta(seconds=1)).isoformat()
    assert rt.process_due_entity_respawns(early) == []
    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    assert rt2.process_due_entity_respawns((due + timedelta(seconds=1)).isoformat())
    ch2 = rt2.state_store.load_character(cid)
    living = rt2.find_visible_entities(ch2.room_id, ch2).get("mobs", [])
    wolves = [e for e in living if e.get("template_id") == "forest_wolf"]
    assert len(wolves) == 1
    assert (wolves[0].get("state") or {}).get("lifecycle_id") != old_lifecycle
    assert (wolves[0].get("state") or {}).get("current_health") == (wolves[0].get("state") or {}).get("maximum_health")
    rt2.create_corpse(wolves[0]["entity_id"], death_id="death_respawn_b", killer_actor_id=f"character:{cid}")
    with sqlite3.connect(rt2.state_store.db_path) as con:
        assert con.execute("SELECT count(*) FROM entity_respawn_queue WHERE template_id='forest_wolf' AND state='WAITING_TO_RESPAWN'").fetchone()[0] == 1
