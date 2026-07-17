from pathlib import Path
from types import SimpleNamespace

from engine.mud_runtime import MudRuntime
from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace


def test_movement_broadcast_excludes_moving_character(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path / "user_data")
    rt.load_world("shattered_realms")
    a = rt.create_character(world_id="shattered_realms", name="Kraevok")["character_id"]
    b = rt.create_character(world_id="shattered_realms", name="Watcher")["character_id"]
    rt.enter_world(a); rt.enter_world(b)
    rt.active_characters[a].room_id = "guildhall_crossing_square"
    rt.active_characters[b].room_id = "old_gate_road"
    out = rt.handle_input(a, "north")["output"]
    assert "You head north." in out
    assert "Kraevok arrives from the south." not in out
    assert "Kraevok leaves north." not in out
    queued = rt.combat_runtime.drain_output_packets(b)
    assert sum("Kraevok arrives from the south." in m.get("message", "") for m in queued) == 1


def test_builder_status_uses_area_display_name_fallback(tmp_path):
    e = MudCommandEngine()
    e.builder = BuilderWorkspace(worlds_dir=Path.cwd() / "worlds")
    c = SimpleNamespace(id="c1", account_id="a1", name="Builder", role="builder", world_id="shattered_realms", room_id="fallen_oak", builder_mode=True)
    text = e._builder_room_status(c, "fallen_oak", e.builder.load("shattered_realms"))
    assert "Area: Emberwood Edge [emberwood_edge]" in text
    assert "(missing display name)" not in text


def test_shop_commands_are_playable_not_phase_placeholders(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path / "user_data")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Shopper")["character_id"]
    rt.enter_world(cid)
    ch = rt.active_characters[cid]
    ch.room_id = "blacksmith_stall"
    rt.command_engine._economy_service(ch).credit_currency("actor", cid, "gold", 100)
    listing = rt.handle_input(cid, "list")["output"]
    assert "Iron Sword" in listing
    assert "Phase 7B" not in listing
    bought = rt.handle_input(cid, "buy 1")["output"]
    assert "gives you" in bought
    assert "Phase 7B" not in bought
    valued = rt.handle_input(cid, "value sword")["output"]
    assert "will give you" in valued
    sold = rt.handle_input(cid, "sell sword")["output"]
    assert "You sell" in sold
    sell_all = rt.handle_input(cid, "sell all")["output"]
    assert "items for" in sell_all
    assert "Phase 7B" not in sell_all


def test_asave_is_distinct_from_character_save(tmp_path):
    e = MudCommandEngine()
    e.builder = BuilderWorkspace(worlds_dir=tmp_path)
    c = SimpleNamespace(id="c1", account_id="a1", name="Builder", role="builder", world_id="shattered_realms", room_id="start", level=1, hp=1, max_hp=1, mana=1, max_mana=1, stamina=1, max_stamina=1, xp=0, gold=0, inventory=[], equipment={}, abilities=[], affects={}, preferences={})
    assert e.handle_command(c, "builder on").ok
    res = e.handle_command(c, "asave changed")
    assert res.ok
    assert "save complete" in res.narrative.lower()
    assert "Your character is saved automatically" not in res.narrative
    save = e.handle_command(c, "save")
    assert "Routing to builder save" in save.narrative
