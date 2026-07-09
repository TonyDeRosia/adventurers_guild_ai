from pathlib import Path

from engine.mud_runtime import MudRuntime
from smart_mud.event_bus import EventBus


def make_runtime(tmp_path):
    bus = EventBus()
    events = []
    for name in ["before_item_pickup","item_picked_up","inventory_changed","room_inventory_changed","after_item_pickup"]:
        bus.subscribe(name, lambda event: events.append(event.event_name), source=f"test_{name}")
    rt = MudRuntime(Path.cwd(), tmp_path, event_bus=bus)
    rt.load_world("shattered_realms")
    return rt, events


def make_char(rt):
    return rt.create_character(world_id="shattered_realms", name="Phase Tester")['character_id']


def test_item_templates_are_loaded_and_immutable(tmp_path):
    rt, _ = make_runtime(tmp_path)
    assert "rusty_sword" in rt.item_templates
    assert rt.item_templates["rusty_sword"]["item_type"] == "weapon"
    try:
        rt.item_templates["rusty_sword"]["name"] = "changed"
    except TypeError:
        pass
    assert rt.item_templates["rusty_sword"]["name"] == "Rusty Sword"


def test_starter_inventory_equipment_and_persistence(tmp_path):
    rt, _ = make_runtime(tmp_path)
    cid = make_char(rt)
    assert any(i["template_id"] == "rusty_sword" for i in rt.find_inventory_items(cid))
    out = rt.handle_input(cid, "wield rusty sword")["output"]
    assert "equip Rusty Sword" in out
    assert any(i["equipped_slot"] == "main_hand" for i in rt.find_equipped_items(cid))
    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    assert any(i["template_id"] == "rusty_sword" for i in rt2.find_equipped_items(cid))


def test_room_seeding_get_drop_and_render_persist(tmp_path):
    rt, events = make_runtime(tmp_path)
    cid = make_char(rt)
    char = rt.state_store.load_character(cid)
    assert any(i["template_id"] == "fountain" for i in rt.find_room_items(char.room_id))
    seeded_count = len(rt.find_room_items(char.room_id))
    rt._seed_room_items()
    assert len(rt.find_room_items(char.room_id)) == seeded_count
    assert "Fountain" in rt.handle_input(cid, "look")["output"]
    assert rt.handle_input(cid, "get fountain")["output"].strip() == "You cannot take that."
    assert any(i["template_id"] == "fountain" for i in rt.find_room_items(char.room_id))
    assert "You aren't carrying that." in rt.handle_input(cid, "drop fountain")["output"]
    rt2 = MudRuntime(Path.cwd(), tmp_path)
    rt2.load_world("shattered_realms")
    assert any(i["template_id"] == "fountain" for i in rt2.find_room_items(char.room_id))
    pickup = [e for e in events if e in {"before_item_pickup","item_picked_up","inventory_changed","room_inventory_changed","after_item_pickup"}]
    assert pickup == []


def test_equipment_commands_conflicts_and_rendering(tmp_path):
    rt, _ = make_runtime(tmp_path)
    cid = make_char(rt)
    assert "equip Small Lantern" in rt.handle_input(cid, "hold lantern")["output"]
    assert "Light: Small Lantern" in rt.handle_input(cid, "equipment")["output"]
    assert "Small Lantern" not in rt.handle_input(cid, "inventory")["output"]
    assert "remove Small Lantern" in rt.handle_input(cid, "rem light")["output"]
    rt.item_templates["rusty_sword"] = {**dict(rt.item_templates["rusty_sword"]), "wear_slots": ["both_hands"]}
    assert "equip Rusty Sword" in rt.handle_input(cid, "wield rusty sword")["output"]
    assert any(i.get("equipped_slot") == "both_hands" for i in rt.find_equipped_items(cid))


def test_keyword_resolution_and_object_commands(tmp_path):
    rt, _ = make_runtime(tmp_path)
    cid = make_char(rt)
    items = rt.find_inventory_items(cid)
    assert rt.resolve_item_keywords("the rusty sword", items)["status"] == "ok"
    assert rt.resolve_item_keywords("traveler", items)["status"] == "ok"
    assert "nicked" in rt.handle_input(cid, "examine rusty sword")["output"]
    rt.spawn_item("rusty_sword", "character", owner_id=cid)
    assert "Which do you mean" in rt.handle_input(cid, "drop sword")["output"]
    assert "aren't carrying" in rt.handle_input(cid, "drop missingthing")["output"]


def test_movement_preserves_inventory_and_equipment(tmp_path):
    rt, _ = make_runtime(tmp_path)
    cid = make_char(rt)
    rt.handle_input(cid, "wield rusty sword")
    before_inv = [i["instance_id"] for i in rt.find_inventory_items(cid)]
    before_eq = [i["instance_id"] for i in rt.find_equipped_items(cid)]
    rt.handle_input(cid, "north")
    assert [i["instance_id"] for i in rt.find_inventory_items(cid)] == before_inv
    assert [i["instance_id"] for i in rt.find_equipped_items(cid)] == before_eq
