"""Listening samples of <en>...</en> tags, through the same steps as the engine.

Run: .venv/bin/python scripts/listen_en_tags.py
Steps: SentenceStream (the text comes in pieces of 3 characters, as from an LLM),
normalize, split_sentences, PiperBackend.synthesize.
The WAV files go to bench/results/audio/en_tags/<text>/<voice>.wav (not in git).
"""
import sys, wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR
from local_tts.normalizer import normalize
from local_tts.splitter import SentenceStream, split_sentences

VOICES = ["meski_wg_glos", "jarvis_wg_glos", "darkman", "mc_speech", "zenski_wg_glos"]
TEXTS = {
    "pl_with_en_words": (
        "Zrobiłem commit'a i wrzuciłem <en>pull request</en>'a na GitHub'a. "
        "Teraz trzeba to push'ować na serwer. "
        "Testy w <en>Python</en>ie przeszły, ale <en>pipeline</en> w <en>C.I.</en> jeszcze się buduje. "
        "<en>Deadline</en> projektu to przyszły weekend, więc mamy trochę czasu. "
        "Słuchawki <en>Bluetooth</en> są już sparowane ze smartfonem. "
        "Włączam playlistę na Spotify'u o nazwie <en>Chill Vibes</en>. "
        "Jeśli chcesz, mogę wysłać mail'a do John'a i <en>Sarah</en> z linkiem do spotkania na <en>Google Meet</en>. "
        "Nowy laptop ma procesor Intel'a i system <en>Linux</en>, a backup'u nie trzeba robić ręcznie."
    ),
}
OUT = REPO / "bench" / "results" / "audio" / "en_tags"


def engine_sentences(text: str) -> list[str]:
    stream = SentenceStream(first_words=2)
    segments = [s for i in range(0, len(text), 3) for s in stream.feed(text[i : i + 3])] + stream.flush()
    return [sentence for segment in segments for sentence in split_sentences(normalize(segment))]


for voice_name in VOICES:
    model = f"pl_PL-{voice_name}-medium"
    backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx")
    for text_id, text in TEXTS.items():
        sentences = engine_sentences(text)
        audio = np.concatenate([c for s in sentences for c in backend.synthesize(s)])
        path = OUT / text_id / f"{voice_name}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(backend.sample_rate)
            w.writeframes(audio.astype(np.int16).tobytes())
        print(f"{voice_name:16} {text_id:18} {len(audio) / backend.sample_rate:5.1f} s")
        if voice_name == VOICES[0]:
            (OUT / text_id / "segments.txt").write_text(
                "\n".join(f"{s}\n    {''.join(p for ps in backend.phonemize(s) for p in ps)}" for s in sentences) + "\n",
                encoding="utf-8")
print(f"done: {OUT}")
