"""trz phonemes, listening round 2: WAV clips of 2 passages in 3 variants, blind names.

Run: .venv/bin/python scripts/trz_listen_round2.py OUTPUT_DIR
"""
import json, random, sys, wave
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR
from local_tts.splitter import split_sentences
import numpy as np

OUT = Path(sys.argv[1])
model = "pl_PL-zenski_wg_glos-medium"
# fix_trz=False: the script makes the variants itself.
backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx", fix_trz=False); voice = backend._voice
VARIANTS = {"V0 domyślny": ["t", "ʃ"], "V1 długie sz": ["t", "ʃ", "ʃ"], "V3 przydech": ["t", "ʰ", "ʃ"]}
PASSAGES = {
    "P1": "Trzeba przyznać, że Piotr patrzył na to trzeźwo. Trzy razy sprawdzał, czy okno jest zamknięte, "
          "a potem trzymał klucze w trzęsącej się dłoni. Często mówił, że trzydzieści lat pracy nauczyło go cierpliwości.",
    "P2": "Wczoraj o trzeciej po południu zadzwonił mój przyjaciel. Powiedział, że w Trzebini otwierają nowy teatr "
          "i trzeba szybko kupić bilety. Czy pójdziesz z nami? Zostały tylko trzy wolne miejsca w trzecim rzędzie.",
}
stats = {"sentences": 0, "aligned": 0}

import re
_TSH_SPELLING = re.compile(r"trz|cz", re.IGNORECASE)

def sentence_phonemes(sentence, variant):
    ph = [p for s in voice.phonemize(sentence) for p in s]
    joined = "".join(ph)
    spellings = [m.group().lower() for m in _TSH_SPELLING.finditer(sentence)]
    stats["sentences"] += 1
    if joined.count("tʃ") != len(spellings):
        return ph, False
    stats["aligned"] += 1
    parts = joined.split("tʃ")
    out = parts[0]
    for spelling, rest in zip(spellings, parts[1:]):
        out += ("".join(variant) if spelling == "trz" else "tʃ") + rest
    return list(out), True

def synth(text, variant):
    pieces = []
    for sentence in split_sentences(text):
        ph, _ = sentence_phonemes(sentence, variant)
        pieces.append(voice.phoneme_ids_to_audio(voice.phonemes_to_ids(ph)))
        pieces.append(np.zeros(int(0.25 * backend.sample_rate), dtype=np.float32))
    audio = np.concatenate(pieces)
    return (audio * 32767).clip(-32768, 32767).astype(np.int16)

clips = [(p, v) for p in PASSAGES for v in VARIANTS]
random.shuffle(clips)
key = {}
for letter, (p, v) in zip("ABCDEF", clips):
    pcm = synth(PASSAGES[p], VARIANTS[v])
    with wave.open(str(OUT / f"klip_{letter}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(backend.sample_rate); w.writeframes(pcm.tobytes())
    key[letter] = {"passage": p, "variant": v, "seconds": round(len(pcm) / backend.sample_rate, 1)}
(OUT / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1))
print("stats", stats)
print({k: v["seconds"] for k, v in key.items()})
