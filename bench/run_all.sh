#!/usr/bin/env bash
# Run the complete M0 benchmark and write bench/results/report.md.
#
# Prerequisite: bench/setup.sh finished without errors.
# Duration on the reference machine (i5-8365U): about 3 hours.
# Keep the machine on AC power and do not run other heavy work during the run.
#
# Extra arguments go to "bench.py run", for example: --backend piper, --quick, --resume.
set -euo pipefail
BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$BENCH_DIR/env_info.py"
python3 "$BENCH_DIR/bench.py" run "$@" || echo "WARNING: some runs failed. The report shows them."
python3 "$BENCH_DIR/env_info.py" --snapshot-only
python3 "$BENCH_DIR/report.py"
