"""Summary of the "metrics" log lines of the daemon, for each voice.

Read the log of the systemd service:
    python scripts/metrics_summary.py --since "-1 day"
Or read a log file (also from stdin with "-"):
    python scripts/metrics_summary.py --file bench/results/logs/daemon.log

first_audio_s: from the first text of a request to the first audio write.
rtf: synthesis time divided by audio time. p95 is the nearest-rank value.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from typing import Iterable

MARKER = " metrics "


def _stats(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": round(statistics.median(ordered), 3),
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
    }


def summarize(lines: Iterable[str]) -> dict:
    results: dict[str, Counter] = defaultdict(Counter)
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for line in lines:
        if MARKER not in line:
            continue
        data = json.loads(line.split(MARKER, 1)[1])
        voice = data["voice"]
        results[voice][data["result"]] += 1
        for key in ("first_audio_s", "rtf"):
            if data.get(key) is not None:
                values[voice][key].append(data[key])
    return {
        voice: {"results": dict(results[voice]), **{key: _stats(v) for key, v in values[voice].items()}}
        for voice in results
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", default="-1 day", help="journalctl --since value. Default: %(default)s")
    parser.add_argument("--file", help="Read this log file instead of the journal. Use - for stdin.")
    args = parser.parse_args()
    if args.file == "-":
        lines = sys.stdin.read().splitlines()
    elif args.file:
        with open(args.file, encoding="utf-8") as log_file:
            lines = log_file.read().splitlines()
    else:
        lines = subprocess.run(
            ["journalctl", "--user", "-u", "local-tts", "-o", "cat", "--no-pager", "--since", args.since],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
    print(json.dumps(summarize(lines), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
