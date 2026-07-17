from pathlib import Path

import pytest

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Container Tester") ["character_id"]
    rt.enter_world(cid)
    return rt, cid


def out(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def test_nested_inventory_display_and_persistent_get_put(tmp_path):
    rt, cid = make_runtime(tmp_path)
    pack = rt.spawn_item("traveler_pack", "character", owner_id=cid)
    pouch = rt.spawn_item("component_pouch", "character", owner_id=cid)
    sword = rt.spawn_item("rusty_sword", "character", owner_id=cid)

    assert "You put" in out(rt, cid, "put 2.component pouch backpack")
    assert "You put" in out(rt, cid, "put 2.rusty sword 2.component pouch")
    text = out(rt, cid, "inventory")
    assert "Traveler" in text and "Pack" in text
    assert "pouch" in text.lower()
    assert "Rusty Sword" in text
    assert "weight" not in text.lower()

    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    assert any(i["template_id"] == "rusty_sword" for c in rt2._fetch_items("owner_type='container'", ()) for i in rt2.find_container_items(c["instance_id"]))
    assert rt2.validate_item_ownership()["ok"]


def test_container_state_and_recursive_rejection(tmp_path):
    rt, cid = make_runtime(tmp_path)
    pack = rt.spawn_item("traveler_pack", "character", owner_id=cid)
    pouch = rt.spawn_item("component_pouch", "character", owner_id=cid)
    assert "close" in out(rt, cid, "close backpack").lower()
    assert "closed" in out(rt, cid, "put component pouch backpack").lower()
    assert "open" in out(rt, cid, "open backpack").lower()
    assert "You put" in out(rt, cid, "put 2.component pouch backpack")
    actual_pouch = next(i for c in rt.find_inventory_items(cid) if c["template_id"] == "traveler_pack" for i in rt.find_container_items(c["instance_id"]) if i["template_id"] == "component_pouch")
    actual_pack_id = actual_pouch["owner_id"]
    with pytest.raises(ValueError):
        rt.move_item(actual_pack_id, "container", pouch["instance_id"])
    assert rt.validate_item_ownership()["ok"]


def test_all_dot_selector_and_examine_container(tmp_path):
    rt, cid = make_runtime(tmp_path)
    pack = rt.spawn_item("traveler_pack", "character", owner_id=cid)
    rt.spawn_item("rusty_sword", "character", owner_id=cid)
    rt.spawn_item("rusty_sword", "character", owner_id=cid)
    expected = sum(1 for i in rt.find_inventory_items(cid) if "sword" in i["name"].lower())
    msg = out(rt, cid, "put all.sword backpack")
    packed = [i for i in rt.find_inventory_items(cid) if i["template_id"] == "traveler_pack" and rt.find_container_items(i["instance_id"])]
    assert packed
    pack = packed[0]
    assert sum(1 for i in rt.find_container_items(pack["instance_id"]) if "sword" in i["name"].lower()) == expected
    assert "Weight:" in out(rt, cid, "examine backpack")
    take = out(rt, cid, "get all backpack")
    assert sum(1 for i in rt.find_inventory_items(cid) if "sword" in i["name"].lower()) == expected
    assert not rt.find_container_items(pack["instance_id"])
