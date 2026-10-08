"""Run benchmark suites for one backend configuration in the current process.

Run this script with the Python interpreter of the backend venv, for example:

    bench/.venvs/piper/bin/python bench/run_backend.py --backend piper \
        --model pl_PL-gosia-medium --threads 4 --suites warm --out /tmp/x.json

bench.py calls this script with taskset. Normally you do not call it directly.

Suites:
  warm     3 warm-up runs, then 10 measured runs, for each corpus text (raw).
  stream   chunk timeline, playback simulation and cancel test (S1, M1, L1).
  repeat   100 consecutive runs of M1 and of M8 (memory and time drift).
  samples  one run for each raw and normalized text. Saves WAV files.
  cold     process cold start. Needs env BENCH_T0 (wall time before the process started).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

T_MAIN = time.time()

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import common as c  # noqa: E402


def parse_options(pairs: list[str]) -> dict[str, str]:
    out = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        out[key] = value
    return out


def run_warm(backend: c.Backend, info: dict[str, Any], texts: list[tuple[str, str, str]], warmup: int, runs: int) -> dict[str, Any]:
    out = {}
    for tid, variant, text in texts:
        c.log(f"warm {tid}/{variant}: {warmup} warm-up + {runs} runs")
        for _ in range(warmup):
            c.synthesize(backend, text, keep_audio=False)
        records = []
        first_checks = None
        for i in range(runs):
            r = c.synthesize(backend, text, keep_audio=True)
            checks = c.audio_checks(r.audio, backend.sample_rate, info["native_dtype"], text)
            if first_checks is None:
                first_checks = checks
            rec = r.record()
            rec["problems"] = checks.get("problems", [])
            records.append(rec)
        out[f"{tid}/{variant}"] = {
            "text": text,
            "runs": records,
            "checks_first_run": first_checks,
            "ttfa_s": c.summary([r["ttfa_s"] for r in records]),
            "total_s": c.summary([r["total_s"] for r in records]),
            "audio_s": c.summary([r["audio_s"] for r in records]),
            "rtf": c.summary([r["rtf"] for r in records]),
            "cpu_cores": c.summary([r["cpu_cores"] for r in records]),
            "other_cpu_cores": c.summary([r["other_cpu_cores"] for r in records]),
            "peak_rss_mb": c.summary([r["peak_rss_mb"] for r in records]),
            "n_chunks": c.summary([r["n_chunks"] for r in records]),
            "failed_runs": sum(not r["ok"] for r in records),
            "runs_with_problems": sum(bool(r["problems"]) for r in records),
            "warnings": sorted({w for r in records for w in r["warnings"]}),
        }
    return out


def run_stream(backend: c.Backend, ids: list[str], runs: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tid, variant, text in c.corpus_texts(ids):
        c.log(f"stream {tid}: 1 warm-up + {runs} runs")
        c.synthesize(backend, text, keep_audio=False)
        records = []
        for _ in range(runs):
            r = c.synthesize(backend, text, keep_audio=False)
            rec = r.record(keep_timeline=True)
            rec["playback"] = c.playback_simulation(r.chunk_times_s, r.chunk_samples, backend.sample_rate)
            rec["first_chunk_audio_s"] = r.chunk_samples[0] / backend.sample_rate if r.chunk_samples else None
            # Audio that is ready before the end of the call is the evidence for streaming.
            rec["first_chunk_before_end"] = bool(r.chunk_times_s) and r.chunk_times_s[0] < 0.9 * r.total_s
            gaps = np.diff([0.0] + r.chunk_times_s)
            rec["max_gap_between_chunks_s"] = float(gaps.max()) if len(gaps) else None
            records.append(rec)
        out[tid] = {
            "runs": records,
            "ttfa_s": c.summary([r["ttfa_s"] for r in records]),
            "total_s": c.summary([r["total_s"] for r in records]),
            "n_chunks": c.summary([r["n_chunks"] for r in records]),
            "first_chunk_audio_s": c.summary([r["first_chunk_audio_s"] for r in records]),
            "max_gap_between_chunks_s": c.summary([r["max_gap_between_chunks_s"] for r in records]),
            "first_chunk_before_end": all(r["first_chunk_before_end"] for r in records),
            "underrun_runs": sum(bool(r["playback"]["underrun"]) for r in records),
            "worst_gap_s": max(r["playback"]["worst_gap_s"] for r in records),
        }
    # Cancel test: set the stop event after the first chunk of L1.
    text = c.corpus_texts(["L1"])[0][2]
    cancels = []
    for _ in range(runs):
        r = c.synthesize(backend, text, keep_audio=False, stop_after_chunks=1)
        cancels.append({
            "ttfa_s": r.ttfa_s,
            "total_s": r.total_s,
            "cancel_latency_s": r.total_s - (r.ttfa_s or 0.0),
            "audio_after_cancel_s": (sum(r.chunk_samples[1:]) / backend.sample_rate) if r.chunk_samples else 0.0,
            "chunks_after_cancel": max(0, r.n_chunks - 1),
            "error": r.error,
        })
    out["cancel_L1"] = {
        "runs": cancels,
        "cancel_latency_s": c.summary([x["cancel_latency_s"] for x in cancels]),
        "audio_after_cancel_s": c.summary([x["audio_after_cancel_s"] for x in cancels]),
        "full_L1_total_s": out.get("L1", {}).get("total_s"),
    }
    return out


def run_repeat(backend: c.Backend, ids: list[str], n: int) -> dict[str, Any]:
    out = {}
    for tid, variant, text in c.corpus_texts(ids):
        c.log(f"repeat {tid}: 3 warm-up + {n} runs")
        for _ in range(3):
            c.synthesize(backend, text, keep_audio=False)
        rss_start = c.rss_mb()
        rows = []
        for i in range(n):
            r = c.synthesize(backend, text, keep_audio=False)
            rows.append({"total_s": round(r.total_s, 4), "audio_s": round(r.audio_s, 4), "rss_after_mb": round(r.rss_after_mb, 1),
                         "ok": r.ok, "error": r.error, "n_warnings": len(r.warnings)})
        rss = [x["rss_after_mb"] for x in rows]
        totals = [x["total_s"] for x in rows]
        audio = [x["audio_s"] for x in rows]
        slope = float(np.polyfit(np.arange(n), rss, 1)[0]) if n > 1 else 0.0
        out[tid] = {
            "n": n,
            "rows": rows,
            "total_s": c.summary(totals),
            "audio_s": c.summary(audio),
            "rtf": c.summary([t / a for t, a in zip(totals, audio) if a > 0]),
            "rss_before_mb": round(rss_start, 1),
            "rss_after_mb": rss[-1],
            "rss_max_mb": max(rss),
            "rss_slope_mb_per_100_runs": round(slope * 100, 2),
            "total_median_first10_s": round(float(np.median(totals[:10])), 4),
            "total_median_last10_s": round(float(np.median(totals[-10:])), 4),
            "distinct_audio_lengths": len(set(audio)),
            "errors": sum(not x["ok"] for x in rows),
            "runs_with_warnings": sum(x["n_warnings"] > 0 for x in rows),
        }
    return out


def run_samples(backend: c.Backend, info: dict[str, Any], audio_dir: Path | None) -> dict[str, Any]:
    out = {}
    for tid, variant, text in c.corpus_texts(variants=("raw", "normalized")):
        c.log(f"sample {tid}/{variant}")
        r = c.synthesize(backend, text, keep_audio=True)
        checks = c.audio_checks(r.audio, backend.sample_rate, info["native_dtype"], text)
        wav = None
        if audio_dir is not None and r.audio is not None:
            wav = audio_dir / f"{tid}_{variant}.wav"
            c.write_wav(wav, r.audio, backend.sample_rate)
        rec = r.record()
        rec.update({"text": text, "checks": checks, "wav": str(wav.relative_to(c.BENCH_DIR)) if wav else None})
        out[f"{tid}/{variant}"] = rec
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", required=True, choices=["piper", "pocket", "supertonic"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--voice", default=None)
    parser.add_argument("--option", action="append", default=[], metavar="KEY=VALUE",
                        help="Backend option, for example quantize=int8 or split=sentence.")
    parser.add_argument("--threads", type=int, default=0, help="Intra-op threads. 0 means the library default.")
    parser.add_argument("--config-name", default="default")
    parser.add_argument("--suites", default="warm", help="Comma-separated: warm,stream,repeat,samples,cold")
    parser.add_argument("--texts", default="", help="Comma-separated corpus ids for the warm suite. Default: all.")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--stream-runs", type=int, default=3)
    parser.add_argument("--repeat-n", type=int, default=100)
    parser.add_argument("--audio-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    suites = [s for s in args.suites.split(",") if s]
    options = parse_options(args.option)
    meta: dict[str, Any] = {
        "config_name": args.config_name,
        "threads_requested": args.threads,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "options": options,
        "python": platform.python_version(),
        "load_avg_start": c.load_avg(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "argv": sys.argv[1:],
    }

    t_import0 = time.time()
    with c.capture_warnings() as load_warnings:
        module = importlib.import_module(f"backends.{args.backend}_backend")
        t_import1 = time.time()
        backend = module.load(args.model, args.voice, args.threads or None, options)
        t_load1 = time.time()
    info = backend.info()
    meta.update({
        "backend_info": info,
        "import_s": round(t_import1 - t_import0, 3),
        "load_s": round(t_load1 - t_import1, 3),
        "rss_after_load_mb": round(c.rss_mb(), 1),
        "load_warnings": load_warnings.messages,
    })
    c.log(f"loaded {args.backend} {args.model} {options} threads={args.threads}: "
          f"import {meta['import_s']}s, load {meta['load_s']}s, rss {meta['rss_after_load_mb']} MB")

    results: dict[str, Any] = {}
    if "cold" in suites:
        t0 = float(os.environ["BENCH_T0"])
        text = c.corpus_texts(["S1"])[0][2]
        r = c.synthesize(backend, text, keep_audio=False)
        t_first = t_load1 + (r.ttfa_s or 0.0)
        results["cold"] = {
            "process_start_to_main_s": round(T_MAIN - t0, 3),
            "import_s": meta["import_s"],
            "load_s": meta["load_s"],
            "first_synthesis_ttfa_s": round(r.ttfa_s or -1, 3),
            "first_synthesis_total_s": round(r.total_s, 3),
            "cold_start_to_first_audio_s": round(t_first - t0, 3),
            "ok": r.ok,
            "error": r.error,
        }
    if "warm" in suites:
        ids = [x for x in args.texts.split(",") if x] or None
        results["warm"] = run_warm(backend, info, c.corpus_texts(ids), args.warmup, args.runs)
    if "stream" in suites:
        results["stream"] = run_stream(backend, ["S1", "M1", "L1"], args.stream_runs)
    if "repeat" in suites:
        results["repeat"] = run_repeat(backend, ["M1", "M8"], args.repeat_n)
    if "samples" in suites:
        results["samples"] = run_samples(backend, info, args.audio_dir)

    meta["load_avg_end"] = c.load_avg()
    meta["lifetime_peak_rss_mb"] = round(c.lifetime_peak_rss_mb(), 1)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"meta": meta, "results": results}, indent=1, ensure_ascii=False), encoding="utf-8")
    c.log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
