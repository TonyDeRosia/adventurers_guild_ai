from pathlib import Path

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Five")['character_id']
    rt.enter_world(cid)
    char = rt.state_store.load_character(cid)
    ok, msg = rt.goto_room(char, "blacksmith_stall")
    assert ok, msg
    return rt, cid


def test_blacksmith_stall_canonical_instances_and_get_flow(tmp_path):
    rt, cid = make_runtime(tmp_path)
    contents = rt.get_room_contents("blacksmith_stall")
    assert [i["name"] for i in contents["item_instances"]].count("Iron Sword") == 2
    assert [i["name"] for i in contents["item_instances"]].count("Training Sword") == 1
    assert all(i.get("instance_id") for i in contents["item_instances"])
    assert [e["name"] for e in contents["entity_instances"]] == ["Blacksmith Harl"]
    look = rt.handle_input(cid, "look")["output"]
    assert look.count("Iron Sword") == 2 and "Training Sword" in look and "Blacksmith Harl" in look
    assert rt.handle_input(cid, "get iron")["output"] == "You pick up Iron Sword."
    look = rt.handle_input(cid, "look")["output"]
    assert look.count("Iron Sword") == 1 and "Training Sword" in look
    msg = rt.handle_input(cid, "get all")["output"]
    assert msg.count("Iron Sword") == 1 and "Training Sword" in msg
    assert not rt.find_room_items("blacksmith_stall")
    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    assert not rt2.find_room_items("blacksmith_stall")
    assert len(rt2.find_inventory_items(cid)) >= 3


def test_materialization_idempotent_and_template_alone_not_rendered(tmp_path):
    rt, _cid = make_runtime(tmp_path)
    ids = {i["instance_id"] for i in rt.find_room_items("blacksmith_stall")}
    rt.materialize_world_content("shattered_realms")
    rt.materialize_room_content("shattered_realms", "blacksmith_stall")
    assert {i["instance_id"] for i in rt.find_room_items("blacksmith_stall")} == ids
    assert not rt.find_room_items("market_lane")
