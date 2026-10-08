"""Amounts with a unit, a currency or a percent sign: 45 km/h, 5,99 zł, 3,5 mln zł, 30%."""

from __future__ import annotations

import re
from dataclasses import dataclass

from local_tts.normalizer.grammar import case_after, previous_word
from local_tts.normalizer.numbers import cardinal, plural_form, scale_word
from local_tts.normalizer.numerals import NUMBER_PATTERN, number_words, parse_int


@dataclass(frozen=True)
class Unit:
    gender: str
    one: str
    few: str
    many: str  # Also the genitive plural.
    gen_one: str
    suffix: str = ""

    def form(self, value: int, case: str, fraction: bool = False, scaled: bool = False) -> str:
        """The noun form after a number with this value, in this case."""
        if fraction:
            word = self.gen_one
        elif scaled:
            word = self.many
        elif case in ("nom", "acc"):
            word = {"one": self.one, "few": self.few, "many": self.many}[plural_form(abs(value))]
        else:
            # Only genitive forms are stored. Other cases use them too (simplification).
            word = self.gen_one if abs(value) == 1 else self.many
        return word + self.suffix


ZLOTY = Unit("m", "złoty", "złote", "złotych", "złotego")
GROSZ = Unit("m", "grosz", "grosze", "groszy", "grosza")

UNITS: dict[str, Unit] = {
    "zł": ZLOTY,
    "PLN": ZLOTY,
    "gr": GROSZ,
    "€": Unit("n", "euro", "euro", "euro", "euro"),
    "EUR": Unit("n", "euro", "euro", "euro", "euro"),
    "USD": Unit("m", "dolar", "dolary", "dolarów", "dolara"),
    "%": Unit("m", "procent", "procent", "procent", "procent"),
    "°C": Unit("m", "stopień", "stopnie", "stopni", "stopnia", " Celsjusza"),
    "km/h": Unit("m", "kilometr", "kilometry", "kilometrów", "kilometra", " na godzinę"),
    "km": Unit("m", "kilometr", "kilometry", "kilometrów", "kilometra"),
    "cm": Unit("m", "centymetr", "centymetry", "centymetrów", "centymetra"),
    "mm": Unit("m", "milimetr", "milimetry", "milimetrów", "milimetra"),
    "m": Unit("m", "metr", "metry", "metrów", "metra"),
    "kg": Unit("m", "kilogram", "kilogramy", "kilogramów", "kilograma"),
    "g": Unit("m", "gram", "gramy", "gramów", "grama"),
    "l": Unit("m", "litr", "litry", "litrów", "litra"),
    "min": Unit("f", "minuta", "minuty", "minut", "minuty"),
    "h": Unit("f", "godzina", "godziny", "godzin", "godziny"),
    "s": Unit("f", "sekunda", "sekundy", "sekund", "sekundy"),
    "GB": Unit("m", "gigabajt", "gigabajty", "gigabajtów", "gigabajta"),
    "MB": Unit("m", "megabajt", "megabajty", "megabajtów", "megabajta"),
}
DOLLAR = UNITS["USD"]

SCALES = {"tys.": 10**3, "tys": 10**3, "mln": 10**6, "mld": 10**9}

_NUMBER = NUMBER_PATTERN
_UNIT_ALTERNATIVES = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
_AMOUNT = re.compile(
    rf"(?<![\w,.]){_NUMBER}(?:\s?(?P<scale>tys\.|tys|mln|mld))?\s?(?P<unit>{_UNIT_ALTERNATIVES})(?![\w])"
)
_DOLLAR_PREFIX = re.compile(rf"\$\s?{_NUMBER}(?![\w])")


def _amount_words(match: re.Match, unit: Unit, case: str) -> str:
    integer = parse_int(match["int"])
    value = -integer if match["minus"] else integer
    fraction = match["frac"]
    scale = match.groupdict().get("scale")

    if scale:
        scale_value = SCALES[scale]
        if fraction is None and integer == 1:
            count_words = scale_word(1, case, scale_value)
        elif fraction is None:
            count_words = f"{cardinal(value, case)} {scale_word(integer, case, scale_value)}"
        else:
            count_words = f"{number_words(value, fraction, case, 'm')} {scale_word(1, 'gen', scale_value)}"
        return f"{count_words} {unit.form(value, case, scaled=True)}"

    if unit is ZLOTY and fraction is not None and len(fraction) in (1, 2):
        fraction = fraction.ljust(2, "0")
        parts = []
        if integer:
            parts.append(f"{cardinal(value, case, unit.gender)} {unit.form(value, case)}")
        grosze = int(fraction)
        if grosze or not integer:
            parts.append(f"{cardinal(grosze, case, GROSZ.gender)} {GROSZ.form(grosze, case)}")
        return " ".join(parts)

    words = number_words(value, fraction, case, unit.gender)
    return f"{words} {unit.form(value, case, fraction=fraction is not None)}"


def units(text: str) -> str:
    def replace(match: re.Match) -> str:
        case = case_after(previous_word(text, match.start()), None)
        return _amount_words(match, UNITS[match["unit"]], case)

    def replace_dollar(match: re.Match) -> str:
        case = case_after(previous_word(text, match.start()), None)
        return _amount_words(match, DOLLAR, case)

    text = _AMOUNT.sub(replace, text)
    return _DOLLAR_PREFIX.sub(replace_dollar, text)
