"""Measure RSS and RTF of the default voices with different ONNX Runtime memory settings.

Run one variant in each process, because ONNX Runtime keeps memory until the process stops:
    python scripts/measure_m5_arena.py --variant arena --out bench/results/m5/arena.json

Variants:
    arena      CPU memory arena on (the setting before 2026-10-15)
    no-arena   SessionOptions.enable_cpu_mem_arena = False (the daemon setting)
    shrink     arena on, RunOptions "memory.enable_memory_arena_shrinkage" = "cpu:0" for each run
    no-arena-no-pattern  no-arena, and SessionOptions.enable_mem_pattern = False

The script plays no audio. RTF is the synthesis time divided by the audio time.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_tts.__main__ import load_voices  # noqa: E402
from local_tts.config import ALIGNED_MODELS_DIR, DEFAULT_MODELS_DIR, DEFAULT_VOICES, REPO_DIR  # noqa: E402

CORPUS = REPO_DIR / "bench" / "corpus.json"
ENGLISH_LONG = (
    "Good morning! I checked the weather forecast for tomorrow in London. In the morning it will be cloudy, "
    "with a light wind from the west and a temperature of about twelve degrees. Around noon the clouds will "
    "break up, and in the afternoon you can expect sunshine and up to eighteen degrees. In the evening the "
    "wind will become stronger, and there is a small chance of rain after nine o'clock, so take an umbrella "
    "if you plan to come home late. Your first meeting starts at half past nine in the office on the third "
    "floor. After that, you have a call with the design team at eleven, and lunch with Anna at one. The "
    "train to Manchester leaves at four fifteen from platform six, and the trip takes about two hours. I "
    "also added a reminder to buy milk, bread and coffee on the way back. Do you want me to read your new "
    "messages now, or should I wait until you finish breakfast?"
)
ENGLISH_SHORT = "Sure, I am checking it now."


def rss_mb() -> tuple[float, float]:
    """Current and peak RSS of this process in MB."""
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    return int(fields["VmRSS"].split()[0]) / 1024, int(fields["VmHWM"].split()[0]) / 1024


def apply_variant(variant: str) -> None:
    """Set the memory options when the backends make their sessions.

    PiperBackend sets the arena off. The sessions are made after this, so the variant decides.
    """
    inference_session, run_options = ort.InferenceSession, ort.RunOptions

    def make_session(path, sess_options=None, **kwargs):
        sess_options.enable_cpu_mem_arena = variant in ("arena", "shrink")
        if variant == "no-arena-no-pattern":
            sess_options.enable_mem_pattern = False
        return inference_session(path, sess_options=sess_options, **kwargs)

    def make_run_options():
        opts = run_options()
        if variant == "shrink":
            opts.add_run_config_entry("memory.enable_memory_arena_shrinkage", "cpu:0")
        return opts

    ort.InferenceSession = make_session
    ort.RunOptions = make_run_options


def synthesize_seconds(backend, text: str) -> tuple[float, float]:
    start = time.perf_counter()
    audio = np.concatenate(list(backend.synthesize(text)))
    return time.perf_counter() - start, len(audio) / backend.sample_rate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=["arena", "no-arena", "shrink", "no-arena-no-pattern"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--rtf-runs", type=int, default=5)
    args = parser.parse_args()

    apply_variant(args.variant)
    items = {i["id"]: i.get("normalized") or i["raw"] for i in json.loads(CORPUS.read_text(encoding="utf-8"))["items"]}
    polish_texts = list(items.values())
    english_texts = [ENGLISH_SHORT, ENGLISH_LONG]

    result: dict = {"variant": args.variant, "ort": ort.__version__, "rss_mb": {}}
    backends = load_voices(DEFAULT_MODELS_DIR, DEFAULT_VOICES, threads=4, fix_trz=True, aligned_dir=ALIGNED_MODELS_DIR)
    result["rss_mb"]["after_load"] = rss_mb()

    def long_text(backend):
        return items["L1"] if backend.language == "pl" else ENGLISH_LONG

    for backend in backends.values():
        synthesize_seconds(backend, long_text(backend))
    result["rss_mb"]["after_one_long_each"] = rss_mb()

    for _ in range(args.rounds):
        for backend in backends.values():
            for text in polish_texts if backend.language == "pl" else english_texts:
                synthesize_seconds(backend, text)
    result["rss_mb"][f"after_{args.rounds}_rounds"] = rss_mb()

    rtf: dict = {}
    for name in ("zenski", "en_hfc_female"):
        backend = backends[name]
        short = items["S1"] if backend.language == "pl" else ENGLISH_SHORT
        for label, text in (("short", short), ("long", long_text(backend))):
            runs = [synthesize_seconds(backend, text) for _ in range(args.rtf_runs)]
            rtf[f"{name}_{label}"] = {
                "median_rtf": statistics.median(t / a for t, a in runs),
                "median_seconds": statistics.median(t for t, _ in runs),
            }
    result["rtf"] = rtf
    result["rss_mb"]["end"] = rss_mb()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
