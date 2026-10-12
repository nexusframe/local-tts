"""Audio output interface."""

from __future__ import annotations

import array
import fcntl
import subprocess
import termios
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

    def queued_seconds(self) -> float:
        """Seconds of written audio that the listener did not hear yet. Can be called from any thread."""
        ...


class PwCatPlayer:
    """Plays audio through PipeWire with one `pw-cat` process for each utterance.

    drain() closes stdin and waits: pw-cat stops only after it played all audio.
    stop() kills the process, so the sound stops at once.

    write() returns when the audio is in the pipe to pw-cat. The pipe holds about
    1.3 s of 22050 Hz audio (measured 2026-10-12), so queued_seconds() reads the
    bytes in the pipe and adds the latency of pw-cat.
    """

    def __init__(self, latency: str = "50ms") -> None:
        self._latency = latency
        self._latency_seconds = float(latency.removesuffix("ms")) / 1000 if latency.endswith("ms") else 0.0
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

    def queued_seconds(self) -> float:
        with self._lock:
            proc, rate = self._proc, self._rate
        if proc is None or rate is None:
            return 0.0
        pipe_bytes = array.array("i", [0])
        try:
            fcntl.ioctl(proc.stdin.fileno(), termios.FIONREAD, pipe_bytes)
        except (OSError, ValueError):
            return 0.0  # stop() or drain() closed the pipe.
        return pipe_bytes[0] / 2 / rate + self._latency_seconds

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
