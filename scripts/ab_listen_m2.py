"""M2 A/B listening test: raw text against normalized text, random order in each pair.

Run: .venv/bin/python scripts/ab_listen_m2.py
The key (which version is A and B) goes to bench/results/m2/ab_key.json.
"""
import json, random, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.normalizer import normalize
from local_tts.player import PwCatPlayer
from local_tts.config import DEFAULT_MODELS_DIR

corpus = {i["id"]: i for i in json.load(open(REPO / "bench" / "corpus.json"))["items"]}
texts = [("M2", corpus["M2"]["raw"]), ("M3", corpus["M3"]["raw"]), ("M4", corpus["M4"]["raw"]),
         ("X1", "Kosztuje 5,99 zł, a rabat wynosi do 30%."), ("X2", "Wrócę za 1,5 godziny, ok. 17:45.")]
model = "pl_PL-zenski_wg_glos-medium"
voice = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx")
player = PwCatPlayer()
rng = random.Random(); key = {}

def say(text):
    for chunk in voice.synthesize(text):
        player.write(chunk, voice.sample_rate)
    player.drain()

for number, (item_id, raw) in enumerate(texts, 1):
    versions = [("raw", raw), ("normalized", normalize(raw))]
    rng.shuffle(versions)
    key[f"para {number}"] = {"id": item_id, "A": versions[0][0], "B": versions[1][0]}
    for label, (_, text) in zip("AB", versions):
        say(normalize(f"Para {number}, wersja {label}."))
        say(text)
    time.sleep(3)
(REPO / "bench" / "results" / "m2" / "ab_key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False))
print("done")
