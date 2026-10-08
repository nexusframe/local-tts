"""Remove markup that must not be read aloud: markdown, URLs, emoji, lector tags."""

from __future__ import annotations

import re

_CODE_FENCE = re.compile(r"^```.*$", re.MULTILINE)
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)\s]+)\)")
_URL = re.compile(r"\b(?:https?://|www\.)(?:www\.)?([\w.-]+?\.[a-z]{2,})(?:[/?#][^\s]*?)?(?=[.,;:!?)]?(?:\s|$))", re.IGNORECASE)
# Lector tags and sound descriptions, for example [pauza] or [śmiech].
_TAG = re.compile(r"\[[^\]\n]*\]")
_EMPHASIS = re.compile(r"(\*\*|__|\*|`)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+(.*)$")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")
_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?…])")


def _spoken_domain(match: re.Match) -> str:
    return match.group(1).replace(".", " kropka ")


def _end_list_item(line: str) -> str:
    match = _LIST_ITEM.match(line)
    if not match:
        return line
    item = match.group(1).rstrip()
    return item if item.endswith((".", "!", "?", "…", ":", ";")) else item + "."


def cleanup(text: str) -> str:
    text = _CODE_FENCE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub(_spoken_domain, text)
    text = _TAG.sub(" ", text)
    text = _EMPHASIS.sub("", text)
    text = _HEADING.sub("", text)
    text = _EMOJI.sub("", text)
    text = " ".join(_end_list_item(line) for line in text.splitlines())
    text = _SPACES.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return text.strip()
