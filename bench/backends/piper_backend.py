"""Piper (piper1-gpl, package piper-tts) adapter.

The adapter builds the ONNX Runtime session itself. PiperVoice.load() uses a
default SessionOptions() and gives no thread control, so the thread benchmark
needs this.
"""

from __future__ import annotations

import json
import threading
from importlib.metadata import version
from typing import Any, Iterator

import numpy as np
import onnxruntime as ort
from piper import PiperVoice
from piper.config import PiperConfig

from common import MODELS_DIR


class PiperBackend:
    def __init__(self, model: str, threads: int | None) -> None:
        model_dir = MODELS_DIR / "piper" / model
        onnx_path = model_dir / f"{model}.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"{onnx_path} not found. Run: python3 bench/fetch_models.py --backend piper")
        config = json.loads((model_dir / f"{model}.onnx.json").read_text(encoding="utf-8"))
        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
            opts.inter_op_num_threads = 1
        self.voice = PiperVoice(
            config=PiperConfig.from_dict(config),
            session=ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"]),
        )
        self.model = model
        self.threads = threads
        self.sample_rate = self.voice.config.sample_rate

    def stream(self, text: str, stop: threading.Event) -> Iterator[np.ndarray]:
        for chunk in self.voice.synthesize(text):
            yield chunk.audio_float_array
            if stop.is_set():
                return

    def info(self) -> dict[str, Any]:
        return {
            "backend": "piper",
            "model": self.model,
            "voice": self.model,
            "sample_rate": self.sample_rate,
            "native_dtype": "float32 (int16 available via AudioChunk.audio_int16_bytes)",
            "native_granularity": "one chunk per sentence (sentence split by espeak-ng)",
            "intra_op_threads": self.threads or "onnxruntime default",
            "versions": {"piper-tts": version("piper-tts"), "onnxruntime": ort.__version__, "numpy": np.__version__},
            "synthesis_config": "library defaults (normalize_audio=True, model inference settings from .onnx.json)",
        }


def load(model: str, voice: str | None, threads: int | None, options: dict[str, Any]) -> PiperBackend:
    return PiperBackend(model, threads)
