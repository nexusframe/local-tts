"""Audio output interface."""

from __future__ import annotations

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
