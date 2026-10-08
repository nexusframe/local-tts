"""Change punctuation that TTS engines read badly into simple punctuation."""

from __future__ import annotations

import re

_WORD_SLASH = re.compile(r"(?<=[^\W\d_])/(?=[^\W\d_])")
_PARENTHESES = re.compile(r"\s*\(([^()]*)\)\s*")
_DASH = re.compile(r"\s+[—–-]\s+")
_SEMICOLON = re.compile(r";\s*(\w)")


def _parentheses_to_commas(match: re.Match) -> str:
    return f", {match.group(1).strip()}, "


def punctuation(text: str) -> str:
    text = _WORD_SLASH.sub(" ", text)
    # A dash between words is a pause: read it as a comma.
    text = _DASH.sub(", ", text)
    text = _SEMICOLON.sub(lambda m: ". " + m.group(1).upper(), text)
    text = text.replace("…", "...")
    text = _PARENTHESES.sub(_parentheses_to_commas, text)
    text = re.sub(r",\s*([.,;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()
