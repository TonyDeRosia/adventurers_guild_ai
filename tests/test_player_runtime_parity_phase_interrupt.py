from pathlib import Path

from engine.mud_runtime import MudRuntime


def make_runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Parity Tester")["character_id"]
    return rt, cid


def output(rt, cid, command):
    return rt.handle_input(cid, command)["output"]


def move_character(rt, cid, room_id):
    ch = rt.state_store.load_character(cid)
    ch.room_id = room_id
    rt.state_store.save_character(ch, "shattered_realms")
    return rt.state_store.load_character(cid)


def test_targeted_look_read_direction_and_no_silent_output(tmp_path):
    rt, cid = make_runtime(tmp_path)
    move_character(rt, cid, "adventurer_notice_board")
    assert "Adventurer Notice Board" in output(rt, cid, "l")
    assert "notice board" in output(rt, cid, "l board").lower()
    assert "notice board" in output(rt, cid, "look at notice board").lower()
    assert "posted notices" in output(rt, cid, "read board").lower()
    assert "north" in output(rt, cid, "look north").lower()
    missing = output(rt, cid, "look imaginary target")
    assert missing.strip()
    assert "do not see" in missing.lower()


def test_dead_mob_reconciles_out_of_living_rendering_and_targeting(tmp_path):
    rt, cid = make_runtime(tmp_path)
    ch = move_character(rt, cid, "emberwood_hunting_trail")
    wolf = rt.resolve_entity_keywords("wolf", rt.find_room_entities(ch.room_id))["entity"]
    state = dict(wolf["state"])
    state.update({"current_health": 0, "is_alive": True, "current_state": "standing"})
    rt.update_entity_state(wolf["entity_id"], state)
    room = output(rt, cid, "look").lower()
    assert "forest wolf is here" not in room
    assert "forest wolf is standing" not in room
    kill = output(rt, cid, "kill wolf").lower()
    assert "already dead" not in kill


def test_get_all_filters_fixed_features_and_drop_reacquire_portable(tmp_path):
    rt, cid = make_runtime(tmp_path)
    move_character(rt, cid, "adventurer_notice_board")
    got = output(rt, cid, "get all").lower()
    assert "guild token" in got
    assert "notice board" not in got
    inv = output(rt, cid, "inventory").lower()
    assert "guild token" in inv
    assert "notice board" not in inv
    assert "cannot take" in output(rt, cid, "get board").lower()
    dropped = output(rt, cid, "drop guild token").lower()
    assert "you drop guild token" in dropped
    assert "guild token" in output(rt, cid, "get guild token").lower()


def test_clean_water_flask_drinks_and_depletes_through_runtime_path(tmp_path):
    rt, cid = make_runtime(tmp_path)
    move_character(rt, cid, "provisioner_stall")
    assert "clean water flask" in output(rt, cid, "get flask").lower()
    first = output(rt, cid, "drink flask").lower()
    assert "drink clean water" in first or "drink from clean water flask" in first
    # Starting servings come from the canonical consumable profile; consume until empty.
    for _ in range(8):
        last = output(rt, cid, "drink water").lower()
        if "empty" in last:
            break
    assert "empty" in last


def test_multiword_abilities_execute_without_cast_reroute(tmp_path):
    rt, cid = make_runtime(tmp_path)
    skills = output(rt, cid, "skills")
    assert "Set Camp" in skills and "Rank 1" in skills and "Status:" not in skills
    assert "establish" in output(rt, cid, "set camp").lower()
    assert "small campsite" in output(rt, cid, "look camp").lower()
    assert "campfire" in output(rt, cid, "build campfire").lower()
    assert "campfire" in output(rt, cid, "look fire").lower()
