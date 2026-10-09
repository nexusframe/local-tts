"""Interface of a TTS backend. The daemon keeps one loaded backend for each voice."""

from __future__ import annotations

from typing import Iterator, Protocol

import numpy as np


class Backend(Protocol):
    sample_rate: int

    def synthesize(self, text: str) -> Iterator[np.ndarray]:
        """Yield mono int16 PCM chunks for one sentence.

        The engine checks for cancel between chunks. A backend that streams
        inside a sentence gives a shorter cancel latency.
        """
        ...

    def interrupt(self) -> None:
        """Stop the current synthesize() call. Called from another thread.

        The stopped call can raise. A call that starts after interrupt() runs normally.
        """
        ...
