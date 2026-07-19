from pathlib import Path
import sqlite3

from app.web import WebRuntime
import os


def _runtime_with_hunter(tmp_path):
    os.environ["SMART_MUD_USER_DATA_DIR"] = str(tmp_path)
    rt = WebRuntime(Path.cwd())
    
    username = "phase18k_" + tmp_path.name.replace("-", "_")
    try:
        rt.create_account({"username": username, "password": ""})
    except Exception:
        rt.login_account({"username": username})
    rt.select_world("shattered_realms")
    import uuid
    suffix = chr(65 + (uuid.uuid4().int % 26)) + chr(65 + ((uuid.uuid4().int // 26) % 26)) + chr(65 + ((uuid.uuid4().int // 676) % 26))
    created = rt.create_character({"name": "Phase Target " + suffix, "race_id": "human", "class_id": "mage"})["character"]
    cid = created["character_id"]
    with sqlite3.connect(rt.mud_runtime.state_store.db_path) as conn:
        for aid in ("magic_missile", "set_camp", "build_campfire", "kick"):
            conn.execute(
                "INSERT OR REPLACE INTO actor_ability_progression(actor_id, ability_id, rank, maximum_rank, proficiency, active) VALUES(?,?,?,?,?,1)",
                (cid, aid, 1, 100, 100),
            )
    rt.enter_world(cid)
    mud = rt.mud_runtime
    char = mud.active_characters[cid]
    old = char.room_id
    char.room_id = "emberwood_hunting_trail"
    mud.move_occupant("character:" + cid, old, char.room_id)
    mud.state_store.save_character(char, mud.active_world_id or "shattered_realms")
    actor = mud.actor_registry.get(cid)
    if actor:
        actor.identity.current_location = char.room_id
    return rt, cid


def test_phase18k_visible_forest_wolf_is_canonical_target(tmp_path):
    rt, cid = _runtime_with_hunter(tmp_path)
    mud = rt.mud_runtime
    char = mud.active_characters[cid]
    visible = mud.find_visible_entities(char.room_id, char)["mobs"] + mud.find_visible_entities(char.room_id, char)["npcs"]
    wolf = next(e for e in visible if e["template_id"] == "forest_wolf")
    assert wolf["instance_id"]
    assert wolf["room_id"] == "emberwood_hunting_trail"
    assert "A forest wolf prowls near the brush." in (rt.handle_input("look")["output_text"])
    actor = mud.actor_registry.get(cid)
    resolved = mud.abilities._resolve_target_canonical(actor, mud.abilities.registry.abilities["magic_missile"], "wolf")
    assert resolved["ok"] is True
    assert resolved["runtime_instance_ids"] == ["entity:" + wolf["instance_id"]]


def test_phase18k_magic_missile_forms_and_skill_invocations(tmp_path):
    rt, _cid = _runtime_with_hunter(tmp_path)
    for command in ["c magic missile wolf", "c magic wolf", "c 'magic missile' wolf", 'c "magic missile" wolf']:
        output = rt.handle_input(command)["output_text"].lower()
        assert "invalid target" not in output
        assert "magic missile" in output or "cooldown" in output or "mana" in output or "ready in" in output
    skills = rt.handle_input("skills")["output_text"].lower()
    # SKILLS is deliberately a compact discoverability display, not help text.
    assert "build campfire" in skills and "set camp" in skills and "100%" in skills
    assert "command:" not in skills and "build_campfire" not in skills and "set_camp" not in skills
    # Routing remains independently covered: the registry command still reaches
    # the canonical ability gateway rather than falling through to HELP.
    routed = rt.handle_input("build campfire")["output_text"].lower()
    assert "help topic" not in routed
