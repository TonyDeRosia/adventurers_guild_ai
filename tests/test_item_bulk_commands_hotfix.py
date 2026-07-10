from pathlib import Path

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Bulk Tester")["character_id"]
    rt.enter_world(cid)
    return rt, cid


def out(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def move_to_blacksmith(rt, cid):
    char = rt.state_store.load_character(cid)
    ok, msg = rt.goto_room(char, "blacksmith_stall")
    assert ok, msg
    return rt.state_store.load_character(cid)


def names(items):
    return [i["name"] for i in items]


def test_blacksmith_get_all_takes_every_portable_duplicate_and_ignores_npc(tmp_path):
    rt, cid = make_runtime(tmp_path)
    char = move_to_blacksmith(rt, cid)
    initial = rt.find_room_items(char.room_id)
    extra_iron = next(i["instance_id"] for i in initial if i["name"] == "Iron Sword")
    assert names(initial).count("Iron Sword") == 2
    assert names(initial).count("Training Sword") == 1
    assert "Blacksmith Harl" in out(rt, cid, "look")

    msg = out(rt, cid, "get all")
    assert msg.count("Iron Sword") == 2
    assert msg.count("Training Sword") == 1
    assert extra_iron in {i["instance_id"] for i in rt.find_inventory_items(cid)}
    assert not rt.find_room_items(char.room_id)
    look = out(rt, cid, "look")
    assert "Iron Sword" not in look and "Training Sword" not in look
    assert "Blacksmith Harl" in look and "[ Exits: south ]" in look


def test_take_aliases_match_bulk_get_and_no_portables_message(tmp_path):
    for command in ("take all", "get everything", "take everything"):
        rt, cid = make_runtime(tmp_path / command.replace(" ", "_"))
        char = move_to_blacksmith(rt, cid)
        msg = out(rt, cid, command)
        assert msg.count("Iron Sword") == 2
        assert msg.count("Training Sword") == 1
        assert not rt.find_room_items(char.room_id)
        assert "There is nothing here you can take." in out(rt, cid, "get all")


def test_get_one_duplicate_then_get_all_remaining(tmp_path):
    rt, cid = make_runtime(tmp_path)
    char = move_to_blacksmith(rt, cid)
    first = out(rt, cid, "get iron")
    assert first == "You pick up Iron Sword."
    assert names(rt.find_room_items(char.room_id)).count("Iron Sword") == 1
    msg = out(rt, cid, "get all")
    assert msg.count("Iron Sword") == 1
    assert msg.count("Training Sword") == 1
    assert not rt.find_room_items(char.room_id)


def test_drop_all_round_trip_preserves_ids_and_skips_equipped(tmp_path):
    rt, cid = make_runtime(tmp_path)
    char = move_to_blacksmith(rt, cid)
    out(rt, cid, "get all")
    assert len(rt.find_inventory_items(cid)) >= 3
    assert "equip" in out(rt, cid, "wield iron").lower()
    equipped_ids = {i["instance_id"] for i in rt.find_equipped_items(cid)}
    droppable_ids = [i["instance_id"] for i in rt.find_inventory_items(cid)]
    portable_droppable_ids = [i["instance_id"] for i in rt.find_inventory_items(cid) if (i.get("template") or {}).get("portable", True)]

    msg = out(rt, cid, "drop all")
    assert "Equipped items were not dropped." in msg
    assert {i["instance_id"] for i in rt.find_room_items(char.room_id)} == set(droppable_ids)
    assert {i["instance_id"] for i in rt.find_equipped_items(cid)} == equipped_ids
    assert not set(droppable_ids) & {i["instance_id"] for i in rt.find_inventory_items(cid)}

    out(rt, cid, "get all")
    assert set(portable_droppable_ids) <= {i["instance_id"] for i in rt.find_inventory_items(cid)}
    assert {i["instance_id"] for i in rt.find_equipped_items(cid)} == equipped_ids


def test_bulk_state_survives_look_movement_and_reload_without_reseeding(tmp_path):
    rt, cid = make_runtime(tmp_path)
    char = move_to_blacksmith(rt, cid)
    out(rt, cid, "get all")
    inv_ids = {i["instance_id"] for i in rt.find_inventory_items(cid)}
    assert not rt.find_room_items(char.room_id)
    out(rt, cid, "look")
    out(rt, cid, "south")
    out(rt, cid, "north")
    assert not rt.find_room_items("blacksmith_stall")
    out(rt, cid, "save")

    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    assert inv_ids <= {i["instance_id"] for i in rt2.find_inventory_items(cid)}
    assert not rt2.find_room_items("blacksmith_stall")


def test_drop_everything_empty_inventory_message_and_equipment_safety(tmp_path):
    rt, cid = make_runtime(tmp_path)
    # Starter character has carried starter items; equip/drop them to make the message deterministic.
    out(rt, cid, "wield rusty")
    out(rt, cid, "hold lantern")
    out(rt, cid, "drop all")
    assert "You are not carrying anything you can drop." in out(rt, cid, "drop everything")
    assert rt.find_equipped_items(cid)
