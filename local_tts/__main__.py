"""Start the local TTS daemon."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from pathlib import Path

from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR, DEFAULT_VOICES, default_socket_path
from local_tts.engine import Engine
from local_tts.player import PwCatPlayer
from local_tts.server import Server

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
    parser.add_argument("--threads", type=int, default=4, help="ONNX Runtime intra-op threads for each voice. Default: %(default)s")
    parser.add_argument("--no-trz-fix", action="store_true", help="Do not lengthen the phonemes of \"trz\". Piper then reads \"trzy\" like \"czy\".")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug messages.")
    return parser.parse_args()


def load_voices(models_dir: Path, voices: dict[str, str], threads: int, fix_trz: bool) -> dict[str, PiperBackend]:
    backends = {}
    for name, model in voices.items():
        start = time.monotonic()
        backend = PiperBackend(models_dir / model / f"{model}.onnx", threads=threads, fix_trz=fix_trz)
        backend.warm_up()
        log.info("voice %s (%s) loaded in %.2f s", name, model, time.monotonic() - start)
        backends[name] = backend
    return backends


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    voices = dict(v.split("=", 1) for v in args.voice) if args.voice else DEFAULT_VOICES
    backends = load_voices(args.models_dir, voices, args.threads, fix_trz=not args.no_trz_fix)
    default_voice = next(iter(voices))
    server = Server(lambda on_event: Engine(backends, PwCatPlayer(), on_event, default_voice), args.socket)
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
