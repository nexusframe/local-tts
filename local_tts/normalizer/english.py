"""<en>...</en> tags mark English text. The Polish rules must not change it.

protect() puts one private-use character in place of each span, so that the
Polish steps see no letters or digits there. restore() puts the spans back.
"""

from __future__ import annotations

import re

# An unclosed <en> ends at the end of the text. A </en> without <en> is removed.
_SPAN = re.compile(r"<en>(.*?)(?:</en>|$)", re.DOTALL)
_STRAY_END = "</en>"
_FIRST_PLACEHOLDER = 0xE000
_PLACEHOLDER = "[\uE000-\uF8FF]"
# Polish spelling of an English word with a Polish ending: "commit'a", "push'ować".
# The stem has 2 or more Latin letters, so "o'clock" stays. English contractions stay.
_INFLECTED = re.compile(r"(?<![\w'’])([A-Za-z][A-Za-z0-9]+)['’]([^\W\d_]+)(?![\w'’])")
_CONTRACTIONS = frozenset({"s", "t", "re", "ve", "ll", "d", "m"})
_APOSTROPHE_AFTER_SPAN = re.compile(f"({_PLACEHOLDER})['’](?=[^\\W\\d_])")


def protect(text: str) -> tuple[str, list[str]]:
    spans: list[str] = []

    def replace(match: re.Match) -> str:
        span = " ".join(match.group(1).split())
        if not span:
            return ""
        spans.append(span)
        return chr(_FIRST_PLACEHOLDER + len(spans) - 1)

    text = _SPAN.sub(replace, text).replace(_STRAY_END, "")
    text = _APOSTROPHE_AFTER_SPAN.sub(r"\1", text)

    def inflected(match: re.Match) -> str:
        if match.group(2).lower() in _CONTRACTIONS:
            return match.group()
        spans.append(match.group(1))
        return chr(_FIRST_PLACEHOLDER + len(spans) - 1) + match.group(2)

    return _INFLECTED.sub(inflected, text), spans


def restore(text: str, spans: list[str]) -> str:
    for i, span in enumerate(spans):
        text = text.replace(chr(_FIRST_PLACEHOLDER + i), f"<en>{span}</en>")
    return text


def remove_tags(text: str) -> str:
    """For an English voice, all text is English: keep the words, remove the tags."""
    return re.sub(r"</?en>", "", text)
