from pathlib import Path
from engine.mud_runtime import MudRuntime


def test_entity_spawn_once_and_context_metadata(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    ents = rt.find_room_entities("blacksmith_stall")
    assert len([e for e in ents if e["template_id"] == "blacksmith_harl"]) == 1
    rt.materialize_world_content("shattered_realms")
    assert len([e for e in rt.find_room_entities("blacksmith_stall") if e["template_id"] == "blacksmith_harl"]) == 1
    ent = rt.find_room_entities("blacksmith_stall")[0]
    assert ent["instance_id"] and ent["template_id"] == "blacksmith_harl"
    assert isinstance(ent.get("plugin_data"), dict)
