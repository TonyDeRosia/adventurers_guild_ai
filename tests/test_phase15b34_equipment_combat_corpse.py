from pathlib import Path
from datetime import datetime, timezone, timedelta

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Kraevok")['character_id']
    return rt, cid


def out(rt, cid, cmd):
    return rt.handle_input(cid, cmd)["output"]


def move_to_wolf_room(rt, cid):
    ch = rt.state_store.load_character(cid)
    ch.room_id = "emberwood_hunting_trail"
    rt.state_store.save_character(ch, "shattered_realms")
    rt.active_characters[cid] = ch
    return ch


def test_equipment_uses_canonical_slots_and_suppresses_duplicate_instance_projection(tmp_path):
    rt, cid = make_runtime(tmp_path)
    assert "equip Small Lantern" in out(rt, cid, "hold lantern")
    lantern = rt.find_equipped_items(cid)[0]
    rt.move_item(lantern["instance_id"], "equipment", cid, equipped_slot="off_hand,light")
    text = out(rt, cid, "eq")
    assert "Main hand" in text and "Off hand" in text and "nothing" in text
    assert text.split("╚", 1)[0].count("Small Lantern") == 1


def test_combat_selects_equipped_sword_not_unarmed_punch(tmp_path):
    rt, cid = make_runtime(tmp_path)
    move_to_wolf_room(rt, cid)
    wolf = rt.resolve_entity_keywords("wolf", rt.find_visible_entities("emberwood_hunting_trail", rt.state_store.load_character(cid)).get("mobs", []))["entity"]
    st = dict(wolf.get("state") or {}); st["current_health"] = 999; st["maximum_health"] = 999
    rt.update_entity_state(wolf["entity_id"], st)
    assert "equip Rusty Sword" in out(rt, cid, "wield rusty sword")
    text = out(rt, cid, "kill wolf")
    assert "Rusty Sword" in text or "slash" in text.lower()
    assert "punch" not in text.lower()


def test_corpse_loot_sacrifice_and_decay_use_runtime_commands(tmp_path):
    rt, cid = make_runtime(tmp_path)
    ch = move_to_wolf_room(rt, cid)
    wolf = rt.resolve_entity_keywords("wolf", rt.find_visible_entities(ch.room_id, ch).get("mobs", []))["entity"]
    corpse = rt.create_corpse(wolf["entity_id"], death_id="phase15b34", killer_actor_id=f"character:{cid}")
    rt.spawn_item("wolf_pelt", "corpse", owner_id=corpse["entity_id"])
    assert "Inside the corpse" in out(rt, cid, "look inside corpse")
    take = out(rt, cid, "take wolf pelt from corpse")
    assert "Wolf Pelt" in take
    assert any(i["template_id"] == "wolf_pelt" for i in rt.find_inventory_items(cid))
    out(rt, cid, "get all from corpse")
    assert not rt.find_container_items(corpse["entity_id"])
    assert "empty" in out(rt, cid, "loot corpse").lower()
    assert "sacrifice" in out(rt, cid, "sac corpse").lower()
    assert "don't see" in out(rt, cid, "sacrifice corpse").lower()

    corpse2 = rt.spawn_entity("forest_wolf", entity_type="corpse", room_id=ch.room_id, state={
        "current_state": "corpse", "is_alive": False, "container_open": True,
        "created_at_utc": (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
        "decay_at_utc": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "decay_seconds": 1,
    }, flags=["corpse"])
    assert rt.process_corpse_decay() >= 1
    assert not rt.find_entity(corpse2["entity_id"])
