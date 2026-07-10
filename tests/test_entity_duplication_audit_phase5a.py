from pathlib import Path
import sqlite3, json
from engine.mud_runtime import MudRuntime

ROOMS = [("blacksmith_stall", "Blacksmith Harl", "blacksmith_harl"), ("spell_practice_circle", "Apprentice Mage Lina", "apprentice_mage_lina"), ("training_yard", "Training Master Borik", "training_master_borik")]

def runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms"); return rt

def test_fresh_database_audit_rooms_render_one_entity(tmp_path):
    rt = runtime(tmp_path)
    for room, name, template in ROOMS:
        ents = rt.get_room_contents(room)["entity_instances"]
        assert [e["name"] for e in ents].count(name) == 1
        assert [e["template_id"] for e in ents].count(template) == 1
        assert len([e for e in ents if e["template_id"] == template]) == 1
        audit = rt.entity_duplication_audit(room)
        assert "Duplicate risks:\n- none" in audit
        assert "Runtime instances:" in audit and "Spawn declarations:" in audit and "Legacy declarations:" in audit

def test_upgraded_legacy_seed_instance_is_adopted_not_duplicated(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.active_world_id = "shattered_realms"; rt.active_world = rt.world_registry.load_world("shattered_realms"); rt._load_entity_templates()
    now = "2026-07-10T00:00:00+00:00"
    with sqlite3.connect(rt.state_store.db_path) as conn:
        conn.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("legacy_harl", "shattered_realms", "npc", "blacksmith_harl", "Blacksmith Harl", "[]", "Blacksmith Harl", "Blacksmith Harl", "blacksmith_stall", "room", "", "", 1, json.dumps({"current_state":"idle"}), "[]", now, now, "{}"))
    rt.load_world("shattered_realms")
    ents = [e for e in rt.find_room_entities("blacksmith_stall") if e["template_id"] == "blacksmith_harl"]
    assert [e["instance_id"] for e in ents] == ["legacy_harl"]
    row = rt._materialization_row("entity_spawn", "legacy_blacksmith_stall_blacksmith_harl")
    assert row and row["instance_ids"] == ["legacy_harl"]
