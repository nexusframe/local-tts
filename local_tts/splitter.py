"""Split text into sentences, so that the first sentence is synthesized first."""

from __future__ import annotations

import re

# A sentence ends at . ! ? or …, then whitespace, then an uppercase letter,
# a digit or a quotation mark.
_CANDIDATE = re.compile(r"[.!?…]+\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9\"„«])")

# Abbreviations that can stand before an uppercase word inside a sentence.
_ABBREVIATIONS = frozenset({"np", "m.in", "dr", "ul", "tzn", "tj", "tel", "inż", "prof", "hab", "godz", "tys"})

# "ok." is an abbreviation only before a number (the normalizer gives "około").
_OK_BEFORE_NUMBER = re.compile(r"(?<![\w.])[Oo]k\.\s+\d")

_LAST_WORD = re.compile(r"(\S+)$")

# A comma between words, not inside a number like 3,5.
_COMMA = re.compile(r",\s")
_COMPLETE_WORD = re.compile(r"\S+(?=\s)")
_PLAIN_WORD = re.compile(r"[^\W\d_]+")


def _ends_with_abbreviation(head: str) -> bool:
    match = _LAST_WORD.search(head)
    return bool(match) and match.group(1).rstrip(".").lower() in _ABBREVIATIONS


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    sentences: list[str] = []
    start = 0
    for match in _CANDIDATE.finditer(text):
        end = match.start() + len(match.group().rstrip())
        if _ends_with_abbreviation(text[start:end]) or _OK_BEFORE_NUMBER.match(text, end - 3):
            continue
        sentences.append(text[start:end])
        start = match.end()
    if text[start:]:
        sentences.append(text[start:])
    return sentences


class SentenceStream:
    """Split text that comes in pieces, for example tokens from an LLM.

    feed() gives the sentences that are complete. A sentence is complete when
    the next sentence starts, because split_sentences() needs the first
    character of the next sentence. flush() gives the rest at the end.

    With early_first, the first segment can be a part of the first sentence,
    so that synthesis starts before the LLM completes the sentence.
    """

    def __init__(self, early_first: bool = True, first_words: int = 6) -> None:
        self._waiting_first = early_first
        self._first_words = first_words
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        segments = self._complete_sentences()
        if self._waiting_first and not segments:
            segments = self._early_first_segment()
        if segments:
            self._waiting_first = False
        return segments

    def _early_first_segment(self) -> list[str]:
        comma = _COMMA.search(self._buffer)
        if comma is not None:
            return [self._cut(comma.start() + 1)]
        # Words with whitespace after them. The last word can still grow.
        words = list(_COMPLETE_WORD.finditer(self._buffer))
        for before, after in zip(words[self._first_words - 1 :], words[self._first_words :]):
            # The normalizer reads numbers and abbreviations with the words
            # next to them, so cut only between two plain words.
            if _PLAIN_WORD.fullmatch(before.group()) and _PLAIN_WORD.fullmatch(after.group()):
                return [self._cut(before.end())]
        return []

    def _cut(self, position: int) -> str:
        head, self._buffer = self._buffer[:position], self._buffer[position:]
        return head.strip()

    def _complete_sentences(self) -> list[str]:
        sentences = split_sentences(self._buffer)
        if len(sentences) < 2:
            return []
        # The last sentence can still grow. Keep it and its trailing whitespace.
        self._buffer = sentences[-1] + self._buffer[len(self._buffer.rstrip()):]
        return sentences[:-1]

    def flush(self) -> list[str]:
        sentences = split_sentences(self._buffer)
        self._buffer = ""
        return sentences
