"""Audio output interface."""

from __future__ import annotations

import subprocess
import threading
from typing import Protocol

import numpy as np


class Player(Protocol):
    def write(self, pcm: np.ndarray, sample_rate: int) -> None:
        """Queue mono int16 PCM for playback. Can block while the output buffer is full."""
        ...

    def drain(self) -> None:
        """Block until all written audio was played."""
        ...

    def stop(self) -> None:
        """Discard all queued audio now. Can be called from any thread. Unblocks write() and drain()."""
        ...


class PwCatPlayer:
    """Plays audio through PipeWire with one `pw-cat` process for each utterance.

    drain() closes stdin and waits: pw-cat stops only after it played all audio.
    stop() kills the process, so the sound stops at once.
    """

    def __init__(self, latency: str = "50ms") -> None:
        self._latency = latency
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._rate: int | None = None
        # All live processes, also a process that drain() waits for.
        self._live: set[subprocess.Popen] = set()

    def write(self, pcm: np.ndarray, sample_rate: int) -> None:
        if self._proc is not None and self._rate != sample_rate:
            self.drain()
        with self._lock:
            proc = self._proc or self._spawn(sample_rate)
        try:
            proc.stdin.write(pcm.astype(np.int16, copy=False).tobytes())
        except (BrokenPipeError, ValueError, OSError):
            pass  # stop() killed the process.

    def drain(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.stdin.close()
        except OSError:
            pass
        proc.wait()
        with self._lock:
            self._live.discard(proc)

    def stop(self) -> None:
        with self._lock:
            self._proc = None
            victims = list(self._live)
            self._live.clear()
        for proc in victims:
            proc.kill()
            proc.wait()

    def _spawn(self, sample_rate: int) -> subprocess.Popen:
        proc = subprocess.Popen(
            [
                "pw-cat", "--playback",
                "--rate", str(sample_rate), "--channels", "1", "--format", "s16",
                "--latency", self._latency, "--media-role", "Communication", "-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._proc = proc
        self._rate = sample_rate
        self._live.add(proc)
        return proc
