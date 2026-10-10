"""Long English listening samples of the English Piper voices.

Run: .venv/bin/python scripts/listen_en_voices.py
The text does not go through the Polish normalizer. Numbers are written as words.
The WAV files go to bench/results/audio/en_voices/<voice>.wav (not in git).
"""
import sys, wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR
from local_tts.splitter import split_sentences

VOICES = ["en_US-lessac", "en_US-amy", "en_US-kristin", "en_US-hfc_female", "en_GB-cori",
          "en_US-joe", "en_US-john", "en_US-bryce", "en_US-hfc_male", "en_GB-alan"]
TEXT = (
    "Good morning! Here is your plan for today. "
    "At half past nine you have a meeting with the team in room three, "
    "and at one o'clock you have lunch with Kate at the Italian place on Main Street. "
    "The weather forecast says it will rain in the afternoon, with a high of fourteen degrees, so take an umbrella. "
    "Your electricity bill is due on Friday, the seventeenth of October. "
    "Yesterday you walked eight thousand steps, which is twelve hundred more than on Monday. "
    "I pushed the latest commit to GitHub, and the pull request is waiting for review. "
    "Would you like me to read the news, or would you prefer to listen to some music? "
    "If anything changes, just tell me, and I will update your calendar."
)
OUT = REPO / "bench" / "results" / "audio" / "en_voices"
OUT.mkdir(parents=True, exist_ok=True)

for voice_name in VOICES:
    model = f"{voice_name}-medium"
    backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx", fix_trz=False)
    audio = np.concatenate([c for s in split_sentences(TEXT) for c in backend.synthesize(s)])
    with wave.open(str(OUT / f"{voice_name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(backend.sample_rate)
        w.writeframes(audio.astype(np.int16).tobytes())
    print(f"{voice_name:18} {len(audio) / backend.sample_rate:5.1f} s")
print(f"done: {OUT}")
