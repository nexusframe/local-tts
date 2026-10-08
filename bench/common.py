"""Shared measurement code for the TTS benchmark.

Every backend venv imports this module. It depends only on the standard
library, numpy and psutil.

Terms used in this module and in the report:
- chunk: one audio array that the backend gives back from its iterator.
- TTFA (time to first audio): seconds from the synthesis call to the first chunk.
- total: seconds from the synthesis call to the end of the iterator.
- RTF (real-time factor): total / audio duration. A value below 1.0 is faster than real time.
- CPU cores used: (process user + system CPU time) / wall time. 2.0 means two cores were busy.
- other CPU cores: (system-wide busy CPU time - this process CPU time) / wall time.
  It shows how much other processes on the machine disturbed the run.
"""

from __future__ import annotations

import json
import logging
import math
import os
import resource
import statistics
import threading
import time
import warnings
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Protocol

import numpy as np
import psutil

BENCH_DIR = Path(__file__).resolve().parent
MODELS_DIR = BENCH_DIR / "models"
RESULTS_DIR = BENCH_DIR / "results"


class Backend(Protocol):
    """The small interface that each backend adapter implements."""

    sample_rate: int

    def stream(self, text: str, stop: threading.Event) -> Iterator[np.ndarray]:
        """Yield mono float32 chunks. Stop early when `stop` is set."""
        ...

    def info(self) -> dict[str, Any]:
        """Return versions, settings and the native chunk granularity."""
        ...


# --------------------------------------------------------------------------- corpus


def load_corpus() -> list[dict[str, Any]]:
    data = json.loads((BENCH_DIR / "corpus.json").read_text(encoding="utf-8"))
    return data["items"]


def corpus_texts(ids: list[str] | None = None, variants: tuple[str, ...] = ("raw",)) -> list[tuple[str, str, str]]:
    """Return (id, variant, text) for the selected ids and variants. Null variants are skipped."""
    out = []
    for item in load_corpus():
        if ids and item["id"] not in ids:
            continue
        for variant in variants:
            if item.get(variant):
                out.append((item["id"], variant, item[variant]))
    return out


# --------------------------------------------------------------------------- memory


def system_busy_s() -> float:
    t = psutil.cpu_times()
    return t.user + t.nice + t.system + t.irq + t.softirq + getattr(t, "steal", 0.0)


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 2**20


