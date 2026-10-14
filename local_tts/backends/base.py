"""Interface of a TTS backend. The daemon keeps one loaded backend for each voice."""

from __future__ import annotations

from typing import Iterator, Protocol

import numpy as np


class Backend(Protocol):
    sample_rate: int
    language: str  # "pl" or "en": the engine selects the normalizer for it

    def synthesize(self, text: str, word_ends: list[float] | None = None, speed: float = 1.0) -> Iterator[np.ndarray]:
        """Yield mono int16 PCM chunks for one sentence.

        speed: multiplier of the speech rate of the voice. A smaller value gives slower speech.

        The engine checks for cancel between chunks. A backend that streams
        inside a sentence gives a shorter cancel latency.

        With a word_ends list: add the end time of each word of the text (words
        split at whitespace), in seconds from the start of the audio of this
        call. The times are in the list when the last chunk comes, so the engine
        knows them before it plays that chunk. A backend without word times adds nothing.
        """
        ...

    def interrupt(self) -> None:
        """Stop the current synthesize() call. Called from another thread.

        The stopped call can raise. A call that starts after interrupt() runs normally.
        """
        ...
