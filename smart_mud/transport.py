"""Shared transport abstractions for Smart MUD clients.

Transports own connection details only. MudRuntime remains the only authority for
command execution and game state mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import re
import uuid
from typing import Any, Protocol


class OutputFormat(StrEnum):
    WEB_HTML = "web_html"
    ANSI_TEXT = "ansi_text"
    PLAIN_TEXT = "plain_text"


@dataclass
class TransportSession:
    session_id: str
    transport_type: str
    remote_address: str
    account_id: str | None = None
    character_id: str | None = None
    world_id: str | None = None
    connected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authenticated: bool = False
    state: str = "connected"
    capabilities: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, transport_type: str, remote_address: str = "", **kwargs: Any) -> "TransportSession":
        return cls(session_id=str(uuid.uuid4()), transport_type=transport_type, remote_address=remote_address, **kwargs)

    def touch(self) -> None:
        self.last_activity_at = datetime.now(timezone.utc).isoformat()


@dataclass
class TransportMessage:
    session: TransportSession
    text: str
    raw: bytes | None = None


@dataclass
class TransportResponse:
    session: TransportSession
    output: str
    output_format: OutputFormat
    prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TransportAdapter(Protocol):
    transport_type: str
    output_format: OutputFormat

    def create_session(self, remote_address: str = "", **kwargs: Any) -> TransportSession: ...
    def handle_message(self, message: TransportMessage) -> TransportResponse: ...


_ROLE_TO_ANSI = {
    "room_name": "\033[1;33m", "area_name": "\033[36m", "room_description": "\033[37m",
    "exit": "\033[32m", "system": "\033[32m", "error": "\033[31m", "warning": "\033[33m",
    "prompt_hp": "\033[31m", "prompt_mana": "\033[34m", "score_label": "\033[36m", "command_echo": "\033[90m",
}
_RESET = "\033[0m"
_SPAN_RE = re.compile(r'<span\s+role="([^"]+)">(.*?)</span>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def html_to_plain_text(value: str) -> str:
    import html
    text = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    return html.unescape(text)


def html_to_ansi_text(value: str) -> str:
    import html
    def repl(match: re.Match[str]) -> str:
        role, body = match.group(1), html.unescape(_TAG_RE.sub("", match.group(2)))
        return f"{_ROLE_TO_ANSI.get(role, '')}{body}{_RESET if role in _ROLE_TO_ANSI else ''}"
    value = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.IGNORECASE)
    return _SPAN_RE.sub(repl, value)


class RuntimeTransportAdapter:
    """Base adapter that routes line input through MudRuntime.handle_input."""
    transport_type = "base"
    output_format = OutputFormat.PLAIN_TEXT

    def __init__(self, mud_runtime: Any) -> None:
        self.mud_runtime = mud_runtime
        self.event_bus = getattr(mud_runtime, "event_bus", None)
        self.sessions: dict[str, TransportSession] = {}

    def create_session(self, remote_address: str = "", **kwargs: Any) -> TransportSession:
        session = TransportSession.create(self.transport_type, remote_address, capabilities={"output_format": self.output_format.value}, **kwargs)
        self.sessions[session.session_id] = session
        if self.event_bus:
            self.event_bus.publish("session_created", {"session_id": session.session_id, "transport_type": session.transport_type, "output_format": self.output_format.value, "character_id": session.character_id or "", "world_id": session.world_id or ""}, source_system="transport", session_id=session.session_id, transport_type=session.transport_type, character_id=session.character_id or "", world_id=session.world_id or "")
        return session

    def handle_message(self, message: TransportMessage) -> TransportResponse:
        message.session.touch()
        if self.event_bus:
            self.event_bus.publish("transport_message_received", {"session_id": message.session.session_id, "transport_type": message.session.transport_type, "output_format": self.output_format.value, "character_id": message.session.character_id or "", "world_id": message.session.world_id or "", "command": message.text}, source_system="transport", session_id=message.session.session_id, transport_type=message.session.transport_type, character_id=message.session.character_id or "", world_id=message.session.world_id or "", command=message.text)
        if not message.session.character_id:
            raise ValueError("Transport session has no character_id; authentication/character selection is required.")
        result = self.mud_runtime.handle_input(message.session.character_id, message.text)
        response = self.render_runtime_result(message.session, result, command=message.text)
        if self.event_bus:
            self.event_bus.publish("transport_response_sent", {"session_id": message.session.session_id, "transport_type": message.session.transport_type, "output_format": response.output_format.value, "character_id": message.session.character_id or "", "world_id": message.session.world_id or "", "command": message.text}, source_system="transport", session_id=message.session.session_id, transport_type=message.session.transport_type, character_id=message.session.character_id or "", world_id=message.session.world_id or "", command=message.text)
        return response

    def render_runtime_result(self, session: TransportSession, result: dict[str, Any], command: str = "") -> TransportResponse:
        view = result.get("view") or {}
        output = str(result.get("output") or view.get("text") or "")
        prompt = str(view.get("prompt") or ">")
        return TransportResponse(session=session, output=output, output_format=self.output_format, prompt=prompt, metadata={"used_mud_runtime": True})


class WebTransportAdapter(RuntimeTransportAdapter):
    transport_type = "web"
    output_format = OutputFormat.WEB_HTML

    def render_runtime_result(self, session: TransportSession, result: dict[str, Any], command: str = "") -> TransportResponse:
        from engine.mud_displays import semantic_html
        view = result.get("view") or {}
        narrative = str(result.get("semantic_output") or result.get("output") or "")
        room_html = str(view.get("html") or "")
        if narrative and room_html:
            output = f'{semantic_html(narrative)}\n{room_html}'
        else:
            output = room_html or (semantic_html(narrative) if narrative else "")
        return TransportResponse(session=session, output=output, output_format=self.output_format, prompt=str(view.get("prompt") or ">"), metadata={"result": result, "used_mud_runtime": True})


class TelnetTransportAdapter(RuntimeTransportAdapter):
    transport_type = "telnet"
    output_format = OutputFormat.ANSI_TEXT

    def render_runtime_result(self, session: TransportSession, result: dict[str, Any], command: str = "") -> TransportResponse:
        view = result.get("view") or {}
        rendered = str(result.get("output") or "")
        if not rendered and view.get("html"):
            rendered = html_to_ansi_text(str(view.get("html") or ""))
        prompt = html_to_ansi_text(str(view.get("prompt") or ">"))
        return TransportResponse(session=session, output=rendered, output_format=self.output_format, prompt=prompt, metadata={"result": result, "used_mud_runtime": True})
