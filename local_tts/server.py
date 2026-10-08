"""Unix socket server. JSON lines in both directions (see protocol.py).

Replies to a request go to the client that sent it. Engine events
(started, done, cancelled, error) go to all connected clients.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from local_tts.engine import Engine
from local_tts.protocol import Cancel, ProtocolError, Speak, Status, encode_event, parse_request

log = logging.getLogger(__name__)


class Server:
    def __init__(self, engine_factory, socket_path: Path) -> None:
        self._socket_path = socket_path
        self._clients: set[asyncio.StreamWriter] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.engine: Engine = engine_factory(self._on_engine_event)

    def _on_engine_event(self, event: str, **fields: object) -> None:
        """Called from engine threads."""
        log.info("%s %s", event, fields)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._broadcast, encode_event(event, **fields))

    def _broadcast(self, line: bytes) -> None:
        for writer in list(self._clients):
            writer.write(line)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._clients.add(writer)
        try:
            while line := await reader.readline():
                writer.write(self._reply(line))
                await writer.drain()
        except (ConnectionError, asyncio.LimitOverrunError, ValueError) as exc:
            log.warning("client error: %s", exc)
        finally:
            self._clients.discard(writer)
            writer.close()

    def _reply(self, line: bytes) -> bytes:
        try:
            request = parse_request(line)
        except ProtocolError as exc:
            return encode_event("error", message=str(exc))
        if isinstance(request, Speak):
            try:
                return encode_event("accepted", id=self.engine.speak(request))
            except ValueError as exc:
                return encode_event("error", id=request.id, message=str(exc))
        if isinstance(request, Cancel):
            self.engine.cancel()
            return encode_event("ack", cmd="cancel")
        assert isinstance(request, Status)
        return encode_event("status", **self.engine.status())

    async def serve_forever(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._socket_path.exists():
            self._socket_path.unlink()
        server = await asyncio.start_unix_server(self._handle, path=str(self._socket_path), limit=1 << 20)
        os.chmod(self._socket_path, 0o600)
        log.info("listening on %s", self._socket_path)
        self.engine.start()
        try:
            async with server:
                await server.serve_forever()
        finally:
            self.engine.close()
            self._socket_path.unlink(missing_ok=True)
