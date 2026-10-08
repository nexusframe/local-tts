"""Select the grammatical case of a numeral from the words around it.

The rules use the preposition before the number. Some prepositions take more
than one case; for them the ending of the noun after the number decides.
This covers common phrases only. It is not a full grammar.
"""

from __future__ import annotations

import re

_GENITIVE = frozenset(
    "do od bez około dla koło u według wśród oprócz spośród sprzed zamiast podczas blisko powyżej poniżej".split()
)
_DATIVE = frozenset("dzięki ku przeciw przeciwko wbrew".split())
_INSTRUMENTAL = frozenset("przed nad pod między pomiędzy".split())
_LOCATIVE = frozenset("przy".split())
_ACCUSATIVE = frozenset("za ponad na przez o".split())

_PREV_WORD = re.compile(r"([^\W\d_]+)\s*$")
_NEXT_WORD = re.compile(r"\s*([^\W\d_]+)")


def previous_word(text: str, position: int) -> str | None:
    match = _PREV_WORD.search(text, 0, position)
    return match.group(1).lower() if match else None


def next_word(text: str, position: int) -> str | None:
    match = _NEXT_WORD.match(text, position)
    return match.group(1).lower() if match else None


def _noun_case(noun: str | None) -> str | None:
    if noun is None:
        return None
    if noun.endswith(("ami", "mi")):
        return "ins"
    if noun.endswith(("ach", "ech")):
        return "loc"
    if noun.endswith("om"):
        return "dat"
    return None


def case_after(preposition: str | None, noun: str | None) -> str:
    """Case of a numeral after `preposition` and before `noun`."""
    if preposition in ("z", "ze"):
        return "ins" if _noun_case(noun) == "ins" else "gen"
    if preposition in ("w", "we", "po"):
        return "loc" if _noun_case(noun) == "loc" else "acc"
    if preposition in _GENITIVE:
        return "gen"
    if preposition in _DATIVE:
        return "dat"
    if preposition in _INSTRUMENTAL:
        return "ins"
    if preposition in _LOCATIVE:
        return "loc"
    if preposition in _ACCUSATIVE:
        return "acc"
    return "nom"
