"""Fakes for the two system boundaries of the engine: the TTS model and the sound card."""

from __future__ import annotations

import threading
import time

import numpy as np


class FakeBackend:
    """Gives one chunk per sentence. The chunk holds the sentence, so tests can see what was played."""

    sample_rate = 22050

    def __init__(self, name: str = "fake", fail_on: str | None = None, language: str = "pl") -> None:
        self.name = name
        self.fail_on = fail_on
        self.language = language
        self.calls: list[str] = []

    def interrupt(self) -> None:
        pass

    def synthesize(self, text: str):
        self.calls.append(text)
        if self.fail_on is not None and self.fail_on in text:
            raise RuntimeError(f"cannot synthesize {text!r}")
        yield FakeChunk(self.name, text)


class SlowBackend(FakeBackend):
    """Like a long sentence in Piper: synthesize() blocks until interrupt(), then raises."""

    def __init__(self, name: str = "fake", slow_on: str = "Długie") -> None:
        super().__init__(name)
        self.slow_on = slow_on
        self.interrupts = 0
        self._interrupted = threading.Event()

    def synthesize(self, text: str):
        if self.slow_on in text:
            self.calls.append(text)
            if not self._interrupted.wait(timeout=5.0):
                raise AssertionError("synthesis was not interrupted")
            self._interrupted.clear()
            raise RuntimeError("Exiting due to terminate flag")
        yield from super().synthesize(text)

    def interrupt(self) -> None:
        self.interrupts += 1
        self._interrupted.set()


class FakeChunk(np.ndarray):
    def __new__(cls, voice: str, text: str):
        chunk = np.zeros(10, dtype=np.int16).view(cls)
        chunk.label = f"{voice}:{text}"
        return chunk

    def __array_finalize__(self, obj):
        self.label = getattr(obj, "label", None)


class FakePlayer:
    """Records played chunks. When `blocking` is set, write() waits until release() or stop()."""

    def __init__(self, blocking: bool = False) -> None:
        self.played: list[str] = []
        self.stops = 0
        self._open = threading.Event()
        if not blocking:
            self._open.set()
        self._lock = threading.Lock()

    def write(self, pcm, sample_rate: int) -> None:
        stops_before = self.stops
        self._open.wait()
        with self._lock:
            if self.stops == stops_before:
                self.played.append(pcm.label)

    def drain(self) -> None:
        self._open.wait()

    def stop(self) -> None:
        self.stops += 1
        self._open.set()

    def release(self) -> None:
        self._open.set()


class EventLog:
    """Collects engine events and lets a test wait for one."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self._cond = threading.Condition()

    def __call__(self, event: str, **fields) -> None:
        with self._cond:
            self.events.append({"event": event, **fields})
            self._cond.notify_all()

    def wait_for(self, event: str, timeout: float = 2.0, **fields) -> dict:
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                for item in self.events:
                    if item["event"] == event and all(item.get(k) == v for k, v in fields.items()):
                        return item
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(f"no {event} {fields} in {self.events}")
                self._cond.wait(remaining)

    def names(self, **fields) -> list[str]:
        with self._cond:
            return [e["event"] for e in self.events if all(e.get(k) == v for k, v in fields.items())]
