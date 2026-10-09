"""M4 listening test: does the early first segment of a stream break the intonation?

Run: .venv/bin/python scripts/listen_m4.py
Each sentence plays in 3 versions in random order: the full sentence (as speak),
and streams with --first-words 3 and 2. The segments play without a pause, as
in the daemon when synthesis is ahead of playback. For each version, write a
score from 1 (broken) to 5 (natural). The key goes to bench/results/m4/listen_key.json.
"""
import json, random, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR
from local_tts.normalizer import normalize
from local_tts.player import PwCatPlayer
from local_tts.splitter import SentenceStream, split_sentences

corpus = {i["id"]: i for i in json.load(open(REPO / "bench" / "corpus.json"))["items"]}
texts = [("M1", corpus["M1"]["raw"]), ("M3", corpus["M3"]["raw"]), ("M5", corpus["M5"]["raw"]),
         ("X1", "Jutro w Warszawie będzie słonecznie przez cały dzień."),
         ("X2", "Przypomnienie o spotkaniu z dentystą ustawiłem na piątek.")]
model = "pl_PL-zenski_wg_glos-medium"
voice = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx")
player = PwCatPlayer()
rng = random.Random(); key = {}


def segments(text: str, first_words: int | None) -> list[str]:
    if first_words is None:
        return [text]
    stream = SentenceStream(first_words=first_words)
    return [s for char in text for s in stream.feed(char)] + stream.flush()


def say(text_segments: list[str]) -> None:
    for segment in text_segments:
        for sentence in split_sentences(normalize(segment)):
            for chunk in voice.synthesize(sentence):
                player.write(chunk, voice.sample_rate)
    player.drain()


for number, (item_id, raw) in enumerate(texts, 1):
    versions = [("full", None), ("fw3", 3), ("fw2", 2)]
    rng.shuffle(versions)
    key[f"zdanie {number}"] = {"id": item_id, **{label: name for label, (name, _) in zip("ABC", versions)},
                               "segments": {name: segments(raw, n) for name, n in versions}}
    for label, (_, first_words) in zip("ABC", versions):
        say([f"Zdanie {number}, wersja {label}."])
        time.sleep(0.4)
        say(segments(raw, first_words))
        time.sleep(1.0)
    time.sleep(2.0)
out = REPO / "bench" / "results" / "m4" / "listen_key.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(key, indent=1, ensure_ascii=False))
print("done")
