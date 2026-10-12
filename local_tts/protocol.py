"""JSON lines protocol of the daemon socket. One JSON object per line."""

from __future__ import annotations

import json
from dataclasses import dataclass


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Speak:
    text: str
    voice: str | None = None
    interrupt: bool = False
    id: str | None = None


@dataclass(frozen=True)
class Begin:
    """Open a stream: the text comes later in Append requests."""

    voice: str | None = None
    interrupt: bool = False
    id: str | None = None


@dataclass(frozen=True)
class Append:
    """Add text to an open stream. The text can be any part of a word."""

    id: str
    text: str


@dataclass(frozen=True)
class End:
    """Close a stream. The daemon speaks the rest of the text."""

    id: str


@dataclass(frozen=True)
class Flush:
    """Speak the text of an open stream that waits for the end of its sentence. The stream stays open.

    Send it before a pause in the text, for example before an LLM tool call.
    """

    id: str


@dataclass(frozen=True)
class Cancel:
    pass


@dataclass(frozen=True)
class Status:
    pass


Request = Speak | Begin | Append | End | Flush | Cancel | Status


def parse_request(line: str | bytes) -> Request:
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc.msg}") from None
    if not isinstance(message, dict):
        raise ProtocolError("request must be a JSON object")
    cmd = message.get("cmd")
    if cmd == "cancel":
        return Cancel()
    if cmd == "status":
        return Status()
    if cmd == "begin":
        return Begin(**_speak_options(message))
    if cmd == "append":
        text = message.get("text")
        if not isinstance(text, str):
            raise ProtocolError("append needs a string 'text'")
        return Append(id=_stream_id(message), text=text)
    if cmd == "end":
        return End(id=_stream_id(message))
    if cmd == "flush":
        return Flush(id=_stream_id(message))
    if cmd != "speak":
        raise ProtocolError(f"unknown cmd: {cmd!r}")

    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ProtocolError("speak needs a non-empty string 'text'")
    return Speak(text=text, **_speak_options(message))


def _speak_options(message: dict) -> dict:
    interrupt = message.get("interrupt", False)
    if not isinstance(interrupt, bool):
        raise ProtocolError("'interrupt' must be true or false")
    return {
        "voice": _optional(message, "voice", str),
        "interrupt": interrupt,
        "id": _optional(message, "id", str),
    }


def _stream_id(message: dict) -> str:
    stream_id = message.get("id")
    if not isinstance(stream_id, str):
        raise ProtocolError(f"{message['cmd']} needs a string 'id' of an open stream")
    return stream_id


def _optional(message: dict, key: str, kind: type) -> object:
    value = message.get(key)
    if value is not None and not isinstance(value, kind):
        raise ProtocolError(f"'{key}' must be a {kind.__name__}")
    return value


def encode_event(event: str, **fields: object) -> bytes:
    return (json.dumps({"event": event, **fields}, ensure_ascii=False) + "\n").encode("utf-8")
