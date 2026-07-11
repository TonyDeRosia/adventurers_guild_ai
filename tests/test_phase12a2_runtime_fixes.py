import sqlite3
from pathlib import Path
from types import SimpleNamespace

from engine.command_registry import CommandRegistry
from engine.mud_commands import MudCommandEngine, CommandResult


class Store:
    def __init__(self, path: Path):
        self.db_path = path
        self.world_id = "shattered_realms"
        self.campaign_id = "shattered_realms"

    def connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con


def _engine(tmp_path):
    return MudCommandEngine(Store(tmp_path / "runtime.sqlite3"))


def _char():
    return SimpleNamespace(id="actor_test", character_id="actor_test", name="Tester", room_id="training_yard", world_id="shattered_realms", role="player", inventory=[])


def test_train_runtime_path_returns_visible_command_result(tmp_path):
    result = _engine(tmp_path).handle_command(_char(), "train")
    assert isinstance(result, CommandResult)
    assert result.ok is True
    assert "Training Master Borik" in result.narrative
    assert "Use TRAIN" in result.narrative
    assert "not implemented" not in result.narrative.lower()
    assert "{" not in result.narrative


def test_practice_and_prac_no_argument_show_balance_guidance(tmp_path):
    engine = _engine(tmp_path)
    for command in ("practice", "prac"):
        result = engine.handle_command(_char(), command)
        assert result.ok is True
        assert "Practice sessions:" in result.narrative
        assert "Use TRAIN" in result.narrative
        assert "That lesson is not available" not in result.narrative


def test_consider_abbreviations_are_read_only(tmp_path):
    engine = _engine(tmp_path)
    for command in ("consider borik", "consid borik", "consi borik"):
        result = engine.handle_command(_char(), command)
        text = result.narrative.lower()
        assert result.ok is True
        assert "you consider borik" in text
        assert "attack" not in text
        assert "clash" not in text
    assert CommandRegistry().resolve("c")[1].startswith("ambiguous")


def test_campfire_player_output_is_prose_not_json(tmp_path):
    engine = _engine(tmp_path)
    char = _char()
    for command in ("campfire", "campfire status", "light campfire", "add fuel", "extinguish campfire"):
        result = engine.handle_command(char, command)
        assert result.narrative.strip()
        assert "{" not in result.narrative
        assert "campfire_instance_id" not in result.narrative
        assert "campsite_instance_id" not in result.narrative
        assert "true" not in result.narrative.lower()


def test_command_normalization_catches_handler_exception(tmp_path, caplog):
    engine = _engine(tmp_path)
    engine.command_handlers["train"] = lambda *_: (_ for _ in ()).throw(RuntimeError("boom internals"))
    result = engine.handle_command(_char(), "train")
    assert result.ok is False
    assert "Something went wrong" in result.narrative
    assert "boom" not in result.narrative


def test_default_world_rooms_do_not_expose_builder_guidance():
    bad = ["playable MUD room", "fixed truth", "GM to narrate", "without inventing"]
    for path in (Path("worlds/shattered_realms/rooms/rooms.json"), Path("data/worlds/shattered_realms/map/rooms.json"), Path("worlds/shattered_realms/builder/rooms.json")):
        text = path.read_text(encoding="utf-8")
        for phrase in bad:
            assert phrase not in text
