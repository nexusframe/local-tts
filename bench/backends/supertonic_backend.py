"""Supertonic 3 adapter. It uses helper.py from the archived official repo.

The model is not autoregressive: it makes the audio for one text chunk in one
pass. Two split modes exist:
- native: the helper's own chunk_text() (up to 300 characters per chunk) and
  0.3 s silence between chunks, as in TextToSpeech.__call__.
- sentence: this adapter splits the text at sentence ends. This is NOT a
  feature of Supertonic. It shows what a daemon can get with its own splitter.
"""

from __future__ import annotations

import re
import sys
import threading
from importlib.metadata import version
from typing import Any, Iterator

import numpy as np
import onnxruntime as ort

from common import BENCH_DIR, MODELS_DIR

HELPER_DIR = BENCH_DIR / ".vendor" / "supertonic" / "py"
SEED = 1234
TOTAL_STEP = 8  # default of the official example_onnx.py
SPEED = 1.05  # default of the official example_onnx.py
SILENCE_S = 0.3  # default of TextToSpeech.__call__
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


class SupertonicBackend:
    def __init__(self, model: str, voice: str, threads: int | None, split: str) -> None:
        if not (HELPER_DIR / "helper.py").exists():
            raise FileNotFoundError(f"{HELPER_DIR}/helper.py not found. Run bench/setup.sh")
        sys.path.insert(0, str(HELPER_DIR))
        import helper  # type: ignore[import-not-found]

        self.helper = helper
        model_dir = MODELS_DIR / "supertonic" / model
        onnx_dir = model_dir / "onnx"
        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
            opts.inter_op_num_threads = 1
        sessions = helper.load_onnx_all(str(onnx_dir), opts, ["CPUExecutionProvider"])
        self.tts = helper.TextToSpeech(helper.load_cfgs(str(onnx_dir)), helper.load_text_processor(str(onnx_dir)), *sessions)
        self.style = helper.load_voice_style([str(model_dir / "voice_styles" / f"{voice}.json")])
        np.random.seed(SEED)
        self.model = model
        self.voice = voice
        self.threads = threads
        self.split = split
        self.sample_rate = self.tts.sample_rate

    def _chunks(self, text: str) -> list[str]:
        if self.split == "sentence":
            return [s for s in SENTENCE_END.split(text.strip()) if s]
        return self.helper.chunk_text(text, max_len=300)

    def stream(self, text: str, stop: threading.Event) -> Iterator[np.ndarray]:
        for i, part in enumerate(self._chunks(text)):
            if stop.is_set():
                return
            if i > 0:
                yield np.zeros(int(SILENCE_S * self.sample_rate), dtype=np.float32)
            wav, dur = self.tts._infer([part], ["pl"], self.style, TOTAL_STEP, SPEED)
            yield wav[0, : int(self.sample_rate * float(dur[0]))]

    def info(self) -> dict[str, Any]:
        return {
            "backend": "supertonic",
            "model": self.model,
            "voice": self.voice,
            "lang": "pl",
            "split": self.split,
            "total_step": TOTAL_STEP,
            "speed": SPEED,
            "sample_rate": self.sample_rate,
            "native_dtype": "float32",
            "native_granularity": "whole text chunk (up to 300 characters) per inference",
            "intra_op_threads": self.threads or "onnxruntime default",
            "seed": SEED,
            "versions": {"onnxruntime": ort.__version__, "numpy": np.__version__,
                         "helper.py": "supertone-oss-archive/supertonic@1e9799e"},
        }


def load(model: str, voice: str | None, threads: int | None, options: dict[str, Any]) -> SupertonicBackend:
    return SupertonicBackend(model, voice or "F1", threads, options.get("split", "native"))
