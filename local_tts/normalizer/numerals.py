"""Replace plain numbers in text with words."""

from __future__ import annotations

import re

from local_tts.normalizer.grammar import case_after, next_word, previous_word
from local_tts.normalizer.numbers import cardinal

# Noun forms after a number that need a feminine numeral (jedna, dwie).
FEMININE_NOUNS = frozenset(
    "osoba osoby osób minuta minuty minut godzina godziny godzin sekunda sekundy sekund "
    "doba doby dób noc noce nocy sztuka sztuki sztuk strona strony stron rzecz rzeczy "
    "wiadomość wiadomości kobieta kobiety kobiet złotówka złotówki złotówek".split()
)
NEUTER_NOUNS = frozenset("okno okna okien zadanie zadania zadań piętro piętra pięter".split())

# A number: optional minus, digits with optional groups of 3 after a space, optional decimal part.
# The decimal separator is a comma, or a dot (English style) when no second dot follows.
NUMBER_PATTERN = r"(?P<minus>-(?=\d))?(?P<int>\d{1,3}(?: \d{3})+(?!\d)|\d+)(?:[,.](?P<frac>\d+)(?![.,]\d))?"
NUMBER = re.compile(rf"(?<![\w,.]){NUMBER_PATTERN}(?![\w])")
_DIGITS = re.compile(r"\d+")


def gender_of(noun: str | None) -> str:
    if noun is None:
        return "m"
    noun = noun.lower()
    if noun in FEMININE_NOUNS:
        return "f"
    if noun in NEUTER_NOUNS:
        return "n"
    return "m"


def number_words(integer: int, fraction: str | None, case: str = "nom", gender: str = "m") -> str:
    if fraction is None:
        return cardinal(integer, case, gender)
    if fraction == "5":
        if integer == 1:
            return "półtorej" if gender == "f" else "półtora"
        return f"{cardinal(integer, case, 'm')} i pół"
    leading_zeros = len(fraction) - len(fraction.lstrip("0"))
    words = [cardinal(integer, case, "m"), "przecinek"] + ["zero"] * leading_zeros
    if fraction.lstrip("0"):
        words.append(cardinal(int(fraction)))
    return " ".join(words)


def parse_int(text: str) -> int:
    return int(text.replace(" ", ""))


def numerals(text: str) -> str:
    def replace(match: re.Match) -> str:
        value = parse_int(match["int"])
        if match["minus"]:
            value = -value
        noun = next_word(text, match.end())
        case = case_after(previous_word(text, match.start()), noun)
        return number_words(value, match["frac"], case, gender_of(noun))

    return NUMBER.sub(replace, text)


def leftover_digits(text: str) -> str:
    """Last step: read every digit sequence that no other rule changed, so no digit reaches the engine."""
    return _DIGITS.sub(lambda m: cardinal(int(m.group())), text)
