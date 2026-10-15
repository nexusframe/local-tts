"""Memory of a real Piper voice: the ONNX Runtime CPU memory arena is off.

With the arena, each voice kept the memory of its longest input: 6 voices grew to 2.0-2.2 GB RSS.
Without it: 586-592 MB, and no RTF change larger than the noise of the measurement (docs/m5-arena.md).
Skipped when the model is not downloaded.
"""

import pytest

from local_tts.config import DEFAULT_MODELS_DIR

NAME = "pl_PL-zenski_wg_glos-medium"
MODEL = DEFAULT_MODELS_DIR / NAME / f"{NAME}.onnx"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="Piper model not found")


def test_session_has_no_cpu_memory_arena():
    from local_tts.backends.piper import PiperBackend

    backend = PiperBackend(MODEL, threads=1)
    assert backend._session.get_session_options().enable_cpu_mem_arena is False
