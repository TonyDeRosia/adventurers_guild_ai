from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from app.web import WebRuntime
from engine.mud_displays import render_object, render_room
from smart_mud.transport import html_to_plain_text


def test_exactly_one_smart_mud_room_renderer_symbol_exists() -> None:
    roots = [Path("engine"), Path("smart_mud"), Path("app")]
    defs = []
    for root in roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            defs.extend((str(path), node.lineno) for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "render_room")
    assert [path for path, _line in defs] == ["engine/mud_displays.py"]


def test_canonical_room_layout_empty_and_populated_visibility_order() -> None:
    empty = SimpleNamespace(title="Empty Room", description="A quiet place.", exits=[{"direction": "north"}], players=[], npcs=[], mobs=[], objects=[])
    empty_text = html_to_plain_text(render_room(empty, {}))
    assert empty_text == "Empty Room\n\nA quiet place.\n\n[ Exits: north ]"
    assert "You see:" not in empty_text

    populated = SimpleNamespace(
        title="Busy Room",
        description="A busy place.",
        exits=[{"direction": "east"}],
        players=[{"name": "Alice"}],
        npcs=[{"name": "Shopkeeper", "description": "Runs the shop."}],
        mobs=[{"name": "Rat", "description": "A rat scurries."}],
        objects=[{"name": "Old Gate", "description": "old gate...", "room_description": "Old Gate - old gate..."}],
    )
    text = html_to_plain_text(render_room(populated, {}))
    assert text.count("Busy Room") == 1
    assert text.count("A busy place.") == 1
    assert "You see:\nAlice\nShopkeeper\nRat\nOld Gate\n\n[ Exits: east ]" in text
    assert text.index("Alice") < text.index("Shopkeeper") < text.index("Rat") < text.index("Old Gate")
    assert "old gate" not in text
    assert 'role="content"' in render_room(populated, {})
    assert 'role="exit"' in render_room(populated, {})


def test_object_renderer_owns_object_descriptions() -> None:
    text = html_to_plain_text(render_object({"name": "Old Gate", "description": "An old gate blocks the road."}))
    assert text == "Old Gate\n\nAn old gate blocks the road."


def _entered_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    runtime.select_world("shattered_realms")
    created = runtime.create_character({"name": "Phaseg", "race_id": "human", "class_id": "mage"})
    cid = created["character"]["character_id"]
    entered = runtime.enter_world(cid)
    return runtime, cid, entered


def test_login_look_and_movement_use_canonical_room_renderer(tmp_path: Path, monkeypatch) -> None:
    runtime, _cid, entered = _entered_runtime(tmp_path, monkeypatch)
    login_text = runtime._plain_text(entered["view"]["html"])
    assert login_text.count("Guildhall Crossing Square") == 1
    assert login_text.endswith("[ Exits: north west east in ]")

    look = runtime.mud_input({"text": "look", "command_echo": False})
    assert look["command_result_text"] == ""
    assert look["room_output_text"].count("Guildhall Crossing Square") == 1
    assert "Fountain -" not in look["room_output_text"]

    moved = runtime.mud_input({"text": "north", "command_echo": False})
    assert moved["command_result_text"].startswith("You travel north.")
    assert moved["command_result_text"].count("Old Gate Road") == 0
    assert moved["room_output_text"].count("Old Gate Road") == 1
    assert moved["output_text"].startswith("You travel north.\nOld Gate Road")
    assert "\n\n" in moved["output_text"]


def test_target_look_uses_command_document_without_room_append(tmp_path: Path, monkeypatch) -> None:
    runtime, _cid, _entered = _entered_runtime(tmp_path, monkeypatch)
    runtime.mud_input({"text": "west", "command_echo": False})
    target = runtime.mud_input({"text": "look borik", "command_echo": False})
    assert "Training Master Borik" in target["command_result_text"]
    assert "broad-shouldered veteran" in target["command_result_text"]
    assert "Training Yard" not in target["command_result_text"]
    assert "[ Exits:" not in target["command_result_text"]
    assert target["room_output_text"] == ""
    assert "Training Yard" not in target["output_text"]


def test_room_renderer_roles_do_not_bleed_from_exits_to_contents() -> None:
    room = SimpleNamespace(
        title="Training Yard",
        description="The packed earth repeats Training Yard safely.",
        exits=[{"direction": "north"}, {"direction": "east"}],
        players=[],
        npcs=[{"entity_type": "npc", "name": "Training Master Borik", "room_description": "Training Master Borik watches the yard with his arms folded."}],
        mobs=[],
        objects=[{"entity_type": "object", "name": "Old Gate Shard", "room_description": "An old gate shard rests near the edge of the yard."}],
    )
    html = render_room(room, {})
    assert html.count('role="room_name"') == 1
    assert html.count('role="room_description"') == 1
    assert 'role="contents_heading">You see:</span><br><span role="content">Training Master Borik watches' in html
    assert '<span role="exit">[ Exits: north east ]</span>' in html
    assert html.count('<span') == html.count('</span>')
