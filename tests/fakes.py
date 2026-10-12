"""Fakes for the two system boundaries of the engine: the TTS model and the sound card."""

from __future__ import annotations

import threading
import time

import numpy as np


class FakeBackend:
    """Gives one chunk per sentence. The chunk holds the sentence, so tests can see what was played.

    The chunk has 10 samples, or chunk_seconds of audio. With word_times, the
    words of the sentence have equal durations.
    """

    sample_rate = 22050

    def __init__(
        self,
        name: str = "fake",
        fail_on: str | None = None,
        language: str = "pl",
        chunk_seconds: float | None = None,
        word_times: bool = True,
    ) -> None:
        self.name = name
        self.fail_on = fail_on
        self.language = language
        self.samples = 10 if chunk_seconds is None else round(chunk_seconds * self.sample_rate)
        self.word_times = word_times
        self.calls: list[str] = []

    def interrupt(self) -> None:
        pass

    def synthesize(self, text: str, word_ends: list[float] | None = None):
        self.calls.append(text)
        if self.fail_on is not None and self.fail_on in text:
            raise RuntimeError(f"cannot synthesize {text!r}")
        if word_ends is not None and self.word_times:
            words = len(text.split())
            word_ends.extend((i + 1) / words * self.samples / self.sample_rate for i in range(words))
        yield FakeChunk(self.name, text, self.samples)


class SlowBackend(FakeBackend):
    """Like a long sentence in Piper: synthesize() blocks until interrupt(), then raises."""

    def __init__(self, name: str = "fake", slow_on: str = "Długie") -> None:
        super().__init__(name)
        self.slow_on = slow_on
        self.interrupts = 0
        self._interrupted = threading.Event()

    def synthesize(self, text: str, word_ends: list[float] | None = None):
        if self.slow_on in text:
            self.calls.append(text)
            if not self._interrupted.wait(timeout=5.0):
                raise AssertionError("synthesis was not interrupted")
            self._interrupted.clear()
            raise RuntimeError("Exiting due to terminate flag")
        yield from super().synthesize(text, word_ends)

    def interrupt(self) -> None:
        self.interrupts += 1
        self._interrupted.set()


class FakeChunk(np.ndarray):
    def __new__(cls, voice: str, text: str, samples: int = 10):
        chunk = np.zeros(samples, dtype=np.int16).view(cls)
        chunk.label = f"{voice}:{text}"
        return chunk

    def __array_finalize__(self, obj):
        self.label = getattr(obj, "label", None)


class FakePlayer:
    """Records played chunks. When `blocking` is set, write() waits until release() or stop().

    With `block_on`, only the write of a chunk that contains this text waits;
    with `block_after`, the first block_after writes of that chunk do not wait.
    `queued` is the value of queued_seconds(): audio that was written but not heard.
    """

    def __init__(self, blocking: bool = False, block_on: str | None = None, block_after: int = 0) -> None:
        self.played: list[str] = []
        self.block_after = block_after
        self.stops = 0
        self.queued = 0.0
        self.block_on = block_on
        self.blocked = threading.Event()
        self._open = threading.Event()
        if not blocking:
            self._open.set()
        self._lock = threading.Lock()

    def write(self, pcm, sample_rate: int) -> None:
        stops_before = self.stops
        if self.block_on is not None and self.block_on in pcm.label:
            if self.block_after > 0:
                self.block_after -= 1
            else:
                self._open.clear()
                self.blocked.set()
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

    def queued_seconds(self) -> float:
        return self.queued


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
