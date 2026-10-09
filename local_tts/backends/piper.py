"""Piper backend (package piper-tts).

The backend makes the ONNX Runtime session itself, because PiperVoice.load()
gives no control of the thread count. M0 measured 4 intra-op threads as the
fastest configuration on 4 physical cores.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import numpy as np
import onnxruntime as ort
from piper import PiperVoice
from piper.config import PiperConfig

from local_tts.backends.phonemes import lengthen_trz


class PiperBackend:
    def __init__(self, model_path: Path, threads: int = 4, fix_trz: bool = True) -> None:
        config_path = model_path.with_name(model_path.name + ".json")
        if not model_path.exists() or not config_path.exists():
            raise FileNotFoundError(f"Piper model or config not found: {model_path}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self._voice = PiperVoice(
            config=PiperConfig.from_dict(json.loads(config_path.read_text(encoding="utf-8"))),
            session=ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]),
        )
        self.sample_rate = self._voice.config.sample_rate
        if fix_trz:
            # PiperVoice.synthesize() calls self.phonemize(). Wrap it for this voice only;
            # the audio processing after phonemization stays the same.
            original = self._voice.phonemize
            self._voice.phonemize = lambda text: lengthen_trz(text, original(text))

    def synthesize(self, text: str) -> Iterator[np.ndarray]:
        for chunk in self._voice.synthesize(text):
            yield chunk.audio_int16_array

    def warm_up(self) -> None:
        """Run one short synthesis, so that the first request is not slower than the next ones."""
        for _ in self.synthesize("Test."):
            pass
