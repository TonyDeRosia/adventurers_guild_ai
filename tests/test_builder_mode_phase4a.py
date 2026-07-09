from types import SimpleNamespace
import shutil
from smart_mud.world_registry import WORLDS_DIR
from engine.mud_commands import MudCommandEngine
from smart_mud.event_bus import EventBus


def char(role="player"):
    return SimpleNamespace(id="c1", account_id="a1", name="Tester", role=role, world_id="shattered_realms", room_id="builder_test_room", level=1, hp=1, max_hp=1, mana=1, max_mana=1, stamina=1, max_stamina=1, xp=0, gold=0, inventory=[], equipment={}, abilities=[], affects={}, preferences={})


def test_player_denied_builder_command():
    e = MudCommandEngine()
    r = e.handle_command(char("player"), "builder on")
    assert not r.ok
    assert "permission" in r.narrative


def test_builder_crud_validate_snapshot_history_events():
    shutil.rmtree(WORLDS_DIR / "shattered_realms" / "builder", ignore_errors=True)
    bus = EventBus(); seen=[]
    for name in ["builder_mode_enabled","builder_room_created","builder_room_updated","builder_exit_created","builder_feature_updated","builder_item_template_created","builder_entity_template_created","builder_spawn_created","builder_validation_run","builder_save_requested","builder_snapshot_created"]:
        bus.subscribe(name, lambda ev: seen.append(ev.event_name), source=name)
    e = MudCommandEngine(event_bus=bus); c = char("builder")
    assert e.handle_command(c, "builder on").ok
    assert e.handle_command(c, "rcreate builder_test_room").ok
    assert e.handle_command(c, "rname Builder Test Room").ok
    assert e.handle_command(c, "rdesc A safe draft room.").ok
    assert e.handle_command(c, "excreate north guildhall_crossing_square").ok
    assert e.handle_command(c, "fcreate fountain").ok
    assert "fountain" in e.handle_command(c, "look fountain").narrative.lower()
    assert e.handle_command(c, "ocreate widget").ok
    assert e.handle_command(c, "mcreate guide").ok
    assert e.handle_command(c, "spawncreate guide_spawn guide").ok
    assert e.handle_command(c, "builder validate").ok
    assert e.handle_command(c, "builder save").ok
    assert e.handle_command(c, "builder snapshot").ok
    assert "Recent builder history" in e.handle_command(c, "builder history").narrative
    assert "Editing room: builder_test_room" in e.handle_command(c, "rstat").narrative
    assert set(["builder_mode_enabled","builder_room_created","builder_room_updated","builder_exit_created","builder_item_template_created","builder_entity_template_created","builder_spawn_created","builder_validation_run","builder_save_requested","builder_snapshot_created"]).issubset(set(seen))


def test_builder_validate_catches_broken_exit():
    e = MudCommandEngine(); c = char("builder"); c.room_id="builder_broken_room"
    e.handle_command(c, "rcreate builder_broken_room")
    e.handle_command(c, "rname Broken")
    e.handle_command(c, "excreate west missing_room_for_validation")
    r = e.handle_command(c, "builder validate")
    assert not r.ok
    assert "missing room" in r.narrative

from pathlib import Path
from engine.mud_runtime import MudStateStore, MudCharacter


def test_owner_and_builder_roles_can_enable_builder():
    e = MudCommandEngine()
    assert e.handle_command(char("owner"), "builder on").ok
    assert e.handle_command(char("admin"), "builder on").ok
    assert e.handle_command(char("builder"), "builder on").ok


def test_whoami_shows_account_and_character_roles():
    e = MudCommandEngine()
    c = char("builder")
    c.account_role = "owner"
    r = e.handle_command(c, "whoami")
    assert r.ok
    assert "Account Role: owner" in r.narrative
    assert "Character Role: builder" in r.narrative
    assert "Effective Role: owner" in r.narrative


def test_player_cannot_grant_roles(tmp_path: Path):
    store = MudStateStore(tmp_path / "mud_state.db")
    e = MudCommandEngine(state_store=store)
    r = e.handle_command(char("player"), "grantrole Tester builder")
    assert not r.ok
    assert "permission" in r.narrative


def test_bootstrap_owner_grants_owner_and_persists_after_reload(tmp_path: Path):
    store = MudStateStore(tmp_path / "mud_state.db")
    store.create_account = None if False else getattr(store, "create_account", None)
    # Seed through the runtime store schema directly to mirror local accounts/characters.
    import sqlite3
    store._init_schema()
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("INSERT INTO accounts(account_id,username,role) VALUES('acct_k','Kraevok','player')")
        conn.execute("INSERT INTO characters(id,account_id,world_id,name,slug,role,immortal_level,builder_enabled,data) VALUES(?,?,?,?,?,?,?,?,?)", ('char_k','acct_k','shattered_realms','Kraevok','kraevok','player',0,0,'{"id":"char_k","name":"Kraevok","role":"player","room_id":"start"}'))
    rec = store.grant_role(account="Kraevok", role="owner", source="cli")
    assert rec["role"] == "owner"
    reloaded = MudStateStore(tmp_path / "mud_state.db")
    loaded = reloaded.load_character("char_k")
    assert loaded.account_role == "owner"
    assert loaded.role == "owner"
    assert MudCommandEngine(state_store=reloaded).handle_command(loaded, "builder on").ok


def test_owner_can_grant_builder(tmp_path: Path):
    store = MudStateStore(tmp_path / "mud_state.db")
    import sqlite3
    store._init_schema()
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("INSERT INTO accounts(account_id,username,role) VALUES('acct_target','Target','player')")
    e = MudCommandEngine(state_store=store)
    owner = char("owner")
    owner.account_id = "acct_owner"
    r = e.handle_command(owner, "grantrole Target builder")
    assert r.ok
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("SELECT role FROM accounts WHERE account_id='acct_target'").fetchone()[0] == "builder"
        log = conn.execute("SELECT account_id,role,source FROM role_grant_log ORDER BY id DESC LIMIT 1").fetchone()
        assert log == ("acct_target", "builder", "game")
