"""Word end times from the phoneme alignments of a real Piper voice.

Skipped when the models are not downloaded or not patched (scripts/patch_alignment.py).
"""

import numpy as np
import pytest

from local_tts.config import ALIGNED_MODELS_DIR, DEFAULT_MODELS_DIR

NAME = "pl_PL-zenski_wg_glos-medium"
ALIGNED = ALIGNED_MODELS_DIR / NAME / f"{NAME}.onnx"
ORIGINAL = DEFAULT_MODELS_DIR / NAME / f"{NAME}.onnx"
pytestmark = pytest.mark.skipif(not ALIGNED.exists(), reason="patched Piper model not found")


@pytest.fixture(scope="module")
def backend():
    from local_tts.backends.piper import PiperBackend

    return PiperBackend(ALIGNED, threads=1)


def synthesize(backend, text):
    word_ends: list[float] = []
    audio = np.concatenate(list(backend.synthesize(text, word_ends=word_ends)))
    return len(audio) / backend.sample_rate, word_ends


def synthesize_with_reference(backend, text):
    """Word ends, and an independent reference from the same synthesis run (VITS adds noise,
    so two runs have different times): the end of the last sound phoneme before each space
    phoneme (a comma pause is after the word)."""
    chunks = []
    synthesize_voice = backend._voice.synthesize

    def spy(*args, **kwargs):
        for chunk in synthesize_voice(*args, **kwargs):
            chunks.append(chunk)
            yield chunk

    backend._voice.synthesize = spy
    try:
        _, word_ends = synthesize(backend, text)
    finally:
        backend._voice.synthesize = synthesize_voice
    reference, samples, sound_end = [], 0, 0
    for alignment in chunks[0].phoneme_alignments:
        samples += alignment.num_samples
        if alignment.phoneme == " ":
            reference.append(sound_end / backend.sample_rate)
        elif alignment.phoneme.isalpha() or alignment.phoneme in "ːʰʲ":
            sound_end = samples
    return word_ends, reference


def test_each_word_has_an_end_time_in_the_audio(backend):
    duration, word_ends = synthesize(backend, "Jutro będzie bardzo ciepło i słonecznie.")
    assert len(word_ends) == 6
    assert word_ends == sorted(word_ends)
    assert 0 < word_ends[0] and word_ends[-1] <= duration


def test_word_ends_agree_with_the_space_phonemes_of_the_alignment(backend):
    word_ends, reference = synthesize_with_reference(backend, "Jutro będzie bardzo ciepło i słonecznie.")
    # The last word ends at the end of its phonemes, not at a space.
    assert word_ends[:-1] == pytest.approx(reference, abs=0.001)


def test_numbers_and_english_spans_keep_one_time_for_each_word(backend):
    _, word_ends = synthesize(backend, "Zrobiłem <en>commit</en> o dwunastej trzydzieści.")
    assert len(word_ends) == 5
    assert word_ends == sorted(word_ends)


@pytest.mark.skipif(not ORIGINAL.exists(), reason="Piper model not downloaded")
def test_model_without_alignment_output_gives_no_word_ends():
    from local_tts.backends.piper import PiperBackend

    duration, word_ends = synthesize(PiperBackend(ORIGINAL, threads=1), "Jutro będzie ciepło.")
    assert duration > 0
    assert word_ends == []


def test_word_ends_are_ready_when_the_last_chunk_comes(backend):
    word_ends: list[float] = []
    lengths_at_chunk = [len(word_ends) for _ in backend.synthesize("Jutro będzie ciepło.", word_ends=word_ends)]
    assert lengths_at_chunk[-1] == 3