def lifetime_peak_rss_mb() -> float:
    """Peak RSS of this process since it started (Linux reports ru_maxrss in KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class RssSampler:
    """Sample the RSS of this process in a background thread to find the peak during a run."""

    def __init__(self, interval_s: float = 0.02) -> None:
        self.interval_s = interval_s
        self._proc = psutil.Process()
        self._stop = threading.Event()
        self.peak = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self._proc.memory_info().rss)
            self._stop.wait(self.interval_s)

    def __enter__(self) -> "RssSampler":
        self.peak = self._proc.memory_info().rss
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, self._proc.memory_info().rss)

    @property
    def peak_mb(self) -> float:
        return self.peak / 2**20


# --------------------------------------------------------------------------- warnings


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(f"{record.levelname} {record.name}: {record.getMessage()}"[:300])


@dataclass
class Captured:
    messages: list[str] = field(default_factory=list)


class capture_warnings:
    """Collect Python warnings and log records at WARNING level or higher."""

    def __enter__(self) -> Captured:
        self.result = Captured()
        self._handler = _ListHandler()
        logging.getLogger().addHandler(self._handler)
        self._cw = warnings.catch_warnings(record=True)
        self._records = self._cw.__enter__()
        warnings.simplefilter("always")
        return self.result

    def __exit__(self, *exc: object) -> None:
        self._cw.__exit__(*exc)
        logging.getLogger().removeHandler(self._handler)
        self.result.messages = [f"{w.category.__name__}: {w.message}"[:300] for w in self._records]
        self.result.messages += self._handler.records


# --------------------------------------------------------------------------- one synthesis


@dataclass
class RunResult:
    ok: bool
    error: str | None
    ttfa_s: float | None
    total_s: float
    audio_s: float
    rtf: float | None
    cpu_cores: float
    other_cpu_cores: float
    peak_rss_mb: float
    rss_before_mb: float
    rss_after_mb: float
    n_chunks: int
    chunk_times_s: list[float]
    chunk_samples: list[int]
    warnings: list[str]
    audio: np.ndarray | None = None

    def record(self, keep_timeline: bool = False) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k not in ("audio", "chunk_times_s", "chunk_samples")}
        if self.chunk_samples:
            d["chunk_samples_min"] = min(self.chunk_samples)
            d["chunk_samples_max"] = max(self.chunk_samples)
        if keep_timeline:
            d["chunk_times_s"] = [round(t, 4) for t in self.chunk_times_s]
            d["chunk_samples"] = self.chunk_samples
        return d


def synthesize(
    backend: Backend,
    text: str,
    keep_audio: bool = True,
    stop_after_chunks: int | None = None,
) -> RunResult:
    """Run one synthesis and measure it.

    If `stop_after_chunks` is set, the run sets the stop event after that many
    chunks and then drains the iterator. This measures how fast the backend
    reacts to a cancel request.
    """
    proc = psutil.Process()
    stop = threading.Event()
    chunks: list[np.ndarray] = []
    times: list[float] = []
    sizes: list[int] = []
    error: str | None = None
    rss_before = rss_mb()
    cpu0 = proc.cpu_times()
    sys0 = system_busy_s()
    with capture_warnings() as cap, RssSampler() as sampler:
        t0 = time.perf_counter()
        try:
            for chunk in backend.stream(text, stop):
                times.append(time.perf_counter() - t0)
                arr = np.asarray(chunk)
                sizes.append(int(arr.shape[-1]))
                if keep_audio:
                    chunks.append(arr)
                if stop_after_chunks is not None and len(times) >= stop_after_chunks:
                    stop.set()
        except Exception as exc:  # noqa: BLE001 - the benchmark must record every failure
            error = f"{type(exc).__name__}: {exc}"[:500]
        total = time.perf_counter() - t0
    cpu1 = proc.cpu_times()
    sys1 = system_busy_s()
    cpu_s = (cpu1.user - cpu0.user) + (cpu1.system - cpu0.system)
    audio_s = sum(sizes) / backend.sample_rate
    audio = np.concatenate(chunks) if keep_audio and chunks else None
    return RunResult(
        ok=error is None and audio_s > 0,
        error=error if error or audio_s > 0 else "empty audio",
        ttfa_s=times[0] if times else None,
        total_s=total,
        audio_s=audio_s,
        rtf=total / audio_s if audio_s > 0 else None,
        cpu_cores=cpu_s / total if total > 0 else 0.0,
        other_cpu_cores=max(0.0, (sys1 - sys0 - cpu_s) / total) if total > 0 else 0.0,
        peak_rss_mb=sampler.peak_mb,
        rss_before_mb=rss_before,
        rss_after_mb=rss_mb(),
        n_chunks=len(times),
        chunk_times_s=times,
        chunk_samples=sizes,
        warnings=cap.messages,
        audio=audio,
    )


# --------------------------------------------------------------------------- audio checks


def audio_checks(audio: np.ndarray | None, sample_rate: int, native_dtype: str, text: str) -> dict[str, Any]:
    """Check one synthesized audio array. Return values and a list of problems."""
    if audio is None or audio.size == 0:
        return {"problems": ["empty audio"]}
    a = np.asarray(audio)
    channels = 1 if a.ndim == 1 else int(a.shape[0])
    a = a.reshape(-1).astype(np.float64)
    finite = np.isfinite(a)
    n_nonfinite = int(a.size - finite.sum())
    a = np.where(finite, a, 0.0)
    peak = float(np.max(np.abs(a)))
    rms = float(np.sqrt(np.mean(a**2)))
    duration = a.size / sample_rate
    words = len(text.split())
    # Leading and trailing silence: samples below -50 dBFS in 10 ms frames.
    frame = max(1, sample_rate // 100)
    n_frames = a.size // frame
    voiced = np.sqrt(np.mean(a[: n_frames * frame].reshape(n_frames, frame) ** 2, axis=1)) > 10 ** (-50 / 20) if n_frames else np.array([])
    lead = int(np.argmax(voiced)) * 0.01 if voiced.any() else duration
    trail = int(np.argmax(voiced[::-1])) * 0.01 if voiced.any() else duration
    res = {
        "sample_rate": sample_rate,
        "channels": channels,
        "dtype": native_dtype,
        "n_samples": int(a.size),
        "duration_s": round(duration, 3),
        "n_nonfinite": n_nonfinite,
        "peak": round(peak, 4),
        "rms_dbfs": round(20 * math.log10(rms), 1) if rms > 0 else None,
        "clip_fraction": round(float(np.mean(np.abs(a) >= 0.999)), 5),
        "leading_silence_s": round(lead, 2),
        "trailing_silence_s": round(trail, 2),
        "words_per_s": round(words / duration, 2) if duration > 0 else None,
    }
    problems = []
    if n_nonfinite:
        problems.append(f"{n_nonfinite} NaN/Inf samples")
    if peak < 0.01:
        problems.append(f"peak {peak:.4f} is too low (silent output)")
    if res["clip_fraction"] > 0.01:
        problems.append(f"clip fraction {res['clip_fraction']} > 1%")
    if channels != 1:
        problems.append(f"{channels} channels, expected mono")
    # Normal Polish speech is about 2-3.5 words/s. Values far outside suggest
    # skipped words (too fast) or extra audio (too slow). This is a heuristic only.
    if res["words_per_s"] is not None and not 1.0 <= res["words_per_s"] <= 4.5:
        problems.append(f"speech rate {res['words_per_s']} words/s is outside 1.0-4.5 (possible skip or extra audio)")
    if lead > 1.0 or trail > 1.5:
        problems.append(f"long silence at start ({lead:.2f}s) or end ({trail:.2f}s)")
    res["problems"] = problems
    return res


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    """Write mono 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(np.nan_to_num(audio.reshape(-1)), -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------- statistics


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile (same method as numpy's default)."""
    return float(np.percentile(np.asarray(values, dtype=float), q))


def summary(values: list[float | None]) -> dict[str, float | int] | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {
        "n": len(vals),
        "median": round(statistics.median(vals), 4),
        "p95": round(percentile(vals, 95), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "mean": round(statistics.fmean(vals), 4),
        "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
    }


def playback_simulation(chunk_times_s: list[float], chunk_samples: list[int], sample_rate: int) -> dict[str, Any]:
    """Simulate playback that starts when the first chunk arrives.

    For every chunk, compare its arrival time with the time when the player
    needs it. A positive gap is an underrun (the player waits for audio).
    """
    if not chunk_times_s:
        return {"underrun": None}
    start = chunk_times_s[0]
    played = 0.0
    gaps = []
    for t, n in zip(chunk_times_s, chunk_samples):
        needed_at = start + played
        gaps.append(t - needed_at)
        played += n / sample_rate
    worst = max(gaps[1:], default=0.0)
    total_stall = sum(g for g in gaps[1:] if g > 0)
    # Smallest start delay after the first chunk that removes every underrun.
    return {
        "underrun": worst > 0,
        "worst_gap_s": round(worst, 4),
        "total_stall_s": round(total_stall, 4),
        "start_delay_for_no_underrun_s": round(max(0.0, worst), 4),
    }


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def env_threads(threads: int) -> dict[str, str]:
    """Environment variables that limit thread pools of common math libraries."""
    n = str(threads)
    return {"OMP_NUM_THREADS": n, "MKL_NUM_THREADS": n, "OPENBLAS_NUM_THREADS": n}


def load_avg() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]

