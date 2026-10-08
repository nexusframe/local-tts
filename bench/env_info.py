"""Record the benchmark environment to bench/results/env.json.

Uses only the Python standard library. Commands that do not exist on the
machine are recorded as missing, not as errors.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
VENVS = BENCH_DIR / ".venvs"


def sh(cmd: list[str], timeout: float = 20) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return f"<missing: {cmd[0]}>"
    except subprocess.TimeoutExpired:
        return f"<timeout: {' '.join(cmd)}>"


def read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def thermal() -> dict[str, float]:
    out = {}
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        t, v = read(str(zone / "type")), read(str(zone / "temp"))
        if t and v and v.lstrip("-").isdigit():
            out[t] = int(v) / 1000
    return out


def power() -> dict[str, str | None]:
    out = {}
    for ps in sorted(Path("/sys/class/power_supply").glob("*")):
        out[ps.name] = {k: read(str(ps / k)) for k in ("type", "online", "status", "capacity") if (ps / k).exists()}
    return out


def snapshot() -> dict:
    """Values that change during the run."""
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "load_avg": [round(x, 2) for x in os.getloadavg()],
        "thermal_c": thermal(),
        "power_supply": power(),
        "meminfo_available_kb": next((line.split()[1] for line in (read("/proc/meminfo") or "").splitlines()
                                      if line.startswith("MemAvailable")), None),
        "cpu_mhz_now": sh(["sh", "-c", "grep MHz /proc/cpuinfo"]).splitlines(),
    }


def venv_info(name: str) -> dict:
    py = VENVS / name / "bin" / "python"
    if not py.exists():
        return {"missing": str(py)}
    return {
        "python": sh([str(py), "-c", "import sys; print(sys.version)"]),
        "pip_freeze": sh([str(py), "-m", "pip", "freeze", "--all"]).splitlines(),
    }


def collect() -> dict:
    gov_files = sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"))
    epp_files = sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/energy_performance_preference"))
    vendor = BENCH_DIR / ".vendor" / "supertonic"
    return {
        "uname": sh(["uname", "-a"]),
        "os_release": read("/etc/os-release"),
        "lscpu": sh(["lscpu"]),
        "lscpu_e": sh(["lscpu", "-e"]),
        "nproc": os.cpu_count(),
        "free_h": sh(["free", "-h"]),
        "cpupower_frequency_info": sh(["cpupower", "frequency-info"]),
        "scaling_governor": sorted({read(str(f)) for f in gov_files}),
        "energy_performance_preference": sorted({read(str(f)) for f in epp_files}),
        "intel_pstate_no_turbo": read("/sys/devices/system/cpu/intel_pstate/no_turbo"),
        "smt_active": read("/sys/devices/system/cpu/smt/active"),
        "system_python": sys.version,
        "platform": platform.platform(),
        "venvs": {name: venv_info(name) for name in ("piper", "pocket", "supertonic")},
        "supertonic_code_revision": sh(["git", "-C", str(vendor), "rev-parse", "HEAD"]) if vendor.exists() else None,
        "repo_git_head": sh(["git", "-C", str(BENCH_DIR.parent), "rev-parse", "HEAD"]),
        "repo_git_status": sh(["git", "-C", str(BENCH_DIR.parent), "status", "--short"]),
        "models_manifest": json.loads((BENCH_DIR / "models.json").read_text(encoding="utf-8")),
        "snapshot": snapshot(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=BENCH_DIR / "results" / "env.json")
    parser.add_argument("--snapshot-only", action="store_true",
                        help="Add only a snapshot (load, temperature, power) to the existing file under 'snapshot_end'.")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.snapshot_only:
        data = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
        data["snapshot_end"] = snapshot()
    else:
        data = collect()
    args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
