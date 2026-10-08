"""Clock times: o 14:30, od 8:00 do 16:00, 14:00-15:30."""

from __future__ import annotations

import re

from local_tts.normalizer.grammar import case_after, previous_word
from local_tts.normalizer.numbers import cardinal, ordinal

_TIME = r"(?P<{h}>[01]?\d|2[0-3]):(?P<{m}>[0-5]\d)"
_RANGE = re.compile(rf"(?<![\w:]){_TIME.format(h='h1', m='m1')}\s?[-–]\s?{_TIME.format(h='h2', m='m2')}(?![\w:])")
_SINGLE = re.compile(rf"(?<![\w:]){_TIME.format(h='h', m='m')}(?![\w:])")

# Words before a time that give the case of the hour.
_HOUR_WORD_CASE = {"godzinie": "loc", "godziny": "gen", "godzina": "nom", "godzinę": "acc"}


def time_words(hour: int, minute: int, case: str) -> str:
    # The hour is a feminine ordinal: (godzina) czternasta, o czternastej.
    words = [ordinal(hour, case, "f") if hour else "zero"]
    if minute:
        words.append(f"zero {cardinal(minute)}" if minute < 10 else cardinal(minute))
    return " ".join(words)


def _case_before(text: str, position: int) -> str:
    word = previous_word(text, position)
    if word in _HOUR_WORD_CASE:
        return _HOUR_WORD_CASE[word]
    case = case_after(word, None)
    # "o" with a time takes the locative: o czternastej.
    return "loc" if word == "o" else case


def times(text: str) -> str:
    def replace_range(match: re.Match) -> str:
        start = time_words(int(match["h1"]), int(match["m1"]), "gen")
        end = time_words(int(match["h2"]), int(match["m2"]), "gen")
        return f"od {start} do {end}"

    def replace_single(match: re.Match) -> str:
        return time_words(int(match["h"]), int(match["m"]), _case_before(text, match.start()))

    text = _RANGE.sub(replace_range, text)
    return _SINGLE.sub(replace_single, text)
