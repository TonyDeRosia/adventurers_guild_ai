from types import SimpleNamespace

from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace


def char(role="builder"):
    return SimpleNamespace(id="c1", account_id="a1", name="Tester", role=role, world_id="shattered_realms", room_id="start", level=1, hp=1, max_hp=1, mana=1, max_mana=1, stamina=1, max_stamina=1, xp=0, gold=0, inventory=[], equipment={}, abilities=[], affects={}, preferences={})


def test_desc_alias_and_save_alias_messages(tmp_path):
    e = MudCommandEngine()
    e.builder = BuilderWorkspace(worlds_dir=tmp_path)
    c = char()
    assert "Enable Builder Mode first" in e.handle_command(c, "desc text").narrative
    assert "Builder save commands require Builder Mode" in e.handle_command(c, "rsave").narrative
    assert e.handle_command(c, "builder on").ok
    assert e.handle_command(c, "rcreate hotfix_room").ok
    desc = e.handle_command(c, "desc A normalized test room.")
    assert desc.ok
    assert "Description updated for room hotfix_room" in desc.narrative
    assert "Builder Status:" in desc.narrative
    save = e.handle_command(c, "rsave")
    assert save.ok
    assert "Routing to builder save" in save.narrative


def test_room_name_id_safety_and_draft_normalization(tmp_path):
    e = MudCommandEngine()
    e.builder = BuilderWorkspace(worlds_dir=tmp_path)
    c = char()
    e.handle_command(c, "builder on")
    e.handle_command(c, "rcreate safe_room")
    rejected = e.handle_command(c, "rname safe_room")
    assert not rejected.ok
    assert "looks like a room ID" in rejected.narrative
    forced = e.handle_command(c, "rname --force safe_room")
    assert forced.ok
    drafts = e.builder.load("shattered_realms")
    room = drafts["rooms"]["safe_room"]
    for key in ["id", "name", "description", "world_id", "area_id", "zone_id", "exits", "features", "flags", "tags", "plugin_data"]:
        assert key in room
