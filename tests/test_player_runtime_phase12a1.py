from types import SimpleNamespace
from pathlib import Path

from engine.mud_commands import MudCommandEngine
from engine.mud_runtime import MudStateStore
from engine.mud_rendering import PRESETS


def make_engine(tmp_path):
    store = MudStateStore(tmp_path / "runtime.sqlite")
    engine = MudCommandEngine(store)
    char = SimpleNamespace(
        id="char_phase12", name="Tester", room_id="guildhall_crossing_square",
        world_id="shattered_realms", role="player", inventory=[], abilities=[],
        level=1, gold=0, hp=100, max_hp=100, mana=50, max_mana=50,
        stamina=100, max_stamina=100, xp=0, equipment={}, affects={},
    )
    return engine, char


def text(engine, char, command):
    return engine.handle_command(char, command).narrative


def test_training_and_quest_player_commands_do_not_emit_placeholders(tmp_path):
    engine, char = make_engine(tmp_path)
    for command in ["train", "practice", "quest", "journal"]:
        out = text(engine, char, command)
        lowered = out.lower()
        assert "not implemented yet" not in lowered
        assert "foundation is available" not in lowered
        assert "builder/admin command" not in lowered
        assert "draft json" not in lowered
    assert "Training options" in text(engine, char, "train")
    assert "Quest Journal" in text(engine, char, "quest")


def test_apostrophe_alias_routes_to_say_and_bare_apostrophe_has_usage(tmp_path):
    engine, char = make_engine(tmp_path)
    assert text(engine, char, "'hello") == '{dialogue}You say, "hello."{/dialogue}'
    assert "Usage:" in text(engine, char, "'")


def test_gathering_campfire_property_and_consider_are_player_safe(tmp_path):
    engine, char = make_engine(tmp_path)
    commands = ["resources here", "gather", "campfire", "property", "consider borik", "attack wolf"]
    for command in commands:
        out = text(engine, char, command)
        lowered = out.lower()
        assert "unknown command" not in lowered
        assert "runtime actor instance" not in lowered
        assert "not available yet" not in lowered
        assert "command recognized" not in lowered
    assert "comparable" in text(engine, char, "consider borik").lower()


def test_dialogue_role_is_white_in_backend_presets_and_css():
    assert PRESETS["Dark Fantasy"]["dialogue"].lower() == "#ffffff"
    assert PRESETS["Green Terminal"]["dialogue"].lower() == "#ffffff"
    css = Path("app/static/styles.css").read_text()
    assert '#mud-world-output span[role="dialogue"]' in css
    assert "color: #ffffff" in css
