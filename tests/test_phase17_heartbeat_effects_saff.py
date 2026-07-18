from pathlib import Path
from engine.mud_runtime import MudRuntime


def runtime(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Phase Seventeen")['character_id']
    rt.enter_world(cid, session_id="phase17")
    rt.pulse_config["pulses_per_second"] = 1
    rt.pulse_config["pulses_per_tick"] = 60
    rt.pulse_config["point_update_pulse_count"] = 1
    rt.pulse_config["world_hour_pulse_count"] = 1
    rt.heartbeat_config.pulses_per_second = 1
    rt.heartbeat_config.pulses_per_tick = 60
    rt.game_clock.config = rt.heartbeat_config
    return rt, cid


def out(rt, cid, cmd):
    return rt.handle_input(cid, cmd)["output"]


def test_heartbeat_events_clock_and_effect_expiration_idle(tmp_path):
    rt, cid = runtime(tmp_path)
    seen=[]
    for name in ["runtime.pulse","runtime.tick","world.minute","world.hour","world.sunset","character.effect.expired"]:
        rt.event_bus.subscribe(name, lambda ev, n=name: seen.append(ev.event_name), source="test")
    ch=rt.active_characters[cid]
    rt.game_clock.hour = 17
    rt.active_effects.apply_effect(ch, name="fly", category="Spell", duration_ticks=1, expiration_message="You drift slowly to the ground.", flags=["flying"])
    assert "Spell   : fly (1m)" in out(rt,cid,"saff")
    rt.process_runtime_pulse(10**6)
    assert "runtime.pulse" in seen and "runtime.tick" in seen
    assert "world.minute" in seen and "world.hour" in seen and "world.sunset" in seen
    assert "character.effect.expired" in seen
    assert "fly" not in out(rt,cid,"saff")
    assert "You drift slowly to the ground." in rt.async_messages(cid)["messages"][0]["output_text"]


def test_saff_empty_mixed_equipment_permanent_plural_alias_sorting(tmp_path):
    rt, cid = runtime(tmp_path); ch=rt.active_characters[cid]
    empty = out(rt,cid,"saff")
    assert "None." in empty and "0 skills and 0 spells" in empty
    rt.active_effects.apply_effect(ch, name="haste", category="Spell", duration_ticks=2)
    rt.active_effects.apply_effect(ch, name="dread dominion", category="Skill", duration_ticks=1)
    rt.active_effects.apply_effect(ch, name="amulet ward", category="Item", permanent=True, equipment=True)
    text = out(rt,cid,"shortaff")
    assert text.index("Skill   : dread dominion") < text.index("Spell   : haste")
    assert "Equipment effects:\n  Item    : amulet ward (permanent)" in text
    assert "1 skill and 1 spell" in text


def test_position_and_regeneration_from_heartbeat(tmp_path):
    rt, cid = runtime(tmp_path)
    ch=rt.active_characters[cid]
    actor=rt.combat_runtime.resident_actors[f"character:{cid}"]
    actor.resources.health = actor.resources.maximum_health - 4
    assert "You sit down and rest your tired bones." in out(rt,cid,"rest")
    before=actor.resources.health
    rt.process_runtime_pulse(10**6)
    assert actor.resources.health > before
    assert "You go to sleep." in out(rt,cid,"sleep")
    assert "In your dreams, or what?" in out(rt,cid,"look")
    assert "You wake and stand up." in out(rt,cid,"wake")
