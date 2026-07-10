from pathlib import Path
import sqlite3, json
from engine.mud_runtime import MudRuntime


def test_renderer_uses_runtime_instances_not_declarations_or_names(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    contents = rt.get_room_contents("guildhall_crossing_square", include_builder_metadata=True)
    assert contents["entity_instances"] == []
    assert "entity_spawn_declarations" in contents
    a = rt.spawn_entity("blacksmith_harl", room_id="guildhall_crossing_square", state={"current_state":"idle"})
    b = rt.spawn_entity("blacksmith_harl", room_id="guildhall_crossing_square", state={"current_state":"idle"})
    names = [e["name"] for e in rt.get_room_contents("guildhall_crossing_square")["entity_instances"]]
    assert names.count("Blacksmith Harl") == 2
    assert {a["instance_id"], b["instance_id"]} <= {e["instance_id"] for e in rt.get_room_contents("guildhall_crossing_square")["entity_instances"]}


def test_entityaudit_is_builder_only(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Audit")['character_id']; rt.enter_world(cid)
    assert "permission" in rt.handle_input(cid, "entityaudit here")["output"].lower()
    with sqlite3.connect(rt.state_store.db_path) as conn:
        conn.execute("UPDATE characters SET role='builder', builder_enabled=1, immortal_level=50 WHERE id=?", (cid,))
    char = rt.state_store.load_character(cid); char.builder_mode = True; rt.goto_room(char, "blacksmith_stall")
    out = rt.handle_input(cid, "entityaudit here")["output"]
    assert "Runtime instances:" in out and "Materialization records:" in out and "Duplicate risks:" in out
