"""Piper backend (package piper-tts).

The backend makes the ONNX Runtime session itself, because PiperVoice.load()
gives no control of the thread count. M0 measured 4 intra-op threads as the
fastest configuration on 4 physical cores.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterator

import numpy as np
import onnxruntime as ort
from piper import PiperVoice
from piper.config import PiperConfig
from piper.phonemize_espeak import EspeakPhonemizer
# piper-tts uses this lock for its espeak-ng calls. espeak-ng has one global state,
# so English calls take the same lock. Private name: piper-tts is pinned to 1.8.0.
from piper.voice import _ESPEAK_PHONEMIZER_LOCK

from local_tts.backends.phonemes import fix_dz as _fix_dz, lengthen_trz, phonemize_mixed, to_polish_phonemes

_english_espeak: EspeakPhonemizer | None = None


def _english_phonemes(text: str) -> list[list[str]]:
    """English text (an <en> span) to phonemes that the Polish voices know."""
    global _english_espeak
    with _ESPEAK_PHONEMIZER_LOCK:
        if _english_espeak is None:
            _english_espeak = EspeakPhonemizer()
        sentences = _english_espeak.phonemize("en-us", text)
    return [list(to_polish_phonemes("".join(s))) for s in sentences]


class _InterruptibleSession:
    """ONNX Runtime session that interrupt() can stop during run().

    PiperVoice calls session.run() without RunOptions. This wrapper gives each
    run its own RunOptions, so that terminate stops only the current run.
    M4 spike: terminate stops a 571 ms run in median 2 ms, maximum 87 ms.
    """

    def __init__(self, session: ort.InferenceSession) -> None:
        self._session = session
        self._lock = threading.Lock()
        self._run_options: ort.RunOptions | None = None

    def run(self, output_names, input_feed, run_options=None):
        options = ort.RunOptions()
        with self._lock:
            self._run_options = options
        try:
            return self._session.run(output_names, input_feed, options)
        finally:
            with self._lock:
                self._run_options = None

    def interrupt(self) -> None:
        with self._lock:
            if self._run_options is not None:
                self._run_options.terminate = True

    def __getattr__(self, name):
        return getattr(self._session, name)


class PiperBackend:
    def __init__(self, model_path: Path, threads: int = 4, fix_trz: bool = True, fix_dz: bool = True) -> None:
        config_path = model_path.with_name(model_path.name + ".json")
        if not model_path.exists() or not config_path.exists():
            raise FileNotFoundError(f"Piper model or config not found: {model_path}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self._session = _InterruptibleSession(
            ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        )
        self._voice = PiperVoice(
            config=PiperConfig.from_dict(json.loads(config_path.read_text(encoding="utf-8"))),
            session=self._session,
        )
        self.sample_rate = self._voice.config.sample_rate
        # "pl" or "en", from the espeak-ng voice of the model ("pl", "en-us", "en-gb-x-rp").
        self.language = self._voice.config.espeak_voice.split("-")[0]
        if self.language == "pl":
            # PiperVoice.synthesize() calls self.phonemize(). Wrap it for this voice only;
            # the audio processing after phonemization stays the same.
            espeak_polish = self._voice.phonemize
            corrections = [c for c, on in ((lengthen_trz, fix_trz), (_fix_dz, fix_dz)) if on]

            def polish(text: str) -> list[list[str]]:
                phonemes = espeak_polish(text)
                for correction in corrections:
                    phonemes = correction(text, phonemes)
                return phonemes

            self._voice.phonemize = lambda text: phonemize_mixed(text, polish, _english_phonemes)

    def phonemize(self, text: str) -> list[list[str]]:
        """The phonemes that synthesize() uses for the text, grouped by sentence."""
        return self._voice.phonemize(text)

    def synthesize(self, text: str) -> Iterator[np.ndarray]:
        for chunk in self._voice.synthesize(text):
            yield chunk.audio_int16_array

    def interrupt(self) -> None:
        self._session.interrupt()

    def warm_up(self) -> None:
        """Run one short synthesis, so that the first request is not slower than the next ones."""
        for _ in self.synthesize("Test."):
            pass
