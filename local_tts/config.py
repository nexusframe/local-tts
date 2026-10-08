"""Default paths."""

from __future__ import annotations

import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
# M1 uses the Piper models that bench/fetch_models.py downloaded.
DEFAULT_MODELS_DIR = REPO_DIR / "bench" / "models" / "piper"
DEFAULT_VOICES = {
    "zenski": "pl_PL-zenski_wg_glos-medium",
    "gosia": "pl_PL-gosia-medium",
}


def default_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/local-tts-{os.getuid()}"
    return Path(runtime_dir) / "local-tts.sock"
