"""normalize() must never raise, and it must not leave digits for the TTS engine."""

import random

import pytest

from local_tts.normalizer import normalize

PIECES = [
    "o", "do", "od", "z", "w", "na", "jest", "kosztuje", "ok.", "godz.", "r.", "zł", "km/h", "%", "°C", "mln", "tys.",
    "-", "—", ":", ".", ",", ";", "(", ")", "[pauza]", "**", "`", "osoby", "minut", "maja", "Ala",
]
NUMBERS = ["0", "1", "07", "25:99", "23:59", "32.13.2026", "31.12.9999", "3000 r.", "2000 r.", "1900 r.",
           "10000000000000", "999999999999", "0,000", "12,345", "1 234 567 890", "3.5", "-0", "00:00",
           "2026-13-45", "2026-02-30", "15.11", "99.99", "1,5 mln zł", "0,5 zł", "100,00 zł", "$0", "1e10"]


def random_text(rng: random.Random) -> str:
    parts = [rng.choice(PIECES + NUMBERS) for _ in range(rng.randint(1, 12))]
    return " ".join(parts)


@pytest.mark.parametrize("seed", range(300))
def test_random_text_gives_words_without_digits(seed):
    rng = random.Random(seed)
    text = random_text(rng)
    result = normalize(text)
    assert not any(ch.isdigit() for ch in result), (text, result)
