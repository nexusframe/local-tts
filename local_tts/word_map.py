"""Map heard words of the spoken text back to the text that the client sent."""

from __future__ import annotations

from typing import Callable


def heard_prefix(text: str, heard_words: int, to_spoken: Callable[[str], str]) -> str:
    """The longest start of text, in whole words, whose spoken form has at most heard_words words.

    to_spoken is the change before synthesis (pronunciation aliases and the
    normalizer). A number can become several words ("1257" is 4 words), so the
    start of the text is changed again for each word count. The search stops at
    the first start that is too long, so the result never goes past a word that
    was not heard. A start never cuts an <en>...</en> span.
    """
    words = text.split()
    result = ""
    for k in range(1, len(words) + 1):
        prefix = " ".join(words[:k])
        if prefix.count("<en>") > prefix.count("</en>"):
            continue
        if len(to_spoken(prefix).split()) > heard_words:
            break
        result = prefix
    return result
