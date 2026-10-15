"""Piper backend (package piper-tts).

The backend makes the ONNX Runtime session itself, because PiperVoice.load()
gives no control of the thread count. M0 measured 4 intra-op threads as the
fastest configuration on 4 physical cores.
"""

from __future__ import annotations

import json
import threading
import unicodedata
from pathlib import Path
from typing import Iterator

import numpy as np
import onnxruntime as ort
from piper import PiperVoice, SynthesisConfig
from piper.config import PiperConfig
from piper.phonemize_espeak import EspeakPhonemizer
# piper-tts uses this lock for its espeak-ng calls. espeak-ng has one global state,
# so English calls take the same lock. Private name: piper-tts is pinned to 1.8.0.
from piper.voice import _ESPEAK_PHONEMIZER_LOCK

from local_tts.backends.phonemes import (
    fix_dz as _fix_dz,
    lengthen_trz,
    phonemize_mixed,
    stress_before_g,
    to_polish_phonemes,
)

_english_espeak: EspeakPhonemizer | None = None
# Phonemes that are not a sound of a word: space, stress, punctuation, and the
# begin, end and pad symbols of Piper.
_SILENT = frozenset(" ˈˌ^$_.,;:!?…—–-\"'()[]«»„”")
# Marks that change the sound before them. espeak-ng can add them only in the full
# sentence ("ciepło i" is "tɕˈɛpwɔː i"), so they do not count as a sound.
_MODIFIERS = frozenset("ːˑʰʲʷ")


def _modifies(phoneme: str) -> bool:
    return phoneme in _MODIFIERS or unicodedata.combining(phoneme[0]) > 0


def _english_phonemes(text: str) -> list[list[str]]:
    """English text (an <en> span) to phonemes that the Polish voices know."""
    global _english_espeak
    with _ESPEAK_PHONEMIZER_LOCK:
        if _english_espeak is None:
            _english_espeak = EspeakPhonemizer()
        sentences = _english_espeak.phonemize("en-us", text)
    return [list(to_polish_phonemes("".join(s))) for s in sentences]


class _InterruptibleSession:
    """ONNX Runtime session that interrupt() can stop during run().

    PiperVoice calls session.run() without RunOptions. This wrapper gives each
    run its own RunOptions, so that terminate stops only the current run.
    M4 spike: terminate stops a 571 ms run in median 2 ms, maximum 87 ms.
    """

    def __init__(self, session: ort.InferenceSession) -> None:
        self._session = session
        self._lock = threading.Lock()
        self._run_options: ort.RunOptions | None = None

    def run(self, output_names, input_feed, run_options=None):
        options = ort.RunOptions()
        with self._lock:
            self._run_options = options
        try:
            return self._session.run(output_names, input_feed, options)
        finally:
            with self._lock:
                self._run_options = None

    def interrupt(self) -> None:
        with self._lock:
            if self._run_options is not None:
                self._run_options.terminate = True

    def __getattr__(self, name):
        return getattr(self._session, name)


class PiperBackend:
    def __init__(
        self, model_path: Path, threads: int = 4, fix_trz: bool = True, fix_dz: bool = True, length_scale: float = 1.0
    ) -> None:
        config_path = model_path.with_name(model_path.name + ".json")
        if not model_path.exists() or not config_path.exists():
            raise FileNotFoundError(f"Piper model or config not found: {model_path}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        # The arena keeps the memory of the longest input of each voice (6 voices: 2.0 GB RSS, without: 0.6 GB).
        opts.enable_cpu_mem_arena = False
        self._session = _InterruptibleSession(
            ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        )
        self._voice = PiperVoice(
            config=PiperConfig.from_dict(json.loads(config_path.read_text(encoding="utf-8"))),
            session=self._session,
        )
        self.sample_rate = self._voice.config.sample_rate
        # Speech rate: a larger value gives slower speech. 1.0 is the rate of the model.
        self.length_scale = length_scale
        # "pl" or "en", from the espeak-ng voice of the model ("pl", "en-us", "en-gb-x-rp").
        self.language = self._voice.config.espeak_voice.split("-")[0]
        if self.language == "pl":
            # PiperVoice.synthesize() calls self.phonemize(). Wrap it for this voice only;
            # the audio processing after phonemization stays the same.
            espeak_polish = self._voice.phonemize
            corrections = [c for c, on in ((lengthen_trz, fix_trz), (_fix_dz, fix_dz)) if on] + [stress_before_g]

            def polish(text: str) -> list[list[str]]:
                phonemes = espeak_polish(text)
                for correction in corrections:
                    phonemes = correction(text, phonemes)
                return phonemes

            self._voice.phonemize = lambda text: phonemize_mixed(text, polish, _english_phonemes)

    def phonemize(self, text: str) -> list[list[str]]:
        """The phonemes that synthesize() uses for the text, grouped by sentence."""
        return self._voice.phonemize(text)

    def synthesize(self, text: str, word_ends: list[float] | None = None, speed: float = 1.0) -> Iterator[np.ndarray]:
        """Yield the audio. With word_ends, also add the end time of each word (see Backend)."""
        syn_config = SynthesisConfig(length_scale=self.length_scale / speed)
        if word_ends is None:
            for chunk in self._voice.synthesize(text, syn_config=syn_config):
                yield chunk.audio_int16_array
            return
        # Piper gives one chunk for each espeak-ng sentence, usually one for the text.
        # The next chunk is made before the current one goes out, so that the word
        # ends are ready with the last chunk.
        chunks = self._voice.synthesize(text, syn_config=syn_config, include_alignments=True)
        # End sample of each sound phoneme, from the alignment output of the model.
        sound_ends: list[int] = []
        aligned = True
        samples = 0
        current = next(chunks, None)
        while current is not None:
            following = next(chunks, None)
            if current.phoneme_alignments is None:
                aligned = False  # The model has no alignment output (scripts/patch_alignment.py).
            else:
                end = samples
                for alignment in current.phoneme_alignments:
                    end += alignment.num_samples
                    if _modifies(alignment.phoneme) and sound_ends:
                        sound_ends[-1] = end
                    elif alignment.phoneme not in _SILENT:
                        sound_ends.append(end)
            audio = current.audio_int16_array
            samples += len(audio)
            if following is None and aligned and sound_ends:
                word_ends.extend(s / self.sample_rate for s in self._word_end_samples(text, sound_ends))
            yield audio
            current = following

    def _word_end_samples(self, text: str, sound_ends: list[int]) -> list[int]:
        """The end sample of each word of the text.

        The phonemes of the first k words give the count of sound phonemes up to
        the end of word k. espeak-ng joins some words ("w domu" is one phoneme
        word), so the words of the text and the spaces of the phonemes do not agree.
        """
        words = text.split()
        ends: list[int] = []
        for k in range(1, len(words) + 1):
            prefix = " ".join(words[:k])
            if prefix.count("<en>") > prefix.count("</en>"):
                prefix += "</en>"
            count = sum(
                1 for sentence in self._voice.phonemize(prefix) for p in sentence if p not in _SILENT and not _modifies(p)
            )
            end = sound_ends[min(count, len(sound_ends)) - 1] if count else 0
            ends.append(max(end, ends[-1] if ends else 0))
        return ends

    def interrupt(self) -> None:
        self._session.interrupt()

    def warm_up(self) -> None:
        """Run one short synthesis, so that the first request is not slower than the next ones."""
        for _ in self.synthesize("Test."):
            pass
