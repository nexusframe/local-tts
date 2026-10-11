"""Split text into sentences, so that the first sentence is synthesized first."""

from __future__ import annotations

import re

# A sentence ends at . ! ? or …, then whitespace, then an uppercase letter,
# a digit or a quotation mark. A line end before more text is also a boundary,
# because LLM answers (Markdown lists) often have no period at the end of a line.
# An <en> tag (English text, see normalizer/english.py) can stand next to the boundary.
_CANDIDATE = re.compile(r"[.!?…]+(?:</en>)?\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9\"„«]|<en>)|[^\S\n]*\n\s*(?=\S)")

# Abbreviations that can stand before an uppercase word inside a sentence.
_ABBREVIATIONS = frozenset({"np", "m.in", "dr", "ul", "tzn", "tj", "tel", "inż", "prof", "hab", "godz", "tys",
                            # English titles, for the English voices.
                            "mr", "mrs", "ms", "vs"})

# "ok." is an abbreviation only before a number (the normalizer gives "około").
_OK_BEFORE_NUMBER = re.compile(r"(?<![\w.])[Oo]k\.\s+\d")

_LAST_WORD = re.compile(r"(\S+)$")

# The number of a list item, for example "2." in "2. Paella", is not a sentence.
_LIST_NUMBER = re.compile(r"\d+[.)]")

# A comma between words, not inside a number like 3,5.
_COMMA = re.compile(r",\s")
_COMPLETE_WORD = re.compile(r"\S+(?=\s)")
# An apostrophe can stand inside a word: "commit'a" (see normalizer/english.py).
_PLAIN_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")
_TAG = re.compile(r"</?en>")
# A Markdown list item, as in normalizer/cleanup.py.
_LIST_ITEM = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s", re.MULTILINE)
# Prepositions and conjunctions. A pause after them breaks the intonation.
_NO_CUT_AFTER = frozenset({
    "a", "ale", "bez", "czy", "dla", "do", "i", "ku", "lub", "na", "nad", "nie", "o", "od", "oraz",
    "po", "pod", "przed", "przez", "przy", "u", "w", "we", "z", "za", "ze", "że",
})


def _ends_with_abbreviation(head: str) -> bool:
    match = _LAST_WORD.search(head)
    # Markup can stand before the word, for example "**dr.".
    return bool(match) and match.group(1).rstrip(".").lstrip("*_(\"„«").lower() in _ABBREVIATIONS


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    sentences: list[str] = []
    start = 0
    for match in _CANDIDATE.finditer(text):
        end = match.start() + len(match.group().rstrip())
        if "\n" not in match.group() and (
            _ends_with_abbreviation(text[start:end])
            or _OK_BEFORE_NUMBER.match(text, end - 3)
            or _LIST_NUMBER.fullmatch(text, start, end)
        ):
            continue
        sentences.append(text[start:end])
        start = match.end()
    if text[start:]:
        sentences.append(text[start:])
    return _balance_tags(sentences)


def _inside_english(segment: str) -> bool:
    return segment.rfind("<en>") > segment.rfind("</en>")


def _balance_tags(segments: list[str]) -> list[str]:
    """Close an <en> span at the end of a segment and open it again in the next segment.

    The last segment can stay open: in a stream, its text can still grow.
    """
    for i in range(len(segments) - 1):
        if _inside_english(segments[i]):
            segments[i] += "</en>"
            segments[i + 1] = "<en>" + segments[i + 1].lstrip()
    return segments


class SentenceStream:
    """Split text that comes in pieces, for example tokens from an LLM.

    feed() gives the sentences that are complete. A sentence is complete when
    the next sentence starts, because split_sentences() needs the first
    character of the next sentence. flush() gives the rest at the end.

    With early_first, the first segment can be a part of the first sentence,
    so that synthesis starts before the LLM completes the sentence.
    """

    def __init__(self, early_first: bool = True, first_words: int = 2) -> None:
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
        if _LIST_ITEM.search(self._buffer):
            # The normalizer ends each list item with a period. Wait for the sentence end.
            return []
        comma = _COMMA.search(self._buffer)
        if comma is not None:
            return [self._cut(comma.start() + 1)]
        # Words with whitespace after them. The last word can still grow.
        words = list(_COMPLETE_WORD.finditer(self._buffer))
        for before_match, after_match in zip(words[self._first_words - 1 :], words[self._first_words :]):
            # A tag does not change the word ("<en>commit</en>" is a plain word).
            before, after = _TAG.sub("", before_match.group()), _TAG.sub("", after_match.group())
            # The normalizer reads numbers and abbreviations with the words
            # next to them, so cut only between two plain words.
            if (
                _PLAIN_WORD.fullmatch(before)
                and _PLAIN_WORD.fullmatch(after)
                and before.lower() not in _NO_CUT_AFTER
                # An uppercase word continues a name, for example "Agnieszka | Brzezińska".
                and not after[0].isupper()
            ):
                return [self._cut(before_match.end())]
        return []

    def _cut(self, position: int) -> str:
        head, self._buffer = self._buffer[:position], self._buffer[position:]
        head, rest = _balance_tags([head.strip(), self._buffer])
        self._buffer = rest
        return head

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
