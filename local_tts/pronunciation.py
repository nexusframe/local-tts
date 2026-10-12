"""Pronunciation dictionary: the user replaces words before the normalizer."""

from __future__ import annotations

import logging
import re
import threading
import tomllib
from pathlib import Path

log = logging.getLogger(__name__)

# The parts at odd indexes of re.split are <en>...</en> spans with their tags.
_ENGLISH_SPAN = re.compile(r"(<en>.*?</en>)", re.DOTALL)


def apply_aliases(text: str, aliases: dict[str, str]) -> str:
    """Replace each whole word of the text that is a key of aliases.

    The keys are case-sensitive. A longer key wins ("GitHub Actions" before
    "GitHub"). Text in <en>...</en> tags does not change.
    """
    if not aliases:
        return text
    keys = sorted(aliases, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, keys)) + r")(?!\w)")
    parts = _ENGLISH_SPAN.split(text)
    return "".join(
        part if i % 2 else pattern.sub(lambda m: aliases[m.group()], part) for i, part in enumerate(parts)
    )


class PronunciationDictionary:
    """Aliases from a TOML file with one table for each language ("pl", "en").

    The file is read again when its modification time changes, so a change
    is used from the next utterance. A missing file gives no aliases. An
    invalid file is logged, and the last valid aliases stay in use.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._mtime: float | None = None
        self._tables: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def aliases(self, language: str) -> dict[str, str]:
        with self._lock:
            self._reload_if_changed()
            return self._tables.get(language, {})

    def _reload_if_changed(self) -> None:
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            mtime = None
        if mtime == self._mtime:
            return
        self._mtime = mtime
        if mtime is None:
            self._tables = {}
            return
        try:
            self._tables = _parse(self._path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
            log.warning("pronunciation file %s not used, the last valid aliases stay: %s", self._path, exc)
            return
        log.info("pronunciation file %s: %s", self._path, {lang: len(table) for lang, table in self._tables.items()})


def _parse(content: str) -> dict[str, dict[str, str]]:
    tables = tomllib.loads(content)
    for language, table in tables.items():
        if not isinstance(table, dict):
            raise ValueError(f"{language!r} must be a table, for example [{language}]")
        for word, alias in table.items():
            if not word.strip():
                raise ValueError(f"[{language}] has an empty word")
            if not isinstance(alias, str):
                raise ValueError(f"[{language}] {word!r} must have a string value")
    return tables
