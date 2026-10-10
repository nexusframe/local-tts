"""English with Polish voices: raw IPA in [[ ]] blocks instead of Polish espeak phonemes.

Run: .venv/bin/python scripts/listen_ipa.py
Piper reads text in [[ ]] as phonemes and does not send it to espeak.
Variant "ipa": English IPA from espeak en-us. Variant "ipa_pl": the same IPA, with the
English-only phonemes changed to the nearest phonemes that the Polish voices learned.
The text does not go through the normalizer, because the normalizer removes [[ ]] blocks.
The WAV files go to bench/results/audio/male_long/<text>/<voice>.wav (not in git).
"""
import re, sys, wave
from pathlib import Path

import numpy as np
import piper
from piper.phonemize_espeak import EspeakPhonemizer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR

VOICES = ["meski_wg_glos", "jarvis_wg_glos", "darkman", "mc_speech", "zenski_wg_glos"]
OUT = REPO / "bench" / "results" / "audio" / "male_long"
espeak = EspeakPhonemizer(Path(piper.__file__).parent / "espeak-ng-data")

# English-only phonemes -> nearest Polish phonemes. Diphthongs first.
TO_POLISH = [("eɪ", "ɛj"), ("aɪ", "aj"), ("ɔɪ", "ɔj"), ("oʊ", "ɔw"), ("aʊ", "aw"), ("ɚ", "ɛr"),
             ("æ", "ɛ"), ("ð", "d"), ("θ", "f"), ("ɐ", "a"), ("ɑ", "a"), ("ə", "ɛ"), ("ɜ", "ɛ"),
             ("ɪ", "ɨ"), ("ᵻ", "ɨ"), ("ɹ", "r"), ("ɾ", "t"), ("ʊ", "u"), ("ʌ", "a"), ("ː", ""),
             ("h", "x"), ("e", "ɛ"), ("o", "ɔ")]


def to_polish(ipa: str) -> str:
    for src, dst in TO_POLISH:
        ipa = ipa.replace(src, dst)
    return ipa


def en_ipa(text: str) -> str:
    return " ".join("".join(s) for s in espeak.phonemize("en-us", text))


EN_SENTENCES = [
    "Good morning!", "Here is your plan for today.",
    "At half past nine you have a meeting with the team, and at one o'clock you have lunch with Kate.",
    "The weather forecast says it will rain in the afternoon, so take an umbrella.",
    "Your electricity bill is due on Friday.",
    "Would you like me to read the news, or would you prefer to listen to some music?",
]
# English word -> (English text for espeak, Polish inflection ending in IPA).
WORDS = {"commit": ("commit", ""), "pull request": ("pull request", ""), "GitHub": ("GitHub", ""),
         "Pythonie": ("Python", "ɲɛ"), "pipeline": ("pipeline", ""), "CI": ("C I", ""),
         "Deadline": ("deadline", ""), "weekend": ("weekend", ""), "Bluetooth": ("Bluetooth", ""),
         "playlistę": ("playlist", "ɛ"), "Spotify": ("Spotify", ""), "Chill Vibes": ("chill vibes", ""),
         "e-mail": ("email", ""), "Johna": ("John", "a"), "Sarah": ("Sarah", ""),
         "meetingu": ("meeting", "u"), "Google Meet": ("Google Meet", ""), "Linux": ("Linux", ""),
         "backup": ("backup", "")}
PL_SENTENCES = [
    "Zrobiłem {commit} i wysłałem {pull request} na {GitHub}.",
    "Testy w {Pythonie} przeszły, ale {pipeline} w {CI} jeszcze się buduje.",
    "{Deadline} projektu to przyszły {weekend}, więc mamy trochę czasu.",
    "Słuchawki {Bluetooth} są już sparowane ze smartfonem.",
    "Włączam {playlistę} na {Spotify} o nazwie {Chill Vibes}.",
    "Jeśli chcesz, mogę wysłać {e-mail} do {Johna} i {Sarah} z linkiem do {meetingu} na {Google Meet}.",
    "Nowy laptop ma procesor intel i system {Linux}, a {backup} zrobi się w nocy.",
]


def word_ipa(word: str) -> str:
    text, ending = WORDS[word]
    return re.sub(r"[.,!?]", "", en_ipa(text)).strip() + ending


def texts(convert) -> dict[str, list[str]]:
    return {
        "en_only": [f"[[{convert(en_ipa(s))}]]" for s in EN_SENTENCES],
        "pl_with_en_words": [re.sub(r"\{([^}]+)\}", lambda m: f"[[{convert(word_ipa(m.group(1)))}]]", s)
                             for s in PL_SENTENCES],
    }


VARIANTS = {"ipa": texts(lambda ipa: ipa), "ipa_pl": texts(to_polish)}

for voice_name in VOICES:
    model = f"pl_PL-{voice_name}-medium"
    backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx")
    for variant, by_text in VARIANTS.items():
        for text_id, sentences in by_text.items():
            audio = np.concatenate([c for s in sentences for c in backend.synthesize(s)])
            path = OUT / f"{text_id}_{variant}" / f"{voice_name}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(backend.sample_rate)
                w.writeframes(audio.astype(np.int16).tobytes())
            print(f"{voice_name:16} {text_id}_{variant:8} {len(audio) / backend.sample_rate:5.1f} s")
for variant, by_text in VARIANTS.items():
    for text_id, sentences in by_text.items():
        (OUT / f"{text_id}_{variant}" / "input.txt").write_text("\n".join(sentences) + "\n", encoding="utf-8")
print(f"done: {OUT}")
