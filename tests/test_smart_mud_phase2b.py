from __future__ import annotations

from pathlib import Path

from app.web import WebRuntime, create_web_app
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _entered_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    runtime.select_world("shattered_realms")
    created = runtime.create_character({"name": "Player", "race_id": "human", "class_id": "mage"})
    character_id = created["character"]["character_id"]
    runtime.enter_world(character_id)
    return runtime, character_id


def _text(runtime: WebRuntime, command: str) -> str:
    return runtime.handle_input(command, command_echo=False)["output_text"]


def test_phase2b_core_aliases_and_clean_unknown(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    assert "Guildhall Crossing Square" in _text(runtime, "look")
    assert "Guildhall Crossing Square" in _text(runtime, "l")
    assert "Name: Player" in _text(runtime, "score")
    assert "Name: Player" in _text(runtime, "sc")
    assert "You are not wearing anything." in _text(runtime, "equipment")
    assert "You are not wearing anything." in _text(runtime, "eq")
    assert "You are carrying:" in _text(runtime, "inventory")
    assert "You are carrying:" in _text(runtime, "inv")
    assert "You are carrying:" in _text(runtime, "i")
    assert "Available commands" in _text(runtime, "commands")
    assert "Available commands" in _text(runtime, "cmds")
    assert "Available commands" in _text(runtime, "help")
    assert "Available commands" in _text(runtime, "h")
    assert "You have 0 gold coins." in _text(runtime, "worth")
    assert "You have no active affects." in _text(runtime, "affects")
    assert "You know no skills." in _text(runtime, "skills")
    assert "You know no spells." in _text(runtime, "spells")
    assert "Your abilities:" in _text(runtime, "abilities")
    assert 'You say, "hello."' in _text(runtime, "say hello")
    assert "Player waves" in _text(runtime, "emote waves")
    assert "Players currently online:\nPlayer" in _text(runtime, "who")
    assert "Unknown command. Type HELP or COMMANDS." in _text(runtime, "frobnicate")


def test_phase2b_room_rendering_movement_and_visible_data(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    start = _text(runtime, "look")
    assert "(stub: NPC rendering)" not in start
    assert "[ Exits: north east west in ]" in start
    assert "Old Gate" in start
    assert "old gate for beginner Smart MUD play." not in start
    moved = _text(runtime, "n")
    assert "You head north." in moved
    assert "Old Gate Road" in moved
    returned = _text(runtime, "s")
    assert "Guildhall Crossing Square" in returned
    inside = _text(runtime, "in")
    assert "Guildhall Archway" in inside
    assert "Guild Registrar Maren" in _text(runtime, "n")
    assert "You cannot go that way." in _text(runtime, "u")


def test_phase2b_transport_rendering_and_favicon(tmp_path: Path, monkeypatch) -> None:
    runtime, character_id = _entered_runtime(tmp_path, monkeypatch)
    web = WebTransportAdapter(runtime.mud_runtime)
    telnet = TelnetTransportAdapter(runtime.mud_runtime)
    web_session = web.create_session("web"); web_session.character_id = character_id
    telnet_session = telnet.create_session("telnet"); telnet_session.character_id = character_id
    web_response = web.handle_message(TransportMessage(web_session, "l"))
    telnet_response = telnet.handle_message(TransportMessage(telnet_session, "l"))
    assert '<span role="room_name">Guildhall Crossing Square</span>' in web_response.output
    assert "<span" not in telnet_response.output
    assert "Guildhall Crossing Square" in telnet_response.output
    app = create_web_app(runtime, Path.cwd() / "app" / "static")
    route = next(route for route in app.routes if getattr(route, "path", "") == "/favicon.ico")
    response = route.endpoint()
    assert getattr(response, "status_code", 200) != 404


def test_mud_input_contract_returns_visible_command_output(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    for command, expected in [("eq", "You are not wearing anything."), ("sc", "Name: Player"), ("worth", "You have 0 gold coins."), ("frobnicate", "Unknown command. Type HELP or COMMANDS.")]:
        data = runtime.mud_input({"text": command})
        assert expected in data["output_text"]
        assert expected in data["command_result_text"]
        assert expected in data["command_result_html"]
        assert data["command_echo_html"]
        assert data["prompt_html"]
        assert data["prompt_text"]


def test_mud_input_movement_returns_result_and_new_room_render(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    data = runtime.mud_input({"text": "n"})
    assert "You head north." in data["command_result_text"]
    assert "You head north." in data["command_result_html"]
    assert "Old Gate Road" in data["room_output_text"]
    assert "Old Gate Road" in data["room_output_html"]
    assert "You head north." in data["output_text"]
    assert "Old Gate Road" in data["output_html"]


def test_play_view_initial_load_is_room_only_and_app_js_appends_input() -> None:
    app_js = (Path.cwd() / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "async function refreshPlayView" in app_js
    assert "dialogueFeed.innerHTML=normalizeMudHtml" in app_js
    assert "async function sendInput" in app_js
    assert "appendMudOutput([d.command_echo_html,d.command_result_html,d.room_output_html]" in app_js
    assert "await refreshPlayView(d)" not in app_js
