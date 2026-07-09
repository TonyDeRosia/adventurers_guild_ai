from __future__ import annotations

import re
from pathlib import Path

from app.web import WebRuntime
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _entered_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    runtime.select_world("shattered_realms")
    created = runtime.create_character({"name": "Jeromaru", "race_id": "human", "class_id": "mage"})
    character_id = created["character"]["character_id"]
    runtime.enter_world(character_id)
    return runtime, character_id


def test_classic_room_layout_and_hidden_ids(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    text = runtime.mud_input({"text": "look", "command_echo": False})["room_output_text"]
    lines = text.splitlines()

    assert lines[0] == "Guildhall Crossing Square"
    assert lines[1] == ""
    assert text.count("Guildhall Crossing Square") == 1
    assert "guildhall_crossing" not in text
    assert "starter_square" not in text
    assert lines[2].startswith("Is a playable MUD room")
    assert lines[-1] == "[ Exits: north east west in ]"
    assert text.index("Fountain") < text.index("[ Exits:")


def test_movement_look_and_command_output_are_separated(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    moved = runtime.mud_input({"text": "north"})
    assert moved["command_result_text"] == "You head north."
    assert moved["output_text"].splitlines()[0] == "> north"
    assert moved["output_text"].splitlines()[1] == "You head north."
    assert moved["output_text"].splitlines()[2] == "Old Gate Road"
    assert moved["room_output_text"].count("Old Gate Road") == 1

    looked = runtime.mud_input({"text": "look"})
    assert looked["command_result_text"] == ""
    assert looked["room_output_text"].count("Old Gate Road") == 1


def test_score_equipment_inventory_semantics_and_newlines(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    score = runtime.mud_input({"text": "score"})
    assert score["output_text"].startswith("> score\nName: Jeromaru\nLevel: 1")
    assert 'role="score_label"' in score["command_result_html"]

    eq = runtime.mud_input({"text": "equipment"})
    assert eq["output_text"].startswith("> equipment\n")
    assert "Equipment:\n" in eq["output_text"]
    assert 'role="equipment_slot"' in eq["command_result_html"]

    inv = runtime.mud_input({"text": "inventory"})
    assert inv["output_text"].startswith("> inventory\n")
    assert "You are carrying:\n" in inv["output_text"] or "You are not carrying anything." in inv["output_text"]
    assert re.search(r'role="(?:item_common|system)"', inv["command_result_html"])


def test_web_and_telnet_preserve_logical_line_breaks_and_prompt_is_separate(tmp_path: Path, monkeypatch) -> None:
    runtime, character_id = _entered_runtime(tmp_path, monkeypatch)
    web = WebTransportAdapter(runtime.mud_runtime)
    web_session = web.create_session("web")
    web_session.character_id = character_id
    web_response = web.handle_message(TransportMessage(web_session, "look"))
    assert '<span role="prompt"' not in web_response.output
    assert '<span role="prompt"' in web_response.prompt
    assert "\n\n" in web_response.output

    telnet = TelnetTransportAdapter(runtime.mud_runtime)
    telnet_session = telnet.create_session("telnet")
    telnet_session.character_id = character_id
    telnet_response = telnet.handle_message(TransportMessage(telnet_session, "look"))
    assert "<span" not in telnet_response.output
    assert "Guildhall Crossing Square" in telnet_response.output
    assert "\n\n" in telnet_response.output


def test_pinned_prompt_frontend_remains_separate_from_room_output() -> None:
    app_js = (Path.cwd() / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "function renderPrompt" in app_js
    assert "mudPlayerPrompt.innerHTML" in app_js
    assert "dialogueFeed.innerHTML=normalizeMudHtml" in app_js
    css = (Path.cwd() / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    assert "#mud-player-prompt" in css
    assert "white-space: pre-wrap" in css
