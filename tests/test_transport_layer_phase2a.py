from __future__ import annotations

import json
from pathlib import Path

from app.runtime_config_mud import MudRuntimeConfigStore
from smart_mud.telnet_server import TelnetServer, TelnetServerConfig, WELCOME_BANNER
from smart_mud.transport import OutputFormat, TelnetTransportAdapter, TransportMessage, TransportSession, WebTransportAdapter


def test_transport_session_creation() -> None:
    session = TransportSession.create("telnet", "127.0.0.1:1234", capabilities={"ansi": True})
    assert session.session_id
    assert session.transport_type == "telnet"
    assert session.remote_address == "127.0.0.1:1234"
    assert session.account_id is None
    assert session.capabilities["ansi"] is True


def test_telnet_config_loads_and_defaults_disabled(tmp_path: Path) -> None:
    store = MudRuntimeConfigStore(tmp_path / "mud_config.json")
    assert store.load().telnet_enabled is False
    (tmp_path / "mud_config.json").write_text(json.dumps({"telnet_enabled": True, "telnet_host": "0.0.0.0", "telnet_port": 4001, "telnet_max_connections": 2}), encoding="utf-8")
    config = store.load()
    assert config.telnet_enabled is True
    assert config.telnet_host == "0.0.0.0"
    assert config.telnet_port == 4001
    assert config.telnet_max_connections == 2


def test_telnet_transport_can_start_disabled_without_runtime_startup() -> None:
    server = TelnetServer(object(), TelnetServerConfig(enabled=False))
    assert server.config.enabled is False
    assert server.config.port == 4000


def test_telnet_welcome_banner_exists() -> None:
    assert "Welcome to Smart MUD." in WELCOME_BANNER
    assert "Account system is not implemented yet." in WELCOME_BANNER
    assert "Enter a temporary character name:" in WELCOME_BANNER


class RuntimeSpy:
    active_world_id = "world"

    def __init__(self) -> None:
        self.calls = []

    def handle_input(self, character_id: str, command: str):
        self.calls.append((character_id, command))
        return {"ok": True, "output": "runtime says ok", "view": {"html": '<span role="room_name">Room</span>', "prompt": '<span role="prompt_marker">&gt;</span>'}}


def test_line_input_routes_to_mud_runtime() -> None:
    runtime = RuntimeSpy()
    adapter = TelnetTransportAdapter(runtime)
    session = adapter.create_session("peer")
    session.character_id = "char1"
    response = adapter.handle_message(TransportMessage(session=session, text="look"))
    assert runtime.calls == [("char1", "look")]
    assert response.metadata["used_mud_runtime"] is True
    assert response.output == "runtime says ok"


def test_web_rendering_and_ansi_rendering_stay_separate() -> None:
    runtime = RuntimeSpy()
    web = WebTransportAdapter(runtime)
    telnet = TelnetTransportAdapter(runtime)
    web_session = web.create_session("web"); web_session.character_id = "char1"
    telnet_session = telnet.create_session("telnet"); telnet_session.character_id = "char1"
    web_response = web.handle_message(TransportMessage(web_session, "look"))
    telnet_response = telnet.handle_message(TransportMessage(telnet_session, "look"))
    assert web_response.output_format == OutputFormat.WEB_HTML
    assert '<span role="room_name">Room</span>' in web_response.output
    assert telnet_response.output_format == OutputFormat.ANSI_TEXT
    assert "<span" not in telnet_response.output


def test_transport_adapter_does_not_bypass_mud_runtime() -> None:
    runtime = RuntimeSpy()
    adapter = WebTransportAdapter(runtime)
    session = adapter.create_session("web")
    session.character_id = "char1"
    adapter.handle_message(TransportMessage(session, "score"))
    assert runtime.calls == [("char1", "score")]



def test_web_mud_input_route_still_works() -> None:
    from app.web import create_web_app

    class RouteRuntime:
        active_world_id = "world"
        active_character_id = "char"
        def shutdown_managed_services(self): return None
        def health(self): return {"status": "ok"}
        def list_worlds(self): return []
        def list_characters(self): return []
        def handle_input(self, command: str, command_echo: bool = True):
            return {"ok": True, "output_text": command, "command_echo": command_echo}

    app = create_web_app(RouteRuntime(), Path("does-not-exist"))
    route = next(route for route in app.routes if getattr(route, "path", "") == "/api/mud/input")
    assert "POST" in route.methods
    assert route.endpoint({"command": "look"})["output_text"] == "look"
