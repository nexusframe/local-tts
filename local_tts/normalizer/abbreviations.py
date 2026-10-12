"""Expand Polish abbreviations. Some forms depend on the word before them."""

from __future__ import annotations

import re

from local_tts.normalizer.grammar import previous_word

ABBREVIATIONS = {
    "np.": "na przykład",
    "m.in.": "między innymi",
    "tzn.": "to znaczy",
    "tj.": "to jest",
    "itd.": "i tak dalej",
    "itp.": "i tym podobne",
    "dr": "doktor",
    "hab.": "habilitowany",
    "prof.": "profesor",
    "mgr": "magister",
    "inż.": "inżynier",
    "nr": "numer",
    "wg": "według",
    "tel.": "telefon",
}
# Abbreviations that often end a sentence: their period stays as the sentence end.
_SENTENCE_FINAL = frozenset({"itd.", "itp."})

# Forms that depend on the preposition before the abbreviation.
_CONTEXT_FORMS = {
    "ul.": ({"z", "ze", "na", "przy", "od", "do", "u"}, "ulicy", "ulica"),
    "godz.": ({"o"}, "godzinie", "godzina"),
}

_KEYS = sorted([*ABBREVIATIONS, *_CONTEXT_FORMS], key=len, reverse=True)
_PATTERN = re.compile(r"(?<![\w.])(" + "|".join(re.escape(k) for k in _KEYS) + r")(?![\w])", re.IGNORECASE)
# "ok." is also the English "ok". Expand it only before a number.
_OK = re.compile(r"(?<![\w.])([Oo])k\.(?=\s?\d)")
# Other "ok"/"OK" is "okej". espeak-ng reads "ok" as "około" (listening test 2026-10-12).
_OKAY = re.compile(r"(?<![\w.'’])([Oo])[Kk](?![\w'’])")
_SENTENCE_END_BEFORE = re.compile(r"(?:^|[.!?…])\s*$")
_SENTENCE_STARTS = re.compile(r"\s*(?:$|[A-ZĄĆĘŁŃÓŚŹŻ])")


def _at_sentence_start(text: str, position: int) -> bool:
    # The splitter needs an uppercase letter after a sentence end.
    return bool(_SENTENCE_END_BEFORE.search(text, 0, position))


def _match_case(source: str, expansion: str) -> str:
    return expansion[0].upper() + expansion[1:] if source[0].isupper() else expansion


def abbreviations(text: str) -> str:
    def replace(match: re.Match) -> str:
        source = match.group(1)
        key = source.lower()
        if key in _CONTEXT_FORMS:
            prepositions, after_preposition, default = _CONTEXT_FORMS[key]
            expansion = after_preposition if previous_word(text, match.start()) in prepositions else default
        else:
            expansion = ABBREVIATIONS[key]
        if key in _SENTENCE_FINAL and _SENTENCE_STARTS.match(text, match.end()):
            expansion += "."
        return _match_case(source, expansion)

    text = _OK.sub(lambda m: "około" if m.group(1) == "o" else "Około", text)
    text = _OKAY.sub(lambda m: "Okej" if m.group()[0] == "O" and _at_sentence_start(text, m.start()) else "okej", text)
    return _PATTERN.sub(replace, text)
