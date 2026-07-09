"""Plain TCP telnet-style server foundation for Smart MUD."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from smart_mud.transport import TelnetTransportAdapter, TransportMessage

WELCOME_BANNER = (
    "Welcome to Smart MUD.\r\n"
    "Account system is not implemented yet.\r\n"
    "Enter a temporary character name: "
)


@dataclass
class TelnetServerConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 4000
    max_connections: int = 25


class TelnetServer:
    def __init__(self, mud_runtime: Any, config: TelnetServerConfig, default_world_id: str = "") -> None:
        self.mud_runtime = mud_runtime
        self.config = config
        self.default_world_id = default_world_id
        self.adapter = TelnetTransportAdapter(mud_runtime)
        self._server: asyncio.AbstractServer | None = None
        self._connections: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        if not self.config.enabled:
            return
        self._server = await asyncio.start_server(self._handle_client, self.config.host, self.config.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for writer in list(self._connections):
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
        self._connections.clear()

    async def _write(self, writer: asyncio.StreamWriter, text: str) -> None:
        writer.write(text.encode("utf-8", errors="replace"))
        await writer.drain()

    async def _readline(self, reader: asyncio.StreamReader) -> str:
        data = await reader.readline()
        return data.decode("utf-8", errors="ignore").strip()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if len(self._connections) >= self.config.max_connections:
            await self._write(writer, "Smart MUD is at its telnet connection limit.\r\n")
            writer.close(); await writer.wait_closed(); return
        self._connections.add(writer)
        peer = writer.get_extra_info("peername")
        session = self.adapter.create_session(remote_address=str(peer or "telnet"))
        try:
            await self._write(writer, WELCOME_BANNER)
            name = await self._readline(reader) or "TelnetPlayer"
            world_id = self.default_world_id or (self.mud_runtime.active_world_id or "")
            if not world_id:
                worlds = self.mud_runtime.world_registry.list_worlds()
                world_id = str(worlds[0]["id"]) if worlds else ""
            character = self.mud_runtime.create_character(world_id=world_id, name=name)
            session.character_id = character["character_id"]
            session.world_id = world_id
            entered = self.mud_runtime.enter_world(session.character_id)
            initial = self.adapter.render_runtime_result(session, entered)
            await self._write(writer, "\r\n" + initial.output + "\r\n" + initial.prompt + " ")
            while not reader.at_eof():
                line = await self._readline(reader)
                if line.lower() in {"quit", "exit"}:
                    await self._write(writer, "Goodbye.\r\n")
                    break
                response = self.adapter.handle_message(TransportMessage(session=session, text=line))
                await self._write(writer, response.output + "\r\n" + response.prompt + " ")
        finally:
            self._connections.discard(writer)
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
