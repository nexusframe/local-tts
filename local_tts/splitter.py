"""Split text into sentences, so that the first sentence is synthesized first."""

from __future__ import annotations

import re

# A sentence ends at . ! ? or …, then whitespace, then an uppercase letter,
# a digit or a quotation mark.
_CANDIDATE = re.compile(r"[.!?…]+\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9\"„«])")

# Abbreviations that can stand before an uppercase word inside a sentence.
_ABBREVIATIONS = frozenset({"np", "m.in", "dr", "ul", "tzn", "prof", "hab", "godz", "tys"})

_LAST_WORD = re.compile(r"(\S+)$")


def _ends_with_abbreviation(head: str) -> bool:
    match = _LAST_WORD.search(head)
    return bool(match) and match.group(1).rstrip(".").lower() in _ABBREVIATIONS


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    sentences: list[str] = []
    start = 0
    for match in _CANDIDATE.finditer(text):
        end = match.start() + len(match.group().rstrip())
        if _ends_with_abbreviation(text[start:end]):
            continue
        sentences.append(text[start:end])
        start = match.end()
    if text[start:]:
        sentences.append(text[start:])
    return sentences
