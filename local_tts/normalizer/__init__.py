"""Polish text normalizer: written text to a form that a TTS engine reads correctly."""

from __future__ import annotations

from local_tts.normalizer.abbreviations import abbreviations
from local_tts.normalizer.cleanup import cleanup
from local_tts.normalizer.dates import dates
from local_tts.normalizer.numerals import leftover_digits, numerals
from local_tts.normalizer.punctuation import punctuation
from local_tts.normalizer.times import times
from local_tts.normalizer.units import units


def normalize(text: str) -> str:
    text = cleanup(text)
    text = abbreviations(text)
    text = dates(text)
    text = times(text)
    text = units(text)
    text = numerals(text)
    text = leftover_digits(text)
    # Last: the unit step needs "km/h" before the slash rule changes it.
    text = punctuation(text)
    return text
