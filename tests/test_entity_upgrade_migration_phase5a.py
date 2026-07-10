from pathlib import Path
import sqlite3, json
from engine.mud_runtime import MudRuntime


def test_existing_duplicate_is_reported_not_name_deleted(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    rt.spawn_entity("blacksmith_harl", room_id="blacksmith_stall", state={"current_state":"idle", "source_spawn_id":"manual_test"})
    audit = rt.entity_duplication_audit("blacksmith_stall")
    assert "duplicate runtime instances template=blacksmith_harl room=blacksmith_stall" in audit
    assert len([e for e in rt.find_room_entities("blacksmith_stall") if e["template_id"] == "blacksmith_harl"]) == 2
