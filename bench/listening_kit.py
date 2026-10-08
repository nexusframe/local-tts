"""Make a blind listening test from the WAV samples of the benchmark.

The script copies the sample WAV files to bench/results/listening/ with random
names. It writes:
- ratings.csv: one row per file. The listener fills in the score columns.
- key.json: the map from random name to backend, model and text. Do not open
  it before you finish the ratings.

After the ratings, run with --score to get the mean score per model.

Scores (1 = bad, 5 = excellent):
- naturalness: does it sound like a person?
- pronunciation: are all words, numbers, dates and abbreviations read correctly?
- prosody: are stress, pauses and intonation correct?
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
AUDIO = BENCH_DIR / "results" / "audio"
OUT = BENCH_DIR / "results" / "listening"
DEFAULT_TEXTS = "S1,M1,M2,M3,M4,M5,M6,M7,M8,L1"
# int8-torchao has the same weights as int8-torch.ao, and bass-high is too slow
# for interactive use on the reference machine, so they are not in the default kit.
DEFAULT_EXCLUDE = "int8-torchao,bass-high"
SCORES = ("naturalness", "pronunciation", "prosody")


def make(texts: list[str], variant: str, seed: int, exclude: list[str]) -> int:
    corpus = {i["id"]: i for i in json.loads((BENCH_DIR / "corpus.json").read_text(encoding="utf-8"))["items"]}
    files = []
    for target_dir in sorted(p for p in AUDIO.iterdir() if p.is_dir()):
        if any(x and x in target_dir.name for x in exclude):
            continue
        for tid in texts:
            v = variant
            if variant == "pipeline":
                # The form that a daemon with a normalizer sends to the engine.
                v = "normalized" if corpus[tid].get("normalized") else "raw"
            wav = target_dir / f"{tid}_{v}.wav"
            if wav.exists():
                files.append((target_dir.name, tid, v, wav))
    if not files:
        print(f"No WAV files in {AUDIO}. Run the benchmark first.")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rng = random.Random(seed)
    rng.shuffle(files)
    key, rows = {}, []
    for n, (target, tid, v, wav) in enumerate(files, 1):
        name = f"{n:03d}_{rng.getrandbits(24):06x}.wav"
        shutil.copy2(wav, OUT / name)
        key[name] = {"target": target, "text_id": tid, "variant": v}
        rows.append({"file": name, "text": corpus[tid][v], **{s: "" for s in SCORES}, "comment": ""})
    (OUT / "key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    with (OUT / "ratings.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "text", *SCORES, "comment"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} files, ratings.csv and key.json to {OUT}")
    return 0


def score() -> int:
    key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))
    per: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    with (OUT / "ratings.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for s in SCORES:
                if row[s].strip():
                    per[key[row["file"]]["target"]][s].append(float(row[s]))
    print("| Target | " + " | ".join(f"{s} (mean, n)" for s in SCORES) + " |")
    print("|---|" + "---:|" * len(SCORES))
    for target in sorted(per):
        cells = [f"{statistics.fmean(v):.2f} ({len(v)})" if (v := per[target][s]) else "–" for s in SCORES]
        print(f"| {target} | " + " | ".join(cells) + " |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--texts", default=DEFAULT_TEXTS, help=f"Comma-separated corpus ids. Default: {DEFAULT_TEXTS}")
    parser.add_argument("--variant", choices=["pipeline", "raw", "normalized"], default="pipeline",
                        help="pipeline (default): the normalized form if it exists, else the raw form.")
    parser.add_argument("--exclude", default=DEFAULT_EXCLUDE,
                        help=f"Comma-separated substrings of target names to leave out. Default: {DEFAULT_EXCLUDE}. Use '' for all.")
    parser.add_argument("--seed", type=int, default=None, help="Seed for the random order. Default: random.")
    parser.add_argument("--score", action="store_true", help="Read ratings.csv and print mean scores per model.")
    args = parser.parse_args()
    if args.score:
        return score()
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**31)
    return make(args.texts.split(","), args.variant, seed, args.exclude.split(","))


if __name__ == "__main__":
    sys.exit(main())
