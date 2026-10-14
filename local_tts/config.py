"""Default paths."""

from __future__ import annotations

import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
# M1 uses the Piper models that bench/fetch_models.py downloaded.
DEFAULT_MODELS_DIR = REPO_DIR / "bench" / "models" / "piper"
# Copies of the models with the phoneme alignment output (scripts/patch_alignment.py).
ALIGNED_MODELS_DIR = REPO_DIR / "bench" / "models" / "piper-aligned"
# The first voice is the default voice. Listening test picks: docs/voices.md.
DEFAULT_VOICES = {
    "zenski": "pl_PL-zenski_wg_glos-medium",
    "jarvis": "pl_PL-jarvis_wg_glos-medium",
    "en_hfc_female": "en_US-hfc_female-medium",
    "en_cori": "en_GB-cori-medium",
    "en_bryce": "en_US-bryce-medium",
    "en_hfc_male": "en_US-hfc_male-medium",
}
# Piper length_scale for each model: a larger value gives slower speech. Other models use 1.0.
# Listening test picks (docs/voices.md).
LENGTH_SCALES = {
    "en_US-hfc_female-medium": 1.3,
    "en_US-bryce-medium": 0.85,
}


def default_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/local-tts-{os.getuid()}"
    return Path(runtime_dir) / "local-tts.sock"


def default_pronunciation_path() -> Path:
    config_dir = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config_dir) / "local-tts" / "pronunciation.toml"
