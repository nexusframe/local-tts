"""Polish text normalizer: written text to a form that a TTS engine reads correctly."""

from __future__ import annotations

from local_tts.normalizer.abbreviations import abbreviations
from local_tts.normalizer.cleanup import cleanup
from local_tts.normalizer.dates import dates
from local_tts.normalizer.english import protect, remove_tags, restore
from local_tts.normalizer.english_units import english_units
from local_tts.normalizer.numerals import leftover_digits, numerals
from local_tts.normalizer.punctuation import punctuation
from local_tts.normalizer.times import times
from local_tts.normalizer.units import units


def normalize(text: str) -> str:
    text, english = protect(text)
    text = cleanup(text)
    text = abbreviations(text)
    text = dates(text)
    text = times(text)
    text = units(text)
    text = numerals(text)
    text = leftover_digits(text)
    # Last: the unit step needs "km/h" before the slash rule changes it.
    text = punctuation(text)
    return restore(text, english)


def normalize_english(text: str) -> str:
    """For an English voice: remove markup and tags, read ranges, units and currency.

    espeak-ng en reads the numbers itself. Ranges go before punctuation(), which
    changes a spaced dash into a comma.
    """
    return punctuation(english_units(cleanup(remove_tags(text), polish=False)))
