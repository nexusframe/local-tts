"""Download the benchmark models at pinned revisions and verify sha256.

Uses only the Python standard library, so any Python 3.10+ can run it.
Files go to bench/models/<backend>/<model>/. Existing files with a correct
hash are not downloaded again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
MODELS_DIR = BENCH_DIR / "models"
URL = "https://huggingface.co/{repo}/resolve/{revision}/{path}"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(repo: str, revision: str, rel: str, expected: str | None, dest: Path) -> None:
    if dest.exists() and (expected is None or sha256_of(dest) == expected):
        print(f"ok (cached)  {dest.relative_to(BENCH_DIR)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    url = URL.format(repo=repo, revision=revision, path=rel)
    print(f"download     {url}")
    with urllib.request.urlopen(url) as resp, tmp.open("wb") as out:
        while block := resp.read(1 << 20):
            out.write(block)
    if expected is not None:
        actual = sha256_of(tmp)
        if actual != expected:
            tmp.unlink()
            raise SystemExit(f"sha256 mismatch for {rel}: expected {expected}, got {actual}")
    tmp.rename(dest)
    print(f"ok           {dest.relative_to(BENCH_DIR)}")


def model_dir(backend: str, model: str) -> Path:
    return MODELS_DIR / backend / model.replace("/", "__")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["piper", "pocket", "supertonic"], action="append",
                        help="Download only this backend. You can repeat the option. Default: all.")
    args = parser.parse_args()

    manifest = json.loads((BENCH_DIR / "models.json").read_text(encoding="utf-8"))
    for backend in args.backend or ["piper", "pocket", "supertonic"]:
        for model, spec in manifest[backend].items():
            for rel, expected in spec["files"].items():
                dest = model_dir(backend, model) / Path(rel).name if backend == "piper" else model_dir(backend, model) / rel
                fetch(spec["repo"], spec["revision"], rel, expected, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
