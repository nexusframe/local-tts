"""Listening samples: English ranges, units and currency, before and after english_units().

Run: .venv/bin/python scripts/listen_en_units.py
"before" is normalize_english() without english_units(). "after" is the daemon path
(normalize_english, split_sentences, PiperBackend.synthesize).
The WAV files go to bench/results/audio/en_units/<voice>_<before|after>.wav (not in git).
"""
import sys, wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR, DEFAULT_VOICES
from local_tts.normalizer import normalize_english
from local_tts.normalizer.cleanup import cleanup
from local_tts.normalizer.english import remove_tags
from local_tts.normalizer.punctuation import punctuation
from local_tts.splitter import split_sentences

VOICES = ["en_hfc_female", "en_bryce"]
TEXT = (
    "Tomorrow it will be 15-20°C, and on Friday about 1 °C. "
    "The shop is 5 km away, and the speed limit is 50 km/h. "
    "The tickets cost $5-10, or €12 at the door. "
    "Take 1 kg of flour and 250 ml of milk. "
    "The meeting is on 2026-10-13, from 9-11."
)
OUT = REPO / "bench" / "results" / "audio" / "en_units"
OUT.mkdir(parents=True, exist_ok=True)


def before(text: str) -> str:
    return punctuation(cleanup(remove_tags(text), polish=False))


for name, normalize_text in (("before", before), ("after", normalize_english)):
    print(f"{name}: {normalize_text(TEXT)}")
for voice in VOICES:
    model = DEFAULT_VOICES[voice]
    backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx", fix_trz=False)
    for name, normalize_text in (("before", before), ("after", normalize_english)):
        sentences = split_sentences(normalize_text(TEXT))
        audio = np.concatenate([c for s in sentences for c in backend.synthesize(s)])
        with wave.open(str(OUT / f"{voice}_{name}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(backend.sample_rate)
            w.writeframes(audio.astype(np.int16).tobytes())
        print(f"{voice:14} {name:6} {len(audio) / backend.sample_rate:5.1f} s")
print(f"done: {OUT}")
