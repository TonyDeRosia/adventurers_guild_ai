from pathlib import Path
from engine.mud_runtime import MudRuntime


def test_builder_rcontents_and_stats_are_builder_only(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Diag Player")['character_id']; rt.enter_world(cid)
    assert "permission" in rt.handle_input(cid, "rcontents")["output"].lower()
    
    import sqlite3
    with sqlite3.connect(rt.state_store.db_path) as conn:
        conn.execute("UPDATE characters SET role='builder', builder_enabled=1, immortal_level=50 WHERE id=?", (cid,))
    char = rt.state_store.load_character(cid); char.builder_mode = True
    rt.goto_room(char, "blacksmith_stall")
    out = rt.handle_input(cid, "rcontents here")["output"]
    assert "Runtime item instances" in out and "Item placement declarations" in out and "Materialization records" in out
    item_id = rt.find_room_items("blacksmith_stall")[0]["instance_id"]
    assert item_id in rt.handle_input(cid, f"istat {item_id}")["output"]
    assert "blacksmith_stall_iron_swords_once" in rt.handle_input(cid, "seedstat blacksmith_stall_iron_swords_once")["output"]
