from __future__ import annotations

from pathlib import Path

from app.web import WebRuntime
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _entered_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    runtime.select_world("shattered_realms")
    created = runtime.create_character({"name": "Kraevok", "race_id": "human", "class_id": "mage"})
    character_id = created["character"]["character_id"]
    runtime.enter_world(character_id)
    return runtime, character_id


def test_room_score_equipment_inventory_prompt_use_semantic_roles(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    view = runtime.play_view()
    assert 'role="room_name"' in view["output_html"]
    assert 'role="room_description"' in view["output_html"]
    assert 'role="exit"' in view["output_html"]
    assert 'role="player"' in view["prompt_html"]
    assert 'role="hp"' in view["prompt_html"]
    assert 'role="mp"' in view["prompt_html"]

    score = runtime.mud_input({"text": "score"})
    assert 'role="score_label"' in score["command_result_html"]
    assert 'role="score_value"' in score["command_result_html"]
    assert 'role="gold"' in score["command_result_html"]

    eq = runtime.mud_input({"text": "equipment"})
    assert 'role="equipment_slot"' in eq["command_result_html"]
    assert 'role="system"' in eq["command_result_html"]

    inv = runtime.mud_input({"text": "inventory"})
    assert 'role="system"' in inv["command_result_html"]


def test_web_html_is_semantic_and_telnet_has_no_html(tmp_path: Path, monkeypatch) -> None:
    runtime, character_id = _entered_runtime(tmp_path, monkeypatch)
    web = WebTransportAdapter(runtime.mud_runtime)
    telnet = TelnetTransportAdapter(runtime.mud_runtime)
    web_session = web.create_session("web"); web_session.character_id = character_id
    telnet_session = telnet.create_session("telnet"); telnet_session.character_id = character_id

    web_response = web.handle_message(TransportMessage(web_session, "score"))
    assert 'role="room_name"' in web_response.output
    assert '<span' in web_response.prompt

    telnet_response = telnet.handle_message(TransportMessage(telnet_session, "score"))
    assert "<span" not in telnet_response.output
    assert "<span" not in telnet_response.prompt


def test_settings_and_css_include_expected_semantic_roles(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    colors = runtime.get_global_settings()["mud_colors"]
    for role in ["room_name", "room_description", "exit", "object", "command_echo", "score_label", "score_value", "equipment_slot", "equipment_item", "gold", "hp", "mp", "stamina", "prompt", "input"]:
        assert role in colors
    css = (Path.cwd() / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    assert "--mud-room-name-color" in css
    assert "--mud-command-echo-color" in css
    assert "--mud-hp-color" in css
