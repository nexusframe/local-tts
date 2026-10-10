"""Benchmark orchestrator. Uses only the Python standard library.

It starts one process per backend configuration (run_backend.py inside the
backend venv), pins it to CPUs with taskset, and writes JSON files to
bench/results/raw/.

Procedure for each target (backend + model + variant):
  1. Thread sweep: the warm suite on every thread configuration.
  2. Select the configuration with the lowest mean of per-text median RTF.
  3. On that configuration: stream, repeat and samples suites.
  4. Cold start: 3 new processes on that configuration.

Examples:
  python3 bench/bench.py run                      # everything
  python3 bench/bench.py run --backend piper      # one backend
  python3 bench/bench.py run --quick              # short smoke run (not for decisions)
  python3 bench/bench.py list                     # show targets and configurations
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
VENVS = BENCH_DIR / ".venvs"
RAW = BENCH_DIR / "results" / "raw"
LOGS = BENCH_DIR / "results" / "logs"
AUDIO = BENCH_DIR / "results" / "audio"


@dataclass(frozen=True)
class ThreadConfig:
    name: str
    threads: int
    cpus: str  # taskset CPU list


# CPUs 0-3 are four different physical cores on the reference machine; 4-7 are
# their hyper-threads. bench.py checks that the CPU list exists on this machine.
THREAD_CONFIGS = [
    ThreadConfig("t1c2", 1, "0,1"),
    ThreadConfig("t2c2", 2, "0,1"),
    ThreadConfig("t4c4", 4, "0-3"),
    ThreadConfig("t8c8", 8, "0-7"),
]


@dataclass
class Target:
    backend: str
    model: str
    variant: str  # short label: voice name or quantization
    voice: str | None = None
    options: dict[str, str] = field(default_factory=dict)
    sweep: bool = True  # False: use the best configuration of `sweep_from`
    sweep_from: str | None = None
    extra_stream_options: dict[str, str] | None = None
    only_configs: tuple[str, ...] | None = None  # None: all THREAD_CONFIGS

    @property
    def key(self) -> str:
        return f"{self.backend}__{self.model.replace('/', '_')}__{self.variant}"


TARGETS = [
    # Order: the most important comparison first (Pocket PL vs Piper wg_glos).
    Target("pocket", "shefowl/pocket-tts-polish-6l", "fp32", options={"quantize": "fp32"}),
    # The torchao int8 kernels were slower than fp32 on an AVX2-only CPU in a probe,
    # so the older torch.ao (FBGEMM) path of pocket-tts is measured as well.
    Target("pocket", "shefowl/pocket-tts-polish-6l", "int8-torch.ao", options={"quantize": "int8", "int8_backend": "torch.ao"}),
    Target("piper", "pl_PL-zenski_wg_glos-medium", "zenski"),
    Target("piper", "pl_PL-gosia-medium", "gosia"),
    Target("piper", "pl_PL-bass-high", "bass"),
    # Male medium voices, added after M4 to find a male voice for the daemon.
    Target("piper", "pl_PL-meski_wg_glos-medium", "meski"),
    Target("piper", "pl_PL-jarvis_wg_glos-medium", "jarvis"),
    Target("piper", "pl_PL-darkman-medium", "darkman"),
    Target("piper", "pl_PL-mc_speech-medium", "mc_speech"),
    # English medium voices (5 female, 5 male). The corpus is Polish, so only speed and memory
    # are comparable. Listening samples with English text: scripts/listen_en_voices.py.
    Target("piper", "en_US-lessac-medium", "lessac"),
    Target("piper", "en_US-amy-medium", "amy"),
    Target("piper", "en_US-kristin-medium", "kristin"),
    Target("piper", "en_US-hfc_female-medium", "hfc_female"),
    Target("piper", "en_GB-cori-medium", "cori"),
    Target("piper", "en_US-joe-medium", "joe"),
    Target("piper", "en_US-john-medium", "john"),
    Target("piper", "en_US-bryce-medium", "bryce"),
    Target("piper", "en_US-hfc_male-medium", "hfc_male"),
    Target("piper", "en_GB-alan-medium", "alan"),
    Target("supertonic", "supertonic-3", "F1", voice="F1", extra_stream_options={"split": "sentence"}),
    # The voice style does not change the network, so M1 reuses the F1 thread sweep.
    Target("supertonic", "supertonic-3", "M1", voice="M1", sweep=False, sweep_from="supertonic__supertonic-3__F1"),
    # Default int8 path of pocket-tts[quantize]. A probe gave RTF 1.40 with 1 thread,
    # so only the configurations with more threads are measured.
    Target("pocket", "shefowl/pocket-tts-polish-6l", "int8-torchao", options={"quantize": "int8", "int8_backend": "torchao"},
           only_configs=("t4c4", "t8c8")),
]


def python_for(backend: str) -> Path:
    py = VENVS / backend / "bin" / "python"
    if not py.exists():
        raise SystemExit(f"{py} not found. Run bench/setup.sh first.")
    return py


def run_child(target: Target, cfg: ThreadConfig, suites: str, out: Path, extra: list[str],
              options: dict[str, str] | None = None, env_extra: dict[str, str] | None = None) -> int:
    """Run run_backend.py for one configuration. Return the exit code."""
    opts = options if options is not None else target.options
    cmd = ["taskset", "-c", cfg.cpus, str(python_for(target.backend)), str(BENCH_DIR / "run_backend.py"),
           "--backend", target.backend, "--model", target.model, "--threads", str(cfg.threads),
           "--config-name", cfg.name, "--suites", suites, "--out", str(out), *extra]
    if target.voice:
        cmd += ["--voice", target.voice]
    for k, v in opts.items():
        cmd += ["--option", f"{k}={v}"]
    env = dict(os.environ)
    env.update({"OMP_NUM_THREADS": str(cfg.threads), "MKL_NUM_THREADS": str(cfg.threads),
                "OPENBLAS_NUM_THREADS": str(cfg.threads), "HF_HUB_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false", "PYTHONUNBUFFERED": "1"})
    env.update(env_extra or {})
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{out.stem}.log"
    print(f"[{time.strftime('%H:%M:%S')}] {target.key} {cfg.name} {suites} -> {out.name}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(" ".join(cmd) + "\n")
        log.flush()
        if "cold" in suites:
            env["BENCH_T0"] = repr(time.time())
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
        _, status, rusage = os.wait4(proc.pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
    if out.exists():
        data = json.loads(out.read_text(encoding="utf-8"))
        data["meta"]["process_max_rss_mb_wait4"] = round(rusage.ru_maxrss / 1024, 1)
        data["meta"]["exit_code"] = proc.returncode
        out.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    if proc.returncode != 0:
        print(f"  FAILED with exit code {proc.returncode}. See {log_path}", flush=True)
    return proc.returncode


def mean_median_rtf(path: Path) -> float | None:
    if not path.exists():
        return None
    warm = json.loads(path.read_text(encoding="utf-8"))["results"].get("warm", {})
    vals = [v["rtf"]["median"] for v in warm.values() if v.get("rtf")]
    return statistics.fmean(vals) if vals else None


def best_config(target_key: str, configs: list[ThreadConfig]) -> ThreadConfig:
    scored = [(mean_median_rtf(RAW / f"{target_key}__{cfg.name}__warm.json"), cfg) for cfg in configs]
    scored = [(s, cfg) for s, cfg in scored if s is not None]
    if not scored:
        raise SystemExit(f"No warm results for {target_key}. Run the sweep first.")
    return min(scored, key=lambda x: x[0])[1]


def check_cpus(configs: list[ThreadConfig]) -> None:
    available = os.sched_getaffinity(0)
    for cfg in configs:
        cpus: set[int] = set()
        for part in cfg.cpus.split(","):
            lo, _, hi = part.partition("-")
            cpus |= set(range(int(lo), int(hi or lo) + 1))
        if not cpus <= available:
            raise SystemExit(f"CPU list {cfg.cpus} of {cfg.name} is not available on this machine ({sorted(available)}). "
                             "Edit THREAD_CONFIGS in bench.py.")


def cmd_run(args: argparse.Namespace) -> int:
    configs = [c for c in THREAD_CONFIGS if not args.configs or c.name in args.configs.split(",")]
    check_cpus(configs)
    targets = [t for t in TARGETS if not args.backend or t.backend in args.backend]
    if args.target:
        targets = [t for t in targets if t.key in args.target]
    if args.quick:
        warm = ["--warmup", "1", "--runs", "3", "--texts", "S1,M1,M8"]
        rest = ["--stream-runs", "1", "--repeat-n", "5"]
    else:
        warm, rest = [], []
    failures = 0
    RAW.mkdir(parents=True, exist_ok=True)
    for t in targets:
        sweep_configs = [c for c in configs if not t.only_configs or c.name in t.only_configs] if t.sweep else []
        for cfg in sweep_configs:
            out = RAW / f"{t.key}__{cfg.name}__warm.json"
            if args.resume and out.exists():
                continue
            failures += run_child(t, cfg, "warm", out, warm) != 0
        best = best_config(t.key if t.sweep else str(t.sweep_from), sweep_configs or configs)
        print(f"  best configuration for {t.key}: {best.name}", flush=True)
        if not t.sweep:
            out = RAW / f"{t.key}__{best.name}__warm.json"
            if not (args.resume and out.exists()):
                failures += run_child(t, best, "warm", out, warm) != 0
        out = RAW / f"{t.key}__{best.name}__detail.json"
        if not (args.resume and out.exists()):
            failures += run_child(t, best, "stream,repeat,samples", out,
                                  rest + ["--audio-dir", str(AUDIO / t.key)]) != 0
        if t.extra_stream_options:
            label = "-".join(f"{k}{v}" for k, v in t.extra_stream_options.items())
            out = RAW / f"{t.key}__{best.name}__stream-{label}.json"
            if not (args.resume and out.exists()):
                failures += run_child(t, best, "stream", out, rest,
                                      options={**t.options, **t.extra_stream_options}) != 0
        for i in range(1, 4):
            out = RAW / f"{t.key}__{best.name}__cold{i}.json"
            if not (args.resume and out.exists()):
                failures += run_child(t, best, "cold", out, []) != 0
    print(f"done, {failures} failed runs", flush=True)
    return 1 if failures else 0


def cmd_list(args: argparse.Namespace) -> int:
    for t in TARGETS:
        print(f"{t.key:55} sweep={'yes' if t.sweep else 'from ' + str(t.sweep_from)} options={t.options}")
    for c in THREAD_CONFIGS:
        print(f"{c.name}: threads={c.threads} cpus={c.cpus}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="Run the benchmark.")
    p.add_argument("--backend", action="append", choices=["piper", "pocket", "supertonic"])
    p.add_argument("--target", action="append", help="Run only this target key (see 'list').")
    p.add_argument("--configs", default="", help="Comma-separated thread configuration names. Default: all.")
    p.add_argument("--quick", action="store_true", help="Few runs and texts. Use only to test the setup.")
    p.add_argument("--resume", action="store_true", help="Skip runs whose result file exists.")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("list", help="Show targets and thread configurations.")
    p.set_defaults(func=cmd_list)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
