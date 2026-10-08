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
class Cancel:
    pass


@dataclass(frozen=True)
class Status:
    pass


Request = Speak | Cancel | Status


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
    if cmd != "speak":
        raise ProtocolError(f"unknown cmd: {cmd!r}")

    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ProtocolError("speak needs a non-empty string 'text'")
    voice = _optional(message, "voice", str)
    request_id = _optional(message, "id", str)
    interrupt = message.get("interrupt", False)
    if not isinstance(interrupt, bool):
        raise ProtocolError("'interrupt' must be true or false")
    return Speak(text=text, voice=voice, interrupt=interrupt, id=request_id)


def _optional(message: dict, key: str, kind: type) -> object:
    value = message.get(key)
    if value is not None and not isinstance(value, kind):
        raise ProtocolError(f"'{key}' must be a {kind.__name__}")
    return value


def encode_event(event: str, **fields: object) -> bytes:
    return (json.dumps({"event": event, **fields}, ensure_ascii=False) + "\n").encode("utf-8")
