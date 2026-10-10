"""Long listening samples of the male medium voices, with the female primary voice as a reference.

Run: .venv/bin/python scripts/listen_male_voices.py
The text goes through the same steps as in the daemon: normalize, split_sentences, synthesize.
The WAV files go to bench/results/audio/male_long/<text>/<voice>.wav (not in git).
"""
import sys, time, wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.backends.piper import PiperBackend
from local_tts.config import DEFAULT_MODELS_DIR
from local_tts.normalizer import normalize
from local_tts.splitter import split_sentences

VOICES = ["meski_wg_glos", "jarvis_wg_glos", "darkman", "mc_speech", "zenski_wg_glos"]
TEXTS = {
    "pl_long": (
        "Dzień dobry! Oto plan na dzisiaj. O 9:30 masz spotkanie z zespołem w sali numer 3, "
        "a o 13:00 obiad z Katarzyną w restauracji przy ulicy Mickiewicza. "
        "Po południu prognoza pogody zapowiada przelotne opady deszczu i temperaturę około 14 stopni, "
        "więc warto zabrać parasol. Przypominam też, że w piątek, 17 października, mija termin opłacenia rachunku za prąd. "
        "Kwota do zapłaty to 243,50 zł. "
        "Wczoraj przeszedłeś 8 tysięcy kroków, czyli o 1200 więcej niż w poniedziałek. "
        "Czy chcesz, żebym przeczytał najważniejsze wiadomości, czy wolisz posłuchać muzyki? "
        "Szczególnie polecam nową audycję o historii Krakowa, która trwa trzy kwadranse. "
        "Gdyby coś się zmieniło, po prostu mi powiedz, a zaktualizuję kalendarz."
    ),
    "pl_with_en_words": (
        "Zrobiłem commit i wysłałem pull request na GitHub. "
        "Testy w Pythonie przeszły, ale pipeline w CI jeszcze się buduje. "
        "Deadline projektu to przyszły weekend, więc mamy trochę czasu. "
        "Słuchawki Bluetooth są już sparowane ze smartfonem. "
        "Włączam playlistę na Spotify o nazwie Chill Vibes. "
        "Jeśli chcesz, mogę wysłać e-mail do Johna i Sarah z linkiem do meetingu na Google Meet. "
        "Nowy laptop ma procesor Intel i system Linux, a backup zrobi się w nocy."
    ),
    "en_only": (
        "Good morning! Here is your plan for today. "
        "At half past nine you have a meeting with the team, and at one o'clock you have lunch with Kate. "
        "The weather forecast says it will rain in the afternoon, so take an umbrella. "
        "Your electricity bill is due on Friday. "
        "Would you like me to read the news, or would you prefer to listen to some music?"
    ),
    # The same texts as above, with the English words written as a Polish speaker says them.
    "pl_with_en_words_fonet": (
        "Zrobiłem komit i wysłałem pul rikłest na githaba. "
        "Testy w pajtonie przeszły, ale pajplajn w si aj jeszcze się buduje. "
        "Dedlajn projektu to przyszły łikend, więc mamy trochę czasu. "
        "Słuchawki blutuf są już sparowane ze smartfonem. "
        "Włączam plejlistę na spotifaj o nazwie czil wajbs. "
        "Jeśli chcesz, mogę wysłać imejl do Dżona i Sery z linkiem do mitingu na gugl mit. "
        "Nowy laptop ma procesor intel i system linuks, a bekap zrobi się w nocy."
    ),
    "en_only_fonet": (
        "Gud morning! Hir yz jor plen for tudej. "
        "Et haf past najn ju hew a miting łyt de tim, end et łan o klok ju hew lancz łyt Kejt. "
        "De łeder forkast sejz yt łyl rejn yn di afternun, sou tejk an ambrela. "
        "Jor elektrysyty byl yz dju on frajdej. "
        "Łud ju lajk mi tu rid de njuz, or łud ju prifer tu lysen tu sam mjuzyk?"
    ),
}
OUT =REPO / "bench" / "results" / "audio" / "male_long"

for voice_name in VOICES:
    model = f"pl_PL-{voice_name}-medium"
    backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx")
    backend.warm_up()
    for text_id, raw in TEXTS.items():
        start = time.monotonic()
        audio = np.concatenate([chunk for sentence in split_sentences(normalize(raw))
                                for chunk in backend.synthesize(sentence)])
        synth = time.monotonic() - start
        path = OUT / text_id / f"{voice_name}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(backend.sample_rate)
            w.writeframes(audio.astype(np.int16).tobytes())
        length = len(audio) / backend.sample_rate
        print(f"{voice_name:16} {text_id:18} {length:5.1f} s audio, RTF {synth / length:.3f}")
for text_id, raw in TEXTS.items():
    (OUT / text_id / "normalized.txt").write_text(
        "\n".join(split_sentences(normalize(raw))) + "\n", encoding="utf-8")
print(f"done: {OUT}")
