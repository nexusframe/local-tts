"""Unix socket server. JSON lines in both directions (see protocol.py).

Replies to a request go to the client that sent it. Engine events
(started, done, cancelled, error) go to all connected clients.

A stream (begin, append, end) belongs to the client that opened it. When
that client disconnects before end, the stream is cancelled.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from pathlib import Path

from local_tts.engine import Engine
from local_tts.protocol import Append, Begin, Cancel, End, Flush, ProtocolError, Speak, Status, encode_event, parse_request

log = logging.getLogger(__name__)


# EX_CONFIG: the unit file does not start the daemon again after this exit code.
EXIT_ALREADY_RUNNING = 78


def socket_in_use(path: Path) -> bool:
    """True if a process accepts connections on the socket file. A file without a listener is free."""
    if not path.exists():
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        try:
            probe.connect(str(path))
        except OSError:
            return False
    return True


def exit_if_running(path: Path) -> None:
    if socket_in_use(path):
        log.error("daemon already running on %s; stop it first (systemctl --user stop local-tts)", path)
        raise SystemExit(EXIT_ALREADY_RUNNING)


def sd_notify(message: str) -> None:
    """Send a state to systemd (Type=notify). Without $NOTIFY_SOCKET, do nothing."""
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):  # Abstract socket namespace.
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify:
            notify.sendto(message.encode(), address)
    except OSError as exc:
        log.warning("cannot notify systemd: %s", exc)


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
        # Streams that this client opened and did not end.
        streams: set[str] = set()
        try:
            while line := await reader.readline():
                reply = self._reply(line, streams)
                if reply is not None:
                    writer.write(reply)
                    await writer.drain()
        except (ConnectionError, asyncio.LimitOverrunError, ValueError) as exc:
            log.warning("client error: %s", exc)
        finally:
            for stream_id in streams:
                self.engine.abort(stream_id)
            self._clients.discard(writer)
            writer.close()

    def _reply(self, line: bytes, streams: set[str]) -> bytes | None:
        """Return the reply line. Append has no reply, because it comes for each LLM token. Flush has none, as append."""
        try:
            request = parse_request(line)
        except ProtocolError as exc:
            return encode_event("error", message=str(exc))
        try:
            if isinstance(request, Speak):
                return encode_event("accepted", id=self.engine.speak(request))
            if isinstance(request, Begin):
                stream_id = self.engine.begin(request)
                streams.add(stream_id)
                return encode_event("accepted", id=stream_id)
            if isinstance(request, Append):
                self.engine.append(request.id, request.text)
                return None
            if isinstance(request, Flush):
                self.engine.flush(request.id)
                return None
            if isinstance(request, End):
                self.engine.end(request.id)
                streams.discard(request.id)
                return encode_event("ack", cmd="end", id=request.id)
        except ValueError as exc:
            return encode_event("error", id=getattr(request, "id", None), message=str(exc))
        if isinstance(request, Cancel):
            self.engine.cancel()
            return encode_event("ack", cmd="cancel")
        assert isinstance(request, Status)
        return encode_event("status", **self.engine.status())

    async def serve_forever(self) -> None:
        self._loop = asyncio.get_running_loop()
        # SIGTERM comes from kill and systemd. SIGINT also when the shell started the
        # daemon with "&", because the handler replaces the ignored setting.
        # Before the socket exists: clients take the socket as the sign that the daemon is ready.
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._loop.add_signal_handler(sig, self._stop, stop, sig)
        exit_if_running(self._socket_path)
        if self._socket_path.exists():
            self._socket_path.unlink()
        server = await asyncio.start_unix_server(self._handle, path=str(self._socket_path), limit=1 << 20)
        os.chmod(self._socket_path, 0o600)
        log.info("listening on %s", self._socket_path)
        self.engine.start()
        sd_notify("READY=1")
        try:
            async with server:
                await stop.wait()
        finally:
            for sig in (signal.SIGTERM, signal.SIGINT):
                self._loop.remove_signal_handler(sig)
            self.engine.close()
            self._socket_path.unlink(missing_ok=True)
            log.info("stopped")

    @staticmethod
    def _stop(stop: asyncio.Event, sig: signal.Signals) -> None:
        log.info("stopping on %s", sig.name)
        sd_notify("STOPPING=1")
        stop.set()
