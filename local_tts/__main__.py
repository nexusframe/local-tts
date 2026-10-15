"""Start the local TTS daemon."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from pathlib import Path

from local_tts.backends.piper import PiperBackend
from local_tts.config import ALIGNED_MODELS_DIR, DEFAULT_MODELS_DIR, DEFAULT_VOICES, LENGTH_SCALES, default_pronunciation_path, default_socket_path
from local_tts.engine import Engine
from local_tts.player import PwCatPlayer
from local_tts.pronunciation import PronunciationDictionary
from local_tts.server import Server, exit_if_running

log = logging.getLogger("local_tts")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m local_tts", description="Start the local TTS daemon.")
    parser.add_argument("--socket", type=Path, default=default_socket_path(), help="Path of the Unix socket. Default: %(default)s")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR, help="Directory with one subdirectory for each Piper model. Default: %(default)s")
    parser.add_argument(
        "--voice", action="append", metavar="NAME=MODEL",
        help="Load a voice. Use the option one time for each voice. The first voice is the default voice. "
        f"Default: {', '.join(f'{k}={v}' for k, v in DEFAULT_VOICES.items())}",
    )
    parser.add_argument(
        "--aligned-models-dir", type=Path, default=ALIGNED_MODELS_DIR,
        help="Directory with copies of the models that give word times (scripts/patch_alignment.py). "
        "The daemon uses a copy when it exists. Without word times, events have no spoken_partial text. Default: %(default)s",
    )
    parser.add_argument("--threads", type=int, default=4, help="ONNX Runtime intra-op threads for each voice. Default: %(default)s")
    parser.add_argument("--no-trz-fix", action="store_true", help="Do not lengthen the phonemes of \"trz\". Piper then reads \"trzy\" like \"czy\".")
    parser.add_argument(
        "--first-words", type=int, default=2,
        help="For a stream: send the first part of the first sentence to synthesis after this number of words, "
        "if no comma comes first. Default: %(default)s",
    )
    parser.add_argument(
        "--pronunciation", type=Path, default=default_pronunciation_path(),
        help="TOML file with words to replace before the normalizer, one table for each language ([pl], [en]). "
        "The daemon reads the file again when it changes. The file is optional. Default: %(default)s",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug messages.")
    return parser.parse_args()


def load_voices(
    models_dir: Path, voices: dict[str, str], threads: int, fix_trz: bool, aligned_dir: Path | None = None
) -> dict[str, PiperBackend]:
    """Load the voices. A copy of a model in aligned_dir is used first: it gives word times."""
    backends = {}
    for name, model in voices.items():
        start = time.monotonic()
        aligned = aligned_dir / model / f"{model}.onnx" if aligned_dir else None
        path = aligned if aligned and aligned.exists() else models_dir / model / f"{model}.onnx"
        backend = PiperBackend(path, threads=threads, fix_trz=fix_trz, length_scale=LENGTH_SCALES.get(model, 1.0))
        backend.warm_up()
        log.info(
            "voice %s (%s) loaded in %.2f s, length_scale %.2f, word times: %s",
            name, model, time.monotonic() - start, backend.length_scale, "yes" if path == aligned else "no (run scripts/patch_alignment.py)",
        )
        backends[name] = backend
    return backends


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Before the voices load (about 10 s): a second daemon must not take the socket of the first.
    exit_if_running(args.socket)
    voices = dict(v.split("=", 1) for v in args.voice) if args.voice else DEFAULT_VOICES
    backends = load_voices(args.models_dir, voices, args.threads, fix_trz=not args.no_trz_fix, aligned_dir=args.aligned_models_dir)
    default_voice = next(iter(voices))
    pronunciation = PronunciationDictionary(args.pronunciation)
    server = Server(
        lambda on_event: Engine(
            backends, PwCatPlayer(), on_event, default_voice, first_words=args.first_words, pronunciation=pronunciation
        ),
        args.socket,
    )
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
