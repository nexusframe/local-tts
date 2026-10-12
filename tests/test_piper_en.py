"""<en>...</en> tags with a real Piper voice. Skipped when the model is not downloaded.

The phonemes are real espeak-ng output of piper-tts 1.8.0: "commit" in en-us is
"kəmˈɪt", "lunch" is "lˈʌntʃ". After the change to Polish phonemes: "kɛmˈɨt", "lˈantʃ".
"""

import pytest

from local_tts.config import DEFAULT_MODELS_DIR

MODEL = DEFAULT_MODELS_DIR / "pl_PL-meski_wg_glos-medium" / "pl_PL-meski_wg_glos-medium.onnx"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="Piper model not downloaded")


@pytest.fixture(scope="module")
def backend():
    from local_tts.backends.piper import PiperBackend

    return PiperBackend(MODEL, threads=1)


def joined(backend, text: str) -> str:
    return "|".join("".join(s) for s in backend.phonemize(text))


def test_english_span_gets_polish_phonemes_of_the_english_word(backend):
    phonemes = joined(backend, "Zrobiłem <en>commit</en>.")
    assert "kɛmˈɨt." in phonemes
    assert "<" not in phonemes and ">" not in phonemes


def test_trz_fix_still_works_next_to_english_tsh(backend):
    phonemes = joined(backend, "Trzy razy <en>lunch</en>.")
    assert phonemes.startswith("tʃʃ")
    assert "lˈantʃ." in phonemes


def test_dz_fix_works_next_to_an_english_span(backend):
    phonemes = joined(backend, "Do widzenia, <en>commit</en> jest w urządzeniu. Dzień dobry.")
    assert "vidzˈɛɲʲa," in phonemes
    assert "ˌuʒɔndzˈɛɲʲu." in phonemes
    assert phonemes.endswith("dʑˈɛɲ dˈɔbrɨ.")


def test_tagged_text_gives_audio(backend):
    audio = list(backend.synthesize("Testy w <en>Python</en>ie przeszły."))
    assert sum(len(chunk) for chunk in audio) > 0.5 * backend.sample_rate


def test_word_with_a_polish_ending_has_polish_stress_and_w_is_not_a_letter_name(backend):
    # Polish stress: the second-to-last syllable of the full word ("pajTOnie", "puSZOwać").
    assert "f pajfˈɛnjɛ." in joined(backend, "Testy w <en>Python</en>ie.")
    assert "kɛmˈɨta" in joined(backend, "Zrobiłem <en>commit</en>a.")
    assert "puʃˈɔvatɕ" in joined(backend, "Trzeba <en>push</en>ować.")


def test_ending_y_is_not_read_as_a_letter_name(backend):
    # Alone, espeak-ng reads "y" as the letter name "ˈiɡrɛk". Found in a real LLM answer.
    assert "kɛmˈɨtɨ tˈutaj." in joined(backend, "Mam <en>commit</en>y tutaj.")
    assert "kɛmˈɨtɨ." in joined(backend, "Mam <en>commit</en>y.")
    assert "kɛmˈɨtɨ, a" in joined(backend, "Mam <en>commit</en>y, a")


EN_MODEL = DEFAULT_MODELS_DIR / "en_GB-alan-medium" / "en_GB-alan-medium.onnx"


@pytest.mark.skipif(not EN_MODEL.exists(), reason="English Piper model not downloaded")
def test_language_comes_from_the_model_and_english_voice_keeps_english_phonemes(backend):
    from local_tts.backends.piper import PiperBackend

    english = PiperBackend(EN_MODEL, threads=1)
    assert (backend.language, english.language) == ("pl", "en")
    # No Polish phoneme map for an English voice: "th" stays θ.
    assert "θ" in "".join(p for s in english.phonemize("Three trees.") for p in s)
