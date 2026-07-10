from pathlib import Path
from engine.mud_runtime import MudRuntime


def test_feature_ref_resolves_but_is_not_pickupable(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Feature Tester")['character_id']; rt.enter_world(cid)
    char = rt.state_store.load_character(cid); rt.goto_room(char, "blacksmith_stall")
    contents = rt.get_room_contents("blacksmith_stall", char)
    assert any(f["id"] == "blacksmith_anvil" for f in contents["features"])
    assert "anvil" in rt.handle_input(cid, "look anvil")["output"].lower()
    assert "don't see" in rt.handle_input(cid, "get anvil")["output"].lower()
