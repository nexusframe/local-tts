"""Pocket TTS adapter for the community Polish model shefowl/pocket-tts-polish-6l.

Important: pocket_tts calls torch.set_num_threads(1) when it is imported. This
adapter sets the thread count after the import, so the requested value is the
value that torch uses.

Options:
- quantize: "int8" applies pocket-tts dynamic int8 quantization at load time.
- int8_backend: "torchao" (default when torchao is installed, as in
  pocket-tts[quantize]) or "torch.ao" (the older FBGEMM fallback of
  pocket-tts). The adapter forces the choice by replacing
  pocket_tts.quantization._get_backend. Both are code paths of pocket-tts 3.3.0.
"""

from __future__ import annotations

import json
import threading
from importlib.metadata import version
from typing import Any, Iterator

import numpy as np
import torch
from pocket_tts import TTSModel

from common import BENCH_DIR, MODELS_DIR

SEED = 1234


class PocketBackend:
    def __init__(self, model: str, threads: int | None, quantize: bool, int8_backend: str | None) -> None:
        manifest = json.loads((BENCH_DIR / "models.json").read_text(encoding="utf-8"))["pocket"][model]
        model_dir = MODELS_DIR / "pocket" / model.replace("/", "__")
        reference = model_dir / "reference.wav"
        if not reference.exists():
            raise FileNotFoundError(f"{reference} not found. Run: python3 bench/fetch_models.py --backend pocket")
        if threads:
            torch.set_num_threads(threads)
        torch.manual_seed(SEED)
        if quantize and int8_backend:
            import pocket_tts.quantization as quantization

            if int8_backend not in ("torchao", "torch.ao"):
                raise ValueError(f"int8_backend must be torchao or torch.ao, not {int8_backend}")
            quantization._get_backend = lambda: int8_backend
        self.int8_backend = int8_backend
        self.model = TTSModel.load_model(config=manifest["config"], quantize=quantize)
        self.state = self.model.get_state_for_audio_prompt(reference)
        self.model_name = model
        self.config_url = manifest["config"]
        self.quantize = quantize
        self.sample_rate = self.model.sample_rate

    def stream(self, text: str, stop: threading.Event) -> Iterator[np.ndarray]:
        for chunk in self.model.generate_audio_stream(self.state, text, copy_state=True, stop=stop):
            yield chunk.numpy()

    def info(self) -> dict[str, Any]:
        from pocket_tts.quantization import _get_backend

        return {
            "backend": "pocket",
            "model": self.model_name,
            "config": self.config_url,
            "voice": "reference.wav from the model repo",
            "quantize": "int8" if self.quantize else "fp32",
            "quantization_backend": (self.int8_backend or _get_backend()) if self.quantize else None,
            "sample_rate": self.sample_rate,
            "native_dtype": "float32 (torch.Tensor)",
            "native_granularity": "Mimi frames (80 ms each) decoded in a separate thread; text split into chunks by token count",
            "torch_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
            "seed": SEED,
            "versions": {"pocket-tts": version("pocket-tts"), "torch": torch.__version__,
                         "torchao": _safe_version("torchao"), "numpy": np.__version__},
        }


def _safe_version(pkg: str) -> str | None:
    try:
        return version(pkg)
    except Exception:  # noqa: BLE001
        return None


def load(model: str, voice: str | None, threads: int | None, options: dict[str, Any]) -> PocketBackend:
    return PocketBackend(model, threads, quantize=options.get("quantize") == "int8",
                         int8_backend=options.get("int8_backend"))
