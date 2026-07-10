from pathlib import Path
from engine.mud_runtime import MudRuntime


def test_repeated_entity_materialization_paths_are_idempotent(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    before = {e["instance_id"] for e in rt.find_entities(template_id="blacksmith_harl")}
    rt.materialize_world_content("shattered_realms")
    rt.materialize_world_content("shattered_realms")
    rt.materialize_room_content("shattered_realms", "blacksmith_stall")
    after = {e["instance_id"] for e in rt.find_entities(template_id="blacksmith_harl")}
    assert after == before and len(after) == 1
    rt2 = MudRuntime(Path.cwd(), tmp_path); rt2.load_world("shattered_realms")
    assert {e["instance_id"] for e in rt2.find_entities(template_id="blacksmith_harl")} == before
