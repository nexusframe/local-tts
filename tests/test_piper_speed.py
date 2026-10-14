"""Speech rate of a real Piper voice (length_scale).

Skipped when the model is not downloaded.
"""

import numpy as np
import pytest

from local_tts.config import DEFAULT_MODELS_DIR

NAME = "en_US-hfc_female-medium"
MODEL = DEFAULT_MODELS_DIR / NAME / f"{NAME}.onnx"
TEXT = (
    "Good morning. The forecast for today is fifteen to twenty degrees Celsius, "
    "with light rain in the afternoon. I have pushed the commit and the tests pass."
)
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="Piper model not found")


def seconds(backend, text=TEXT, **kwargs):
    return len(np.concatenate(list(backend.synthesize(text, **kwargs)))) / backend.sample_rate


def test_larger_length_scale_gives_slower_speech():
    from local_tts.backends.piper import PiperBackend

    # Measured with this text: 8.4 s at 1.0, 9.9 s at 1.3 (+18 %). VITS adds noise to durations.
    normal = seconds(PiperBackend(MODEL, threads=1))
    slow = seconds(PiperBackend(MODEL, threads=1, length_scale=1.3))
    assert slow > normal * 1.1


def test_load_voices_gives_each_model_its_rate():
    from local_tts.__main__ import load_voices

    models = {"woman": NAME, "man": "en_US-bryce-medium", "pl": "pl_PL-zenski_wg_glos-medium"}
    if not all((DEFAULT_MODELS_DIR / m / f"{m}.onnx").exists() for m in models.values()):
        pytest.skip("Piper models not found")
    backends = load_voices(DEFAULT_MODELS_DIR, models, threads=1, fix_trz=True)
    # Listening test picks (docs/voices.md).
    assert {name: b.length_scale for name, b in backends.items()} == {"woman": 1.3, "man": 0.85, "pl": 1.0}


def test_speed_of_a_request_divides_the_length_scale_of_the_voice():
    from local_tts.backends.piper import PiperBackend

    # 1.3 / 0.7 = 1.86: much slower than the rate of the voice. VITS adds noise to durations.
    backend = PiperBackend(MODEL, threads=1, length_scale=1.3)
    normal = seconds(backend)
    assert seconds(backend, speed=0.7) > normal * 1.2
    assert seconds(backend, speed=1.5) < normal / 1.15
    assert seconds(backend, word_ends=[], speed=0.7) > normal * 1.2
